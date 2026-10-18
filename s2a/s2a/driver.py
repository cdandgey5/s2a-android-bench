"""Headless Claude Code driver — the same contract as the benchmark's specs/headless-agent-driving.md
(own copy; the packages never import each other).

One `call()` = one `claude -p` process (+ its nudge continuations): the prompt on stdin,
stream-json saved verbatim to transcripts/<name>.jsonl, the exact prompt to prompts/<name>.md,
a PhaseCall-schema record appended to calls.jsonl. Flags: `-p --output-format stream-json --verbose
--model M --max-turns N --max-budget-usd X --permission-mode bypassPermissions --disallowedTools …
[--resume S] [--append-system-prompt TEXT]`. Nudge protocol: (a) an AskUserQuestion call, (b) a
question in the last text (off for artifact stages), (c) an empty diff after an editing call;
≤ 2 per call, ≤ 4 per run. Per-process cost (a resumed process reports session totals; D-041 in
the benchmark), several results per process (D-042). Probe rule: a call that ends without an
explaining subtype runs one `claude -p ping --tools "" --max-turns 1` probe; a usage limit makes
the call `usage_limited`, an authentication refusal raises ServiceRefused.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import threading
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from s2a import transcript as tx
from s2a.platform import get_platform

NUDGE_TEXT = ("No human is available. Make reasonable assumptions, state them briefly, and proceed to complete the "
              "task end to end without asking further questions.")
QUESTION_HEURISTIC = re.compile(r"(\?\s*$)|should I|do you want|which option|let me know|please confirm|"
                                r"would you like|clarify|please tell me|tell me which|I'll wait|I will wait|"
                                r"waiting for your|before I (?:proceed|continue)", re.I)
SLASH_COMMAND = re.compile(r"(?<![\w/])/[A-Za-z][\w.:-]*")  # "/some-command" names a command, it asks nothing


def asks_question(text: str | None) -> bool:
    """Nudge trigger (b): the question heuristic on the end of the last text, slash-command names removed."""
    return bool(QUESTION_HEURISTIC.search(SLASH_COMMAND.sub("", (text or "").strip()[-400:]).strip()))


AUTH_TEXT = re.compile(r"\b401\b|\b403\b|authentication_error|invalid (?:api key|oauth)|oauth token (?:has )?(?:expired|"
                       r"revoked)|not authorized|please run /login|Invalid bearer", re.I)
MODEL_TEXT = re.compile(r"model[^\n]{0,60}(?:not found|invalid|does not exist|not available|not supported)|"
                        r"not_found_error", re.I)
EXPLAINED = ("success", "error_max_turns", "error_max_budget_usd")
BASE_DENIED = ["WebFetch", "WebSearch"]
EDIT_TOOLS = ["Edit", "Write", "MultiEdit", "NotebookEdit"]


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


class ServiceRefused(RuntimeError):
    """The model service refused (authentication): the orchestrator saves state and exits 6."""

    def __init__(self, reason: str, detail: str) -> None:
        super().__init__(f"{reason}: {detail[:300]}")
        self.reason, self.detail = reason, detail


class DriverError(RuntimeError):
    """Orchestrator-side failure (launcher, unparsable transcript, model drift): exit 1."""


@dataclass
class PhaseCall:
    """The benchmark's PhaseCall schema (specs/adapter-interface.md), one record per headless call."""
    name: str
    session_id: str | None
    cmd: list[str]
    started_at: str
    duration_ms: int
    num_turns: int
    tool_calls: int
    tool_errors: int
    cost_usd: float | None
    cost_usd_imputed: float | None
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_write_tokens: int
    subtype: str
    interventions: int
    asked_question: bool
    rate_limit_retries: int
    other_retries: int
    claude_code_version: str
    model_drift: bool
    transcript_path: str
    interventions_log: list[dict] = field(default_factory=list)
    background_models: list[str] = field(default_factory=list)
    nudge_transcript_paths: list[str] = field(default_factory=list)
    prompt_sha256: str = ""
    system_prompt_sha256: str = ""


