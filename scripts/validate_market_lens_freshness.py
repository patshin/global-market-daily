#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DAILY_DIR = ROOT / "docs/data/daily"
ROLLING_PATH = ROOT / "docs/data/trends/rolling-30d.json"
ARCHIVE_PATH = ROOT / "docs/data/archive.json"


def load_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected object: {path}")
    return value


def main() -> int:
    errors: list[str] = []
    rolling = load_json(ROLLING_PATH)
    archive = load_json(ARCHIVE_PATH)
    archive_dates = {
        str(entry.get("date"))
        for entry in (archive.get("entries") or [])
        if isinstance(entry, dict) and entry.get("date")
    }

    eligible: set[str] = set()
    for path in DAILY_DIR.glob("*.json"):
        try:
            report = load_json(path)
        except Exception:
            continue
        cycle = report.get("publication_cycle") or {}
        if cycle.get("is_final") is True and cycle.get("market_lens_native_eligible") is True:
            day = str(report.get("date", ""))
            if day:
                eligible.add(day)
                if day not in archive_dates:
                    errors.append(f"native-eligible final {day} is missing from formal archive")

    if not eligible:
        errors.append("no native-eligible final daily reports found")
    else:
        expected_latest = max(eligible)
        as_of = str(rolling.get("as_of", ""))
        window_start = str(rolling.get("window_start", ""))
        window_end = str(rolling.get("window_end", ""))
        native_dates = {
            str(day.get("date"))
            for day in (rolling.get("days") or [])
            if isinstance(day, dict) and day.get("source_mode") == "native_daily"
        }
        if not as_of or as_of < expected_latest:
            errors.append(f"rolling-30d stale: as_of={as_of!r}, latest native-eligible final={expected_latest}")
        if expected_latest not in native_dates:
            errors.append(f"latest native-eligible final {expected_latest} missing from rolling-30d native days")
        for day in sorted(eligible):
            if window_start <= day <= window_end and day not in native_dates:
                errors.append(f"formal native day {day} is inside the lens window but missing from native_daily days")

    if errors:
        print("MARKET LENS FRESHNESS FAILED")
        for error in errors:
            print(f" - {error}")
        return 1
    print(f"MARKET LENS FRESHNESS PASSED — rolling as_of={rolling.get('as_of')} includes latest native final={max(eligible)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
