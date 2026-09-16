#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
DAILY_DIR = ROOT / "docs/data/daily"
ARCHIVE_PATH = ROOT / "docs/data/archive.json"
SGT = ZoneInfo("Asia/Singapore")
FALLBACK_NOTICE = (
    "> **Morning snapshot used as Final Daily fallback because Evening Official was missing.** "
    "This final-daily record preserves the original Morning research cutoff and factual snapshot; "
    "no later facts were added."
)
SOURCE_ID_RE = re.compile(r"S\d+")


def load_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def report_path_for(day: str) -> Path:
    y, m, _ = day.split("-")
    return ROOT / f"docs/reports/{y}/{m}/{day}.md"


def source_path_for(report: dict) -> Path:
    return ROOT / "docs" / str(report.get("sources_path", ""))


def canonical_literals(report: dict) -> list[str]:
    literals = [
        str(report.get("data_cutoff_sgt", "")),
        str(report.get("data_cutoff_et", "")),
        str(report.get("thesis", "")),
        str(report.get("dominant_narrative", "")),
    ]
    sections = report.get("sections") or {}
    for key in report.get("section_order") or []:
        section = sections.get(key) or {}
        literals.append(str(section.get("title", "")))
    literals.extend(str(x.get("event", "")) for x in (report.get("top_catalysts") or []) if isinstance(x, dict))
    literals.extend(str(x.get("risk", "")) for x in (report.get("top_risks") or []) if isinstance(x, dict))
    return literals


def collect_source_refs(value, refs: set[str] | None = None) -> set[str]:
    refs = refs if refs is not None else set()
    if isinstance(value, dict):
        for key, child in value.items():
            if key == "sources" and isinstance(child, list):
                for item in child:
                    if isinstance(item, str) and SOURCE_ID_RE.fullmatch(item):
                        refs.add(item)
            else:
                collect_source_refs(child, refs)
    elif isinstance(value, list):
        for child in value:
            collect_source_refs(child, refs)
    return refs


def is_morning_provisional(report: dict) -> bool:
    cycle = report.get("publication_cycle") or {}
    return (
        cycle.get("cycle") == "morning"
        and cycle.get("is_final") is False
        and report.get("edition_status") == "provisional"
    )


def validate_morning_bundle(day: str, report: dict, markdown: str, sources_doc: dict) -> list[str]:
    errors: list[str] = []
    if report.get("date") != day:
        errors.append("daily date mismatch")
    if report.get("sources_path") != f"data/sources/{day}.json":
        errors.append("sources_path mismatch")
    if sources_doc.get("date") != day:
        errors.append("sources archive date mismatch")
    order = report.get("section_order") or []
    sections = report.get("sections") or {}
    if len(order) != 15 or len(set(order)) != 15:
        errors.append("section_order must contain 15 unique keys")
    if any(key not in sections for key in order):
        errors.append("sections missing section_order key")
    if len(report.get("top_catalysts") or []) != 3:
        errors.append("top_catalysts must contain exactly 3 items")
    if len(report.get("top_risks") or []) != 3:
        errors.append("top_risks must contain exactly 3 items")
    literals = canonical_literals(report)
    expected_literal_count = 4 + 15 + 3 + 3
    if len(literals) != expected_literal_count:
        errors.append(f"canonical literal count must be {expected_literal_count}, got {len(literals)}")
    for literal in literals:
        if not literal:
            errors.append("empty canonical literal")
        elif literal not in markdown:
            errors.append(f"Markdown canonical literal missing: {literal[:100]}")
    source_ids = {
        str(item.get("id"))
        for item in (sources_doc.get("sources") or [])
        if isinstance(item, dict) and item.get("id")
    }
    unresolved = sorted(collect_source_refs(report) - source_ids)
    if unresolved:
        errors.append(f"unresolved source IDs: {', '.join(unresolved)}")
    return errors


def open_close_pr_dates() -> set[str]:
    repo = os.environ.get("GITHUB_REPOSITORY") or "patshin/global-market-daily"
    token = os.environ.get("GITHUB_TOKEN", "")
    url = f"https://api.github.com/repos/{repo}/pulls?state=open&per_page=100"
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "GlobalMarketDaily-Fallback/1.0",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        with urlopen(Request(url, headers=headers), timeout=30) as response:
            pulls = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        raise RuntimeError(f"Cannot prove absence of a valid Close PR: {exc}") from exc
    out: set[str] = set()
    for pr in pulls:
        title = str(pr.get("title", ""))
        match = re.fullmatch(r"GMD Publish (\d{4}-\d{2}-\d{2}) Close", title)
        head_ref = str((pr.get("head") or {}).get("ref", ""))
        if match and head_ref == f"publish/gmd-{match.group(1)}-close":
            out.add(match.group(1))
    return out


