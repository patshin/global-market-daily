#!/usr/bin/env python3
"""Deterministic publication gate for Global Market Daily.

Uses the Python standard library only so GitHub Actions can run without
dependency installation or network access.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Iterable

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
SGT_RE = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2} SGT$")
ET_RE = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2} (?:EDT|EST)$")
IMPORTANCE = {"★★★★★", "★★★★", "★★★"}
REQUIRED_REGIME = {"growth", "inflation", "rates", "earnings", "liquidity", "geopolitics", "overall"}
REQUIRED_FILES = [
    "docs/index.html",
    "docs/assets/styles.css",
    "docs/assets/app.js",
    "docs/data/latest.json",
    "docs/data/archive.json",
]


class Gate:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def require(self, condition: bool, message: str) -> None:
        if not condition:
            self.errors.append(message)

    def warn(self, condition: bool, message: str) -> None:
        if not condition:
            self.warnings.append(message)


def load_json(path: Path, gate: Gate) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        gate.errors.append(f"Missing JSON: {path}")
    except json.JSONDecodeError as exc:
        gate.errors.append(f"Invalid JSON {path}: line {exc.lineno}, column {exc.colno}: {exc.msg}")
    return None


def iter_source_refs(value: Any, path: str = "$") -> Iterable[tuple[str, str]]:
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if key == "sources" and isinstance(child, list):
                for item in child:
                    if isinstance(item, str):
                        yield child_path, item
            else:
                yield from iter_source_refs(child, child_path)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from iter_source_refs(child, f"{path}[{index}]")


def validate_source_doc(path: Path, expected_date: str, gate: Gate) -> tuple[dict[str, Any], set[str]]:
    doc = load_json(path, gate)
    if not isinstance(doc, dict):
        return {}, set()

    gate.require(doc.get("date") == expected_date, f"{path}: source date must be {expected_date}")
    records = doc.get("sources")
    gate.require(isinstance(records, list) and records, f"{path}: sources must be a non-empty array")
    if not isinstance(records, list):
        return doc, set()

    ids: list[str] = []
    for index, source in enumerate(records):
        label = f"{path}: sources[{index}]"
        gate.require(isinstance(source, dict), f"{label} must be an object")
        if not isinstance(source, dict):
            continue
        source_id = source.get("id")
        gate.require(isinstance(source_id, str) and re.fullmatch(r"S\d{2,}", source_id or "") is not None,
                     f"{label}.id must look like S01")
        if isinstance(source_id, str):
            ids.append(source_id)
        for field in ("source_name", "source_title", "retrieved_at", "tier", "used_for", "confidence"):
            gate.require(field in source, f"{label} missing {field}")
        url = source.get("source_url")
        gate.require(url is None or (isinstance(url, str) and url.startswith("https://")),
                     f"{label}.source_url must be https:// or null")
        gate.require(not (isinstance(url, str) and "{{" in url), f"{label}.source_url contains placeholder")
    gate.require(len(ids) == len(set(ids)), f"{path}: duplicate source IDs")
    return doc, set(ids)


def validate_earnings_section(section: dict[str, Any], path: Path, gate: Gate) -> None:
    # Validate N reported and N upcoming earnings events; never a single-company slot.
    label = f"{path}: sections.earnings"
    reported = section.get("reported")
    upcoming = section.get("upcoming_72h")
    gate.require(isinstance(reported, list), f"{label}.reported must be an array")
    gate.require(isinstance(upcoming, list), f"{label}.upcoming_72h must be an array")
    if not isinstance(reported, list) or not isinstance(upcoming, list):
        return

    ids: list[str] = []

    for index, item in enumerate(reported):
        item_label = f"{label}.reported[{index}]"
        gate.require(isinstance(item, dict), f"{item_label} must be an object")
        if not isinstance(item, dict):
            continue
        for field in (
            "id", "company", "ticker", "period", "status", "release_date",
            "release_time_et", "release_time_sgt", "market_session",
            "key_takeaway", "metrics", "guidance", "market_reaction",
            "one_offs", "read_through", "sources",
        ):
            gate.require(field in item, f"{item_label} missing {field}")
        if isinstance(item.get("id"), str):
            ids.append(item["id"])
        gate.require(isinstance(item.get("metrics"), list) and bool(item["metrics"]),
                     f"{item_label}.metrics must be a non-empty array")
        if isinstance(item.get("metrics"), list):
            for metric_index, metric in enumerate(item["metrics"]):
                metric_label = f"{item_label}.metrics[{metric_index}]"
                gate.require(isinstance(metric, dict), f"{metric_label} must be an object")
                if isinstance(metric, dict):
                    for field in ("metric", "actual", "consensus", "previous_or_yoy", "surprise", "notes"):
                        gate.require(bool(metric.get(field)), f"{metric_label} missing {field}")
        gate.require(isinstance(item.get("guidance"), list),
                     f"{item_label}.guidance must be an array")
        reaction = item.get("market_reaction")
        gate.require(isinstance(reaction, dict), f"{item_label}.market_reaction must be an object")
        if isinstance(reaction, dict):
            for field in ("session", "move", "as_of"):
                gate.require(bool(reaction.get(field)), f"{item_label}.market_reaction missing {field}")
        gate.require(isinstance(item.get("read_through"), list) and bool(item["read_through"]),
                     f"{item_label}.read_through must be a non-empty array")

    for index, item in enumerate(upcoming):
        item_label = f"{label}.upcoming_72h[{index}]"
        gate.require(isinstance(item, dict), f"{item_label} must be an object")
        if not isinstance(item, dict):
            continue
        for field in (
            "id", "company", "ticker", "period", "status", "date", "et", "sgt",
            "market_session", "consensus", "previous_guidance", "actual",
            "what_matters", "read_through_targets", "sources",
        ):
            gate.require(field in item, f"{item_label} missing {field}")
        if isinstance(item.get("id"), str):
            ids.append(item["id"])
        gate.require(item.get("actual") == "待公布",
                     f"{item_label}.actual must be 待公布")
        consensus = item.get("consensus")
        gate.require(isinstance(consensus, dict), f"{item_label}.consensus must be an object")
        if isinstance(consensus, dict):
            gate.require(bool(consensus.get("revenue")), f"{item_label}.consensus.revenue is required")
            gate.require(bool(consensus.get("eps")), f"{item_label}.consensus.eps is required")
        gate.require(isinstance(item.get("what_matters"), list) and bool(item["what_matters"]),
                     f"{item_label}.what_matters must be a non-empty array")
        gate.require(
            isinstance(item.get("read_through_targets"), list) and bool(item["read_through_targets"]),
            f"{item_label}.read_through_targets must be a non-empty array",
        )

    gate.require(len(ids) == len(set(ids)), f"{label} contains duplicate earnings event IDs")
    if not re.search(r"无重大新增", str(section.get("status", ""))):
        gate.require(bool(reported or upcoming),
                     f"{label} is marked as an update but contains no earnings events")


def validate_daily(path: Path, root: Path, gate: Gate) -> str | None:
    display_path = path.relative_to(root) if path.is_absolute() else path
    report = load_json(path, gate)
    if not isinstance(report, dict):
        return None

    date = report.get("date")
    gate.require(isinstance(date, str) and DATE_RE.fullmatch(date or "") is not None,
                 f"{path}: invalid date")
    if not isinstance(date, str):
        return None
    gate.require(path.stem == date, f"{path}: filename must equal report date")

    required = [
        "schema_version", "edition", "timezone", "data_cutoff_sgt", "data_cutoff_et",
        "last_updated", "thesis", "dominant_narrative", "market_regime", "market_tape",
        "what_changed", "top_catalysts", "section_order", "sections", "signal_panel",
        "scenario_matrix", "upcoming_market_watch", "top_risks", "next_catalyst", "sources"
    ]
    for field in required:
        gate.require(field in report, f"{path}: missing {field}")

    gate.require(report.get("timezone") == "Asia/Singapore", f"{path}: timezone must be Asia/Singapore")
    gate.require(SGT_RE.fullmatch(str(report.get("data_cutoff_sgt", ""))) is not None,
                 f"{path}: invalid SGT cutoff")
    gate.require(ET_RE.fullmatch(str(report.get("data_cutoff_et", ""))) is not None,
                 f"{path}: invalid ET cutoff or missing EDT/EST")
    gate.require(isinstance(report.get("thesis"), str) and len(report["thesis"]) >= 40,
                 f"{path}: thesis is too short")
    gate.require(isinstance(report.get("dominant_narrative"), str) and len(report["dominant_narrative"]) >= 40,
                 f"{path}: dominant narrative is too short")

    regime = report.get("market_regime")
    gate.require(isinstance(regime, dict) and REQUIRED_REGIME.issubset(regime),
                 f"{path}: market_regime must include {sorted(REQUIRED_REGIME)}")

    tape = report.get("market_tape")
    gate.require(isinstance(tape, list) and len(tape) >= 12, f"{path}: market_tape needs at least 12 assets")
    if isinstance(tape, list):
        assets = [item.get("asset") for item in tape if isinstance(item, dict)]
        gate.require(len(assets) == len(set(assets)), f"{path}: duplicate market_tape asset")
        for index, item in enumerate(tape):
            if not isinstance(item, dict):
                gate.errors.append(f"{path}: market_tape[{index}] must be object")
                continue
            for field in ("asset", "level", "change_1d", "change_5d", "signal", "driver", "status", "as_of"):
                gate.require(field in item, f"{path}: market_tape[{index}] missing {field}")

    changes = report.get("what_changed")
    gate.require(isinstance(changes, list) and 1 <= len(changes) <= 5,
                 f"{path}: what_changed must contain 1–5 entries")

    catalysts = report.get("top_catalysts")
    gate.require(isinstance(catalysts, list) and len(catalysts) == 3,
                 f"{path}: top_catalysts must contain exactly 3 entries")
    if isinstance(catalysts, list):
        for index, item in enumerate(catalysts):
            if isinstance(item, dict):
                gate.require(item.get("importance") in {"★★★★★", "★★★★"},
                             f"{path}: top_catalysts[{index}] importance must be 4 or 5 stars")
                for field in ("status", "event_time_et", "event_time_sgt", "what_happened",
                              "what_changed", "why_it_matters", "transmission",
                              "confirmation", "invalidation"):
                    gate.require(bool(item.get(field)), f"{path}: top_catalysts[{index}] missing {field}")

    order = report.get("section_order")
    sections = report.get("sections")
    gate.require(isinstance(order, list) and len(order) == 15 and len(set(order)) == 15,
                 f"{path}: section_order must contain 15 unique keys")
    gate.require(isinstance(sections, dict) and len(sections) == 15,
                 f"{path}: sections must contain exactly 15 sections")
    if isinstance(order, list) and isinstance(sections, dict):
        gate.require(set(order) == set(sections), f"{path}: section_order and sections keys differ")
        numbers = []
        for key in order:
            section = sections.get(key)
            if not isinstance(section, dict):
                gate.errors.append(f"{path}: section {key} must be object")
                continue
            numbers.append(section.get("number"))
            for field in ("number", "title", "status", "summary", "paragraphs", "tables"):
                gate.require(field in section, f"{path}: section {key} missing {field}")
        gate.require(numbers == list(range(1, 16)), f"{path}: section numbers must be 1..15 in order")
        earnings_section = sections.get("earnings")
        gate.require(isinstance(earnings_section, dict),
                     f"{path}: sections.earnings must be an object")
        if isinstance(earnings_section, dict):
            validate_earnings_section(earnings_section, path, gate)

    panel = report.get("signal_panel")
    gate.require(isinstance(panel, dict) and len(panel) == 6, f"{path}: signal_panel must contain 6 signals")

    matrix = report.get("scenario_matrix")
    gate.require(isinstance(matrix, dict) and set(matrix) == {"base_case", "bull_case", "bear_case"},
                 f"{path}: scenario_matrix must contain base/bull/bear only")

    watch = report.get("upcoming_market_watch")
    gate.require(isinstance(watch, list) and watch, f"{path}: upcoming_market_watch cannot be empty")
    if isinstance(watch, list):
        for index, item in enumerate(watch):
            if not isinstance(item, dict):
                gate.errors.append(f"{path}: upcoming_market_watch[{index}] must be object")
                continue
            gate.require(item.get("actual") == "待公布",
                         f"{path}: upcoming_market_watch[{index}].actual must be 待公布")
            gate.require(item.get("importance") in IMPORTANCE,
                         f"{path}: upcoming_market_watch[{index}] importance must be 3–5 stars")

    risks = report.get("top_risks")
    gate.require(isinstance(risks, list) and len(risks) == 3, f"{path}: top_risks must contain exactly 3")

    next_catalyst = report.get("next_catalyst")
    gate.require(isinstance(next_catalyst, dict), f"{path}: next_catalyst must be object")
    if isinstance(next_catalyst, dict):
        gate.require(next_catalyst.get("actual") == "待公布",
                     f"{path}: next_catalyst.actual must be 待公布")

    source_path = root / "docs" / str(report.get("sources_path", ""))
    source_doc, source_ids = validate_source_doc(source_path, date, gate)
    declared = report.get("sources")
    gate.require(isinstance(declared, list), f"{path}: sources must be array")
    if isinstance(declared, list):
        gate.require(set(declared) == source_ids, f"{path}: daily source ID list must equal source archive IDs")
    for ref_path, source_id in iter_source_refs(report):
        gate.require(source_id in source_ids, f"{path}: unresolved source {source_id} at {ref_path}")

    markdown_path = root / "docs/reports" / date[:4] / date[5:7] / f"{date}.md"
    gate.require(markdown_path.exists(), f"{path}: missing Markdown archive {markdown_path}")
    if markdown_path.exists():
        markdown = markdown_path.read_text(encoding="utf-8")
        gate.require(report["data_cutoff_sgt"] in markdown, f"{markdown_path}: SGT cutoff differs from JSON")
        gate.require(report["data_cutoff_et"] in markdown, f"{markdown_path}: ET cutoff differs from JSON")
        gate.require(report["thesis"] in markdown, f"{markdown_path}: thesis differs from JSON")
        gate.require(report["dominant_narrative"] in markdown, f"{markdown_path}: narrative differs from JSON")
        if isinstance(order, list) and isinstance(sections, dict):
            for key in order:
                title = sections[key].get("title")
                gate.require(isinstance(title, str) and title in markdown,
                             f"{markdown_path}: missing section title {title}")
        if isinstance(catalysts, list):
            for item in catalysts:
                if isinstance(item, dict):
                    gate.require(item.get("event", "") in markdown,
                                 f"{markdown_path}: missing catalyst {item.get('event')}")
        if isinstance(risks, list):
            for item in risks:
                if isinstance(item, dict):
                    gate.require(item.get("risk", "") in markdown,
                                 f"{markdown_path}: missing risk {item.get('risk')}")

    serialized = json.dumps(report, ensure_ascii=False)
    gate.require(re.search(r"\{\{[^{}]+\}\}", serialized) is None, f"{path}: unresolved template placeholder")
    return date


def validate_repository(root: Path) -> int:
    gate = Gate()
    for relative in REQUIRED_FILES:
        gate.require((root / relative).exists(), f"Missing required file: {relative}")

    daily_paths = sorted((root / "docs/data/daily").glob("*.json"))
    gate.require(bool(daily_paths), "No daily JSON files found")
    dates = [validate_daily(path, root, gate) for path in daily_paths]
    valid_dates = [date for date in dates if date]

    latest = load_json(root / "docs/data/latest.json", gate)
    archive = load_json(root / "docs/data/archive.json", gate)

    if isinstance(archive, dict):
        entries = archive.get("entries")
        gate.require(isinstance(entries, list) and entries, "archive.json entries must be non-empty")
        if isinstance(entries, list):
            archive_dates = [item.get("date") for item in entries if isinstance(item, dict)]
            gate.require(len(archive_dates) == len(set(archive_dates)), "archive.json contains duplicate dates")
            gate.require(archive_dates == sorted(archive_dates, reverse=True),
                         "archive.json entries must be newest first")
            gate.require(set(archive_dates) == set(valid_dates),
                         "archive.json dates must exactly match daily JSON dates")
            for index, item in enumerate(entries):
                if not isinstance(item, dict):
                    gate.errors.append(f"archive.json entries[{index}] must be object")
                    continue
                for field in ("date","thesis","overall_regime","dominant_narrative",
                              "report_path","daily_json_path","sources_path"):
                    gate.require(bool(item.get(field)), f"archive.json entries[{index}] missing {field}")
                for field in ("report_path","daily_json_path","sources_path"):
                    value = item.get(field)
                    if isinstance(value, str):
                        gate.require((root / "docs" / value).exists(),
                                     f"archive.json entries[{index}] points to missing {value}")

    if isinstance(latest, dict):
        latest_date = latest.get("date")
        gate.require(latest_date in valid_dates, "latest.json date has no daily JSON")
        if valid_dates:
            gate.require(latest_date == max(valid_dates), "latest.json must point to newest daily date")
        for field in ("daily_json_path","report_path","sources_path"):
            value = latest.get(field)
            gate.require(isinstance(value, str) and (root / "docs" / value).exists(),
                         f"latest.json points to missing {value}")
        if isinstance(archive, dict) and isinstance(archive.get("entries"), list):
            match = next((item for item in archive["entries"] if item.get("date") == latest_date), None)
            gate.require(match is not None, "latest date missing from archive")
            if isinstance(match, dict):
                gate.require(latest.get("thesis") == match.get("thesis"),
                             "latest thesis must match archive thesis")
                gate.require(latest.get("dominant_narrative") == match.get("dominant_narrative"),
                             "latest narrative must match archive narrative")

    if gate.warnings:
        print("WARNINGS")
        for warning in gate.warnings:
            print(f"  - {warning}")

    if gate.errors:
        print("PUBLICATION GATE FAILED")
        for error in gate.errors:
            print(f"  - {error}")
        return 1

    print(f"PUBLICATION GATE PASSED — {len(valid_dates)} daily edition(s), latest {max(valid_dates)}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".", help="Repository root")
    args = parser.parse_args()
    return validate_repository(Path(args.root).resolve())


if __name__ == "__main__":
    sys.exit(main())
