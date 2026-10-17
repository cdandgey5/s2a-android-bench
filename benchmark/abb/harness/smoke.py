"""`abb ws smoke`: the pinned claude.exe, headless, through the platform layer (specs/headless-agent-driving.md,
"Smoke test"). Builds the environment block exactly as a trial would (minus the proxy until Phase 1)
and saves the verbatim stream-json as a parser fixture on request.
"""
from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

from abb import paths
from abb.config import load_sandbox
from abb.harness.agent_env import AuthError, TrialDirs, build_agent_env, claude_template_dir, preflight, redact
from abb.harness.platform import ProcSpec, get_platform
from abb.util import sha256_bytes, stamp, utcnow_iso

TOKEN_PATTERN = rb"sk-ant-[a-z]+\d{2}-"


def parse_stream(text: str) -> dict:
    """Summarise a stream-json transcript (the real parser is Phase 4's transcript.py)."""
    out: dict = {"lines": 0, "unparsable": 0, "init": None, "result": None, "rate_limit_events": [],
                 "api_retries": [], "assistant_messages": 0, "tool_uses": [], "event_types": {}}
    for line in text.splitlines():
        if not line.strip():
            continue
        out["lines"] += 1
        try:
            ev = json.loads(line)
        except ValueError:
            out["unparsable"] += 1
            continue
        t = f"{ev.get('type')}/{ev.get('subtype')}" if ev.get("subtype") else str(ev.get("type"))
        out["event_types"][t] = out["event_types"].get(t, 0) + 1
        if ev.get("type") == "system" and ev.get("subtype") == "init":
            out["init"] = {k: ev.get(k) for k in ("model", "claude_code_version", "permissionMode", "apiKeySource",
                                                    "cwd", "session_id", "output_style")}
            out["init"]["tools"] = ev.get("tools")
        elif ev.get("type") == "system" and ev.get("subtype") == "api_retry":
            out["api_retries"].append({k: ev.get(k) for k in ("error", "error_status", "attempt")})
        elif ev.get("type") == "rate_limit_event":
            out["rate_limit_events"].append(ev)
        elif ev.get("type") == "assistant":
            out["assistant_messages"] += 1
            for b in (ev.get("message") or {}).get("content") or []:
                if b.get("type") == "tool_use":
                    out["tool_uses"].append(b.get("name"))
        elif ev.get("type") == "result":
            out["result"] = {k: ev.get(k) for k in ("subtype", "is_error", "num_turns", "duration_ms", "duration_api_ms",
                                                      "total_cost_usd", "session_id", "usage", "permission_denials",
                                                      "stop_reason", "terminal_reason")}
            out["result"]["modelUsage_keys"] = sorted((ev.get("modelUsage") or {}).keys())
            out["result"]["result_text"] = (ev.get("result") or "")[:500] if isinstance(ev.get("result"), str) else None
    return out


def leak_scan(files: list[Path], token: str) -> list[Path]:
    """Files containing the token value or an sk-ant-* key shape. Never returns the match."""
    pat = re.compile(TOKEN_PATTERN)
    bad = []
    tb = token.encode("utf-8")
    for f in files:
        if f.exists() and f.is_file():
            data = f.read_bytes()
            if tb in data or pat.search(data):
                bad.append(f)
    return bad


