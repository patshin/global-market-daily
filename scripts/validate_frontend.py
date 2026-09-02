#!/usr/bin/env python3
"""Deterministic frontend/data visibility gate for Global Market Daily.

This gate protects the UX contract that the report is readable, continuously
visible, and complete on desktop and mobile. It intentionally avoids browser
or network dependencies so it is stable in GitHub Actions.
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
        gate.errors.append(
            f"Invalid JSON {path}: line {exc.lineno}, column {exc.colno}: {exc.msg}"
        )
    return None


def meaningful(value: Any, minimum: int = 1) -> bool:
    return isinstance(value, str) and len(value.strip()) >= minimum


def validate_frontend_sources(root: Path, gate: Gate) -> None:
    index = read(root / "docs/index.html", gate)
    app = read(root / "docs/assets/app.js", gate)
    css = read(root / "docs/assets/styles.css", gate)
    schema = read(root / "schemas/daily.schema.json", gate)

    # Continuous reading contract: no disclosure widgets may hide core report data.
    gate.require("<details" not in index.lower(), "index.html must not contain <details>")
    gate.require("<summary" not in index.lower(), "index.html must not contain <summary>")
    gate.require('create("details"' not in app, "app.js must not create <details>")
    gate.require("defaultOpen" not in app, "app.js still contains collapsed-section logic")
    gate.require("details.open" not in app, "app.js still toggles disclosure state")
    gate.require('create("section", "report-section")' in app,
                 "app.js must render each core section as an always-visible <section>")

    # Full catalyst evidence must be rendered, not reduced to a headline and one sentence.
    gate.require("function renderCatalyst(" in app, "Missing full catalyst renderer")
    for field in (
        "event_time_et", "event_time_sgt", "what_happened", "what_changed",
        "why_it_matters", "transmission", "affected_assets", "confirmation",
        "invalidation",
    ):
        gate.require(f"item.{field}" in app, f"Catalyst renderer does not expose {field}")
    gate.require("function renderCatalystMatrix(" in app,
                 "Section 1 must include the catalyst transmission matrix")

    # Risk and next-catalyst details must remain visible.
    for field in ("why_not_fully_priced", "trigger", "transmission"):
        gate.require(f"item.{field}" in app, f"Risk renderer does not expose {field}")
    for field in ("first_market", "bull_interpretation", "bear_interpretation", "watch_first"):
        gate.require(f"item.{field}" in app, f"Next catalyst renderer does not expose {field}")

    # Mobile tables must be a true vertical information flow, not hidden off-screen.
    gate.require("td.dataset.label = headers[cellIndex]" in app,
                 "Table cells must retain their column label for mobile card rendering")
    gate.require("Mobile single-scroll completion (v1.1.1)" in css,
                 "Missing v1.1.1 mobile single-scroll CSS contract")
    gate.require("content: attr(data-label)" in css,
                 "Mobile table cells must visibly render their labels")
    gate.require(".data-table thead" in css and "clip: rect(0, 0, 0, 0)" in css,
                 "Mobile table headers must be accessibly hidden after labels move to cells")

    # Readability contract and the corrected semantic colours.
    gate.require("Readability + continuous-report audit (v1.1.0)" in css,
                 "Missing consolidated readability layer")
    gate.require("font-size: clamp(2.05rem, 3vw, 2.5rem)" in css,
                 "Desktop thesis size has drifted outside the approved readable scale")
    gate.require(".risk-item .risk-detail__value" in css and "font-size: 0.88rem" in css,
                 "Risk detail copy may not fall back to the legacy 10px rule")
    gate.require(".neutral" in css and "color: var(--muted) !important" in css,
                 "Neutral text must remain legible on the paper background")
    gate.require(".market-tape .neutral" in css,
                 "Market-tape neutral colour requires a dark-background override")

    # Cache-busting prevents the old collapsed/tiny-font bundle from surviving deployment.
    gate.require("styles.css?v=1.2.0" in index, "index.html must load styles.css?v=1.2.0")
    gate.require("app.js?v=1.2.0" in index, "index.html must load app.js?v=1.2.0")
    gate.require('class="catalyst-grid" id="top-catalysts"' in index,
                 "Top 3 catalysts must have a dedicated full-width evidence grid")
    gate.require('id="report-sections"' in index, "Missing continuous report container")

    # Earnings is an unbounded event collection, not a one-company table slot.
    for token in (
        "function renderEarningsCollection(", "function renderReportedEarning(",
        "function renderUpcomingEarning(", "section.reported", "section.upcoming_72h",
    ):
        gate.require(token in app, f"Missing structured multi-company earnings renderer token: {token}")
    gate.require("group.items.forEach((item, index)" in app,
                 "Earnings arrays must be iterated; renderer may not assume index zero")
    gate.require("Earnings collections + deterministic section navigation (v1.2.0)" in css,
                 "Missing earnings/navigation v1.2.0 CSS contract")
    gate.require('"earningsSection"' in schema and '"reportedEarning"' in schema and '"upcomingEarning"' in schema,
                 "Schema must define structured earnings collections")

    # Section navigation must be an in-page button action, never a document/hash reload.
    gate.require('create("button", "section-jump__button"' in app,
                 "Section navigation must render explicit buttons")
    gate.require("event.preventDefault()" in app and "scrollToSection(id)" in app,
                 "Section navigation must prevent default navigation and scroll explicitly")
    gate.require("scrollIntoView" in app and "history.replaceState" in app,
                 "Section navigation must scroll in place and update the hash without navigation")
    gate.require("targetDate === state.selectedDate" in app,
                 "popstate handler must not reload the current report for section-only navigation")
    gate.require('create("a", "", String(section.number)' not in app,
                 "Legacy hash anchors remain in section navigation")


def validate_daily_visibility(path: Path, gate: Gate) -> None:
    report = load_json(path, gate)
    if not isinstance(report, dict):
        return

    date = report.get("date", path.stem)
    catalysts = report.get("top_catalysts")
    gate.require(isinstance(catalysts, list) and len(catalysts) == 3,
                 f"{path}: exactly three catalysts are required")
    if isinstance(catalysts, list):
        for index, item in enumerate(catalysts):
            label = f"{path}: top_catalysts[{index}]"
            gate.require(isinstance(item, dict), f"{label} must be an object")
            if not isinstance(item, dict):
                continue
            for field, minimum in (
                ("event", 12), ("status", 3), ("event_time_et", 5),
                ("event_time_sgt", 5), ("what_happened", 60),
                ("what_changed", 35), ("why_it_matters", 35),
                ("transmission", 20), ("confirmation", 25),
                ("invalidation", 25),
            ):
                gate.require(meaningful(item.get(field), minimum),
                             f"{label}.{field} is empty or too thin")
            assets = item.get("affected_assets")
            gate.require(isinstance(assets, list) and len(assets) >= 3,
                         f"{label}.affected_assets needs at least three assets")
            numeric_context = " ".join(str(item.get(field, "")) for field in (
                "event", "event_time_et", "event_time_sgt", "what_happened", "what_changed"
            ))
            gate.require(re.search(r"\d", numeric_context) is not None,
                         f"{label} contains no visible quantitative or dated evidence")

    order = report.get("section_order")
    sections = report.get("sections")
    gate.require(isinstance(order, list) and len(order) == 15,
                 f"{path}: section_order must contain 15 entries")
    gate.require(isinstance(sections, dict) and len(sections) == 15,
                 f"{path}: sections must contain 15 entries")
    if not isinstance(order, list) or not isinstance(sections, dict):
        return

    for key in order:
        section = sections.get(key)
        label = f"{path}: sections.{key}"
        gate.require(isinstance(section, dict), f"{label} must be an object")
        if not isinstance(section, dict):
            continue
        gate.require(meaningful(section.get("title"), 3), f"{label}.title is empty")
        gate.require(meaningful(section.get("status"), 2), f"{label}.status is empty")
        gate.require(meaningful(section.get("summary"), 20), f"{label}.summary is too thin")

        paragraphs = section.get("paragraphs")
        tables = section.get("tables")
        gate.require(isinstance(paragraphs, list), f"{label}.paragraphs must be an array")
        gate.require(isinstance(tables, list), f"{label}.tables must be an array")
        paragraph_text = "".join(p.strip() for p in paragraphs if isinstance(p, str)) if isinstance(paragraphs, list) else ""
        gate.require(len(paragraph_text) >= 25 or bool(tables),
                     f"{label} has neither meaningful narrative nor a table")

        if isinstance(tables, list):
            for table_index, table in enumerate(tables):
                table_label = f"{label}.tables[{table_index}]"
                gate.require(isinstance(table, dict), f"{table_label} must be an object")
                if not isinstance(table, dict):
                    continue
                headers = table.get("headers")
                rows = table.get("rows")
                gate.require(isinstance(headers, list) and headers,
                             f"{table_label}.headers cannot be empty")
                gate.require(isinstance(rows, list) and rows,
                             f"{table_label}.rows cannot be empty")
                if isinstance(headers, list) and isinstance(rows, list):
                    for row_index, row in enumerate(rows):
                        gate.require(isinstance(row, list) and len(row) == len(headers),
                                     f"{table_label}.rows[{row_index}] must match header count")

    earnings = sections.get("earnings")
    gate.require(isinstance(earnings, dict), f"{path}: sections.earnings must be an object")
    if isinstance(earnings, dict):
        reported = earnings.get("reported")
        upcoming = earnings.get("upcoming_72h")
        gate.require(isinstance(reported, list), f"{path}: earnings.reported must be an array")
        gate.require(isinstance(upcoming, list), f"{path}: earnings.upcoming_72h must be an array")
        if isinstance(reported, list) and isinstance(upcoming, list):
            event_ids = [
                item.get("id")
                for item in [*reported, *upcoming]
                if isinstance(item, dict)
            ]
            gate.require(len(event_ids) == len(set(event_ids)),
                         f"{path}: earnings event IDs must be unique")
            if "无重大新增" not in str(earnings.get("status", "")):
                gate.require(bool(reported or upcoming),
                             f"{path}: updated earnings section has no event objects")
            for index, item in enumerate(reported):
                item_label = f"{path}: earnings.reported[{index}]"
                gate.require(isinstance(item, dict), f"{item_label} must be an object")
                if isinstance(item, dict):
                    gate.require(isinstance(item.get("metrics"), list) and bool(item["metrics"]),
                                 f"{item_label}.metrics must be non-empty")
                    gate.require(isinstance(item.get("read_through"), list) and bool(item["read_through"]),
                                 f"{item_label}.read_through must be non-empty")
            for index, item in enumerate(upcoming):
                item_label = f"{path}: earnings.upcoming_72h[{index}]"
                gate.require(isinstance(item, dict), f"{item_label} must be an object")
                if isinstance(item, dict):
                    gate.require(item.get("actual") == "待公布",
                                 f"{item_label}.actual must be 待公布")

    # The file name and date remain the unique edition key.
    gate.require(date == path.stem, f"{path}: date must match filename")


def validate_repository(root: Path) -> int:
    gate = Gate()
    validate_frontend_sources(root, gate)

    daily_paths = sorted((root / "docs/data/daily").glob("*.json"))
    gate.require(bool(daily_paths), "No daily JSON files found")
    for path in daily_paths:
        validate_daily_visibility(path, gate)

    if gate.errors:
        print("FRONTEND VISIBILITY GATE FAILED")
        for error in gate.errors:
            print(f"  - {error}")
        return 1

    print(
        "FRONTEND VISIBILITY GATE PASSED — "
        f"continuous report, complete catalysts, multi-company earnings, stable in-page navigation, {len(daily_paths)} edition(s)"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".", help="Repository root")
    args = parser.parse_args()
    return validate_repository(Path(args.root).resolve())


if __name__ == "__main__":
    sys.exit(main())
