#!/usr/bin/env python3
"""Deterministic quality gate for the 30-day Market Lens and P0 UX."""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any


class Gate:
    def __init__(self) -> None:
        self.errors: list[str] = []

    def require(self, condition: bool, message: str) -> None:
        if not condition:
            self.errors.append(message)


def read(path: Path, gate: Gate) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        gate.errors.append(f"Missing file: {path}")
        return ""


def load(path: Path, gate: Gate) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        gate.errors.append(f"Missing JSON: {path}")
    except json.JSONDecodeError as exc:
        gate.errors.append(f"Invalid JSON {path}: {exc}")
    return None


def validate(root: Path) -> int:
    gate = Gate()
    docs = root / "docs"
    lens = load(docs / "data/trends/rolling-30d.json", gate)
    history = load(docs / "data/trends/market-history.json", gate)
    latest = load(docs / "data/latest.json", gate)
    registry = load(docs / "data/trends/theme-registry.json", gate)
    version = load(docs / "version.json", gate)
    index = read(docs / "index.html", gate)
    trends_html = read(docs / "trends.html", gate)
    trends_js = read(docs / "assets/trends.js", gate)
    p0_js = read(docs / "assets/p0.js", gate)
    css = read(docs / "assets/market-lens.css", gate)

    if not isinstance(lens, dict) or not isinstance(history, dict):
        return finish(gate)

    gate.require(lens.get("schema_version") == "2.0.0", "rolling-30d schema_version must be 2.0.0")
    gate.require(history.get("schema_version") == "2.0.0", "market-history schema_version must be 2.0.0")
    gate.require(lens.get("as_of") == latest.get("date"), "Market Lens as_of must match latest daily edition")
    try:
        start = date.fromisoformat(lens["window_start"])
        end = date.fromisoformat(lens["window_end"])
        gate.require((end - start).days == 29, "Market Lens must cover exactly 30 calendar days")
    except Exception:
        gate.errors.append("Invalid Market Lens date window")

    coverage = lens.get("coverage", {})
    gate.require(coverage.get("market_sessions", 0) >= 12, "At least 12 market sessions are required for Day 1")
    gate.require(coverage.get("native_daily_days", 0) >= 1, "At least one native daily edition is required")
    gate.require(coverage.get("objective_reconstruction_days", 0) >= 10, "Historical reconstruction must make Day 1 useful")
    gate.require(coverage.get("history_days_retained", 0) >= 150, "At least 150 history days must be retained for normalisation")
    gate.require(coverage.get("day1_ready") is True, "Day 1 readiness flag must be true")

    days = lens.get("days")
    gate.require(isinstance(days, list) and len(days) == coverage.get("market_sessions"), "days must match market session coverage")
    allowed_regimes = {"risk_on", "neutral", "risk_off", "event_risk"}
    allowed_modes = {"native_daily", "objective_market_reconstruction"}
    registry_themes = set((registry or {}).get("themes", {}).keys())
    seen_dates: set[str] = set()
    native_dates = []
    for index_day, item in enumerate(days or []):
        label = f"days[{index_day}]"
        gate.require(item.get("date") not in seen_dates, f"{label} has duplicate date")
        seen_dates.add(item.get("date"))
        gate.require(item.get("regime_code") in allowed_regimes, f"{label} has invalid regime")
        gate.require(item.get("source_mode") in allowed_modes, f"{label} has invalid source_mode")
        if item.get("source_mode") == "native_daily":
            native_dates.append(item.get("date"))
        catalysts = item.get("catalysts")
        gate.require(isinstance(catalysts, list) and 1 <= len(catalysts) <= 3, f"{label} must expose one to three catalysts")
        for rank, catalyst in enumerate(catalysts or [], 1):
            gate.require(catalyst.get("rank") == rank, f"{label} catalyst ranks must be consecutive")
            gate.require(catalyst.get("theme_id") in registry_themes, f"{label} has unknown catalyst theme")
            gate.require(catalyst.get("source_mode") == item.get("source_mode"), f"{label} catalyst provenance mismatch")
            gate.require(bool(catalyst.get("evidence")), f"{label} catalyst evidence is empty")
            gate.require(bool(catalyst.get("transmission")), f"{label} catalyst transmission is empty")
        gate.require(set((item.get("signals") or {}).keys()) == {"growth", "inflation", "rates", "earnings", "liquidity", "geopolitics"}, f"{label} signal matrix is incomplete")

    gate.require(native_dates == [lens.get("as_of")], "Only the actual published edition may be labelled native_daily")
    gate.require(all(day <= lens.get("as_of") for day in seen_dates), "Future dates are prohibited")

    themes = lens.get("persistent_themes")
    gate.require(isinstance(themes, list) and len(themes) >= 3, "Persistent theme lifecycle must contain useful history")
    allowed_states = {"new", "escalating", "persistent", "active", "easing", "resolved"}
    for item in themes or []:
        gate.require(item.get("theme_id") in registry_themes, "Lifecycle theme must resolve through registry")
        gate.require(item.get("state") in allowed_states, "Lifecycle state is invalid")
        gate.require(item.get("days_in_top3", 0) >= 1, "Lifecycle occurrence count must be positive")
        gate.require(item.get("first_seen") <= item.get("last_seen"), "Lifecycle dates are reversed")

    validation = lens.get("cross_asset_validation", {})
    gate.require(validation.get("theme_id") in registry_themes, "Cross-asset validation theme is unresolved")
    gate.require(isinstance(validation.get("confirming"), list), "Confirming assets must be an array")
    gate.require(isinstance(validation.get("diverging"), list), "Diverging assets must be an array")
    gate.require(bool(validation.get("what_would_flip_it")), "Cross-asset flip condition is required")

    assets = lens.get("asset_series")
    gate.require(isinstance(assets, list) and len(assets) >= 5, "At least five separate cross-asset series are required")
    for item in assets or []:
        gate.require(len(item.get("observations", [])) >= 12, f"Asset {item.get('key')} has insufficient observations")

    raw_series = history.get("series", {})
    for key in ("sp500", "nasdaq", "vix", "ust2y", "ust10y", "brent"):
        gate.require(len(raw_series.get(key, [])) >= 25, f"Required market history missing: {key}")

    serialized = json.dumps(lens, ensure_ascii=False).lower()
    gate.require("risk_score" not in serialized and "composite_score" not in serialized, "Black-box risk scores are prohibited")
    gate.require("historical_reconstruction" not in serialized or "objective_market_reconstruction" in serialized, "Historical provenance must use the approved source mode")

    for token in ("assets/market-lens.css?v=2.0.0", "assets/p0.js?v=2.0.0"):
        gate.require(token in index, f"Homepage is not loading {token}")
    for token in ("30-Day Market Lens", "regime-ribbon", "signal-matrix", "catalyst-map", "persistent-themes", "cross-asset-charts"):
        gate.require(token in trends_html, f"trends.html missing {token}")
    for token in ("renderRegimeRibbon", "renderSignalMatrix", "renderCatalystMap", "renderPersistentThemes", "renderAssetCharts"):
        gate.require(token in trends_js, f"trends.js missing {token}")
    for token in ("insertMarketLensPreview", "renderCrossAssetConfirmation", "createReadingDock", "MutationObserver"):
        gate.require(token in p0_js, f"p0.js missing {token}")
    for token in ("P0 MARKET LENS", "reading-dock", "catalyst-map", "@media (max-width: 900px)"):
        gate.require(token in css, f"market-lens.css missing {token}")
    gate.require(version.get("site_version") == "2.0.0", "Site version must be 2.0.0")
    gate.require(version.get("release_state") == "production", "Site release_state must be production")

    return finish(gate, coverage)


def finish(gate: Gate, coverage: dict[str, Any] | None = None) -> int:
    if gate.errors:
        print("MARKET LENS GATE FAILED")
        for error in gate.errors:
            print(f"  - {error}")
        return 1
    coverage = coverage or {}
    print(
        "MARKET LENS GATE PASSED — "
        f"{coverage.get('market_sessions')} sessions, "
        f"{coverage.get('native_daily_days')} native, "
        f"{coverage.get('objective_reconstruction_days')} reconstructed"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    args = parser.parse_args()
    return validate(Path(args.root).resolve())


if __name__ == "__main__":
    sys.exit(main())
