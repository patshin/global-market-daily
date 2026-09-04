#!/usr/bin/env python3
"""Fail-closed watchdog for the external 09:00 and 18:00 publisher tasks."""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


SGT = ZoneInfo("Asia/Singapore")


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--cycle", required=True, choices=("morning", "close"))
    parser.add_argument("--date", help="Expected SGT date, YYYY-MM-DD. Defaults to now in Asia/Singapore.")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    expected_date = args.date or datetime.now(SGT).date().isoformat()
    latest = load(root / "docs/data/latest.json")
    require(latest.get("date") == expected_date,
            f"latest.date={latest.get('date')!r}; expected SGT date {expected_date}")

    daily_path = root / "docs" / latest["daily_json_path"]
    report = load(daily_path)
    cycle = report.get("publication_cycle") or {}
    require(report.get("date") == expected_date, "Daily JSON date does not match watchdog date")
    require(cycle.get("cycle") == args.cycle,
            f"publication_cycle.cycle={cycle.get('cycle')!r}; expected {args.cycle!r}")

    panel = report.get("signal_panel") or {}
    require(isinstance(panel, dict) and len(panel) >= 6, "Signal panel is missing one or more dimensions")
    for key, item in panel.items():
        require(isinstance(item, dict), f"signal_panel.{key} must be an object")
        for field in ("label", "current", "yesterday", "change_reason", "evidence", "sources"):
            require(field in item, f"signal_panel.{key}.{field} is missing")
        require(str(item.get("change_reason", "")).strip() != str(item.get("evidence", "")).strip(),
                f"signal_panel.{key} duplicates change_reason and evidence")

    watch = (report.get("next_catalyst") or {}).get("watch_first")
    watch_items = [str(item).strip() for item in watch or [] if str(item).strip()]
    require(2 <= len(watch_items) <= 3, "next_catalyst.watch_first must contain 2–3 items")

    archive = load(root / "docs/data/archive.json")
    archive_dates = [item.get("date") for item in archive.get("entries", [])]
    rolling = load(root / "docs/data/trends/rolling-30d.json")
    native_dates = {
        item.get("date")
        for item in rolling.get("days", [])
        if item.get("source_mode") == "native_daily"
    }

    if args.cycle == "morning":
        require(cycle.get("is_final") is False, "Morning publication must be provisional")
        require(cycle.get("archive_eligible") is False, "Morning publication cannot be archive eligible")
        require(cycle.get("market_lens_native_eligible") is False,
                "Morning publication cannot be native 30D eligible")
        require(expected_date not in archive_dates, "Morning publication leaked into formal archive")
        require(expected_date not in native_dates, "Morning publication leaked into native 30D history")
    else:
        require(cycle.get("is_final") is True, "Close publication must be final")
        require(cycle.get("archive_eligible") is True, "Close publication must be archive eligible")
        require(cycle.get("market_lens_native_eligible") is True,
                "Close publication must be native 30D eligible")
        require(archive_dates.count(expected_date) == 1,
                "Close publication must appear exactly once in formal archive")
        require(expected_date in native_dates, "Close publication is missing from native 30D history")

    print(
        f"SCHEDULED PUBLICATION VERIFIED: cycle={args.cycle}, date={expected_date}, "
        "signal panel canonical, watch_first complete, archive semantics correct"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