@dataclass
class Budget:
    """What is left of the run's limits; every call shares it."""
    max_turns_total: int = 200
    max_usd: float = 15.0
    timeout_minutes: int = 45
    max_interventions: int = 2
    max_interventions_per_trial: int = 4
    turns_used: int = 0
    usd_used: float = 0.0
    nudges_used: int = 0
    deadline: float = 0.0
    seconds_used_before: float = 0.0   # resumed runs: time already spent in earlier invocations

    def start_clock(self) -> None:
        self.deadline = time.monotonic() + max(0.0, self.timeout_minutes * 60 - self.seconds_used_before)

    @property
    def turns_left(self) -> int:
        return max(0, self.max_turns_total - self.turns_used)

    @property
    def usd_left(self) -> float:
        return max(0.0, self.max_usd - self.usd_used)

    def seconds_left(self) -> int:
        return max(0, int(self.deadline - time.monotonic()))

    def exhausted(self) -> str | None:
        if self.seconds_left() <= 5:
            return "timeout"
        if self.turns_left <= 0:
            return "max_turns"
        if self.usd_left <= 0.01:
            return "budget"
        return None

    def charge(self, turns: int, usd: float | None) -> None:
        self.turns_used += int(turns or 0)
        self.usd_used += float(usd or 0.0)


@dataclass
class CallResult:
    call: PhaseCall
    texts: list[str]                     # every assistant text block of the call (incl. nudges), in order
    last_text: str
    transcripts: list[tx.Transcript]


