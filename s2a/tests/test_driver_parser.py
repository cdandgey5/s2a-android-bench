"""stream-json parser over the shared fixtures (copied from benchmark/tests/fixtures/transcripts/;
identical in intent to the benchmark's test_transcript.py: both packages' parsers must pass)."""
from __future__ import annotations

import pytest

from pathlib import Path

from s2a import transcript as tx

FIX = Path(__file__).parent / "fixtures" / "transcripts"


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


def test_resumed_result_is_session_cumulative_and_invocation_cost_subtracts_it() -> None:
    # Phase 4 driver check: the nudge resumed the first call's session; its total_cost_usd and
    # modelUsage include the first call, its usage and num_turns do not (D-041)
    a, b = p("resume-first"), p("resume-nudge")
    assert a.session_id == b.session_id and b.num_turns == 1
    assert b.model_usage["claude-sonnet-5-5"]["outputTokens"] == (
        a.usage_totals()["output_tokens"] + b.usage_totals()["output_tokens"])
    assert tx.invocation_cost(a, []) == a.cost_usd
    own = tx.invocation_cost(b, [a])
    assert own == pytest.approx(b.cost_usd - a.cost_usd) and 0 < own < 0.02
    assert own == pytest.approx(tx.impute_cost(b, "claude-sonnet-5-5"), abs=1e-6)  # priced from its own usage
    assert tx.invocation_cost(b, []) is None  # base not identifiable -> caller imputes


def test_two_results_in_one_process_background_task() -> None:
    # a real capture: an auto-backgrounded Bash finished after the first
    # result; Claude Code ran one more turn for its notification and wrote a second init/result
    # pair. Turns and usage add up per result; cost and modelUsage are the process's running total.
    t = p("two-results-bg-task")
    assert len(t.results) == 2 and t.results[1]["origin"]["kind"] == "task-notification"
    assert t.num_turns == 26 + 1
    assert t.usage_totals()["output_tokens"] == 5230 + 83 == t.model_usage["claude-sonnet-5-5"]["outputTokens"]
    assert t.cost_usd == pytest.approx(0.229231)
    assert tx.invocation_cost(t, []) == t.cost_usd  # nothing restored: the base is 0
    assert t.tool_calls == 25 and t.subtype == "success"


def test_gradle_health_counters() -> None:
    # D-043: the same transcript is an invalid-environment trial (read-only cache not readable)
    t = p("two-results-bg-task")
    assert t.gradle_ok == 0 and t.gradle_failed >= 1 and t.env_errors >= 1
    ok = p("smoke-success")
    assert ok.env_errors == 0


def test_usage_limit_canary_is_detected() -> None:
    # the real limit output captured in the benchmark's Phase 4 (reference/verified.md)
    t = p("usage-limited-canary")
    text = t.usage_limited_text()
    assert text and "session limit" in text and tx.parse_resets(text) == "2am"
    assert (t.result or {}).get("is_error") is True and t.subtype == "success"
