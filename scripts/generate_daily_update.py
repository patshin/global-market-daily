#!/usr/bin/env python3
"""Generate and publish a full Global Market Daily edition via OpenAI Responses API.

The morning edition is an intraday snapshot. The close edition is the canonical
archive point and the only new native day admitted to the 30D Market Lens.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
DAILY_DIR = DOCS / "data/daily"
SOURCES_DIR = DOCS / "data/sources"
REPORTS_DIR = DOCS / "reports"
RUNS_DIR = DOCS / "data/runs"
PROMPT_PATH = ROOT / "prompts/global-market-daily-master.md"
API_URL = "https://api.openai.com/v1/responses"


def load_json(path: Path, default=None):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def output_text(response: dict) -> str:
    if isinstance(response.get("output_text"), str):
        return response["output_text"]
    parts: list[str] = []
    for item in response.get("output", []):
        if item.get("type") != "message":
            continue
        for content in item.get("content", []):
            if content.get("type") in {"output_text", "text"} and content.get("text"):
                parts.append(content["text"])
    return "\n".join(parts)


def parse_json_response(text: str) -> dict:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    value = json.loads(text)
    if not isinstance(value, dict):
        raise ValueError("API output must be a JSON object")
    return value


def previous_final_report(current_date: str) -> dict | None:
    archive = load_json(DOCS / "data/archive.json", {"entries": []})
    for entry in archive.get("entries", []):
        if entry.get("date", "") >= current_date:
            continue
        path = DOCS / entry.get("daily_json_path", "")
        report = load_json(path)
        if not isinstance(report, dict):
            continue
        cycle = report.get("publication_cycle") or {}
        if cycle.get("is_final", True):
            return report
    return None


def call_openai(api_key: str, prompt: str, model: str, effort: str) -> dict:
    payload = {
        "model": model,
        "reasoning": {"effort": effort},
        "tools": [{"type": "web_search"}],
        "tool_choice": "auto",
        "max_output_tokens": 110000,
        "input": [
            {
                "role": "user",
                "content": [{"type": "input_text", "text": prompt}],
            }
        ],
        "metadata": {"product": "global-market-daily", "pipeline": "twice-daily"},
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "User-Agent": "GlobalMarketDaily/2.1 github.com/patshin/global-market-daily",
    }
    if os.getenv("OPENAI_PROJECT_ID"):
        headers["OpenAI-Project"] = os.environ["OPENAI_PROJECT_ID"]
    if os.getenv("OPENAI_ORG_ID"):
        headers["OpenAI-Organization"] = os.environ["OPENAI_ORG_ID"]
    request = Request(API_URL, data=json.dumps(payload).encode(), headers=headers, method="POST")
    try:
        with urlopen(request, timeout=3600) as response:
            return json.loads(response.read().decode())
    except HTTPError as exc:
        body = exc.read().decode(errors="replace")
        raise RuntimeError(f"OpenAI API HTTP {exc.code}: {body[:2000]}") from exc
    except URLError as exc:
        raise RuntimeError(f"OpenAI API network error: {exc}") from exc


def ensure_report_shape(report: dict, sources: list[dict]) -> None:
    required = {
        "thesis", "dominant_narrative", "market_regime", "market_tape",
        "what_changed", "top_catalysts", "section_order", "sections",
        "signal_panel", "scenario_matrix", "upcoming_market_watch",
        "top_risks", "next_catalyst",
    }
    missing = sorted(required - set(report))
    if missing:
        raise ValueError(f"daily report missing fields: {missing}")
    if len(report.get("top_catalysts", [])) != 3:
        raise ValueError("top_catalysts must contain exactly 3 items")
    if len(report.get("top_risks", [])) != 3:
        raise ValueError("top_risks must contain exactly 3 items")
    if len(report.get("section_order", [])) != 15 or len(report.get("sections", {})) != 15:
        raise ValueError("daily report must contain exactly 15 core sections")
    ids = [item.get("id") for item in sources if isinstance(item, dict)]
    if not ids or len(ids) != len(set(ids)):
        raise ValueError("sources must contain unique source IDs")


def markdown_table(headers, rows) -> str:
    headers = [str(x) for x in headers]
    out = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    for row in rows:
        values = [str(x if x is not None else "—").replace("\n", " ").replace("|", "\\|") for x in row]
        out.append("| " + " | ".join(values) + " |")
    return "\n".join(out)


def render_markdown(report: dict, sources: list[dict]) -> str:
    lines = [
        f"# Global Market Daily — {report['date']}", "",
        f"**Edition：{report['edition']}**  ",
        f"**Data Cutoff / 数据截止时间：{report['data_cutoff_sgt']}**  ",
        f"**Equivalent ET：{report['data_cutoff_et']}**", "",
        "## 今日一句话投资结论", "", report["thesis"], "",
        "## Dominant Market Narrative", "", report["dominant_narrative"], "",
        "## Current Market Regime", "",
    ]
    regime_rows = []
    for key, item in report.get("market_regime", {}).items():
        if isinstance(item, dict):
            regime_rows.append([key, item.get("state", "—"), item.get("evidence", "—")])
        else:
            regime_rows.append([key, item, "—"])
    lines += [markdown_table(["Dimension", "State", "Evidence"], regime_rows), "", "## Cross-Asset Tape", ""]
    tape = report.get("market_tape", [])
    if tape:
        keys = ["asset", "level", "change_1d", "change_5d", "signal", "driver", "status", "as_of"]
        lines += [markdown_table(["Asset", "Level", "1D", "5D", "Signal", "Driver", "Status", "As of"], [[x.get(k, "—") for k in keys] for x in tape]), ""]
    lines += ["## What Changed Since Yesterday", ""]
    for item in report.get("what_changed", []):
        lines.append(f"- **{item.get('yesterday','—')} → {item.get('today','—')}**：{item.get('why_it_matters') or item.get('why') or '—'}")
    lines += ["", "## Top 3 Market Catalysts", ""]
    for c in report.get("top_catalysts", []):
        lines += [
            f"### {c.get('rank','')}. {c.get('event','')}", "",
            f"- **Status：** {c.get('status','—')}",
            f"- **Time：** {c.get('event_time_et','—')} / {c.get('event_time_sgt','—')}",
            f"- **What Happened：** {c.get('what_happened','—')}",
            f"- **What Changed：** {c.get('what_changed','—')}",
            f"- **Why It Matters：** {c.get('why_it_matters','—')}",
            f"- **Transmission：** {c.get('transmission','—')}",
            f"- **Affected Assets：** {'、'.join(c.get('affected_assets', []))}",
            f"- **Direction / Importance：** {c.get('direction','—')} / {c.get('importance','—')}",
            f"- **Confirmation：** {c.get('confirmation','—')}",
            f"- **Invalidation：** {c.get('invalidation','—')}", "",
        ]
    for key in report.get("section_order", []):
        section = report["sections"][key]
        lines += [f"## {section.get('number')}. {section.get('title')}", "", f"**Status：{section.get('status','—')}**", "", section.get("summary", ""), ""]
        for paragraph in section.get("paragraphs", []):
            lines += [str(paragraph), ""]
        for table in section.get("tables", []):
            lines += [f"### {table.get('title','Data')}", "", markdown_table(table.get("headers", []), table.get("rows", [])), ""]
        if key == "earnings":
            for item in section.get("reported", []):
                lines += [f"### {item.get('company')} ({item.get('ticker')}) — Reported", "", item.get("key_takeaway", ""), ""]
                metrics = item.get("metrics", [])
                if metrics:
                    lines += [markdown_table(["Metric", "Actual", "Consensus", "Previous/YoY", "Surprise", "Notes"], [[m.get("metric"), m.get("actual"), m.get("consensus"), m.get("previous_or_yoy"), m.get("surprise"), m.get("notes")] for m in metrics]), ""]
            for item in section.get("upcoming_72h", []):
                lines += [f"### {item.get('company')} ({item.get('ticker')}) — Upcoming", "", f"{item.get('date')} · {item.get('et')} / {item.get('sgt')} · Actual: {item.get('actual','待公布')}", ""]
    lines += ["## Market Signal Panel", ""]
    for item in report.get("signal_panel", {}).values():
        if isinstance(item, dict):
            lines.append(f"- **{item.get('label','Signal')}：{item.get('current','—')}**（昨日 {item.get('yesterday','—')}）— {item.get('change_reason','—')} Evidence: {item.get('evidence','—')}")
    lines += ["", "## 24–72H Scenario Matrix", ""]
    for key, item in report.get("scenario_matrix", {}).items():
        lines += [f"### {key.replace('_',' ').title()}", ""]
        if isinstance(item, dict):
            for field, value in item.items():
                lines.append(f"- **{field.replace('_',' ').title()}：** {value}")
        lines.append("")
    lines += ["## Upcoming Market Watch", ""]
    watch = report.get("upcoming_market_watch", [])
    if watch:
        keys = ["sgt", "et", "event", "consensus", "previous", "actual", "importance"]
        lines += [markdown_table(["SGT", "ET", "Event", "Consensus", "Previous", "Actual", "Importance"], [[x.get(k, "—") for k in keys] for x in watch]), ""]
    lines += ["## 今日三大风险", ""]
    for r in report.get("top_risks", []):
        lines += [f"### {r.get('risk','')}", "", f"- **Why monitor：** {r.get('why_not_fully_priced') or r.get('why_monitor') or '—'}", f"- **Trigger：** {r.get('trigger','—')}", f"- **First Asset：** {r.get('first_asset','—')}", f"- **Transmission：** {r.get('transmission','—')}", ""]
    n = report.get("next_catalyst", {})
    lines += ["## 下一关键催化剂", "", f"**{n.get('event','—')}**", ""]
    for field in ["status", "date", "et", "sgt", "consensus", "previous", "actual", "why_it_matters", "first_market", "bull_interpretation", "bear_interpretation"]:
        lines.append(f"- **{field.replace('_',' ').title()}：** {n.get(field,'—')}")
    lines += ["", "## Sources", ""]
    for source in sources:
        url = source.get("source_url")
        title = source.get("source_title") or source.get("source_name")
        label = f"[{title}]({url})" if url else title
        lines.append(f"- **{source.get('id')} · {source.get('source_name')}** — {label} · {source.get('tier')} · {source.get('confidence')}")
    return "\n".join(lines).strip() + "\n"


def update_metadata(report: dict, date_str: str, edition: str, now_sgt: datetime, sources: list[dict]) -> None:
    now_et = now_sgt.astimezone(ZoneInfo("America/New_York"))
    et_tz = now_et.tzname() or "ET"
    report["schema_version"] = report.get("schema_version", "1.0.0")
    report["date"] = date_str
    report["edition"] = "Morning Update" if edition == "morning" else "Evening Final Edition"
    report["timezone"] = "Asia/Singapore"
    report["data_cutoff_sgt"] = now_sgt.strftime("%Y-%m-%d %H:%M SGT")
    report["data_cutoff_et"] = now_et.strftime(f"%Y-%m-%d %H:%M {et_tz}")
    report["last_updated"] = now_sgt.isoformat(timespec="seconds")
    report["sources_path"] = f"data/sources/{date_str}.json"
    report["report_path"] = f"reports/{date_str[:4]}/{date_str[5:7]}/{date_str}.md"
    report["publication_cycle"] = {
        "run_type": edition,
        "scheduled_sgt": "09:00" if edition == "morning" else "18:00",
        "is_final": edition == "close",
        "canonical_daily_archive": edition == "close",
    }
    report["sources"] = [x["id"] for x in sources]
    retrieved = now_sgt.isoformat(timespec="seconds")
    for source in sources:
        source.setdefault("retrieved_at", retrieved)
        source.setdefault("published_at", "")
        source.setdefault("event_time", "")
        source.setdefault("used_for", "")
        source.setdefault("confidence", "Medium")
        if not source.get("tier"):
            source["tier"] = source.get("source_tier") or "Tier 2"
        if not source.get("source_url"):
            source["source_url"] = None


def update_archive_and_latest(report: dict, sources: list[dict], now_sgt: datetime) -> None:
    date_str = report["date"]
    archive_path = DOCS / "data/archive.json"
    archive = load_json(archive_path, {"schema_version": "1.0.0", "entries": []})
    entry = {
        "date": date_str,
        "thesis": report["thesis"],
        "overall_regime": (report.get("market_regime", {}).get("overall") or {}).get("state", "Neutral") if isinstance(report.get("market_regime", {}).get("overall"), dict) else report.get("market_regime", {}).get("overall", "Neutral"),
        "dominant_narrative": report["dominant_narrative"],
        "edition": report["edition"],
        "is_final": report["publication_cycle"]["is_final"],
        "report_path": report["report_path"],
        "daily_json_path": f"data/daily/{date_str}.json",
        "sources_path": report["sources_path"],
    }
    entries = [x for x in archive.get("entries", []) if x.get("date") != date_str]
    entries.append(entry)
    entries.sort(key=lambda x: x["date"], reverse=True)
    archive["entries"] = entries
    archive["updated_at"] = now_sgt.isoformat(timespec="seconds")
    archive_path.write_text(json.dumps(archive, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    latest = {
        "schema_version": "1.0.0", "date": date_str, "edition": report["edition"],
        "is_final": report["publication_cycle"]["is_final"], "thesis": report["thesis"],
        "regime": entry["overall_regime"], "dominant_narrative": report["dominant_narrative"],
        "top_catalysts": [{k: c.get(k) for k in ("rank", "event", "direction", "importance")} for c in report.get("top_catalysts", [])],
        "top_risks": [{"risk": r.get("risk"), "first_asset": r.get("first_asset")} for r in report.get("top_risks", [])],
        "next_catalyst": {k: report.get("next_catalyst", {}).get(k) for k in ("event", "et", "sgt")},
        "daily_json_path": entry["daily_json_path"], "report_path": entry["report_path"],
        "sources_path": entry["sources_path"], "updated_at": now_sgt.isoformat(timespec="seconds"),
    }
    # latest.json is deliberately the final filesystem write.
    (DOCS / "data/latest.json").write_text(json.dumps(latest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--edition", choices=("morning", "close"), required=True)
    parser.add_argument("--date", help="Override SGT date for controlled recovery runs")
    parser.add_argument("--now", help="ISO timestamp override for tests")
    args = parser.parse_args()

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit("OPENAI_API_KEY is required for scheduled research publication")
    model = os.getenv("OPENAI_MODEL", "gpt-5.6-sol")
    effort = os.getenv("OPENAI_REASONING_EFFORT", "xhigh")
    now_sgt = datetime.fromisoformat(args.now).astimezone(ZoneInfo("Asia/Singapore")) if args.now else datetime.now(ZoneInfo("Asia/Singapore"))
    date_str = args.date or now_sgt.date().isoformat()
    previous = previous_final_report(date_str)
    template = previous or load_json(DAILY_DIR / sorted(p.name for p in DAILY_DIR.glob("*.json"))[-1])
    master = PROMPT_PATH.read_text(encoding="utf-8")
    request_prompt = "\n\n".join([
        master,
        f"RUN CONTEXT\n- edition: {args.edition}\n- current SGT: {now_sgt.isoformat(timespec='seconds')}\n- target date: {date_str}\n- model must research all sections again.",
        "STRUCTURAL TEMPLATE (preserve its full shape, but replace all facts with current verified research):\n" + json.dumps(template, ensure_ascii=False),
        "PREVIOUS FINAL REPORT FOR WHAT-CHANGED COMPARISON ONLY:\n" + (json.dumps(previous, ensure_ascii=False) if previous else "No previous final report is available."),
    ])

    last_error = None
    for attempt in range(1, 3):
        try:
            response = call_openai(api_key, request_prompt if attempt == 1 else request_prompt + f"\n\nPrevious output failed validation: {last_error}. Return corrected JSON only.", model, effort)
            envelope = parse_json_response(output_text(response))
            report = envelope.get("daily")
            sources = envelope.get("sources")
            if not isinstance(report, dict) or not isinstance(sources, list):
                raise ValueError("output requires daily object and sources array")
            ensure_report_shape(report, sources)
            break
        except Exception as exc:
            last_error = str(exc)
            if attempt == 2:
                raise
            time.sleep(2)

    update_metadata(report, date_str, args.edition, now_sgt, sources)
    DAILY_DIR.mkdir(parents=True, exist_ok=True)
    SOURCES_DIR.mkdir(parents=True, exist_ok=True)
    report_dir = REPORTS_DIR / date_str[:4] / date_str[5:7]
    report_dir.mkdir(parents=True, exist_ok=True)
    run_dir = RUNS_DIR / date_str[:4] / date_str[5:7]
    run_dir.mkdir(parents=True, exist_ok=True)

    source_doc = {"schema_version": "1.0.0", "date": date_str, "data_cutoff_sgt": report["data_cutoff_sgt"], "data_cutoff_et": report["data_cutoff_et"], "retrieved_at": now_sgt.isoformat(timespec="seconds"), "sources": sources}
    daily_text = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    source_text = json.dumps(source_doc, ensure_ascii=False, indent=2) + "\n"
    markdown = render_markdown(report, sources)

    (DAILY_DIR / f"{date_str}.json").write_text(daily_text, encoding="utf-8")
    (SOURCES_DIR / f"{date_str}.json").write_text(source_text, encoding="utf-8")
    (report_dir / f"{date_str}.md").write_text(markdown, encoding="utf-8")
    stamp = "0900" if args.edition == "morning" else "1800"
    (run_dir / f"{date_str}-{stamp}.json").write_text(daily_text, encoding="utf-8")
    (run_dir / f"{date_str}-{stamp}-sources.json").write_text(source_text, encoding="utf-8")
    run_meta = {
        "date": date_str, "edition": args.edition, "scheduled_sgt": report["publication_cycle"]["scheduled_sgt"],
        "model": model, "reasoning_effort": effort, "response_id": response.get("id"),
        "source_count": len(sources), "generated_at": now_sgt.isoformat(timespec="seconds"),
        "usage": response.get("usage", {}),
    }
    (run_dir / f"{date_str}-{stamp}-run.json").write_text(json.dumps(run_meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    update_archive_and_latest(report, sources, now_sgt)
    print(json.dumps({"date": date_str, "edition": args.edition, "model": model, "reasoning_effort": effort, "sources": len(sources)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