class Driver:
    def __init__(self, *, run_dir: Path, cwd: Path, model: str, budget: Budget, stop: threading.Event | None = None,
                 claude_exe: str | None = None, permission_mode: str = "bypassPermissions", grace_s: float = 30.0,
                 expect_version: str | None = None) -> None:
        self.run_dir, self.cwd, self.model, self.budget = run_dir, cwd, model, budget
        self.stop = stop
        self.claude = claude_exe or os.environ.get("S2A_CLAUDE_EXE") or shutil.which("claude") or "claude"
        # S2A_GRACE_S: how long a stopped claude gets to write its result; an outer supervisor that itself
        # waits N seconds after its Ctrl+C sets this below N so the interrupted call is still recorded
        self.permission_mode, self.grace_s = permission_mode, float(os.environ.get("S2A_GRACE_S") or grace_s)
        self.expect_version = expect_version or os.environ.get("S2A_EXPECT_CLAUDE_VERSION") or None
        self.history: list[tx.Transcript] = []   # every process of this run, in order (per-process cost)
        self.probes = 0
        self.events: list[dict] = []
        self.plat = get_platform()
        for d in ("prompts", "transcripts", "agent-out"):
            (run_dir / d).mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ helpers
    def _argv(self, *, turns: int, disallowed: list[str], system: str | None, session_id: str | None,
              extra: list[str] | None = None) -> list[str]:
        a = [self.claude, "-p", "--output-format", "stream-json", "--verbose", "--model", self.model,
             "--max-turns", str(max(1, turns)), "--max-budget-usd", f"{max(0.01, self.budget.usd_left):.4f}",
             "--permission-mode", self.permission_mode, "--disallowedTools", ",".join(disallowed)]
        if session_id:
            a += ["--resume", session_id]
        if system:
            a += ["--append-system-prompt", system]
        return a + list(extra or [])

    def _exec(self, argv: list[str], prompt: str, name: str):
        return self.plat.run_agent(argv, cwd=self.cwd, out_dir=self.run_dir / "agent-out" / name,
                                   timeout_s=max(10, self.budget.seconds_left()), stdin_text=prompt,
                                   grace_s=self.grace_s, stop=self.stop)

    def _save(self, r, name: str) -> Path:
        dst = self.run_dir / "transcripts" / f"{name}.jsonl"
        if r.stdout_path.exists():
            shutil.copyfile(r.stdout_path, dst)
        else:
            dst.write_bytes(b"")
        (self.run_dir / "transcripts" / f"{name}.stderr.txt").write_text(r.stderr(), encoding="utf-8")
        return dst

    def _check(self, t: tx.Transcript) -> tuple[list[str], bool]:
        if t.init:
            if not str(t.init.get("model") or "").startswith(self.model):
                raise DriverError(f"init.model {t.init.get('model')!r} is not {self.model!r}")
            if self.expect_version and t.init.get("claude_code_version") != self.expect_version:
                raise DriverError(f"claude_code_version {t.init.get('claude_code_version')!r} != {self.expect_version}")
        background, drift = [], False
        for k in t.model_usage:
            if k.startswith(self.model):
                continue
            if k.startswith("claude-haiku"):
                background.append(k)
            else:
                drift = True
        if drift:
            raise DriverError(f"modelUsage has a foreign model {list(t.model_usage)} (pinned {self.model})")
        return background, drift

    def probe(self, stage: str) -> tuple[str, str]:
        self.probes += 1
        name = f"probe-{stage}-{self.probes}"
        argv = [self.claude, "-p", "--output-format", "stream-json", "--verbose", "--model", self.model,
                "--tools", "", "--max-turns", "1"]
        r = self.plat.run_agent(argv, cwd=self.cwd, out_dir=self.run_dir / "agent-out" / name, timeout_s=120,
                                stdin_text="ping", grace_s=10, stop=self.stop)
        path = self._save(r, name)
        t = tx.parse_file(path)
        text = "\n".join([t.result_text(), t.last_text, r.stderr()])
        if t.subtype == "success" and not (t.result or {}).get("is_error"):
            out = ("ok", "")
        elif t.usage_limited_text(r.stderr()) or re.search(r"\b429\b", text):
            out = ("usage_limited", (t.usage_limited_text(r.stderr()) or text)[:400])
        elif AUTH_TEXT.search(text):
            out = ("auth", text[:400])
        elif MODEL_TEXT.search(text):
            out = ("model", text[:400])
        else:
            out = ("probe_failed", f"exit {r.exit_code}: {text[-400:]}")
        self.events.append({"at": utcnow_iso(), "event": "probe", "stage": stage, "outcome": out[0], "file": path.name})
        return out

    def _classify(self, stage: str, t: tx.Transcript, r) -> str:
        if r.timed_out or r.stopped:
            return "timeout"
        limited = t.usage_limited_text(r.stderr())
        if limited:
            self.events.append({"at": utcnow_iso(), "event": "usage_limited", "stage": stage, "text": limited,
                                "resets_hint": tx.parse_resets(limited)})
            return "usage_limited"
        if t.subtype in EXPLAINED and not (t.subtype == "success" and (t.result or {}).get("is_error")):
            return t.subtype
        outcome, detail = self.probe(stage)
        if outcome == "usage_limited":
            self.events.append({"at": utcnow_iso(), "event": "usage_limited", "stage": stage, "text": detail,
                                "resets_hint": tx.parse_resets(detail)})
            return "usage_limited"
        if outcome == "auth":
            raise ServiceRefused("auth_failed", detail)
        if outcome == "model":
            raise DriverError(f"model refused: {detail}")
        if outcome == "probe_failed":
            raise DriverError(f"call ended without an explaining result and the probe failed: {detail}")
        return t.subtype or "no_result"

    def _needs_nudge(self, t: tx.Transcript, *, structured: bool, implementing: bool,
                     diff_empty: Callable[[], bool] | None) -> str | None:
        if t.subtype != "success":
            return None
        if t.asked_question:
            return "a"
        if not structured and asks_question(t.last_text):
            return "b"
        if implementing and diff_empty is not None and diff_empty():
            return "c"
        return None

    # ------------------------------------------------------------------ the call
    def _partial(self, name: str) -> Path:
        """The stream an interrupted process wrote so far, saved as its transcript."""
        dst = self.run_dir / "transcripts" / f"{name}.jsonl"
        out = self.run_dir / "agent-out" / name / "stdout.txt"
        if out.exists():
            shutil.copyfile(out, dst)
        elif not dst.exists():
            dst.write_bytes(b"")
        return dst

    def _new_call(self, name: str, t: tx.Transcript, path: Path, argv: list[str], started: str, prompt: str,
                  system: str) -> tuple[PhaseCall, float | None]:
        own = tx.invocation_cost(t, self.history)
        self.history.append(t)
        u = t.usage_totals()
        red = [x if len(x) < 400 else x[:60] + f"…[{len(x)} chars]" for x in argv]
        call = PhaseCall(name=name, session_id=t.session_id, cmd=red, started_at=started, duration_ms=0,
                         num_turns=t.num_turns, tool_calls=t.tool_calls, tool_errors=t.tool_errors, cost_usd=own,
                         cost_usd_imputed=None if own is not None else tx.impute_cost(t, self.model),
                         input_tokens=u["input_tokens"], output_tokens=u["output_tokens"],
                         cache_read_tokens=u["cache_read_tokens"], cache_write_tokens=u["cache_write_tokens"],
                         subtype="", interventions=0, asked_question=t.asked_question,
                         rate_limit_retries=t.rate_limit_retries, other_retries=t.other_retries,
                         claude_code_version=(t.init or {}).get("claude_code_version") or "", model_drift=False,
                         transcript_path=str(path), prompt_sha256=sha256_text(prompt),
                         system_prompt_sha256=sha256_text(system or ""))
        self.budget.charge(t.num_turns, own if own is not None else call.cost_usd_imputed)
        return call, own

    def _fold(self, call: PhaseCall, nt: tx.Transcript, npath: Path, trigger: str) -> None:
        """Add one nudge continuation (its own process) to the call it continues."""
        nown = tx.invocation_cost(nt, self.history)
        self.history.append(nt)
        call.nudge_transcript_paths.append(str(npath))
        call.interventions += 1
        call.interventions_log.append({"trigger": trigger, "text": NUDGE_TEXT, "at": utcnow_iso()})
        call.num_turns += nt.num_turns
        call.tool_calls += nt.tool_calls
        call.tool_errors += nt.tool_errors
        for k, v in nt.usage_totals().items():
            setattr(call, k, getattr(call, k) + v)
        if nown is None or call.cost_usd is None:
            call.cost_usd_imputed = round((call.cost_usd if call.cost_usd is not None else (call.cost_usd_imputed or 0))
                                          + (nown if nown is not None else (tx.impute_cost(nt, self.model) or 0)), 6)
            call.cost_usd = None
        else:
            call.cost_usd = round(call.cost_usd + nown, 6)
        call.asked_question = call.asked_question or nt.asked_question
        call.rate_limit_retries += nt.rate_limit_retries
        call.other_retries += nt.other_retries
        self.budget.charge(nt.num_turns, nown if nown is not None else tx.impute_cost(nt, self.model))

    def _record(self, call: PhaseCall, t0: float) -> None:
        call.duration_ms = int((time.monotonic() - t0) * 1000)
        with open(self.run_dir / "calls.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(call), default=str) + "\n")

    def call(self, stage: str, prompt: str, *, name: str, system: str, turn_cap: int, read_only: bool,
             session_id: str | None = None, structured: bool = False, implementing: bool = False,
             diff_empty: Callable[[], bool] | None = None) -> CallResult:
        b = self.budget
        disallowed = BASE_DENIED + (EDIT_TOOLS if read_only else [])
        (self.run_dir / "prompts" / f"{name}.md").write_text(prompt, encoding="utf-8", newline="\n")
        started = utcnow_iso()
        t0 = time.monotonic()
        turns = max(1, min(turn_cap, b.turns_left))
        argv = self._argv(turns=turns, disallowed=disallowed, system=system, session_id=session_id)
        try:
            r = self._exec(argv, prompt, name)
        except KeyboardInterrupt:  # stopped from outside (Ctrl+C, a harness deadline): record the call, then stop
            path = self._partial(name)
            call, _ = self._new_call(name, tx.parse_file(path), path, argv, started, prompt, system)
            call.subtype = "timeout"
            self._record(call, t0)
            raise
        path = self._save(r, name)
        t = tx.parse_file(path)
        if t.unparsable and not t.lines - t.unparsable:
            raise DriverError(f"{name}: transcript unparsable ({t.unparsable} lines)")
        background, drift = self._check(t)
        call, _ = self._new_call(name, t, path, argv, started, prompt, system)
        call.background_models, call.model_drift = background, drift
        call.subtype = self._classify(stage, t, r)
        texts, transcripts, last = list(t.texts), [t], t
        per_call = 0
        while call.subtype == "success":
            trig = self._needs_nudge(last, structured=structured, implementing=implementing, diff_empty=diff_empty)
            if (not trig or per_call >= b.max_interventions or b.nudges_used >= b.max_interventions_per_trial
                    or b.exhausted()):
                break
            per_call += 1
            b.nudges_used += 1
            nname = f"{name}.nudge{per_call}"
            (self.run_dir / "prompts" / f"{nname}.md").write_text(NUDGE_TEXT, encoding="utf-8", newline="\n")
            nargv = self._argv(turns=b.turns_left, disallowed=disallowed, system=system,
                               session_id=call.session_id)
            try:
                nr = self._exec(nargv, NUDGE_TEXT, nname)
            except KeyboardInterrupt:
                npath = self._partial(nname)
                self._fold(call, tx.parse_file(npath), npath, trig)
                call.subtype = "timeout"
                self._record(call, t0)
                raise
            npath = self._save(nr, nname)
            nt = tx.parse_file(npath)
            nb, _ = self._check(nt)
            self._fold(call, nt, npath, trig)
            call.background_models = sorted(set(call.background_models) | set(nb))
            call.subtype = self._classify(stage, nt, nr)
            texts += nt.texts
            transcripts.append(nt)
            last = nt
        self._record(call, t0)
        return CallResult(call=call, texts=texts, last_text=last.last_text or "", transcripts=transcripts)
