"""`run_headless(...)` (specs/headless-agent-driving.md): one headless Claude Code call, as the trial's
sandbox user, through the platform layer, with the nudge protocol, model/version assertions,
budget bookkeeping, usage-limit detection and the probe.

Raises only for harness problems (`HarnessError`, re-queued once by the runner) and run aborts
(`AbortRun`: auth / model). Agent failures are returned as a PhaseCall subtype.
"""
from __future__ import annotations

import json
import re
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path

from abb.arms.base import Limits, PhaseCall
from abb.config import load_sandbox, load_toolchain
from abb.harness import transcript as tx
from abb.harness.platform import get_platform
from abb.harness.workspace import Workspace
from abb.log import get_logger
from abb.util import sha256_bytes, stamp, utcnow_iso

log = get_logger("abb.driver")

NUDGE_TEXT = ("No human is available. Make reasonable assumptions, state them briefly, and proceed to complete the "
              "task end to end without asking further questions.")
QUESTION_HEURISTIC = re.compile(r"(\?\s*$)|should I|do you want|which option|let me know|please confirm|"
                                r"would you like|clarify|please tell me|tell me which|I'll wait|I will wait|"
                                r"waiting for your|before I (?:proceed|continue)", re.I)  # D-040: -p has no AskUserQuestion
AUTH_TEXT = re.compile(r"\b401\b|\b403\b|authentication_error|invalid (?:api key|oauth)|oauth token (?:has )?(?:expired|"
                       r"revoked)|not authorized|please run /login|Invalid bearer", re.I)
MODEL_TEXT = re.compile(r"model[^\n]{0,60}(?:not found|invalid|does not exist|not available|not supported)|"
                        r"not_found_error", re.I)
EXPLAINED = ("success", "error_max_turns", "error_max_budget_usd")


class HarnessError(RuntimeError):
    """Our bug or the environment's (platform failure, unparsable transcript, model drift): re-queued once."""


class AbortRun(RuntimeError):
    def __init__(self, reason: str, detail: str):
        super().__init__(f"run aborted ({reason}): {detail}")
        self.reason = reason
        self.detail = detail


@dataclass
class TrialBudget:
    """What is left of one trial's Limits; shared by every call the arm makes."""
    limits: Limits
    deadline: float = 0.0
    turns_left: int = 0
    usd_left: float = 0.0
    nudges_left: int = 0
    turns_used: int = 0
    usd_used: float = 0.0

    @classmethod
    def start(cls, limits: Limits) -> "TrialBudget":
        return cls(limits=limits, deadline=time.monotonic() + limits.timeout_minutes * 60,
                   turns_left=limits.max_turns_total, usd_left=limits.max_usd,
                   nudges_left=limits.max_interventions_per_trial)

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
        self.turns_left -= turns
        self.turns_used += turns
        if usd:
            self.usd_left -= usd
            self.usd_used += usd


@dataclass
class DriverContext:
    ws: Workspace
    record_dir: Path          # results/<run>/<arm>/<task>/t<k>  (transcript/, prompts/)
    run_dir: Path             # results/<run>                    (probes/)
    tag: str                  # "<arm>-<task>-t<k>"
    token: str
    budget: TrialBudget
    as_agent: bool = True
    proxy: bool = True
    events: list = field(default_factory=list)   # usage_limited / probe records for events.jsonl
    probes: int = 0


def _claude(ctx: DriverContext) -> str:
    return str(get_platform().claude_exe())


def _argv(ctx: DriverContext, *, model: str, turns: int, usd: float, disallowed: list[str], system: str | None,
          session_id: str | None) -> list[str]:
    a = [_claude(ctx), "-p", "--output-format", "stream-json", "--verbose", "--model", model,
         "--max-turns", str(max(1, turns)), "--max-budget-usd", f"{max(0.01, usd):.4f}",
         "--permission-mode", "bypassPermissions", "--disallowedTools", ",".join(disallowed)]
    if session_id:
        a += ["--resume", session_id]
    if system:
        a += ["--append-system-prompt", system]
    return a


