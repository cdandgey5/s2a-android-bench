"""The Phase 0 smoke fixtures exist, parse, and carry the subtypes the driver will map (Phase 4 reuses them)."""
from __future__ import annotations

import json
import re

import pytest

from abb import paths
from abb.config import load_toolchain
from abb.harness.smoke import parse_stream

FIX = paths.fixtures_dir() / "transcripts"
PIN = load_toolchain().claude_code.version


def _parsed(name: str) -> dict:
    return parse_stream((FIX / f"{name}.jsonl").read_text(encoding="utf-8"))


@pytest.mark.parametrize("name", ["smoke-success", "smoke-success-opus", "smoke-maxturns1", "smoke-interrupt",
                                  "smoke-interrupt-ctrlc"])
def test_fixture_parses_with_pinned_init(name: str) -> None:
    p = _parsed(name)
    assert p["unparsable"] == 0
    assert p["init"]["claude_code_version"] == PIN
    assert p["init"]["permissionMode"] == "bypassPermissions"
    assert p["init"]["apiKeySource"] == "none"


@pytest.mark.parametrize("name,model", [("smoke-success", "claude-sonnet-5-5"), ("smoke-success-opus", "claude-opus-5-5")])
def test_success_fixture(name: str, model: str) -> None:
    r = _parsed(name)["result"]
    assert r["subtype"] == "success" and r["is_error"] is False
    assert r["total_cost_usd"] > 0 and r["usage"]["output_tokens"] > 0
    assert all(k.startswith(model) for k in r["modelUsage_keys"])


def test_maxturns_fixture() -> None:
    r = _parsed("smoke-maxturns1")["result"]
    assert r["subtype"] == "error_max_turns"


@pytest.mark.parametrize("name,signal,subtype", [("smoke-interrupt", "ctrl_break", None),
                                                  ("smoke-interrupt-ctrlc", "ctrl_c", "error_during_execution")])
def test_interrupt_fixtures(name: str, signal: str, subtype: str | None) -> None:
    """Ctrl+Break ends claude.exe without a result line; Ctrl+C makes it write one (D-032)."""
    p = _parsed(name)
    assert p["assistant_messages"] >= 1
    if subtype is None:
        assert p["result"] is None
    else:
        assert p["result"]["subtype"] == subtype and p["result"]["total_cost_usd"] > 0
    meta = json.loads((FIX / f"{name}.meta.json").read_text(encoding="utf-8"))
    assert meta["stopped_by_harness"] is True and meta["launcher"]["interrupt_sent"] == signal


def test_rate_limit_event_shape() -> None:
    ev = _parsed("smoke-success")["rate_limit_events"]
    assert ev, "-p stream-json emitted no rate_limit_event"
    info = ev[0]["rate_limit_info"]
    assert {"status", "resetsAt", "rateLimitType"} <= set(info)


def test_fixtures_carry_no_credentials() -> None:
    pat = re.compile(rb"sk-ant-[a-z]+\d{2}-")
    for f in FIX.iterdir():
        assert not pat.search(f.read_bytes()), f.name
