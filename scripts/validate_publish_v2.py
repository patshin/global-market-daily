#!/usr/bin/env python3
"""Publication gate with explicit support for provisional morning editions.

This module reuses the detailed per-edition validation in validate_publish.py,
but separates the live/latest publication surface from the formal archive:
- all daily editions are validated;
- publication_cycle.is_final == false editions may become latest;
- only final editions must appear in archive.json;
- provisional editions must not appear in archive.json.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from validate_publish import Gate, REQUIRED_FILES, load_json, validate_daily


def is_final_report(report: dict) -> bool:
    cycle = report.get("publication_cycle") or {}
    return cycle.get("is_final") is not False


def validate_repository(root: Path) -> int:
    gate = Gate()
    for relative in REQUIRED_FILES:
        gate.require((root / relative).exists(), f"Missing required file: {relative}")

    daily_paths = sorted((root / "docs/data/daily").glob("*.json"))
    gate.require(bool(daily_paths), "No daily JSON files found")

    valid_dates: list[str] = []
    final_dates: list[str] = []
    reports: dict[str, dict] = {}

    for path in daily_paths:
        # validate_daily() expects daily.sources_path to resolve to a JSON file.
        # Guard that contract here so a malformed candidate fails closed with a
        # useful gate error rather than raising IsADirectoryError on docs/.
        report = load_json(path, gate)
        if not isinstance(report, dict):
            continue
        sources_path = report.get("sources_path")
        has_sources_path = isinstance(sources_path, str) and bool(sources_path.strip())
        gate.require(has_sources_path, f"{path}: sources_path must be a non-empty string")
        if not has_sources_path:
            continue
        resolved_sources = root / "docs" / sources_path
        gate.require(resolved_sources.is_file(),
                     f"{path}: sources_path must resolve to a JSON file: {sources_path}")
        if not resolved_sources.is_file():
            continue

        date = validate_daily(path, root, gate)
        if not date:
            continue
        valid_dates.append(date)
        reports[date] = report
        if is_final_report(report):
            final_dates.append(date)

    latest = load_json(root / "docs/data/latest.json", gate)
    archive = load_json(root / "docs/data/archive.json", gate)

    archive_dates: list[str] = []
    if isinstance(archive, dict):
        entries = archive.get("entries")
        gate.require(isinstance(entries, list) and entries, "archive.json entries must be non-empty")
        if isinstance(entries, list):
            archive_dates = [item.get("date") for item in entries if isinstance(item, dict)]
            gate.require(len(archive_dates) == len(set(archive_dates)), "archive.json contains duplicate dates")
            gate.require(archive_dates == sorted(archive_dates, reverse=True),
                         "archive.json entries must be newest first")
            gate.require(set(archive_dates) == set(final_dates),
                         "archive.json dates must exactly match FINAL daily JSON dates; provisional editions are excluded")
            for index, item in enumerate(entries):
                if not isinstance(item, dict):
                    gate.errors.append(f"archive.json entries[{index}] must be object")
                    continue
                for field in ("date", "thesis", "overall_regime", "dominant_narrative",
                              "report_path", "daily_json_path", "sources_path"):
                    gate.require(bool(item.get(field)), f"archive.json entries[{index}] missing {field}")
                for field in ("report_path", "daily_json_path", "sources_path"):
                    value = item.get(field)
                    if isinstance(value, str):
                        gate.require((root / "docs" / value).exists(),
                                     f"archive.json entries[{index}] points to missing {value}")

    if isinstance(latest, dict):
        latest_date = latest.get("date")
        gate.require(latest_date in valid_dates, "latest.json date has no daily JSON")
        if valid_dates:
            gate.require(latest_date == max(valid_dates), "latest.json must point to newest daily date")
        for field in ("daily_json_path", "report_path", "sources_path"):
            value = latest.get(field)
            gate.require(isinstance(value, str) and (root / "docs" / value).exists(),
                         f"latest.json points to missing {value}")

        latest_report = reports.get(latest_date) if isinstance(latest_date, str) else None
        if isinstance(latest_report, dict):
            latest_is_final = is_final_report(latest_report)
            if latest_is_final:
                match = None
                if isinstance(archive, dict) and isinstance(archive.get("entries"), list):
                    match = next((item for item in archive["entries"] if item.get("date") == latest_date), None)
                gate.require(match is not None, "latest FINAL date missing from archive")
                if isinstance(match, dict):
                    gate.require(latest.get("thesis") == match.get("thesis"),
                                 "latest thesis must match archive thesis for FINAL edition")
                    gate.require(latest.get("dominant_narrative") == match.get("dominant_narrative"),
                                 "latest narrative must match archive narrative for FINAL edition")
            else:
                gate.require(latest_date not in archive_dates,
                             "latest PROVISIONAL date must not be present in formal archive")
                cycle = latest_report.get("publication_cycle") or {}
                gate.require(cycle.get("archive_eligible") is False,
                             "PROVISIONAL daily must explicitly set publication_cycle.archive_eligible=false")
                gate.require(cycle.get("market_lens_native_eligible") is False,
                             "PROVISIONAL daily must explicitly set publication_cycle.market_lens_native_eligible=false")
                gate.require(latest.get("edition_status") == "provisional",
                             "latest.json must mark edition_status=provisional for a provisional live edition")

    if gate.warnings:
        print("WARNINGS")
        for warning in gate.warnings:
            print(f"  - {warning}")

    if gate.errors:
        print("PUBLICATION GATE FAILED")
        for error in gate.errors:
            print(f"  - {error}")
        return 1

    newest = max(valid_dates) if valid_dates else "n/a"
    print(
        f"PUBLICATION GATE PASSED — {len(valid_dates)} daily edition(s), "
        f"{len(final_dates)} formal archive edition(s), latest {newest}"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".", help="Repository root")
    args = parser.parse_args()
    return validate_repository(Path(args.root).resolve())


if __name__ == "__main__":
    sys.exit(main())