def _exec(ctx: DriverContext, argv: list[str], prompt: str, out_name: str, timeout_s: int):
    out = ctx.ws.dirs.agent_out / out_name
    env = ctx.ws.agent_env(ctx.token, proxy=ctx.proxy)
    return ctx.ws.exec(argv, env=env, timeout_s=timeout_s, out_dir=out, as_agent=ctx.as_agent, stdin_text=prompt)


def probe(ctx: DriverContext, model: str) -> tuple[str, str]:
    """`claude -p ping --tools "" --max-turns 1` through the same launch path -> (outcome, detail).
    outcome: ok | usage_limited | auth | model | probe_failed. Transcript kept under <run>/probes/."""
    ctx.probes += 1
    argv = [_claude(ctx), "-p", "--output-format", "stream-json", "--verbose", "--model", model, "--tools", "",
            "--max-turns", "1"]
    r = _exec(ctx, argv, "ping", f"probe-{ctx.probes}", 120)
    pdir = ctx.run_dir / "probes"
    pdir.mkdir(parents=True, exist_ok=True)
    dst = pdir / f"{stamp()}-{ctx.tag}-{ctx.probes}.jsonl"
    if r.stdout_path and r.stdout_path.exists():
        shutil.copyfile(r.stdout_path, dst)
    t = tx.parse_file(dst)
    text = "\n".join([t.result_text(), t.last_text, r.stderr()])
    if t.subtype == "success" and not (t.result or {}).get("is_error"):
        out = ("ok", "")
    elif t.usage_limited_text(r.stderr()) or re.search(r"\b429\b", text):
        out = ("usage_limited", (t.usage_limited_text(r.stderr()) or text)[:400])
    elif AUTH_TEXT.search(text):
        out = ("auth", text[:400])
    elif MODEL_TEXT.search(text) or (t.init and not str(t.init.get("model", "")).startswith(model)):
        out = ("model", text[:400])
    else:
        out = ("probe_failed", f"exit {r.exit_code}: {text[-400:]}")
    ctx.events.append({"at": utcnow_iso(), "event": "probe", "tag": ctx.tag, "outcome": out[0], "file": str(dst)})
    return out


def _check_init(t: tx.Transcript, model: str) -> None:
    pin = load_toolchain().claude_code.version
    if not t.init:
        return
    if not str(t.init.get("model") or "").startswith(model):
        raise HarnessError(f"init.model {t.init.get('model')!r} is not the pinned {model!r}")
    if t.init.get("claude_code_version") != pin:
        raise HarnessError(f"claude_code_version {t.init.get('claude_code_version')!r} != pinned {pin}")
    if t.init.get("permissionMode") != "bypassPermissions":
        raise HarnessError(f"permissionMode {t.init.get('permissionMode')!r}: bypassPermissions was not honoured")


def _models(t: tx.Transcript, model: str) -> tuple[list[str], bool]:
    background, drift = [], False
    for k in t.model_usage:
        if k.startswith(model):
            continue
        if k.startswith("claude-haiku"):
            background.append(k)
        else:
            drift = True
    return background, drift


def _needs_nudge(ctx: DriverContext, t: tx.Transcript, *, implementing: bool, structured: bool) -> str | None:
    if t.subtype != "success":
        return None
    if t.asked_question:
        return "a"
    if not structured and QUESTION_HEURISTIC.search((t.last_text or "").strip()[-400:]):
        return "b"
    if implementing and not ctx.ws.diff().strip():
        return "c"
    return None


