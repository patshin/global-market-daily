#!/usr/bin/env python3
"""Validate every formal archived edition against the current browser renderer contract.

The live-contract gate historically checked only latest/newest, which can let a backfilled
or older formal report become unrenderable without breaking the current homepage. This
wrapper treats every archive entry as a user-facing API surface.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from validate_live_contract import Gate, load_json, validate_report


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
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            gate.errors.append(f"archive.entries[{index}] must be an object")
            continue
        date = entry.get("date")
        if not isinstance(date, str):
            gate.errors.append(f"archive.entries[{index}].date is invalid")
            continue
        gate.require(date not in seen, f"duplicate formal archive date: {date}")
        seen.add(date)
        path = root / "docs" / str(entry.get("daily_json_path", ""))
        gate.require(path.is_file(), f"formal archive daily file missing: {path}")
        if not path.is_file():
            continue
        report = load_json(path)
        cycle = report.get("publication_cycle") or {}
        gate.require(cycle.get("is_final") is not False, f"formal archive {date} is not final")
        gate.require(cycle.get("archive_eligible") is not False, f"formal archive {date} is not archive eligible")
        before = len(gate.errors)
        validate_report(report, gate, index_html)
        if len(gate.errors) == before:
            print(f"ARCHIVE LIVE CONTRACT OK: {date}")

    if gate.errors:
        print("ARCHIVE LIVE CONTRACT FAILED")
        for error in gate.errors:
            print(f"  - {error}")
        return 1

    print(f"ARCHIVE LIVE CONTRACT PASSED — {len(seen)} formal edition(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
