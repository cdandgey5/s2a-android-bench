"""One-time per-repo setup (specs/adapter-interface.md: `one_time_setup`), reported separately.

Cached per (setup_kind, repo, setup_commit, environment fingerprint, prompt hash) under
<results>/_setup_cache/<key>/ so arms that share a setup kind share the artifact (D-012). The
plain arms have no setup (setup_kind None); Spec Kit (Phase 5) and S2A (Phase 6) fill this in.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from abb import paths
from abb.config import load_repo
from abb.harness.env import load_env_lock


def cache_key(setup_kind: str, repo_key: str, prompt_hash: str) -> str:
    repo = load_repo(repo_key)
    fp = (load_env_lock().get(repo_key) or {}).get("fingerprint", "")
    raw = json.dumps([setup_kind, repo_key, repo.build.setup_commit, fp, prompt_hash])
    return f"{setup_kind}-{repo_key}-{hashlib.sha256(raw.encode()).hexdigest()[:16]}"


def cache_dir(key: str) -> Path:
    return paths.results_dir() / "_setup_cache" / key


def ensure_setup(arm, repo_key: str, run_dir: Path) -> dict | None:
    """Return the cached setup record for (arm.setup_kind, repo), or None when the arm needs none."""
    if getattr(arm, "setup_kind", None) is None:
        return None
    raise NotImplementedError(f"setup kind {arm.setup_kind!r} arrives with its arm (Phases 5/6)")