def run_smoke(
    prompt: str, *, model: str, max_turns: int, max_usd: float, deadline: int | None, grace: int,
    interrupt: str | None, tools: str | None, proxy: bool, label: str = "smoke",
    env_overrides: dict[str, str] | None = None, allowed_tools: str | None = None,
    permission_mode: str = "bypassPermissions",
) -> dict:
    token = preflight()
    plat = get_platform()
    sb = load_sandbox()
    claude = plat.claude_exe()
    if not claude.exists():
        raise FileNotFoundError(f"{claude} missing: run `abb tools install`")
    trial = TrialDirs(paths.work_dir() / "smoke" / f"{stamp()}-{label}").create(claude_template=claude_template_dir())
    env = build_agent_env(trial, token=token, proxy=proxy)
    for k, v in (env_overrides or {}).items():
        if k.upper() in ("CLAUDE_CODE_OAUTH_TOKEN", "ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"):
            raise AuthError(f"--env may not set {k}")
        env[k] = v
    argv = [str(claude), "-p", "--output-format", "stream-json", "--verbose", "--model", model,
            "--max-turns", str(max_turns), "--max-budget-usd", f"{max_usd}",
            "--permission-mode", permission_mode, "--disallowedTools", ",".join(sb.process.disallowed_tools)]
    if allowed_tools is not None:
        argv += ["--allowedTools", allowed_tools]
    if tools is not None:
        argv += ["--tools", tools]
    spec = ProcSpec(
        argv=argv, cwd=trial.work, env=env, stdin_text=prompt, timeout_s=deadline or 900,
        memory_mb=sb.process.memory_mb, as_user=None, out_dir=trial.agent_out,
        interrupt=interrupt or sb.process.interrupt, stop_file=trial.stop_file, grace_s=grace,
    )
    started = utcnow_iso()
    r = plat.wait(plat.run(spec))
    stdout = r.stdout()
    summary = {
        "started_at": started,
        "trial_dir": str(trial.root),
        "argv": redact(argv, token),
        "prompt": prompt,
        "env_overrides": env_overrides or {},
        "prompt_sha256": sha256_bytes(prompt.encode("utf-8")),
        "exit_code": r.exit_code,
        "stopped_by_harness": r.stopped_by_harness,
        "duration_s": r.duration_s,
        "peak_memory_mb": r.peak_memory_mb,
        "job_memory_hit": r.job_memory_hit,
        "launcher": r.launcher,
        "stderr_tail": r.stderr()[-1500:],
        "parsed": parse_stream(stdout),
    }
    leaks = leak_scan([p for p in trial.root.rglob("*") if p.is_file()], token)
    summary["token_leak_files"] = [str(p) for p in leaks]
    (trial.root / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def smoke_cli(prompt: str, *, model: str, max_turns: int, max_usd: float, deadline: int | None, grace: int,
              interrupt: str | None, save: str | None, tools: str | None, proxy: bool,
              env_overrides: dict[str, str] | None = None, allowed_tools: str | None = None,
              permission_mode: str = "bypassPermissions") -> int:
    if proxy:
        print("the harness proxy arrives in Phase 1; run without --proxy")
        return 2
    try:
        s = run_smoke(prompt, model=model, max_turns=max_turns, max_usd=max_usd, deadline=deadline, grace=grace,
                      interrupt=interrupt, tools=tools, proxy=proxy, label=save or "smoke",
                      env_overrides=env_overrides, allowed_tools=allowed_tools, permission_mode=permission_mode)
    except AuthError as e:
        print(f"ERROR: {e}")
        return 1
    if s["token_leak_files"]:
        print("TOKEN FOUND in: " + ", ".join(s["token_leak_files"]) + " — stop (D-026); nothing saved")
        return 3
    p = s["parsed"]
    view = {k: s[k] for k in ("trial_dir", "exit_code", "stopped_by_harness", "duration_s", "peak_memory_mb")}
    view["interrupt_sent"] = s["launcher"].get("interrupt_sent")
    view["console_window_visible"] = s["launcher"].get("console_window_visible")
    view["init"] = {k: (p["init"] or {}).get(k) for k in ("model", "claude_code_version", "permissionMode", "apiKeySource")}
    view["result"] = p["result"]
    view["event_types"] = p["event_types"]
    view["rate_limit_events"] = p["rate_limit_events"]
    view["tool_uses"] = p["tool_uses"]
    view["stderr_tail"] = s["stderr_tail"][-600:]
    print(json.dumps(view, indent=2))
    if save:
        dst = paths.fixtures_dir() / "transcripts" / f"{save}.jsonl"
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(Path(s["trial_dir"]) / "agent-out" / "stdout.txt", dst)
        meta = {k: s[k] for k in ("started_at", "argv", "prompt", "env_overrides", "exit_code", "stopped_by_harness",
                                  "duration_s")}
        meta["launcher"] = {k: s["launcher"].get(k) for k in ("interrupt_mode", "interrupt_sent", "interrupt_ok",
                                                               "child_exit_code")}
        meta["result_subtype"] = (p["result"] or {}).get("subtype")
        (dst.with_suffix(".meta.json")).write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8", newline="\n")
        print(f"saved {dst}")
    return 0
