#!/usr/bin/env python3
"""Regression test: every native daily report in the window overrides reconstruction."""
from __future__ import annotations

import importlib.util
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("market_lens_builder", ROOT / "scripts/build_market_lens.py")
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)


def native_report(day: str, label: str) -> dict:
    catalysts = []
    risks = []
    for rank, theme_id in enumerate(("global_duration", "energy_inflation", "ai_earnings"), 1):
        theme = module.THEMES[theme_id]
        catalysts.append({
            "rank": rank,
            "event": f"{label} catalyst {rank}",
            "status": "Confirmed",
            "event_time_et": f"{day} 08:30 EDT",
            "event_time_sgt": f"{day} 20:30 SGT",
            "what_happened": f"Native published evidence for {label} item {rank} with dated and quantitative context.",
            "what_changed": "The published market interpretation changed from the prior edition.",
            "why_it_matters": "This item changes the transmission path across rates, equities and commodities.",
            "transmission": theme["transmission"],
            "affected_assets": [theme["primary_asset"], "Nasdaq", "USD"],
            "direction": "Mixed",
            "importance": "★★★★★" if rank == 1 else "★★★★",
            "confirmation": "The primary asset continues in the expected direction.",
            "invalidation": theme["flip"],
            "theme_id": theme_id,
            "category": theme["category"],
            "sources": ["TEST"],
        })
        risks.append({
            "risk": theme["risk_label"],
            "first_asset": theme["primary_asset"],
            "trigger": "Synthetic regression trigger",
            "transmission": theme["transmission"],
            "theme_id": theme_id,
        })
    signal_panel = {
        "growth_impulse": {"current": "→"},
        "inflation_impulse": {"current": "↑"},
        "rates_pressure": {"current": "↑"},
        "earnings_revision": {"current": "→"},
        "liquidity": {"current": "↓"},
        "geopolitical_risk": {"current": "→"},
    }
    return {
        "date": day,
        "market_regime": {"overall": {"state": "Event Risk"}},
        "top_catalysts": catalysts,
        "top_risks": risks,
        "signal_panel": signal_panel,
    }


start = date(2026, 1, 5)
rows = []
for index in range(15):
    day = start + timedelta(days=index)
    values = {
        "sp500": 6000 + index * 8,
        "nasdaq": 20000 + index * 24,
        "vix": 17 + (index % 3),
        "ust2y": 4.0 + index * 0.005,
        "ust10y": 4.3 + index * 0.008,
        "brent": 80 + index * 0.2,
        "broad_usd": 120 + index * 0.05,
        "hy_spread": 3.1 + index * 0.01,
    }
    rows.append({"date": day.isoformat(), "values": values, "stale_days": {key: 0 for key in values}})

native_dates = [rows[5]["date"], rows[12]["date"]]
reports = {
    native_dates[0]: native_report(native_dates[0], "EARLIER"),
    native_dates[1]: native_report(native_dates[1], "LATEST"),
}
result = module.build_session_days(rows, reports, date.fromisoformat(rows[2]["date"]), date.fromisoformat(rows[-1]["date"]))
observed_native = [item["date"] for item in result if item["source_mode"] == "native_daily"]
assert observed_native == native_dates, (observed_native, native_dates)
assert next(item for item in result if item["date"] == native_dates[0])["catalysts"][0]["title"].startswith("EARLIER")
assert next(item for item in result if item["date"] == native_dates[1])["catalysts"][0]["title"].startswith("LATEST")
assert all(item["source_mode"] == "objective_market_reconstruction" for item in result if item["date"] not in native_dates)
print("NATIVE HISTORY ACCUMULATION TEST PASSED — 2 archived editions override reconstruction")
