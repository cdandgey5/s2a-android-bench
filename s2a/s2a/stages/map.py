"""Stage 1 — map (one-time per repository): .s2a/map.md + map.json, cached by (commit, profile, prompt hash);
`--map PATH` installs a supplied map as-is. The gate runs the smoke test the map names (its results
become that module's baseline); a soft post-check times lint once."""
from __future__ import annotations

import hashlib
import json
import shutil
import time
from pathlib import Path

from s2a import gitutil, render
from s2a.context import Ctx
from s2a.gates import first_failure, run_gates, summarize
from s2a.profile import prompt_text
from s2a.stages.base import Stop, after_call, base_values, call_name, can_retry, check_budget, stage_turns


def prompt_hash(ctx: Ctx) -> str:
    return hashlib.sha256(prompt_text("map", ctx.state.profile).encode("utf-8")).hexdigest()[:16]


def cache_key(ctx: Ctx) -> dict:
    return {"commit": gitutil.head(ctx.repo), "profile": ctx.state.profile, "prompt_hash": prompt_hash(ctx)}


def load(ctx: Ctx) -> bool:
    md, js = ctx.s2a_dir / "map.md", ctx.s2a_dir / "map.json"
    if md.exists() and js.exists():
        ctx.map_md = md.read_text(encoding="utf-8")
        ctx.map_json = json.loads(js.read_text(encoding="utf-8"))
        return True
    return False


def install_supplied(ctx: Ctx, path: Path) -> None:
    """--map PATH: copy map.md (and the map.json next to it) into .s2a/, no key or staleness check."""
    ctx.s2a_dir.mkdir(parents=True, exist_ok=True)
    src_md = Path(path)
    if src_md.resolve() != (ctx.s2a_dir / "map.md").resolve():
        shutil.copyfile(src_md, ctx.s2a_dir / "map.md")
    src_js = src_md.with_name("map.json")
    if src_js.exists() and src_js.resolve() != (ctx.s2a_dir / "map.json").resolve():
        shutil.copyfile(src_js, ctx.s2a_dir / "map.json")
    if not load(ctx):
        raise Stop(3, "gate_failed", f"--map {path}: map.md/map.json not found")


def cached_ok(ctx: Ctx) -> bool:
    kf = ctx.s2a_dir / "map.key.json"
    if not (kf.exists() and load(ctx)):
        return False
    k = json.loads(kf.read_text(encoding="utf-8"))
    stale_days = ((ctx.pipeline.stage("map").cache or {}).get("stale_after_days") or 30)
    fresh = time.time() - k.get("built_at", 0) < stale_days * 86400
    return fresh and all(k.get(x) == v for x, v in cache_key(ctx).items())


def build(ctx: Ctx) -> None:
    """Run the map stage (full tools); retry once on a gate failure with the failure appended."""
    cfg = ctx.pipeline.stage("map")
    ctx.s2a_dir.mkdir(parents=True, exist_ok=True)
    vals = base_values(ctx)
    prompt, _ = render.render(prompt_text("map", ctx.state.profile), vals)
    st = ctx.state.stage("map")
    used, last = st.get("turns_used", 0), None
    for attempt in range(1 + cfg.retry):
        if attempt and not can_retry(ctx, cfg, used):
            break
        check_budget(ctx, "map")
        p = prompt if attempt == 0 else (prompt + f"\n\n## Previous attempt\nThe map did not pass `{last[0]}`: "
                                         f"{last[1].message}\nFix .s2a/map.md and .s2a/map.json.")
        ctx.state.mark("map", "running", attempts=attempt + 1, cached=False)
        res = ctx.driver.call("map", p, name=call_name(ctx, "map"), system=ctx.system,
                              turn_cap=stage_turns(ctx, cfg, used), read_only=False)
        used += res.call.num_turns
        st["turns_used"] = used
        st.setdefault("calls", []).append(res.call.name)
        after_call(ctx, res)
        results = run_gates(ctx, cfg.gate, stage="map")
        st["gates"] = summarize(results)
        last = first_failure(results)
        if last is None:
            for post in cfg.post:
                run_gates(ctx, [post], stage="map")
            load(ctx)
            key = {**cache_key(ctx), "built_at": time.time()}
            (ctx.s2a_dir / "map.key.json").write_text(json.dumps(key, indent=2), encoding="utf-8")
            _keep_records(ctx)
            ctx.state.mark("map", "done", cached=False)
            ctx.save()
            return
        ctx.save()
    raise Stop(3, "gate_failed", f"map: {last[0]} — {last[1].message}")


def _keep_records(ctx: Ctx) -> None:
    """.s2a/map.calls.jsonl + map/transcripts + map/prompts: the map's cost and transcripts, kept beside it so
    whoever caches or shares a map can account for it."""
    out = ctx.s2a_dir / "map"
    for sub in ("transcripts", "prompts"):
        (out / sub).mkdir(parents=True, exist_ok=True)
        for f in (ctx.run_dir / sub).glob("map*"):
            shutil.copyfile(f, out / sub / f.name)
    lines = [ln for ln in ctx.read("calls.jsonl").splitlines() if ln.strip() and json.loads(ln)["name"].startswith("map")]
    (ctx.s2a_dir / "map.calls.jsonl").write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def run(ctx: Ctx) -> None:
    if ctx.state.map_path:
        install_supplied(ctx, Path(ctx.state.map_path))
        ctx.state.mark("map", "done", cached=True, supplied=ctx.state.map_path)
    elif cached_ok(ctx):
        ctx.state.mark("map", "done", cached=True)
    else:
        build(ctx)
    ctx.save()
