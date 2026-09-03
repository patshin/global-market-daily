#!/usr/bin/env python3
"""Generate and publish one Global Market Daily edition through the OpenAI Responses API.

The script fails closed: no canonical publication file is changed until research,
structured-output validation, source reconciliation and deterministic rendering
have completed successfully. The 18:00 SGT edition is the official archive.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import re
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

import jsonschema

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
DAILY_DIR = DOCS / "data" / "daily"
SOURCES_DIR = DOCS / "data" / "sources"
REPORTS_DIR = DOCS / "reports"
INTRADAY_DATA_DIR = DOCS / "data" / "intraday"
INTRADAY_SOURCES_DIR = SOURCES_DIR / "intraday"
INTRADAY_REPORTS_DIR = REPORTS_DIR / "intraday"
AUTOMATION_DIR = DOCS / "data" / "automation"
SCHEMA_PATH = ROOT / "schemas" / "daily.schema.json"
PROMPT_PATH = ROOT / "prompts" / "global-market-daily-master.md"
ARCHIVE_PATH = DOCS / "data" / "archive.json"
LATEST_PATH = DOCS / "data" / "latest.json"

SGT = ZoneInfo("Asia/Singapore")
ET = ZoneInfo("America/New_York")
SOURCE_ID = re.compile(r"^S\d{2,4}$")


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return copy.deepcopy(default)
    return json.loads(path.read_text(encoding="utf-8"))


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        handle.write(text)
        temp = Path(handle.name)
    temp.replace(path)


def atomic_write_json(path: Path, payload: Any) -> None:
    atomic_write_text(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def normalize_edition(value: str) -> str:
    edition = value.strip().lower()
    if edition not in {"morning", "eod"}:
        raise ValueError("GMD_EDITION must be morning or eod")
    return edition


def run_clock(report_date: str | None = None) -> tuple[str, datetime, datetime]:
    now_sgt = datetime.now(SGT)
    if report_date:
        datetime.strptime(report_date, "%Y-%m-%d")
        date_text = report_date
    else:
        date_text = now_sgt.date().isoformat()
    return date_text, now_sgt, now_sgt.astimezone(ET)


def previous_official_report(report_date: str) -> dict[str, Any] | None:
    archive = read_json(ARCHIVE_PATH, {"entries": []}) or {"entries": []}
    entries = sorted(archive.get("entries", []), key=lambda item: item.get("date", ""), reverse=True)
    for entry in entries:
        if entry.get("date", "") >= report_date:
            continue
        if entry.get("official_archive") is False or entry.get("report_edition") == "morning":
            continue
        path_text = entry.get("daily_json_path")
        if not path_text:
            continue
        path = DOCS / path_text
        report = read_json(path)
        if isinstance(report, dict):
            return report
    return None


def source_record_schema() -> dict[str, Any]:
    nullable_string = {"type": ["string", "null"]}
    return {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "id", "source_name", "source_title", "source_url", "published_at",
            "event_time", "retrieved_at", "tier", "used_for", "confidence",
        ],
        "properties": {
            "id": {"type": "string", "pattern": "^S[0-9]{2,4}$"},
            "source_name": {"type": "string", "minLength": 1},
            "source_title": {"type": "string", "minLength": 1},
            "source_url": nullable_string,
            "published_at": nullable_string,
            "event_time": nullable_string,
            "retrieved_at": {"type": "string", "minLength": 1},
            "tier": {"type": "string", "minLength": 1},
            "used_for": {"type": "string", "minLength": 1},
            "confidence": {"type": "string", "minLength": 1},
        },
    }


def build_envelope_schema(daily_schema: dict[str, Any]) -> dict[str, Any]:
    report_schema = copy.deepcopy(daily_schema)
    report_schema.pop("$schema", None)
    definitions = report_schema.pop("$defs", {})
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["report", "source_records"],
        "properties": {
            "report": report_schema,
            "source_records": {
                "type": "array",
                "minItems": 1,
                "items": source_record_schema(),
            },
        },
        "$defs": definitions,
    }


def api_output_text(response: dict[str, Any]) -> str:
    direct = response.get("output_text")
    if isinstance(direct, str) and direct.strip():
        return direct
    chunks: list[str] = []
    for item in response.get("output", []):
        if not isinstance(item, dict):
            continue
        for content in item.get("content", []):
            if isinstance(content, dict) and content.get("type") == "output_text":
                text = content.get("text")
                if isinstance(text, str):
                    chunks.append(text)
    if not chunks:
        raise RuntimeError("OpenAI response did not contain output_text")
    return "".join(chunks)


def call_openai(
    *,
    api_key: str,
    base_url: str,
    model: str,
    reasoning_effort: str,
    system_prompt: str,
    run_prompt: str,
    schema: dict[str, Any],
) -> tuple[dict[str, Any], str]:
    endpoint = base_url.rstrip("/") + "/responses"

    def request_with_effort(effort: str) -> dict[str, Any]:
        payload = {
            "model": model,
            "store": False,
            "reasoning": {"effort": effort},
            "tools": [{"type": "web_search"}],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "global_market_daily_envelope",
                    "strict": True,
                    "schema": schema,
                }
            },
            "input": [
                {"role": "system", "content": [{"type": "input_text", "text": system_prompt}]},
                {"role": "user", "content": [{"type": "input_text", "text": run_prompt}]},
            ],
        }
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = Request(
            endpoint,
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "User-Agent": "global-market-daily/2.1",
            },
        )
        try:
            with urlopen(req, timeout=900) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"OpenAI API HTTP {exc.code}: {detail[:4000]}") from exc
        except URLError as exc:
            raise RuntimeError(f"OpenAI API connection failed: {exc}") from exc

    try:
        response = request_with_effort(reasoning_effort)
        used_effort = reasoning_effort
    except RuntimeError as first_error:
        if reasoning_effort != "xhigh":
            raise
        print(f"xhigh reasoning was rejected; retrying with high: {first_error}", file=sys.stderr)
        response = request_with_effort("high")
        used_effort = "high"

    envelope = json.loads(api_output_text(response))
    return envelope, used_effort


def collect_source_ids(value: Any, *, key: str | None = None) -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        for child_key, child in value.items():
            found.update(collect_source_ids(child, key=child_key))
    elif isinstance(value, list):
        for child in value:
            if key == "sources" and isinstance(child, str) and SOURCE_ID.fullmatch(child):
                found.add(child)
            found.update(collect_source_ids(child, key=key))
    return found


def validate_source_reconciliation(report: dict[str, Any], records: list[dict[str, Any]]) -> list[str]:
    ids = [record.get("id") for record in records]
    if len(ids) != len(set(ids)):
        raise ValueError("source_records contains duplicate IDs")
    known = {source_id for source_id in ids if isinstance(source_id, str)}
    used = collect_source_ids(report)
    missing = sorted(used - known)
    if missing:
        raise ValueError(f"Report references missing source IDs: {missing}")
    return sorted(known)


def markdown_table(headers: Iterable[Any], rows: Iterable[Iterable[Any]]) -> str:
    header_values = [str(value) for value in headers]
    if not header_values:
        return ""
    lines = [
        "| " + " | ".join(header_values) + " |",
        "| " + " | ".join("---" for _ in header_values) + " |",
    ]
    for row in rows:
        values = [str(value if value is not None else "") for value in row]
        if len(values) < len(header_values):
            values.extend([""] * (len(header_values) - len(values)))
        lines.append("| " + " | ".join(value.replace("|", "\\|") for value in values[:len(header_values)]) + " |")
    return "\n".join(lines)


def definition_lines(item: dict[str, Any], fields: list[tuple[str, str]]) -> list[str]:
    lines: list[str] = []
    for key, label in fields:
        value = item.get(key)
        if value in (None, "", [], {}):
            continue
        if isinstance(value, list):
            value = "；".join(str(part) for part in value)
        lines.append(f"- **{label}：** {value}")
    return lines


def render_earnings(section: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    reported = section.get("reported", [])
    upcoming = section.get("upcoming_72h", [])
    if reported:
        lines.append("### 已公布财报")
    for item in reported:
        lines.append(f"#### {item.get('company', 'Company')}（{item.get('ticker', '—')}）")
        lines.extend(definition_lines(item, [
            ("period", "Period"), ("status", "Status"), ("release_date", "Release Date"),
            ("release_time_et", "ET"), ("release_time_sgt", "SGT"),
            ("market_session", "Session"), ("key_takeaway", "Key Takeaway"),
        ]))
        metrics = item.get("metrics", [])
        if metrics:
            lines.append(markdown_table(
                ["Metric", "Actual", "Consensus", "Previous / YoY", "Surprise", "Notes"],
                [[m.get("metric"), m.get("actual"), m.get("consensus"), m.get("previous_or_yoy"), m.get("surprise"), m.get("notes")] for m in metrics],
            ))
        for label, key in [("Guidance", "guidance"), ("One-offs", "one_offs"), ("Read-through", "read_through")]:
            values = item.get(key, [])
            if values:
                lines.append(f"**{label}**")
                lines.extend(f"- {value}" for value in values)
        reaction = item.get("market_reaction")
        if isinstance(reaction, dict):
            lines.extend(definition_lines(reaction, [("session", "Reaction Session"), ("move", "Move"), ("as_of", "As Of")]))

    if upcoming:
        lines.append("### Upcoming 72H Earnings")
    for item in upcoming:
        lines.append(f"#### {item.get('company', 'Company')}（{item.get('ticker', '—')}）")
        lines.extend(definition_lines(item, [
            ("period", "Period"), ("status", "Status"), ("date", "Date"),
            ("et", "ET"), ("sgt", "SGT"), ("market_session", "Session"),
            ("previous_guidance", "Previous Guidance"), ("actual", "Actual"),
        ]))
        consensus = item.get("consensus")
        if isinstance(consensus, dict):
            lines.extend(definition_lines(consensus, [("revenue", "Revenue Consensus"), ("eps", "EPS Consensus")]))
        values = item.get("what_matters", [])
        if values:
            lines.append("**What Matters**")
            lines.extend(f"- {value}" for value in values)
    return lines


def render_section(section_key: str, section: dict[str, Any]) -> list[str]:
    number = section.get("number", "")
    title = section.get("title", section_key)
    lines = [f"## {number}. {title}", f"**Status：** {section.get('status', '—')}", "", section.get("summary", "")]
    for paragraph in section.get("paragraphs", []):
        lines.extend(["", str(paragraph)])

    if section_key == "earnings":
        lines.extend(["", *render_earnings(section)])

    for group in section.get("event_groups", []):
        lines.append(f"### {group.get('title', group.get('label', 'Events'))}")
        for item in group.get("items", []):
            lines.append(f"#### {item.get('title', 'Event')}")
            lines.extend(definition_lines(item, [
                ("category", "Category"), ("status", "Status"), ("importance", "Importance"),
                ("actual", "Actual"), ("time", "Time"), ("summary", "Summary"),
                ("why_it_matters", "Why It Matters"), ("transmission", "Transmission"),
            ]))

    for table in section.get("tables", []):
        lines.extend(["", f"### {table.get('title', 'Data')}", markdown_table(table.get("headers", []), table.get("rows", []))])
    return lines


def render_markdown(report: dict[str, Any], source_records: list[dict[str, Any]]) -> str:
    edition_label = "Morning / Provisional" if report.get("report_edition") == "morning" else "EOD / Official Archive"
    lines = [
        f"# Global Market Daily — {report.get('date', '')}",
        "",
        f"**Edition：** {edition_label}",
        f"**Data Cutoff / 数据截止时间：** {report.get('data_cutoff_sgt', '')}",
        f"**Equivalent ET：** {report.get('data_cutoff_et', '')}",
        "",
        "## 今日一句话投资结论",
        report.get("thesis", ""),
        "",
        "## Dominant Market Narrative",
        report.get("dominant_narrative", ""),
        "",
        "## Current Market Regime",
    ]

    regime = report.get("market_regime", {})
    regime_rows = []
    for key, item in regime.items():
        if isinstance(item, dict):
            regime_rows.append([key, item.get("state", ""), item.get("evidence", "")])
        else:
            regime_rows.append([key, item, ""])
    lines.append(markdown_table(["Dimension", "State", "Evidence"], regime_rows))

    lines.extend(["", "## Cross-Asset Tape"])
    tape = report.get("market_tape", [])
    if tape:
        headers = ["Asset", "Level", "1D", "5D", "Signal", "Driver", "As Of"]
        rows = [[item.get("asset"), item.get("level"), item.get("change_1d"), item.get("change_5d"), item.get("signal"), item.get("driver"), item.get("as_of")] for item in tape]
        lines.append(markdown_table(headers, rows))

    lines.extend(["", "## What Changed Since Yesterday"])
    for item in report.get("what_changed", []):
        if isinstance(item, dict):
            label = item.get("label") or item.get("metric") or item.get("topic") or "Change"
            lines.append(f"- **{label}：** {item.get('yesterday', '')} → {item.get('today', '')}。{item.get('why_it_matters', item.get('why', ''))}")
        else:
            lines.append(f"- {item}")

    lines.extend(["", "## Top 3 Market Catalysts"])
    for item in report.get("top_catalysts", []):
        lines.append(f"### {item.get('rank', '')}. {item.get('event', '')}")
        lines.extend(definition_lines(item, [
            ("status", "Status"), ("importance", "Importance"), ("direction", "Direction"),
            ("event_time_et", "ET"), ("event_time_sgt", "SGT"),
            ("what_happened", "What Happened"), ("what_changed", "What Changed"),
            ("why_it_matters", "Why It Matters"), ("transmission", "Transmission"),
            ("affected_assets", "Affected Assets"), ("confirmation", "Confirmation"),
            ("invalidation", "Invalidation"),
        ]))

    sections = report.get("sections", {})
    for key in report.get("section_order", []):
        section = sections.get(key)
        if isinstance(section, dict):
            lines.extend(["", *render_section(key, section)])

    lines.extend(["", "# Market Signal Panel"])
    for item in report.get("signal_panel", {}).values():
        if isinstance(item, dict):
            lines.append(f"- **{item.get('label', '')}：** {item.get('current', '')}（昨日 {item.get('yesterday', '')}）— {item.get('change_reason', '')}；证据：{item.get('evidence', '')}")

    lines.extend(["", "# 24–72H Scenario Matrix"])
    for key, item in report.get("scenario_matrix", {}).items():
        if isinstance(item, dict):
            lines.append(f"## {item.get('label', key.replace('_', ' ').title())}")
            lines.extend(definition_lines(item, [
                ("probability", "Probability"), ("trigger", "Trigger"),
                ("expected_market_reaction", "Expected Market Reaction"),
                ("assets_most_sensitive", "Assets Most Sensitive"),
                ("what_confirms_it", "Confirmation"), ("what_invalidates_it", "Invalidation"),
            ]))

    lines.extend(["", "# Upcoming Market Watch"])
    watch = report.get("upcoming_market_watch", [])
    if watch:
        lines.append(markdown_table(
            ["SGT", "ET", "Event", "Consensus", "Previous", "Actual", "Importance"],
            [[item.get("sgt"), item.get("et"), item.get("event"), item.get("consensus"), item.get("previous"), item.get("actual"), item.get("importance")] for item in watch],
        ))

    lines.extend(["", "# 今日三大风险"])
    for item in report.get("top_risks", []):
        lines.append(f"## {item.get('risk', '')}")
        lines.extend(definition_lines(item, [
            ("why_not_fully_priced", "Why It Matters"), ("trigger", "Trigger"),
            ("first_asset", "First Asset"), ("transmission", "Transmission"),
        ]))

    next_item = report.get("next_catalyst", {})
    lines.extend(["", "# 下一关键催化剂", f"## {next_item.get('event', '')}"])
    lines.extend(definition_lines(next_item, [
        ("status", "Status"), ("date", "Date"), ("et", "ET"), ("sgt", "SGT"),
        ("consensus", "Consensus"), ("previous", "Previous"), ("actual", "Actual"),
        ("why_it_matters", "Why It Matters"), ("first_market", "First Market"),
        ("bull_interpretation", "Bull Interpretation"), ("bear_interpretation", "Bear Interpretation"),
        ("watch_first", "What I Would Watch First"),
    ]))

    lines.extend(["", "# Sources"])
    for record in source_records:
        url = record.get("source_url") or "URL unavailable"
        lines.append(f"- **{record.get('id')} · {record.get('source_name')}：** {record.get('source_title')} — {url}")
    return "\n".join(str(line) for line in lines).strip() + "\n"


def publication_paths(report_date: str, edition: str) -> dict[str, Path]:
    year, month, _ = report_date.split("-")
    clock = "0900" if edition == "morning" else "1800"
    return {
        "daily": DAILY_DIR / f"{report_date}.json",
        "sources": SOURCES_DIR / f"{report_date}.json",
        "report": REPORTS_DIR / year / month / f"{report_date}.md",
        "snapshot_daily": INTRADAY_DATA_DIR / f"{report_date}-{clock}.json",
        "snapshot_sources": INTRADAY_SOURCES_DIR / f"{report_date}-{clock}.json",
        "snapshot_report": INTRADAY_REPORTS_DIR / year / month / f"{report_date}-{clock}.md",
    }


def archive_entry(report: dict[str, Any]) -> dict[str, Any]:
    date_text = report["date"]
    year, month, _ = date_text.split("-")
    return {
        "date": date_text,
        "thesis": report.get("thesis", ""),
        "overall_regime": (
            report.get("market_regime", {}).get("overall", {}).get("state")
            if isinstance(report.get("market_regime", {}).get("overall"), dict)
            else report.get("market_regime", {}).get("overall", "")
        ),
        "dominant_narrative": report.get("dominant_narrative", ""),
        "report_path": f"reports/{year}/{month}/{date_text}.md",
        "daily_json_path": f"data/daily/{date_text}.json",
        "sources_path": f"data/sources/{date_text}.json",
        "report_edition": report.get("report_edition"),
        "official_archive": report.get("official_archive", False),
        "updated_at": report.get("generated_at_sgt"),
    }


def latest_payload(report: dict[str, Any]) -> dict[str, Any]:
    entry = archive_entry(report)
    return {
        "schema_version": "1.1.0",
        "date": report["date"],
        "thesis": report.get("thesis", ""),
        "regime": entry["overall_regime"],
        "dominant_narrative": report.get("dominant_narrative", ""),
        "top_catalysts": [
            {key: item.get(key) for key in ("rank", "event", "direction", "importance", "theme_id", "category")}
            for item in report.get("top_catalysts", [])
        ],
        "top_risks": [
            {key: item.get(key) for key in ("risk", "first_asset", "theme_id", "category", "continuity")}
            for item in report.get("top_risks", [])
        ],
        "next_catalyst": report.get("next_catalyst", {}),
        "daily_json_path": entry["daily_json_path"],
        "report_path": entry["report_path"],
        "sources_path": entry["sources_path"],
        "report_edition": report.get("report_edition"),
        "official_archive": report.get("official_archive", False),
        "updated_at": report.get("generated_at_sgt"),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--edition", default=os.getenv("GMD_EDITION", ""))
    parser.add_argument("--report-date", default=os.getenv("GMD_REPORT_DATE"))
    args = parser.parse_args()

    edition = normalize_edition(args.edition)
    report_date, now_sgt, now_et = run_clock(args.report_date)
    paths = publication_paths(report_date, edition)

    existing = read_json(paths["daily"])
    if edition == "morning" and isinstance(existing, dict) and existing.get("official_archive") is True:
        print(f"{report_date} already has an official EOD archive; morning rerun will not downgrade it.")
        return 0

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    model = os.getenv("GMD_MODEL", "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY repository secret is not configured")
    if not model:
        raise RuntimeError("GMD_OPENAI_MODEL repository variable is not configured")
    effort = os.getenv("GMD_REASONING_EFFORT", "xhigh").strip() or "xhigh"
    base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")

    daily_schema = read_json(SCHEMA_PATH)
    if not isinstance(daily_schema, dict):
        raise RuntimeError("Daily JSON Schema is missing or invalid")
    envelope_schema = build_envelope_schema(daily_schema)
    system_prompt = PROMPT_PATH.read_text(encoding="utf-8")
    previous = previous_official_report(report_date)
    previous_context = json.dumps(previous, ensure_ascii=False) if previous else "null"
    run_prompt = f"""
