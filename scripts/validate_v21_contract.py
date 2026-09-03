#!/usr/bin/env python3
"""Validate the v2.1 trend-copy and twice-daily publication contract."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
errors: list[str] = []


def require(condition: bool, message: str) -> None:
    if not condition:
        errors.append(message)


def text(path: str) -> str:
    p = ROOT / path
    if not p.exists():
        errors.append(f"Missing {path}")
        return ""
    return p.read_text(encoding="utf-8")


def payload(path: str) -> dict:
    raw = text(path)
    if not raw:
        return {}
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        errors.append(f"Invalid JSON {path}: {exc}")
        return {}
    return value if isinstance(value, dict) else {}


trends_html = text("docs/trends.html")
trends_js = text("docs/assets/trends.js")
p0_js = text("docs/assets/p0.js")
builder = text("scripts/build_market_lens.py")
generator = text("scripts/generate_daily_with_openai.py")
workflow = text(".github/workflows/daily-market-intelligence.yml")
rolling = payload("docs/data/trends/rolling-30d.json")
schedule = payload("docs/data/automation/schedule.json")
policy = payload("docs/data/trends/policy-events.json")

banned_copy = [
    "离散状态，不使用黑箱综合分数",
    "Growth / Inflation / Rates / Earnings / Liquidity / Geopolitics 六条信号与同一交易日对齐",
    "横轴是日期，纵轴是稳定主题类别",
    "衡量的是进入 Top 3 的持续性与生命周期，而不是人为制造的 0–100 风险分",
    "价格共振仅作为 Narrative confirmation/divergence evidence，不等同于因果证明",
]
for phrase in banned_copy:
    require(phrase not in trends_html, f"Internal-sounding copy remains: {phrase}")

require("本窗口未进入 Top 3" in trends_js, "Catalyst map needs an explicit empty-category state")
require("china_trade_policy" in builder, "Trend builder lacks China/trade category support")
require("DEXCHUS" in builder, "Trend builder lacks objective China market proxy")
require("load_policy_events" in builder, "Trend builder lacks verified policy-event ingestion")
require("official_archive') is False" in builder or 'official_archive") is False' in builder,
        "Morning editions are not excluded from native history")

series = rolling.get("series", {})
activity = rolling.get("category_activity", {})
require("DEXCHUS" in series, "rolling-30d.json lacks USD/CNY history")
require("china_trade_policy" in activity, "rolling-30d.json lacks China category activity status")
require(activity.get("china_trade_policy", {}).get("status") in {"active", "not_in_top3"},
        "China category activity status is invalid")
require(isinstance(policy.get("events"), list), "policy-events.json events must be an array")

require('cron: "0 1 * * *"' in workflow, "09:00 SGT schedule is missing")
require('cron: "0 10 * * *"' in workflow, "18:00 SGT schedule is missing")
require("GMD_OPENAI_MODEL" in workflow, "Scheduled model is not externally configurable")
require("GMD_REASONING_EFFORT" in workflow and "xhigh" in workflow,
        "Extra-high reasoning default is missing")
require("OPENAI_API_KEY" in workflow, "OpenAI credential preflight is missing")
require("official_archive" in generator and 'edition == "eod"' in generator,
        "Generator does not make EOD the official archive")
require("latest.json" in generator.lower() or "LATEST_PATH" in generator,
        "Generator does not control latest.json")
require("web_search" in generator, "Generator is not configured for independent web research")
require("source_records" in generator, "Generator lacks source reconciliation")

runs = schedule.get("runs", [])
require(len(runs) == 2, "Schedule contract must contain exactly two daily editions")
require(any(item.get("local_time") == "09:00" and item.get("edition") == "morning" for item in runs),
        "Schedule contract lacks 09:00 morning edition")
require(any(item.get("local_time") == "18:00" and item.get("edition") == "eod" for item in runs),
        "Schedule contract lacks 18:00 EOD edition")

# Guard against accidental hidden disclosure controls in the report or trend page.
require("<details" not in trends_html.lower(), "Trend page must not hide content in details controls")
require("<summary" not in trends_html.lower(), "Trend page must not hide content in summary controls")
require("30D context temporarily unavailable" not in p0_js,
        "Homepage still contains untranslated internal fallback copy")

# Static syntax sanity for the two UTC cron values.
for expression in re.findall(r'cron:\s*"([^"]+)"', workflow):
    require(len(expression.split()) == 5, f"Invalid cron expression: {expression}")

if errors:
    print("V2.1 CONTRACT GATE FAILED")
    for error in errors:
        print(f"  - {error}")
    sys.exit(1)

print(
    "V2.1 CONTRACT GATE PASSED — China/trade coverage, reader-facing copy, "
    "09:00/18:00 publication semantics and EOD archive rule"
)
