"""Claude Code `--output-format stream-json --verbose` parser (specs/headless-agent-driving.md §2).

One `Transcript` per stream: the `init` event, assistant tool calls and last text, tool errors,
`api_retry` events split by cause, `rate_limit_event`s, and the final `result` (usage, modelUsage
in camelCase, permission_denials). Tolerates unknown event types and a missing `result` line
(then `cost_usd` is None and `cost_usd_imputed` comes from the per-message usage and
config/prices.yaml). Pure parsing: no I/O except reading the file and the price table.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from abb import paths

LIMIT_TEXT = re.compile(r"hit your (?:session|weekly|Opus|Sonnet|usage)? ?limit|usage limit reached|rate_limit_error", re.I)
RESETS = re.compile(r"resets\s+(?:at\s+)?([0-9]{1,2}(?::[0-9]{2})?\s*(?:am|pm)?)", re.I)


@dataclass
class Transcript:
    lines: int = 0
    unparsable: int = 0
    event_types: dict = field(default_factory=dict)
    init: dict | None = None
    assistant_messages: int = 0
    tool_calls: int = 0
    tool_names: list = field(default_factory=list)
    tool_errors: int = 0
    last_text: str = ""
    asked_question: bool = False
    rate_limit_retries: int = 0
    other_retries: int = 0
    rate_limit_events: list = field(default_factory=list)
    result: dict | None = None
    message_usage: dict = field(default_factory=dict)  # message id -> usage dict (deduplicated)

    # ---------------------------------------------------------------- derived
    @property
    def has_result(self) -> bool:
        return self.result is not None

    @property
    def subtype(self) -> str | None:
        return (self.result or {}).get("subtype")

    @property
    def session_id(self) -> str | None:
        if self.result and self.result.get("session_id"):
            return self.result["session_id"]
        return (self.init or {}).get("session_id")

    @property
    def num_turns(self) -> int:
        return int((self.result or {}).get("num_turns") or 0)

    @property
    def cost_usd(self) -> float | None:
        c = (self.result or {}).get("total_cost_usd")
        return float(c) if c is not None else None

    @property
    def model_usage(self) -> dict:
        return (self.result or {}).get("modelUsage") or {}

    def usage_totals(self) -> dict:
        """Tokens from the result line when present, else summed from the assistant messages."""
        u = (self.result or {}).get("usage")
        src = [u] if u else list(self.message_usage.values())
        tot = {"input_tokens": 0, "output_tokens": 0, "cache_read_tokens": 0, "cache_write_tokens": 0}
        for x in src:
            tot["input_tokens"] += int(x.get("input_tokens") or 0)
            tot["output_tokens"] += int(x.get("output_tokens") or 0)
            tot["cache_read_tokens"] += int(x.get("cache_read_input_tokens") or 0)
            tot["cache_write_tokens"] += int(x.get("cache_creation_input_tokens") or 0)
        return tot

    def permission_denials(self) -> list:
        return (self.result or {}).get("permission_denials") or []

    def result_text(self) -> str:
        r = (self.result or {}).get("result")
        return r if isinstance(r, str) else ""

    def usage_limited_text(self, stderr: str = "") -> str | None:
        """The usage-limit message when the stream or stderr carries one (the -p wording is undocumented)."""
        for text in (self.result_text(), self.last_text, stderr):
            m = LIMIT_TEXT.search(text or "")
            if m:
                return (text or "")[max(0, m.start() - 80): m.end() + 120]
        for ev in self.rate_limit_events:
            info = ev.get("rate_limit_info") or {}
            if str(info.get("status", "allowed")).lower() not in ("allowed", "allowed_warning"):
                return json.dumps(info)[:300]
        return None


def _usage_of(msg: dict) -> dict:
    return msg.get("usage") or {}


def parse_text(text: str) -> Transcript:
    t = Transcript()
    for line in text.splitlines():
        if not line.strip():
            continue
        t.lines += 1
        try:
            ev = json.loads(line)
        except ValueError:
            t.unparsable += 1
            continue
        typ, sub = ev.get("type"), ev.get("subtype")
        key = f"{typ}/{sub}" if sub else str(typ)
        t.event_types[key] = t.event_types.get(key, 0) + 1
        if typ == "system" and sub == "init":
            t.init = {k: ev.get(k) for k in ("model", "claude_code_version", "permissionMode", "session_id", "cwd",
                                              "apiKeySource")}
            t.init["slash_commands"] = ev.get("slash_commands") or []
            t.init["tools"] = ev.get("tools") or []
        elif typ == "system" and sub == "api_retry":
            err = str(ev.get("error") or "")
            if err == "rate_limit" or ev.get("error_status") == 429:
                t.rate_limit_retries += 1
            else:
                t.other_retries += 1
        elif typ == "rate_limit_event":
            t.rate_limit_events.append(ev)
        elif typ == "assistant":
            msg = ev.get("message") or {}
            mid = msg.get("id") or f"anon-{t.lines}"
            if mid not in t.message_usage:
                t.assistant_messages += 1
            t.message_usage[mid] = _usage_of(msg)
            for b in msg.get("content") or []:
                if b.get("type") == "tool_use":
                    t.tool_calls += 1
                    t.tool_names.append(b.get("name"))
                    if b.get("name") == "AskUserQuestion":
                        t.asked_question = True
                elif b.get("type") == "text" and b.get("text"):
                    t.last_text = b["text"]
        elif typ == "user":
            for b in (ev.get("message") or {}).get("content") or []:
                if isinstance(b, dict) and b.get("type") == "tool_result" and b.get("is_error"):
                    t.tool_errors += 1
        elif typ == "result":
            t.result = ev
    for d in t.permission_denials():
        if (d or {}).get("tool_name") == "AskUserQuestion":
            t.asked_question = True
    return t


def parse_file(p: Path) -> Transcript:
    return parse_text(Path(p).read_text(encoding="utf-8", errors="replace") if Path(p).exists() else "")


# ---------------------------------------------------------------------------- prices / imputation
_PRICES: dict | None = None


def prices() -> dict:
    global _PRICES
    if _PRICES is None:
        _PRICES = yaml.safe_load((paths.config_dir() / "prices.yaml").read_text(encoding="utf-8"))["models"]
    return _PRICES


def price_for(model: str) -> dict | None:
    for k, v in prices().items():
        if model.startswith(k):
            return v
    return None


def impute_cost(t: Transcript, model: str) -> float | None:
    """List-price estimate from per-message usage (1h cache writes unless the message says 5m)."""
    p = price_for(model)
    if not p:
        return None
    usd = 0.0
    for u in t.message_usage.values():
        cc = u.get("cache_creation") or {}
        w5 = int(cc.get("ephemeral_5m_input_tokens") or 0)
        w1 = int(cc.get("ephemeral_1h_input_tokens") or 0)
        wall = int(u.get("cache_creation_input_tokens") or 0)
        if not (w5 or w1):
            w1 = wall
        usd += (int(u.get("input_tokens") or 0) * p["input"] + int(u.get("output_tokens") or 0) * p["output"]
                + int(u.get("cache_read_input_tokens") or 0) * p["cache_read"] + w5 * p["cache_write_5m"]
                + w1 * p["cache_write_1h"]) / 1e6
    return round(usd, 6)


def parse_resets(text: str) -> str | None:
    m = RESETS.search(text or "")
    return m.group(1).strip() if m else None
