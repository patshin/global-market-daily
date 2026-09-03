#!/usr/bin/env python3
"""Capability-level frontend gate for Global Market Daily v2.

The gate protects user-visible behaviour rather than brittle historical version
strings. It validates continuous reading, complete event collections, stable
navigation, P0 Market Lens integration and responsive rendering contracts.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
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
        gate.errors.append(f"Missing frontend file: {path}")
        return ""


def load_json(path: Path, gate: Gate) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        gate.errors.append(f"Missing JSON: {path}")
    except json.JSONDecodeError as exc:
        gate.errors.append(f"Invalid JSON {path}: line {exc.lineno}, column {exc.colno}: {exc.msg}")
    return None


def meaningful(value: Any, minimum: int = 1) -> bool:
    return isinstance(value, str) and len(value.strip()) >= minimum


def validate_sources(root: Path, gate: Gate) -> None:
    index = read(root / "docs/index.html", gate)
    app = read(root / "docs/assets/app.js", gate)
    p0 = read(root / "docs/assets/p0.js", gate)
    trends = read(root / "docs/assets/trends.js", gate)
    css = read(root / "docs/assets/styles.css", gate)
    lens_css = read(root / "docs/assets/market-lens.css", gate)
    trends_html = read(root / "docs/trends.html", gate)

    # Core daily report remains one continuous document.
    gate.require("<details" not in index.lower(), "index.html must not contain <details>")
    gate.require("<summary" not in index.lower(), "index.html must not contain <summary>")
    gate.require('create("details"' not in app, "app.js must not create <details>")
    gate.require('create("section", "report-section")' in app, "Core sections must render as always-visible sections")
    gate.require('id="report-sections"' in index, "Missing continuous report container")

    # Full catalyst evidence remains visible.
    gate.require("function renderCatalyst(" in app, "Missing full catalyst renderer")
    for field in (
        "event_time_et", "event_time_sgt", "what_happened", "what_changed",
        "why_it_matters", "transmission", "affected_assets", "confirmation", "invalidation",
    ):
        gate.require(f"item.{field}" in app, f"Catalyst renderer does not expose {field}")
    gate.require("function renderCatalystMatrix(" in app, "Missing Top 3 catalyst transmission matrix")

    # Multi-company earnings and unbounded event collections.
    for token in (
        "function renderEarningsCollection(", "function renderReportedEarning(",
        "function renderUpcomingEarning(", "group.items.forEach",
        "function renderEventCollection(", "function renderGenericEvent(",
    ):
        gate.require(token in app, f"Missing collection renderer token: {token}")
    gate.require("items[0]" not in app and "reported[0]" not in app and "upcoming[0]" not in app,
                 "Collection renderer may not assume a single first event")

    # Mobile table cells retain their labels.
    gate.require("td.dataset.label = headers[cellIndex]" in app, "Responsive table labels are missing")
    gate.require("content: attr(data-label)" in css, "Mobile table labels are not visibly rendered")

    # Section navigation is an in-page action and preserves the current report.
    gate.require('create("button", "section-jump__button"' in app, "Section navigation must use buttons")
    gate.require("event.preventDefault()" in app and "scrollToSection(id)" in app,
                 "Section navigation must prevent default navigation and scroll explicitly")
    gate.require("scrollIntoView" in app or "window.scrollTo" in app, "Section navigation lacks in-page scrolling")
    gate.require("history.replaceState" in app, "Section navigation must update URL without navigation")
    gate.require("targetDate === state.selectedDate" in app, "Same-date history changes must not reload the report")

    # P0 homepage modules and compact mobile dock.
    for token in (
        "assets/market-lens.css?v=2.0.0", "assets/p0.js?v=2.0.0",
    ):
        gate.require(token in index, f"Homepage is not loading {token}")
    for token in (
        "insertMarketLensPreview", "renderCrossAssetConfirmation", "createReadingDock", "MutationObserver",
    ):
        gate.require(token in p0, f"P0 renderer missing {token}")
    gate.require("Market Lens preview unavailable; daily report remains unaffected" in p0,
                 "P0 failure must degrade safely without breaking the daily report")

    # Dedicated Lens page contains every P0 analytical view.
    for token in (
        "regime-ribbon", "signal-matrix", "catalyst-map", "persistent-themes",
        "cross-confirmation", "cross-asset-charts", "lens-methodology",
    ):
        gate.require(token in trends_html, f"trends.html missing {token}")
    for token in (
        "renderRegimeRibbon", "renderSignalMatrix", "renderCatalystMap",
        "renderPersistentThemes", "renderCrossAssetConfirmation", "renderAssetCharts",
    ):
        gate.require(token in trends, f"trends.js missing {token}")

    # Responsive typography and no horizontal-only mobile chart contract.
    gate.require("P0 MARKET LENS" in lens_css, "Missing P0 Market Lens CSS layer")
    gate.require("@media (max-width: 900px)" in lens_css, "Missing tablet/mobile breakpoint")
    gate.require("@media (max-width: 560px)" in lens_css, "Missing phone breakpoint")
    gate.require(".catalyst-map__mobile" in lens_css, "Catalyst map lacks a mobile reading mode")
    gate.require(".signal-matrix__mobile" in lens_css, "Signal matrix lacks a mobile reading mode")
    gate.require(".reading-dock" in lens_css, "Compact mobile reading dock styles are missing")
    gate.require("font-size: clamp(2.05rem, 3vw, 2.5rem)" in css,
                 "Desktop thesis typography drifted outside the approved scale")


def validate_daily(path: Path, gate: Gate) -> None:
    report = load_json(path, gate)
    if not isinstance(report, dict):
        return
    date_value = report.get("date", path.stem)
    gate.require(date_value == path.stem, f"{path}: date must match filename")

    catalysts = report.get("top_catalysts")
    gate.require(isinstance(catalysts, list) and len(catalysts) == 3,
                 f"{path}: exactly three Top Catalysts are required")
    for index, item in enumerate(catalysts or []):
        label = f"{path}: top_catalysts[{index}]"
        gate.require(isinstance(item, dict), f"{label} must be an object")
        if not isinstance(item, dict):
            continue
        for field, minimum in (
            ("event", 12), ("status", 3), ("what_happened", 35),
            ("why_it_matters", 25), ("transmission", 15),
            ("confirmation", 20), ("invalidation", 20),
        ):
            gate.require(meaningful(item.get(field), minimum), f"{label}.{field} is empty or too thin")
        gate.require(meaningful(item.get("theme_id"), 3), f"{label}.theme_id is required for history")
        gate.require(meaningful(item.get("category"), 3), f"{label}.category is required for history")

    sections = report.get("sections")
    order = report.get("section_order")
    gate.require(isinstance(order, list) and len(order) == 15, f"{path}: section_order must contain 15 entries")
    gate.require(isinstance(sections, dict) and len(sections) >= 15, f"{path}: sections must contain 15 entries")
    if not isinstance(sections, dict) or not isinstance(order, list):
        return

    event_sections = {
        "us_macro", "central_banks", "geopolitics", "regional_policy",
        "index_changes", "flows", "etf", "options", "treasury",
        "commodities", "financing", "breaking_news",
    }
    for key in order:
        section = sections.get(key)
        label = f"{path}: sections.{key}"
        gate.require(isinstance(section, dict), f"{label} must be an object")
        if not isinstance(section, dict):
            continue
        gate.require(meaningful(section.get("summary"), 20), f"{label}.summary is too thin")
        if key in event_sections:
            groups = section.get("event_groups")
            gate.require(isinstance(groups, list) and groups, f"{label}.event_groups must be a non-empty array")
            for group_index, group in enumerate(groups or []):
                group_label = f"{label}.event_groups[{group_index}]"
                gate.require(isinstance(group, dict), f"{group_label} must be an object")
                if not isinstance(group, dict):
                    continue
                gate.require(isinstance(group.get("items"), list), f"{group_label}.items must be an array")
                for item_index, item in enumerate(group.get("items", [])):
                    item_label = f"{group_label}.items[{item_index}]"
                    gate.require(isinstance(item, dict), f"{item_label} must be an object")
                    if not isinstance(item, dict):
                        continue
                    gate.require(meaningful(item.get("id"), 5), f"{item_label}.id is required")
                    gate.require(meaningful(item.get("title"), 3), f"{item_label}.title is required")
                    gate.require(meaningful(item.get("status"), 2), f"{item_label}.status is required")

    earnings = sections.get("earnings")
    gate.require(isinstance(earnings, dict), f"{path}: earnings section is missing")
    if isinstance(earnings, dict):
        gate.require(isinstance(earnings.get("reported"), list), f"{path}: earnings.reported must be an array")
        gate.require(isinstance(earnings.get("upcoming_72h"), list), f"{path}: earnings.upcoming_72h must be an array")
        for item in earnings.get("upcoming_72h", []):
            gate.require(item.get("actual") == "待公布", f"{path}: future earnings Actual must be 待公布")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    gate = Gate()
    validate_sources(root, gate)
    paths = sorted((root / "docs/data/daily").glob("*.json"))
    gate.require(bool(paths), "No daily JSON files found")
    for path in paths:
        validate_daily(path, gate)
    if gate.errors:
        print("FRONTEND CAPABILITY GATE FAILED")
        for error in gate.errors:
            print(f"  - {error}")
        return 1
    print(f"FRONTEND CAPABILITY GATE PASSED — continuous report, collections, P0 Lens and responsive UX; {len(paths)} edition(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