def run_headless(
    ctx: DriverContext,
    prompt: str,
    *,
    call_name: str,
    append_system_prompt: str | None = None,
    extra_disallowed_tools: list[str] | tuple = (),
    turn_cap: int | None = None,
    session_id: str | None = None,
    is_implementing_call: bool = False,
    structured: bool = False,
) -> PhaseCall:
    b = ctx.budget
    model = b.limits.model
    sb = load_sandbox()
    disallowed = list(dict.fromkeys(sb.process.disallowed_tools + list(extra_disallowed_tools)))
    (ctx.record_dir / "prompts").mkdir(parents=True, exist_ok=True)
    (ctx.record_dir / "transcript").mkdir(parents=True, exist_ok=True)
    (ctx.record_dir / "prompts" / f"{call_name}.md").write_text(prompt, encoding="utf-8", newline="\n")
    if append_system_prompt is not None:
        (ctx.record_dir / "prompts" / f"{call_name}.system.md").write_text(append_system_prompt, encoding="utf-8",
                                                                           newline="\n")
    started = utcnow_iso()
    turns = min(turn_cap or b.turns_left, b.turns_left)
    argv = _argv(ctx, model=model, turns=turns, usd=b.usd_left, disallowed=disallowed, system=append_system_prompt,
                 session_id=session_id)
    t0 = time.monotonic()
    r = _exec(ctx, argv, prompt, call_name, b.seconds_left())
    tpath = ctx.record_dir / "transcript" / f"{call_name}.jsonl"
    if r.stdout_path and r.stdout_path.exists():
        shutil.copyfile(r.stdout_path, tpath)
    else:
        tpath.write_bytes(b"")
    stderr = r.stderr()
    (ctx.record_dir / "transcript" / f"{call_name}.stderr.txt").write_text(stderr, encoding="utf-8")
    t = tx.parse_file(tpath)
    if t.unparsable and not t.lines - t.unparsable:
        raise HarnessError(f"{call_name}: transcript unparsable ({t.unparsable} lines)")
    _check_init(t, model)
    call = PhaseCall(
        name=call_name, session_id=t.session_id, cmd=argv, started_at=started, duration_ms=0, num_turns=t.num_turns,
        tool_calls=t.tool_calls, tool_errors=t.tool_errors, cost_usd=t.cost_usd,
        cost_usd_imputed=None if t.has_result else tx.impute_cost(t, model),
        **{k: v for k, v in t.usage_totals().items()}, subtype="", interventions=0,
        asked_question=t.asked_question, rate_limit_retries=t.rate_limit_retries, other_retries=t.other_retries,
        claude_code_version=(t.init or {}).get("claude_code_version") or "", model_drift=False,
        transcript_path=str(tpath), prompt_sha256=sha256_bytes(prompt.encode("utf-8")),
        system_prompt_sha256=sha256_bytes((append_system_prompt or "").encode("utf-8")),
    )
    call.subtype = _classify(ctx, t, r, stderr, model)
    background, drift = _models(t, model)
    call.background_models, call.model_drift = background, drift
    if drift:
        raise HarnessError(f"{call_name}: modelUsage has a foreign model {list(t.model_usage)} (pinned {model})")
    b.charge(t.num_turns, t.cost_usd if t.cost_usd is not None else call.cost_usd_imputed)
    # ---- nudge protocol (D-005): identical caps for every arm
    per_call = 0
    last = t
    while call.subtype == "success":
        trigger = _needs_nudge(ctx, last, implementing=is_implementing_call, structured=structured)
        if not trigger or per_call >= b.limits.max_interventions or b.nudges_left <= 0 or b.exhausted():
            break
        per_call += 1
        b.nudges_left -= 1
        name = f"{call_name}.nudge{per_call}"
        (ctx.record_dir / "prompts" / f"{name}.md").write_text(NUDGE_TEXT, encoding="utf-8", newline="\n")
        nargv = _argv(ctx, model=model, turns=b.turns_left, usd=b.usd_left, disallowed=disallowed,
                      system=append_system_prompt, session_id=call.session_id)
        nr = _exec(ctx, nargv, NUDGE_TEXT, name, b.seconds_left())
        npath = ctx.record_dir / "transcript" / f"{name}.jsonl"
        if nr.stdout_path and nr.stdout_path.exists():
            shutil.copyfile(nr.stdout_path, npath)
        nt = tx.parse_file(npath)
        _check_init(nt, model)
        nb, nd = _models(nt, model)
        if nd:
            raise HarnessError(f"{name}: modelUsage has a foreign model {list(nt.model_usage)}")
        call.nudge_transcript_paths.append(str(npath))
        call.interventions += 1
        call.interventions_log.append({"trigger": trigger, "text": NUDGE_TEXT, "at": utcnow_iso()})
        call.num_turns += nt.num_turns
        call.tool_calls += nt.tool_calls
        call.tool_errors += nt.tool_errors
        for k, v in nt.usage_totals().items():
            setattr(call, k, getattr(call, k) + v)
        if nt.cost_usd is None or call.cost_usd is None:
            call.cost_usd_imputed = round((call.cost_usd if call.cost_usd is not None else (call.cost_usd_imputed or 0))
                                          + (nt.cost_usd if nt.cost_usd is not None else (tx.impute_cost(nt, model) or 0)), 6)
            call.cost_usd = None
        else:
            call.cost_usd = round(call.cost_usd + nt.cost_usd, 6)
        call.asked_question = call.asked_question or nt.asked_question
        call.rate_limit_retries += nt.rate_limit_retries
        call.other_retries += nt.other_retries
        call.background_models = sorted(set(call.background_models) | set(nb))
        call.subtype = _classify(ctx, nt, nr, nr.stderr(), model)
        b.charge(nt.num_turns, nt.cost_usd if nt.cost_usd is not None else tx.impute_cost(nt, model))
        last = nt
    call.duration_ms = int((time.monotonic() - t0) * 1000)
    if call.cost_usd is None and call.cost_usd_imputed is None:
        call.cost_usd_imputed = tx.impute_cost(t, model)
    return call


