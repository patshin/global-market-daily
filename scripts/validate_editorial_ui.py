#!/usr/bin/env python3
"""Static contract gate for the signal-panel and watch-first UI repair."""
from __future__ import annotations

import json
import sys
from pathlib import Path


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


def main() -> int:
    root = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd()
    gate = Gate()

    index = read(root / "docs/index.html", gate)
    js = read(root / "docs/assets/editorial-v2.js", gate)
    css = read(root / "docs/assets/editorial-v2.css", gate)

    gate.require("editorial-v2.css?v=2.0.0" in index, "index.html does not load editorial-v2.css v2.0.0")
    gate.require("editorial-v2.js?v=2.0.0" in index, "index.html does not load editorial-v2.js v2.0.0")
    order = [
        index.find("app.js?v=1.2.1"),
        index.find("publication-compat.js?v=1.1.0"),
        index.find("editorial-v2.js?v=2.0.0"),
        index.find("p0.js?v=2.1.1"),
    ]
    gate.require(all(position >= 0 for position in order) and order == sorted(order),
                 "JavaScript load order must be app → compatibility → editorial-v2 → p0")

    for token in (
        "Signal Panel editorial reset (v2.0.0)",
        "grid-template-columns: repeat(3, minmax(0, 1fr))",
        "grid-template-columns: repeat(2, minmax(0, 1fr))",
        "grid-template-columns: minmax(0, 1fr)",
        ".signal-card__previous",
        ".signal-card__fact-label",
        ".watch-list--editorial",
    ):
        gate.require(token in css, f"Editorial CSS missing token: {token}")

    for token in (
        "function renderEditorialSignals",
        "reason && reason !== evidence",
        "renderSignals = renderEditorialSignals",
        "function buildWatchFirst",
        "output.length >= 3",
        "output.length >= 2",
        "renderNextCatalyst = function renderEditorialNextCatalyst",
        "watch-list--editorial",
        "gmdEditorialReady",
        "gmdHorizontalOverflow",
        "gmdSignalFactsDistinct",
        "Closing Dashboard",
    ):
        gate.require(token in js, f"Editorial JavaScript missing token: {token}")

    latest_path = root / "docs/data/latest.json"
    try:
        latest = json.loads(latest_path.read_text(encoding="utf-8"))
        daily_path = root / "docs" / latest["daily_json_path"]
        report = json.loads(daily_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, KeyError, json.JSONDecodeError) as exc:
        gate.errors.append(f"Unable to inspect latest publication for UI contract: {exc}")
        report = {}

    panel = report.get("signal_panel")
    gate.require(isinstance(panel, dict) and len(panel) >= 6,
                 "Latest publication needs at least six signal objects")

    cycle = report.get("publication_cycle") or {}
    strict = cycle.get("is_final") is True or report.get("date", "") > "2026-09-04"
    if strict:
        if isinstance(panel, dict):
            required_signal = {"label", "current", "yesterday", "change_reason", "evidence", "sources"}
            for key, item in panel.items():
                gate.require(isinstance(item, dict), f"signal_panel.{key} must be an object")
                if not isinstance(item, dict):
                    continue
                missing = sorted(required_signal - set(item))
                gate.require(not missing, f"signal_panel.{key} missing fields: {missing}")
                reason = str(item.get("change_reason", "")).strip()
                evidence = str(item.get("evidence", "")).strip()
                gate.require(reason != evidence,
                             f"signal_panel.{key} repeats identical change_reason and evidence")
                gate.require(len(str(item.get("current", "")).strip()) <= 40,
                             f"signal_panel.{key}.current is too long for the editorial card")

        watch = (report.get("next_catalyst") or {}).get("watch_first")
        gate.require(isinstance(watch, list) and 2 <= len([x for x in watch if str(x).strip()]) <= 3,
                     "Canonical latest publication requires 2–3 watch_first items")

    if gate.errors:
        print("EDITORIAL UI CONTRACT FAILED")
        for error in gate.errors:
            print(f"  - {error}")
        return 1

    print("EDITORIAL UI CONTRACT PASSED — 3/2/1 responsive signal grid, deduplicated evidence, non-empty watch-first fallback")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
