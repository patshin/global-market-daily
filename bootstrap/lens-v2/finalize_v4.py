#!/usr/bin/env python3
"""Compatibility wrapper that fixes FRED date-column parsing before v3 finalization."""
from __future__ import annotations

import runpy
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BOOT = ROOT / "bootstrap/lens-v2"


def patch(path: Path) -> None:
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8")
    if "date_column = next(" in text:
        return
    old = '            value_column = next((name for name in (reader.fieldnames or []) if name != "DATE"), None)'
    new = (
        '            fieldnames = reader.fieldnames or []\n'
        '            date_column = next((name for name in fieldnames if name.lower() in {"date", "observation_date"}), fieldnames[0] if fieldnames else None)\n'
        '            value_column = next((name for name in fieldnames if name != date_column), None)'
    )
    if old not in text:
        raise RuntimeError(f"FRED value-column line not found in {path}")
    text = text.replace(old, new, 1)
    text = text.replace(
        '            if not value_column:\n                raise ValueError(f"FRED response for {series_id} has no value column")',
        '            if not date_column or not value_column:\n                raise ValueError(f"FRED response for {series_id} has no date/value columns")',
        1,
    )
    text = text.replace(
        '                if value is not None:\n                    rows[row["DATE"]] = value',
        '                if value is not None and row.get(date_column):\n                    rows[row[date_column]] = value',
        1,
    )
    path.write_text(text, encoding="utf-8")


for candidate in (BOOT / "build_market_lens.py", ROOT / "scripts/build_market_lens.py"):
    patch(candidate)

v3 = BOOT / "finalize_v3.py"
if v3.exists():
    runpy.run_path(str(v3), run_name="__main__")
else:
    required = [
        ROOT / "scripts/build_market_lens.py",
        ROOT / "scripts/validate_market_lens.py",
        ROOT / "scripts/validate_frontend.py",
        ROOT / "scripts/browser_smoke.sh",
        ROOT / "docs/trends.html",
        ROOT / "docs/assets/trends.js",
        ROOT / "docs/assets/p0.js",
        ROOT / "docs/assets/market-lens.css",
        ROOT / "docs/data/trends/theme-registry.json",
    ]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise RuntimeError(f"v3 source missing and production is incomplete: {missing}")
    commands = [
        ["python3", "scripts/build_market_lens.py", "--root", ".", "--network"],
        ["python3", "scripts/validate_publish.py", "--root", "."],
        ["python3", "scripts/validate_frontend.py", "--root", "."],
        ["python3", "scripts/validate_market_lens.py", "--root", "."],
        ["node", "--check", "docs/assets/app.js"],
        ["node", "--check", "docs/assets/p0.js"],
        ["node", "--check", "docs/assets/trends.js"],
    ]
    for command in commands:
        subprocess.run(command, cwd=ROOT, check=True)
    print("Existing P0 Market Lens v2 production state revalidated")