def _classify(ctx: DriverContext, t: tx.Transcript, r, stderr: str, model: str) -> str:
    """Map one process's ending to a subtype; runs the probe for every unexplained ending."""
    if r.stopped_by_harness:
        return "timeout"
    limited = t.usage_limited_text(stderr)
    if limited:
        ctx.events.append({"at": utcnow_iso(), "event": "usage_limited", "tag": ctx.tag, "text": limited,
                           "resets_hint": tx.parse_resets(limited)})
        return "usage_limited"
    if t.subtype in EXPLAINED and not (t.subtype == "success" and (t.result or {}).get("is_error")):
        return t.subtype
    if r.job_memory_hit:
        return "job_memory_hit"
    outcome, detail = probe(ctx, model)
    if outcome == "usage_limited":
        ctx.events.append({"at": utcnow_iso(), "event": "usage_limited", "tag": ctx.tag, "text": detail,
                           "resets_hint": tx.parse_resets(detail)})
        return "usage_limited"
    if outcome == "auth":
        raise AbortRun("auth", detail)
    if outcome == "model":
        raise AbortRun("model", detail)
    if outcome == "probe_failed":
        raise HarnessError(f"call ended without an explaining result and the probe failed: {detail}")
    if t.assistant_messages == 0:
        raise HarnessError("no assistant message at all although the probe succeeded")
    return t.subtype or "no_result"


def phasecall_dict(c: PhaseCall) -> dict:
    from dataclasses import asdict

    d = asdict(c)
    d["cmd"] = [x if len(x) < 400 else x[:60] + f"…[{len(x)} chars]" for x in c.cmd]
    return d


def write_json(p: Path, data) -> None:
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    tmp.replace(p)


__all__ = ["AbortRun", "DriverContext", "HarnessError", "NUDGE_TEXT", "TrialBudget", "phasecall_dict", "probe",
           "run_headless", "write_json"]
