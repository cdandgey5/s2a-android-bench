"""stream-json parser over the recorded fixtures (shared with s2a's driver tests in Phase 6)."""
from __future__ import annotations

import pytest

from abb import paths
from abb.harness import transcript as tx

FIX = paths.fixtures_dir() / "transcripts"


def p(name: str) -> tx.Transcript:
    return tx.parse_file(FIX / f"{name}.jsonl")


def test_success() -> None:
    t = p("smoke-success")
    assert t.unparsable == 0 and t.has_result and t.subtype == "success"
    assert t.init["model"] == "claude-sonnet-5-5" and t.init["permissionMode"] == "bypassPermissions"
    assert t.tool_calls >= 1 and t.tool_calls == len(t.tool_names) and t.last_text
    assert t.num_turns == 2 and t.cost_usd and t.cost_usd > 0
    u = t.usage_totals()
    assert u["output_tokens"] > 0 and u["cache_read_tokens"] > 0
    assert list(t.model_usage) == ["claude-sonnet-5-5"]
    assert t.usage_limited_text() is None and t.rate_limit_events


def test_maxturns() -> None:
    t = p("smoke-maxturns1")
    assert t.subtype == "error_max_turns"


def test_killed_without_result_line_imputes_cost() -> None:
    t = p("smoke-interrupt")
    assert not t.has_result and t.cost_usd is None and t.num_turns == 0
    assert t.assistant_messages >= 1 and t.tool_errors >= 1
    est = tx.impute_cost(t, "claude-sonnet-5-5")
    assert est is not None and est > 0
    u = t.usage_totals()  # from the per-message usage blocks
    assert u["output_tokens"] > 0


def test_ctrl_c_result_line() -> None:
    t = p("smoke-interrupt-ctrlc")
    assert t.subtype == "error_during_execution" and t.cost_usd is not None


def test_api_retry_split() -> None:
    t = p("api-retry")
    assert t.rate_limit_retries == 1 and t.other_retries == 1 and t.subtype == "success"


def test_probe_fixtures() -> None:
    ok = p("probe-ok")
    assert ok.subtype == "success" and ok.usage_limited_text() is None
    lim = p("probe-limited")
    text = lim.usage_limited_text()
    assert text and "limit" in text.lower()
    assert tx.parse_resets(lim.result_text()) == "3:45pm"


def test_imputed_cost_matches_reported_for_a_full_transcript() -> None:
    t = p("smoke-success")
    est = tx.impute_cost(t, "claude-sonnet-5-5")
    # per-message usage misses the result's aggregation of some tokens, so allow 15 %
    assert est == pytest.approx(t.cost_usd, rel=0.15)


def test_opus_prices_known() -> None:
    assert tx.price_for("claude-opus-5-5")["output"] == 20.0
    assert tx.price_for("claude-sonnet-5-5-20261001")["input"] == 2.0  # dated snapshot ids match by prefix


def test_unknown_events_and_garbage_tolerated() -> None:
    t = tx.parse_text('{"type":"brand_new_event"}\nnot json\n{"type":"result","subtype":"success","num_turns":1}\n')
    assert t.unparsable == 1 and t.subtype == "success" and t.event_types.get("brand_new_event") == 1
