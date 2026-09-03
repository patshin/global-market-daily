#!/usr/bin/env python3
"""Fetch confirmed policy milestones for the 30D policy lane.

Only official government/regulator endpoints are used. Policy milestones are
shown with a `P` marker and never impersonate ranked Top-3 catalysts.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
LENS_PATH = ROOT / "docs/data/trends/rolling-30d.json"
OUT_PATH = ROOT / "docs/data/trends/policy-events.json"
USER_AGENT = "GlobalMarketDaily/2.1 (+https://github.com/patshin/global-market-daily)"
FEDERAL_REGISTER = "https://www.federalregister.gov/api/v1/documents.json"

TERMS = (
    "China",
    "Chinese semiconductor",
    "export controls semiconductor",
    "tariff China",
    "Section 301 China",
    "outbound investment China",
    "industrial policy semiconductor",
)

ALLOWED_AGENCY_FRAGMENTS = (
    "Commerce Department",
    "Industry and Security Bureau",
    "International Trade Administration",
    "Office of the United States Trade Representative",
    "Treasury Department",
    "Foreign Assets Control Office",
    "Executive Office of the President",
    "State Department",
    "Defense Department",
    "Energy Department",
)

SUBJECT_RE = re.compile(
    r"\b(china|chinese|semiconductor|advanced computing|artificial intelligence|"
    r"export control|tariff|section 301|outbound investment|industrial policy|"
    r"critical mineral|supply chain)\b",
    re.I,
)
ACTION_RE = re.compile(
    r"\b(rule|regulation|order|notice|determination|designation|restriction|"
    r"control|tariff|sanction|prohibition|investigation|implementation|amendment)\b",
    re.I,
)


def load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def request_json(url: str) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=45) as response:
        return json.loads(response.read().decode("utf-8"))


def agency_names(document: dict[str, Any]) -> list[str]:
    names: list[str] = []
    for agency in document.get("agencies", []):
        if not isinstance(agency, dict):
            continue
        name = agency.get("name") or agency.get("raw_name")
        if isinstance(name, str) and name.strip():
            names.append(name.strip())
    return names


def is_material(document: dict[str, Any]) -> bool:
    title = str(document.get("title") or "")
    abstract = str(document.get("abstract") or "")
    text = f"{title} {abstract}"
    agencies = agency_names(document)
    allowed_agency = any(
        fragment.lower() in agency.lower()
        for fragment in ALLOWED_AGENCY_FRAGMENTS
        for agency in agencies
    )
    return bool(allowed_agency and SUBJECT_RE.search(text) and ACTION_RE.search(text))


def importance(document: dict[str, Any]) -> int:
    text = f"{document.get('title', '')} {document.get('abstract', '')}".lower()
    high = (
        "final rule",
        "executive order",
        "section 301",
        "export administration regulations",
        "outbound investment",
        "tariff",
        "sanction",
        "semiconductor",
        "advanced computing",
    )
    return 4 if any(token in text for token in high) else 3


def transmission(document: dict[str, Any]) -> str:
    text = f"{document.get('title', '')} {document.get('abstract', '')}".lower()
    if any(token in text for token in ("semiconductor", "advanced computing", "export control")):
        return "Technology access / supply chain → AI and semiconductor capex, revenue mix and valuation"
    if any(token in text for token in ("tariff", "section 301", "trade")):
        return "Trade cost / market access → corporate margins and inflation → rates, FX and affected equities"
    if any(token in text for token in ("sanction", "ofac")):
        return "Sanctions / payment restrictions → trade and funding channels → FX, commodities and risk assets"
    if "investment" in text:
        return "Capital restrictions → cross-border financing and valuation → affected technology and industrial assets"
    return "Policy implementation → industry costs and market access → affected equities, rates and FX"


def event_from_document(document: dict[str, Any]) -> dict[str, Any]:
    number = str(document.get("document_number") or "").strip()
    url = document.get("html_url") or document.get("raw_text_url")
    title = str(document.get("title") or "Official policy document").strip()
    abstract = re.sub(r"\s+", " ", str(document.get("abstract") or "")).strip()
    agencies = agency_names(document)
    event_id = f"federal-register-{number}" if number else "policy-" + hashlib.sha1(
        f"{document.get('publication_date')}|{title}".encode("utf-8")
    ).hexdigest()[:12]
    return {
        "id": event_id,
        "date": document.get("publication_date"),
        "title": title,
        "status": "Confirmed / Released",
        "importance": importance(document),
        "theme_id": "china_trade_policy",
        "category": "china_trade_policy",
        "market_bias": "mixed",
        "evidence": abstract[:600] if abstract else "Official Federal Register publication.",
        "transmission": transmission(document),
        "confirmation": "Implementation details, effective date and subsequent official guidance",
        "invalidation": "Formal withdrawal, judicial stay or superseding official rule",
        "source_name": "Federal Register" + (f" — {', '.join(agencies[:2])}" if agencies else ""),
        "source_url": url,
        "document_number": number or None,
        "provenance": "primary_policy_source",
    }


def fetch_events(start: str, end: str) -> list[dict[str, Any]]:
    events: dict[str, dict[str, Any]] = {}
    for term in TERMS:
        params = {
            "conditions[publication_date][gte]": start,
            "conditions[publication_date][lte]": end,
            "conditions[term]": term,
            "per_page": "100",
            "order": "newest",
        }
        url = FEDERAL_REGISTER + "?" + urllib.parse.urlencode(params)
        try:
            data = request_json(url)
        except Exception as exc:
            print(f"warning: Federal Register query failed for {term!r}: {exc}")
            continue
        for document in data.get("results", []):
            if not isinstance(document, dict) or not is_material(document):
                continue
            event = event_from_document(document)
            if event.get("date") and event.get("source_url"):
                events[event["id"]] = event
    return sorted(events.values(), key=lambda item: (str(item.get("date")), -int(item.get("importance", 0))))


def resolve_window(args: argparse.Namespace) -> tuple[str, str]:
    if args.start and args.end:
        return args.start, args.end
    lens = load_json(LENS_PATH, {})
    end = args.end or lens.get("window_end") or datetime.now(timezone.utc).date().isoformat()
    start = args.start or lens.get("window_start")
    if not start:
        start = (datetime.fromisoformat(end).date() - timedelta(days=29)).isoformat()
    return str(start), str(end)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start")
    parser.add_argument("--end")
    args = parser.parse_args()
    start, end = resolve_window(args)
    previous = load_json(OUT_PATH, {})
    try:
        events = fetch_events(start, end)
        fetch_status = "success"
    except Exception as exc:
        events = previous.get("events", []) if isinstance(previous, dict) else []
        fetch_status = f"fallback: {exc}"
    payload = {
        "schema_version": "1.1.0",
        "window_start": start,
        "window_end": end,
        "source_policy": "Primary government and regulator releases only",
        "source_endpoints": [FEDERAL_REGISTER],
        "retrieved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "fetch_status": fetch_status,
        "events": events,
        "empty_state": "本窗口没有符合重大性筛选、可进入政策节点层的官方中国、贸易或产业政策文件。",
        "display_rule": "Official policy milestones use P; P is not a Top-3 rank.",
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"start": start, "end": end, "events": len(events), "status": fetch_status}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
