#!/usr/bin/env python3
"""Validate the data contract consumed by the production browser renderer.

This is intentionally stricter than the historical JSON schema. Field names used by
app.js are an API. A publication can be factually correct and schema-valid while still
breaking the website if nested keys drift.

One migration exception exists for the already-published 2026-09-04 morning provisional
edition. That edition may rely on publication-compat.js. Any final edition on that date,
and every later edition, must be canonical.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


MIGRATION_DATE = "2026-09-04"


class Gate:
    def __init__(self) -> None:
        self.errors: list[str] = []

    def require(self, condition: bool, message: str) -> None:
        if not condition:
            self.errors.append(message)


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def canonical_required(report: dict[str, Any]) -> bool:
    cycle = report.get("publication_cycle") or {}
    is_migration_provisional = (
        report.get("date") == MIGRATION_DATE
        and cycle.get("is_final") is False
        and cycle.get("status") == "provisional"
    )
    return not is_migration_provisional


def validate_signal_panel(report: dict[str, Any], gate: Gate, strict: bool) -> None:
    panel = report.get("signal_panel")
    gate.require(isinstance(panel, dict) and len(panel) >= 6, "signal_panel must contain at least six objects")
    if not isinstance(panel, dict):
        return
    canonical = {"label", "current", "yesterday", "change_reason", "evidence", "sources"}
    legacy_safe = {"current", "evidence", "sources"}
    for key, item in panel.items():
        label = f"signal_panel.{key}"
        gate.require(isinstance(item, dict), f"{label} must be an object")
        if not isinstance(item, dict):
            continue
        required = canonical if strict else legacy_safe
        missing = sorted(required - set(item))
        gate.require(not missing, f"{label} missing renderer contract fields: {missing}")
        if strict:
            gate.require("previous" not in item or "yesterday" in item,
                         f"{label}: legacy 'previous' cannot replace canonical 'yesterday'")


def validate_scenarios(report: dict[str, Any], gate: Gate, strict: bool) -> None:
    matrix = report.get("scenario_matrix")
    gate.require(isinstance(matrix, dict), "scenario_matrix must be an object")
    if not isinstance(matrix, dict):
        return
    canonical = {
        "label", "probability", "trigger", "expected_market_reaction",
        "assets_most_sensitive", "what_confirms_it", "what_invalidates_it"
    }
    for key in ("base_case", "bull_case", "bear_case"):
        item = matrix.get(key)
        label = f"scenario_matrix.{key}"
        gate.require(isinstance(item, dict), f"{label} must be an object")
        if not isinstance(item, dict):
            continue
        if strict:
            missing = sorted(canonical - set(item))
            gate.require(not missing, f"{label} missing canonical renderer fields: {missing}")
            gate.require(isinstance(item.get("assets_most_sensitive"), list),
                         f"{label}.assets_most_sensitive must be an array")
            gate.require("market_path" not in item or "expected_market_reaction" in item,
                         f"{label}: legacy 'market_path' cannot replace expected_market_reaction")
            gate.require("invalidation" not in item or "what_invalidates_it" in item,
                         f"{label}: legacy 'invalidation' cannot replace what_invalidates_it")
        else:
            gate.require(bool(item.get("probability")), f"{label}.probability is required")
            gate.require(bool(item.get("trigger")), f"{label}.trigger is required")
            gate.require(bool(item.get("expected_market_reaction") or item.get("market_path")),
                         f"{label} needs expected_market_reaction or migration alias market_path")
            gate.require(bool(item.get("what_invalidates_it") or item.get("invalidation")),
                         f"{label} needs what_invalidates_it or migration alias invalidation")


def validate_next_catalyst(report: dict[str, Any], gate: Gate, strict: bool) -> None:
    item = report.get("next_catalyst")
    gate.require(isinstance(item, dict), "next_catalyst must be an object")
    if not isinstance(item, dict):
        return
    base = {"event", "status", "date", "et", "sgt", "consensus", "previous", "actual", "why_it_matters"}
    missing = sorted(base - set(item))
    gate.require(not missing, f"next_catalyst missing required fields: {missing}")
    if strict:
        extra = {"first_market", "bull_interpretation", "bear_interpretation", "watch_first"}
        missing = sorted(extra - set(item))
        gate.require(not missing, f"next_catalyst missing canonical renderer fields: {missing}")
        gate.require(isinstance(item.get("watch_first"), list), "next_catalyst.watch_first must be an array")


def validate_risks(report: dict[str, Any], gate: Gate, strict: bool) -> None:
    risks = report.get("top_risks")
    gate.require(isinstance(risks, list) and len(risks) == 3, "top_risks must contain exactly three items")
    if not isinstance(risks, list):
        return
    required = {"risk", "trigger", "transmission", "first_asset", "sources"}
    if strict:
        required.add("why_not_fully_priced")
    for index, item in enumerate(risks):
        label = f"top_risks[{index}]"
        gate.require(isinstance(item, dict), f"{label} must be an object")
        if isinstance(item, dict):
            missing = sorted(required - set(item))
            gate.require(not missing, f"{label} missing renderer fields: {missing}")


def validate_earnings(report: dict[str, Any], gate: Gate, strict: bool) -> None:
    sections = report.get("sections") or {}
    earnings = sections.get("earnings") if isinstance(sections, dict) else None
    gate.require(isinstance(earnings, dict), "sections.earnings must be an object")
    if not isinstance(earnings, dict):
        return
    reported = earnings.get("reported")
    upcoming = earnings.get("upcoming_72h")
    gate.require(isinstance(reported, list), "sections.earnings.reported must be an array")
    gate.require(isinstance(upcoming, list), "sections.earnings.upcoming_72h must be an array")
    if not isinstance(reported, list):
        return
    for index, item in enumerate(reported):
        if not isinstance(item, dict):
            gate.errors.append(f"earnings.reported[{index}] must be an object")
            continue
        guidance = item.get("guidance")
        read_through = item.get("read_through")
        gate.require(isinstance(guidance, list), f"earnings.reported[{index}].guidance must be an array")
        gate.require(isinstance(read_through, list), f"earnings.reported[{index}].read_through must be an array")
        if strict and isinstance(guidance, list):
            for j, entry in enumerate(guidance):
                gate.require(
                    isinstance(entry, dict)
                    and {"metric", "current", "previous_or_consensus", "change", "interpretation"} <= set(entry),
                    f"earnings.reported[{index}].guidance[{j}] must use canonical guidance object fields",
                )
        if strict and isinstance(read_through, list):
            for j, entry in enumerate(read_through):
                gate.require(
                    isinstance(entry, dict) and {"asset", "implication"} <= set(entry),
                    f"earnings.reported[{index}].read_through[{j}] must be an asset/implication object",
                )


def validate_tables(report: dict[str, Any], gate: Gate, strict: bool) -> None:
    if not strict:
        return
    sections = report.get("sections")
    if not isinstance(sections, dict):
        return
    for section_key, section in sections.items():
        if not isinstance(section, dict):
            continue
        tables = section.get("tables")
        if not isinstance(tables, list):
            continue
        for index, table in enumerate(tables):
            if not isinstance(table, dict):
                continue
            gate.require(bool(table.get("title")),
                         f"sections.{section_key}.tables[{index}].title is required by canonical contract")


def validate_report(report: dict[str, Any], gate: Gate, index_html: str) -> None:
    strict = canonical_required(report)
    if not strict:
        gate.require("publication-compat.js" in index_html,
                     "migration provisional requires publication-compat.js in docs/index.html")
    validate_signal_panel(report, gate, strict)
    validate_scenarios(report, gate, strict)
    validate_next_catalyst(report, gate, strict)
    validate_risks(report, gate, strict)
    validate_earnings(report, gate, strict)
    validate_tables(report, gate, strict)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    gate = Gate()

    index_html = (root / "docs/index.html").read_text(encoding="utf-8")
    latest = load_json(root / "docs/data/latest.json")
    latest_path = root / "docs" / str(latest.get("daily_json_path", ""))
    gate.require(latest_path.is_file(), f"latest daily path not found: {latest_path}")

    candidates: dict[Path, dict[str, Any]] = {}
    if latest_path.is_file():
        candidates[latest_path] = load_json(latest_path)

    daily_paths = sorted((root / "docs/data/daily").glob("*.json"))
    if daily_paths:
        newest_path = daily_paths[-1]
        candidates[newest_path] = load_json(newest_path)

    for path, report in candidates.items():
        before = len(gate.errors)
        validate_report(report, gate, index_html)
        if len(gate.errors) == before:
            mode = "canonical" if canonical_required(report) else "migration-compatible provisional"
            print(f"LIVE CONTRACT OK: {path.relative_to(root)} ({mode})")

    if gate.errors:
        print("LIVE PUBLICATION CONTRACT FAILED")
        for error in gate.errors:
            print(f"  - {error}")
        return 1

    print("LIVE PUBLICATION CONTRACT PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
