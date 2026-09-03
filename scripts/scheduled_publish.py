#!/usr/bin/env python3
"""Generate and publish a scheduled Global Market Daily edition.

The research call is intentionally external to GitHub Actions: a callable model
API credential is required. Morning output is provisional; the evening output
becomes the official daily archive for the date.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
SGT = ZoneInfo("Asia/Singapore")
API_URL = os.environ.get("OPENAI_API_URL", "https://api.openai.com/v1/responses")


def read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default


def extract_output_text(response: dict[str, Any]) -> str:
    if isinstance(response.get("output_text"), str):
        return response["output_text"]
    chunks: list[str] = []
    for item in response.get("output", []):
        if not isinstance(item, dict):
            continue
        for content in item.get("content", []):
            if not isinstance(content, dict):
                continue
            text = content.get("text")
            if isinstance(text, str):
                chunks.append(text)
    if not chunks:
        raise RuntimeError("Model response did not contain output text")
    return "\n".join(chunks)


def call_research_model(prompt: str) -> dict[str, Any]:
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    model = os.environ.get("GMD_MODEL", "").strip()
    effort = os.environ.get("GMD_REASONING_EFFORT", "xhigh").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured in repository secrets")
    if not model:
        raise RuntimeError("GMD_MODEL is not configured as a repository variable")

    payload: dict[str, Any] = {
        "model": model,
        "input": prompt,
        "tools": [{"type": "web_search"}],
        "reasoning": {"effort": effort},
    }
    request = urllib.request.Request(
        API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=900) as response:
            raw = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Research API failed: HTTP {exc.code}: {detail[:1000]}") from exc
    return json.loads(extract_output_text(raw))


def previous_official_daily(current_date: str) -> dict[str, Any]:
    archive = read_json(DOCS / "data/archive.json", {"entries": []})
    entries = archive.get("entries", []) if isinstance(archive, dict) else []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        entry_date = str(entry.get("date", ""))
        status = str(entry.get("archive_status", "official"))
        if not entry_date or entry_date >= current_date or status != "official":
            continue
        path = entry.get("daily_json_path")
        if path and (DOCS / path).exists():
            daily = read_json(DOCS / path, {})
            if daily.get("official_daily_archive", True):
                return daily
    return {}


def validate_bundle(bundle: dict[str, Any], date: str, edition: str) -> tuple[dict[str, Any], str, list[dict[str, Any]]]:
    daily = bundle.get("daily")
    markdown = bundle.get("markdown")
    sources = bundle.get("sources")
    if not isinstance(daily, dict):
        raise ValueError("bundle.daily must be an object")
    if not isinstance(markdown, str) or len(markdown.strip()) < 2000:
        raise ValueError("bundle.markdown is missing or too short")
    if not isinstance(sources, list) or not sources:
        raise ValueError("bundle.sources must be a non-empty array")
    if daily.get("date") != date:
        raise ValueError(f"daily.date must equal scheduled SGT date {date}")
    if len(daily.get("top_catalysts", [])) != 3:
        raise ValueError("daily.top_catalysts must contain exactly three items")
    order = daily.get("section_order", [])
    sections = daily.get("sections", {})
    if not isinstance(order, list) or len(order) != 15:
        raise ValueError("daily.section_order must contain 15 sections")
    if not isinstance(sections, dict) or any(key not in sections for key in order):
        raise ValueError("daily.sections does not match section_order")
    daily["edition"] = edition
    daily["archive_status"] = "official" if edition == "evening" else "provisional"
    daily["official_daily_archive"] = edition == "evening"
    return daily, markdown.strip() + "\n", sources


def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(text, encoding="utf-8")
    temp.replace(path)


def upsert_archive(daily: dict[str, Any], date: str, paths: dict[str, str], edition: str) -> None:
    path = DOCS / "data/archive.json"
    archive = read_json(path, {"schema_version": "1.0.0", "entries": []})
    entries = [x for x in archive.setdefault("entries", []) if isinstance(x, dict) and x.get("date") != date]
    entry = {
        "date": date,
        "edition": edition,
        "archive_status": "official" if edition == "evening" else "provisional",
        "thesis": daily.get("thesis", ""),
        "overall_regime": daily.get("market_regime", {}).get("overall", daily.get("regime", "")),
        "dominant_narrative": daily.get("dominant_narrative", ""),
        **paths,
    }
    archive["entries"] = [entry, *entries]
    archive["updated_at"] = daily.get("updated_at") or datetime.now(SGT).isoformat(timespec="seconds")
    atomic_write(path, json.dumps(archive, ensure_ascii=False, indent=2) + "\n")


def write_publication(bundle: dict[str, Any], date: str, edition: str) -> None:
    daily, markdown, sources = validate_bundle(bundle, date, edition)
    year, month, _ = date.split("-")
    paths = {
        "daily_json_path": f"data/daily/{date}.json",
        "report_path": f"reports/{year}/{month}/{date}.md",
        "sources_path": f"data/sources/{date}.json",
    }

    # Publish all dated assets first. latest.json remains the final write.
    atomic_write(DOCS / paths["daily_json_path"], json.dumps(daily, ensure_ascii=False, indent=2) + "\n")
    atomic_write(DOCS / paths["report_path"], markdown)
    atomic_write(
        DOCS / paths["sources_path"],
        json.dumps({"date": date, "edition": edition, "sources": sources}, ensure_ascii=False, indent=2) + "\n",
    )
    upsert_archive(daily, date, paths, edition)

    latest = {
        "schema_version": "1.1.0",
        "date": date,
        "edition": edition,
        "archive_status": "official" if edition == "evening" else "provisional",
        "thesis": daily.get("thesis", ""),
        "regime": daily.get("market_regime", {}).get("overall", daily.get("regime", "")),
        "dominant_narrative": daily.get("dominant_narrative", ""),
        "top_catalysts": daily.get("top_catalysts", [])[:3],
        "top_risks": daily.get("top_risks", [])[:3],
        "next_catalyst": daily.get("next_catalyst", {}),
        **paths,
        "updated_at": datetime.now(SGT).isoformat(timespec="seconds"),
    }
    atomic_write(DOCS / "data/latest.json", json.dumps(latest, ensure_ascii=False, indent=2) + "\n")


def build_prompt(date: str, edition: str) -> str:
    specification = (ROOT / "prompts/global-market-daily.md").read_text(encoding="utf-8")
    previous = previous_official_daily(date)
    cutoff = "09:00" if edition == "morning" else "18:00"
    return f"""{specification}

RUN CONTEXT
- Scheduled SGT date: {date}
- Edition: {edition}
- Target data cutoff: {date} {cutoff} Asia/Singapore
- The evening edition is the official daily archive. The morning edition is provisional and must still independently re-research every current fact.
- Previous official daily JSON is supplied only for What Changed Since Yesterday; re-verify all current facts.

PREVIOUS OFFICIAL DAILY JSON
{json.dumps(previous, ensure_ascii=False)}

Return exactly one valid JSON object with keys: daily, markdown, sources. Do not wrap it in Markdown fences.
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--edition", choices=("morning", "evening"), required=True)
    parser.add_argument("--date", help="YYYY-MM-DD in Asia/Singapore; default is now")
    parser.add_argument("--fixture", help="Use a local JSON fixture instead of calling the API")
    args = parser.parse_args()

    date = args.date or datetime.now(SGT).date().isoformat()
    bundle = read_json(Path(args.fixture), {}) if args.fixture else call_research_model(build_prompt(date, args.edition))
    write_publication(bundle, date, args.edition)
    print(json.dumps({"date": date, "edition": args.edition, "status": "generated"}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
