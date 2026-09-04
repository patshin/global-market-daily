#!/usr/bin/env python3
"""Validate the standalone twice-daily automation prompt contract."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


FORBIDDEN_PHRASES = (
    "基于对话上下文",
    "基于本对话",
    "参考上文",
    "参考前文",
    "根据之前的对话",
    "based on the conversation",
    "based on prior conversation",
    "previous conversation",
    "as discussed above",
    "earlier context",
)

COMMON_REQUIRED = (
    "patshin/global-market-daily",
    "branch: `main`",
    "https://patshin.github.io/global-market-daily/",
    "Asia/Singapore",
    "independently research",
    "schemas/daily.schema.json",
    "scripts/validate_live_contract.py",
    "docs/data/daily/YYYY-MM-DD.json",
    "docs/reports/YYYY/MM/YYYY-MM-DD.md",
    "docs/data/sources/YYYY-MM-DD.json",
    "docs/data/latest.json",
    "latest.date",
    "real browser",
    "six editorial signal cards",
    "What I Would Watch First",
    "2–3",
    "actual: \"待公布\"",
)


class Gate:
    def __init__(self) -> None:
        self.errors: list[str] = []

    def require(self, condition: bool, message: str) -> None:
        if not condition:
            self.errors.append(message)


def load_json(path: Path, gate: Gate) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        gate.errors.append(f"Missing file: {path}")
        return {}
    except json.JSONDecodeError as exc:
        gate.errors.append(f"Invalid JSON {path}: {exc}")
        return {}
    if not isinstance(value, dict):
        gate.errors.append(f"Expected object in {path}")
        return {}
    return value


def read_text(path: Path, gate: Gate) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        gate.errors.append(f"Missing file: {path}")
        return ""


def validate_prompt(path: Path, gate: Gate, mode: str, schedule: str) -> None:
    text = read_text(path, gate)
    lower = text.lower()
    gate.require(len(text) >= 9_000, f"{path} is too short to be a standalone production prompt")
    for phrase in FORBIDDEN_PHRASES:
        gate.require(phrase.lower() not in lower, f"{path} contains forbidden context-dependent phrase: {phrase}")
    for token in COMMON_REQUIRED:
        gate.require(token.lower() in lower, f"{path} missing standalone production token: {token}")
    gate.require(f"fixed run mode: `{mode}`" in lower, f"{path} does not lock run mode {mode}")
    gate.require(f"scheduled time: `{schedule} sgt`" in lower, f"{path} does not lock schedule {schedule} SGT")
    gate.require("do not stop at a draft json response or a plan" in lower,
                 f"{path} may stop before publication")
    gate.require("watch_first` is mandatory" in lower,
                 f"{path} does not make watch_first mandatory")
    gate.require("change_reason` and `evidence` must not be identical" in lower,
                 f"{path} does not prevent duplicated signal text")


def main() -> int:
    root = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd()
    gate = Gate()

    registry_path = root / "prompts/automation-registry.json"
    registry = load_json(registry_path, gate)
    gate.require(registry.get("timezone") == "Asia/Singapore", "Automation timezone must be Asia/Singapore")
    gate.require(registry.get("repository") == "patshin/global-market-daily", "Automation repository mismatch")
    gate.require(registry.get("branch") == "main", "Automation branch must be main")
    gate.require(registry.get("publisher_architecture") == "connected_scheduled_agent",
                 "Research publisher architecture must remain connected_scheduled_agent")

    tasks = registry.get("tasks")
    gate.require(isinstance(tasks, list) and len(tasks) == 2,
                 "Automation registry must contain exactly morning and close tasks")

    expected = {
        "morning": {
            "schedule_sgt": "09:00",
            "cron_utc": "0 1 * * *",
            "prompt_path": "prompts/automation-morning.md",
            "archive_eligible": False,
            "market_lens_native_eligible": False,
        },
        "close": {
            "schedule_sgt": "18:00",
            "cron_utc": "0 10 * * *",
            "prompt_path": "prompts/automation-close.md",
            "archive_eligible": True,
            "market_lens_native_eligible": True,
        },
    }

    if isinstance(tasks, list):
        indexed = {task.get("run_mode"): task for task in tasks if isinstance(task, dict)}
        gate.require(set(indexed) == set(expected), "Automation registry modes must be morning and close")
        for mode, contract in expected.items():
            task = indexed.get(mode, {})
            for key, value in contract.items():
                gate.require(task.get(key) == value, f"Automation registry {mode}.{key} must be {value!r}")
            validate_prompt(root / contract["prompt_path"], gate, mode, contract["schedule_sgt"])

    master = read_text(root / "prompts/global-market-daily-master.md", gate)
    gate.require(len(master) >= 9_000, "Master prompt is too short")
    for phrase in FORBIDDEN_PHRASES:
        gate.require(phrase.lower() not in master.lower(),
                     f"Master prompt contains forbidden context-dependent phrase: {phrase}")
    gate.require("watch_first` is mandatory" in master.lower(),
                 "Master prompt must require non-empty watch_first")
    gate.require("six editorial signal cards" in master.lower(),
                 "Master prompt must include the browser UI gate")

    gate.require(not (root / "prompts/global-market-daily.md").exists(),
                 "Legacy prompts/global-market-daily.md must be removed to avoid automation ambiguity")

    if gate.errors:
        print("AUTOMATION CONTRACT FAILED")
        for error in gate.errors:
            print(f"  - {error}")
        return 1

    print("AUTOMATION CONTRACT PASSED — standalone 09:00/18:00 prompts, fixed modes, browser gate, no context-dependent wording")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