def protected_snapshot(report: dict) -> str:
    keys = [
        "data_cutoff_sgt",
        "data_cutoff_et",
        "thesis",
        "dominant_narrative",
        "market_regime",
        "market_tape",
        "market_tape_data_quality",
        "what_changed",
        "top_catalysts",
        "section_order",
        "sections",
        "signal_panel",
        "scenario_matrix",
        "upcoming_market_watch",
        "top_risks",
        "next_catalyst",
        "sources",
        "sources_path",
    ]
    return json.dumps({key: report.get(key) for key in keys}, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def promote_markdown(day: str, markdown: str) -> str:
    lines = markdown.splitlines()
    if not lines:
        raise ValueError(f"Empty Markdown for {day}")
    lines[0] = f"# Global Market Daily — Morning Fallback Final — {day}"
    cycle_index = None
    for index, line in enumerate(lines):
        if line.startswith("- Publication Cycle:"):
            lines[index] = "- Publication Cycle: close / official"
            cycle_index = index
            break
    if cycle_index is None:
        insert_at = 1
        while insert_at < len(lines) and (not lines[insert_at].strip() or lines[insert_at].startswith("- Data Cutoff")):
            insert_at += 1
        lines.insert(insert_at, "- Publication Cycle: close / official")
        cycle_index = insert_at
    if FALLBACK_NOTICE not in lines:
        lines.insert(cycle_index + 1, "")
        lines.insert(cycle_index + 2, FALLBACK_NOTICE)
    return "\n".join(lines).rstrip() + "\n"


def archive_entry(report: dict) -> dict:
    day = report["date"]
    y, m, _ = day.split("-")
    overall = ((report.get("market_regime") or {}).get("overall") or {}).get("state", "")
    return {
        "date": day,
        "thesis": report.get("thesis", ""),
        "overall_regime": overall,
        "dominant_narrative": report.get("dominant_narrative", ""),
        "report_path": f"reports/{y}/{m}/{day}.md",
        "daily_json_path": f"data/daily/{day}.json",
        "sources_path": f"data/sources/{day}.json",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Promote eligible missing-Evening Morning snapshots without changing factual content.")
    parser.add_argument("--through-date", help="Last SGT calendar date eligible for fallback promotion (YYYY-MM-DD).")
    parser.add_argument("--strict", action="store_true", help="Fail if an otherwise eligible Morning bundle is incomplete.")
    args = parser.parse_args()

    through = date.fromisoformat(args.through_date) if args.through_date else datetime.now(SGT).date() - timedelta(days=1)
    promoted_at = datetime.now(SGT).replace(microsecond=0).isoformat()
    open_close = open_close_pr_dates()
    archive = load_json(ARCHIVE_PATH)
    entries = archive.get("entries") or []
    archive_dates = {str(entry.get("date")) for entry in entries if isinstance(entry, dict)}
    promoted: list[str] = []
    skipped_incomplete: list[tuple[str, list[str]]] = []

    for path in sorted(DAILY_DIR.glob("*.json")):
        day = path.stem
        try:
            day_date = date.fromisoformat(day)
        except ValueError:
            continue
        if day_date > through or day in archive_dates:
            continue
        report = load_json(path)
        if not is_morning_provisional(report):
            continue
        if day in open_close:
            print(f"FALLBACK NOT_NEEDED {day}: valid open Close PR exists")
            continue
        md_path = report_path_for(day)
        src_path = source_path_for(report)
        errors: list[str] = []
        try:
            markdown = md_path.read_text(encoding="utf-8")
        except Exception as exc:
            markdown = ""
            errors.append(f"Markdown unavailable: {exc}")
        try:
            sources_doc = load_json(src_path)
        except Exception as exc:
            sources_doc = {}
            errors.append(f"source archive unavailable: {exc}")
        if not errors:
            errors.extend(validate_morning_bundle(day, report, markdown, sources_doc))
        if errors:
            skipped_incomplete.append((day, errors))
            print(f"FALLBACK SKIPPED_WITH_REASON {day}: {'; '.join(errors)}")
            continue

        before = protected_snapshot(report)
        report["edition"] = "Morning Fallback Final"
        report["edition_status"] = "official"
        cycle = report.setdefault("publication_cycle", {})
        cycle.update(
            {
                "status": "official",
                "cycle": "close",
                "is_final": True,
                "archive_eligible": True,
                "market_lens_native_eligible": True,
            }
        )
        report["is_morning_fallback"] = True
        report["fallback_reason"] = "evening_missing"
        report["source_cycle"] = "morning"
        report["original_data_cutoff_sgt"] = report.get("data_cutoff_sgt")
        report["original_data_cutoff_et"] = report.get("data_cutoff_et")
        report["fallback_promoted_at_sgt"] = promoted_at
        if protected_snapshot(report) != before:
            raise RuntimeError(f"Protected factual content changed while promoting {day}")

        promoted_md = promote_markdown(day, markdown)
        post_errors = validate_morning_bundle(day, report, promoted_md, sources_doc)
        if post_errors:
            raise RuntimeError(f"Post-promotion canonical parity failed for {day}: {'; '.join(post_errors)}")
        path.write_text(json.dumps(report, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        md_path.write_text(promoted_md, encoding="utf-8")
        promoted.append(day)
        print(f"FALLBACK APPLIED {day} source_cycle=morning cutoff={report['data_cutoff_sgt']}")

    if promoted:
        by_date = {
            str(entry.get("date")): entry
            for entry in entries
            if isinstance(entry, dict) and entry.get("date")
        }
        for day in promoted:
            by_date[day] = archive_entry(load_json(DAILY_DIR / f"{day}.json"))
        archive["entries"] = [by_date[d] for d in sorted(by_date, reverse=True)]
        archive["updated_at"] = promoted_at
        if len(archive["entries"]) != len({entry["date"] for entry in archive["entries"]}):
            raise RuntimeError("Archive duplicate date introduced")
        ARCHIVE_PATH.write_text(json.dumps(archive, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    print(json.dumps({"through_date": through.isoformat(), "promoted": promoted, "skipped_incomplete": [d for d, _ in skipped_incomplete]}, ensure_ascii=False))
    if args.strict and skipped_incomplete:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