REPORT_DATE_SGT: {report_date}
DATA_CUTOFF_SGT: {now_sgt.strftime('%Y-%m-%d %H:%M %Z')}
DATA_CUTOFF_ET: {now_et.strftime('%Y-%m-%d %H:%M %Z')}
REPORT_EDITION: {edition}

Previous official EOD report for comparison only:
{previous_context}

Perform a fresh web-researched run now. Return only the structured JSON envelope required by the schema.
""".strip()

    envelope, used_effort = call_openai(
        api_key=api_key,
        base_url=base_url,
        model=model,
        reasoning_effort=effort,
        system_prompt=system_prompt,
        run_prompt=run_prompt,
        schema=envelope_schema,
    )
    report = envelope.get("report")
    records = envelope.get("source_records")
    if not isinstance(report, dict) or not isinstance(records, list):
        raise ValueError("Structured output must contain report and source_records")

    jsonschema.Draft202012Validator(daily_schema).validate(report)
    source_ids = validate_source_reconciliation(report, records)

    official = edition == "eod"
    generated_at = now_sgt.isoformat(timespec="seconds")
    report["date"] = report_date
    report["data_cutoff_sgt"] = now_sgt.strftime("%Y-%m-%d %H:%M %Z")
    report["data_cutoff_et"] = now_et.strftime("%Y-%m-%d %H:%M %Z")
    report["report_edition"] = edition
    report["official_archive"] = official
    report["generated_at_sgt"] = generated_at
    report["generation_model"] = model
    report["reasoning_effort"] = used_effort
    report["sources"] = source_ids
    report["sources_path"] = f"data/sources/{report_date}.json"

    source_document = {
        "schema_version": "1.1.0",
        "date": report_date,
        "report_edition": edition,
        "official_archive": official,
        "generated_at_sgt": generated_at,
        "sources": records,
    }
    markdown = render_markdown(report, records)

    archive = read_json(ARCHIVE_PATH, {"schema_version": "1.1.0", "entries": []}) or {"entries": []}
    entries = [entry for entry in archive.get("entries", []) if entry.get("date") != report_date]
    entries.append(archive_entry(report))
    entries.sort(key=lambda item: item.get("date", ""), reverse=True)
    archive["schema_version"] = "1.1.0"
    archive["updated_at"] = generated_at
    archive["entries"] = entries

    # Immutable execution snapshots are written first.
    atomic_write_json(paths["snapshot_daily"], report)
    atomic_write_json(paths["snapshot_sources"], source_document)
    atomic_write_text(paths["snapshot_report"], markdown)

    # Canonical publication sequence: daily, report, sources, archive, latest last.
    atomic_write_json(paths["daily"], report)
    atomic_write_text(paths["report"], markdown)
    atomic_write_json(paths["sources"], source_document)
    atomic_write_json(ARCHIVE_PATH, archive)
    atomic_write_json(LATEST_PATH, latest_payload(report))

    status = {
        "last_successful_run": generated_at,
        "report_date": report_date,
        "edition": edition,
        "official_archive": official,
        "model": model,
        "reasoning_effort": used_effort,
    }
    atomic_write_json(AUTOMATION_DIR / "last-success.json", status)
    print(json.dumps(status, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"GMD GENERATION FAILED: {exc}", file=sys.stderr)
        raise
