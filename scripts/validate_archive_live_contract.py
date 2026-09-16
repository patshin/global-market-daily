#!/usr/bin/env python3
"""Validate every formal archived edition and the Morning-fallback publication contract."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path

from promote_morning_fallback import (
    FALLBACK_NOTICE,
    is_morning_provisional,
    load_json as load_fallback_json,
    open_close_pr_dates,
    report_path_for,
    source_path_for,
    validate_morning_bundle,
)
from validate_live_contract import Gate, load_json, validate_report


def validate_fallback_record(root: Path, report: dict, archive_dates: list[str], gate: Gate) -> None:
    if report.get("is_morning_fallback") is not True:
        return
    day = str(report.get("date", ""))
    cycle = report.get("publication_cycle") or {}
    gate.require(report.get("edition") == "Morning Fallback Final", f"fallback {day} edition label invalid")
    gate.require(report.get("edition_status") == "official", f"fallback {day} must be official")
    gate.require(report.get("fallback_reason") == "evening_missing", f"fallback {day} fallback_reason invalid")
    gate.require(report.get("source_cycle") == "morning", f"fallback {day} source_cycle must remain morning")
    gate.require(report.get("original_data_cutoff_sgt") == report.get("data_cutoff_sgt"), f"fallback {day} SGT cutoff drifted")
    gate.require(report.get("original_data_cutoff_et") == report.get("data_cutoff_et"), f"fallback {day} ET cutoff drifted")
    gate.require(bool(report.get("fallback_promoted_at_sgt")), f"fallback {day} promotion timestamp missing")
    gate.require(cycle.get("status") == "official", f"fallback {day} publication status invalid")
    gate.require(cycle.get("cycle") == "close", f"fallback {day} publication cycle must be close")
    gate.require(cycle.get("is_final") is True, f"fallback {day} must be final")
    gate.require(cycle.get("archive_eligible") is True, f"fallback {day} must be archive eligible")
    gate.require(cycle.get("market_lens_native_eligible") is True, f"fallback {day} must be native-30D eligible")
    gate.require(archive_dates.count(day) == 1, f"fallback {day} must appear exactly once in formal archive")
    md_path = report_path_for(day)
    gate.require(md_path.is_file(), f"fallback {day} Markdown missing")
    if md_path.is_file():
        markdown = md_path.read_text(encoding="utf-8")
        gate.require(FALLBACK_NOTICE in markdown, f"fallback {day} explanatory Markdown notice missing")
        gate.require(f"# Global Market Daily — Morning Fallback Final — {day}" in markdown, f"fallback {day} Markdown edition label invalid")
        gate.require("- Publication Cycle: close / official" in markdown, f"fallback {day} Markdown publication cycle invalid")


def enforce_previous_day_fallback(root: Path, archive_dates: list[str], gate: Gate) -> None:
    latest = load_json(root / "docs/data/latest.json")
    latest_path = root / "docs" / str(latest.get("daily_json_path", ""))
    if not latest_path.is_file():
        return
    current = load_json(latest_path)
    cycle = current.get("publication_cycle") or {}
    if not (cycle.get("cycle") == "morning" and cycle.get("is_final") is False):
        return
    try:
        previous_day = (date.fromisoformat(str(current.get("date"))) - timedelta(days=1)).isoformat()
    except ValueError:
        return
    previous_path = root / f"docs/data/daily/{previous_day}.json"
    if not previous_path.is_file() or previous_day in archive_dates:
        return
    previous = load_json(previous_path)
    if not is_morning_provisional(previous):
        return
    md_path = report_path_for(previous_day)
    source_path = source_path_for(previous)
    if not md_path.is_file() or not source_path.is_file():
        return
    try:
        sources_doc = load_fallback_json(source_path)
        bundle_errors = validate_morning_bundle(
            previous_day,
            previous,
            md_path.read_text(encoding="utf-8"),
            sources_doc,
        )
    except Exception:
        return
    # Incomplete/unparseable Morning snapshots are explicitly allowed to remain unpromoted.
    if bundle_errors:
        return
    try:
        close_dates = open_close_pr_dates()
    except Exception as exc:
        gate.errors.append(
            f"eligible D-1 Morning {previous_day} requires fallback promotion, but absence of a valid Close PR could not be proven: {exc}"
        )
        return
    if previous_day in close_dates:
        print(f"MORNING FALLBACK EXEMPT: {previous_day} has a valid open Close PR")
        return
    skip = current.get("previous_day_fallback") or {}
    skip_reason = str(skip.get("reason", ""))
    detail = f" Existing skip reason: {skip_reason}" if skip_reason else ""
    gate.errors.append(
        f"eligible D-1 Morning {previous_day} must be promoted to Morning Fallback Final in the same Morning candidate; "
        f"a minified JSON/round-trip limitation is not an acceptable merge state when the complete canonical bundle is available.{detail}"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    args = parser.parse_args()
    root = Path(args.root).resolve()

    gate = Gate()
    index_html = (root / "docs/index.html").read_text(encoding="utf-8")
    archive = json.loads((root / "docs/data/archive.json").read_text(encoding="utf-8"))
    entries = archive.get("entries") or []
    gate.require(bool(entries), "archive.json must contain at least one formal edition")

    seen: set[str] = set()
    archive_dates: list[str] = []
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            gate.errors.append(f"archive.entries[{index}] must be an object")
            continue
        day = entry.get("date")
        if not isinstance(day, str):
            gate.errors.append(f"archive.entries[{index}].date is invalid")
            continue
        archive_dates.append(day)
        gate.require(day not in seen, f"duplicate formal archive date: {day}")
        seen.add(day)
        path = root / "docs" / str(entry.get("daily_json_path", ""))
        gate.require(path.is_file(), f"formal archive daily file missing: {path}")
        if not path.is_file():
            continue
        report = load_json(path)
        cycle = report.get("publication_cycle") or {}
        gate.require(cycle.get("is_final") is not False, f"formal archive {day} is not final")
        gate.require(cycle.get("archive_eligible") is not False, f"formal archive {day} is not archive eligible")
        before = len(gate.errors)
        validate_report(report, gate, index_html)
        validate_fallback_record(root, report, archive_dates, gate)
        if len(gate.errors) == before:
            print(f"ARCHIVE LIVE CONTRACT OK: {day}")

    gate.require(archive_dates == sorted(archive_dates, reverse=True), "formal archive dates must be newest-first")

    # Every fallback-tagged daily file is a formal edition and must satisfy the same semantics,
    # even if an archive-list regression would otherwise hide it from the loop above.
    for daily_path in sorted((root / "docs/data/daily").glob("*.json")):
        try:
            report = load_json(daily_path)
        except Exception:
            continue
        if report.get("is_morning_fallback") is True:
            validate_fallback_record(root, report, archive_dates, gate)

    # Blocking anti-regression: a complete D-1 Morning may not be silently skipped merely
    # because a connected runtime disliked minified JSON. A valid open Close PR is the only
    # normal exception; incomplete Morning bundles remain fail-closed and are not fabricated.
    enforce_previous_day_fallback(root, archive_dates, gate)

    gate.require((root / "scripts/promote_morning_fallback.py").is_file(), "fallback promotion helper missing")

    if gate.errors:
        print("ARCHIVE LIVE CONTRACT FAILED")
        for error in gate.errors:
            print(f"  - {error}")
        return 1

    print(f"ARCHIVE LIVE CONTRACT PASSED — {len(seen)} formal edition(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
