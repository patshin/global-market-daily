#!/usr/bin/env python3
"""Integrate the 30D/P0 layer into the existing static site without redesigning it."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"

CATEGORY_BY_THEME = {
    "geopolitics_energy": "geopolitics_energy",
    "global_duration": "inflation_rates",
    "fed_policy_path": "central_banks_fiscal",
    "ai_earnings": "earnings_ai_semis",
    "volatility_event_risk": "market_structure",
    "usd_financial_conditions": "liquidity_credit_financing",
    "equity_risk_appetite": "growth_macro",
    "market_structure": "market_structure",
}

THEME_PATTERNS = [
    (re.compile(r"Hormuz|Iran|伊朗|航运|油价|原油|中东", re.I), "geopolitics_energy"),
    (re.compile(r"Treasury|10Y|JGB|收益率|主权债|债券|期限溢价|term premium", re.I), "global_duration"),
    (re.compile(r"Fed|2Y|加息|降息|政策利率", re.I), "fed_policy_path"),
    (re.compile(r"Dell|Broadcom|NVIDIA|NVDA|AVGO|AI|Semiconductor|半导体|财报", re.I), "ai_earnings"),
    (re.compile(r"VIX|波动率|OPEX|期权", re.I), "volatility_event_risk"),
    (re.compile(r"美元|DXY|USD|流动性|融资|credit|信用", re.I), "usd_financial_conditions"),
]

EVENT_SECTION_KEYS = [
    "us_macro",
    "central_banks",
    "geopolitics",
    "regional_policy",
    "index_changes",
    "flows",
    "etf",
    "options",
    "treasury",
    "commodities",
    "financing",
    "breaking_news",
]

ASSET_HINTS = {
    "us_macro": ["UST 2Y", "UST 10Y", "DXY", "Nasdaq", "S&P 500"],
    "central_banks": ["Rates", "FX", "Equities"],
    "geopolitics": ["Oil", "Rates", "FX", "Equities"],
    "regional_policy": ["Regional FX", "Rates", "Equities"],
    "index_changes": ["Index constituents", "Passive flows"],
    "flows": ["Index futures", "Equities", "Rates"],
    "etf": ["ETF", "Underlying constituents"],
    "options": ["VIX", "Index futures", "Equities"],
    "treasury": ["UST", "USD", "Equities"],
    "commodities": ["Commodities", "Inflation", "Rates", "Risk assets"],
    "financing": ["Credit", "UST", "AI infrastructure", "Equities"],
    "breaking_news": ["Cross-asset"],
}


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def theme_for(text: str) -> str:
    for pattern, theme in THEME_PATTERNS:
        if pattern.search(text):
            return theme
    return "market_structure"


def stable_id(date_value: str, section_key: str, group_index: int, item_index: int, title: str) -> str:
    digest = hashlib.sha1(f"{date_value}|{section_key}|{group_index}|{item_index}|{title}".encode()).hexdigest()[:10]
    return f"{date_value}-{section_key}-{digest}"


def status_from_row(headers: list[str], row: list[Any], fallback: str) -> str:
    lookup = {str(header).lower(): str(row[index]) for index, header in enumerate(headers) if index < len(row)}
    actual = next((value for key, value in lookup.items() if "actual" in key), "")
    status = next((value for key, value in lookup.items() if "status" in key), "")
    if actual == "待公布":
        return "Confirmed Upcoming"
    if status:
        return status
    return fallback


def actual_from_row(headers: list[str], row: list[Any]) -> str | None:
    for index, header in enumerate(headers):
        if "actual" in str(header).lower() and index < len(row):
            return str(row[index])
    return None


def time_from_row(headers: list[str], row: list[Any]) -> dict[str, str]:
    result = {}
    for index, header in enumerate(headers):
        lower = str(header).lower()
        if index >= len(row):
            continue
        if lower in {"date", "actual event time", "announcement date"} or "time" in lower:
            result[str(header)] = str(row[index])
        elif lower in {"et", "sgt", "effective date", "implementation date"}:
            result[str(header)] = str(row[index])
    return result


def row_to_event(report_date: str, section_key: str, section: dict[str, Any], table: dict[str, Any], group_index: int, item_index: int, row: list[Any]) -> dict[str, Any]:
    headers = [str(value) for value in table.get("headers", [])]
    title = str(row[0]) if row else f"{section.get('title', section_key)} event {item_index + 1}"
    facts = [
        {"label": headers[index] if index < len(headers) else f"Field {index + 1}", "value": str(value)}
        for index, value in enumerate(row)
    ]
    combined = " ".join([title, section.get("summary", ""), *[str(value) for value in row]])
    theme = theme_for(combined)
    actual = actual_from_row(headers, row)
    status = status_from_row(headers, row, section.get("status", "已公布"))
    if title in {"—", "尚无法可靠确认", "无重大新增事件"}:
        status = "Unavailable"
    return {
        "id": stable_id(report_date, section_key, group_index, item_index, title),
        "title": title,
        "theme_id": theme,
        "category": CATEGORY_BY_THEME[theme],
        "status": status,
        "importance": "★★★★" if "重大" in str(section.get("status", "")) else "★★★",
        "actual": actual,
        "time": time_from_row(headers, row),
        "summary": section.get("summary", ""),
        "why_it_matters": section.get("summary", ""),
        "transmission": next((paragraph for paragraph in section.get("paragraphs", []) if "→" in paragraph or "transmission" in paragraph.lower()), section.get("paragraphs", [section.get("summary", "")])[-1] if section.get("paragraphs") else section.get("summary", "")),
        "affected_assets": ASSET_HINTS.get(section_key, ["Cross-asset"]),
        "facts": facts,
        "integrity": [
            {"label": "Source mode", "value": "native_daily"},
            {"label": "Section status", "value": str(section.get("status", ""))},
        ],
        "sources": table.get("sources", []),
        "source_mode": "native_daily",
    }


def build_event_groups(report: dict[str, Any], section_key: str, section: dict[str, Any]) -> list[dict[str, Any]]:
    if isinstance(section.get("event_groups"), list):
        return section["event_groups"]
    if "无重大新增" in str(section.get("status", "")):
        return [{"id": f"{section_key}-no-update", "label": "No Major Update", "items": []}]

    groups = []
    for group_index, table in enumerate(section.get("tables", [])):
        rows = table.get("rows", []) if isinstance(table, dict) else []
        items = []
        for item_index, row in enumerate(rows):
            if not isinstance(row, list) or not row:
                continue
            if str(row[0]) in {"尚无法可靠确认", "—"} and section_key in {"treasury", "index_changes", "flows", "etf", "options"}:
                continue
            items.append(row_to_event(report["date"], section_key, section, table, group_index, item_index, row))
        groups.append({
            "id": f"{section_key}-group-{group_index + 1}",
            "label": table.get("title", f"Event Group {group_index + 1}"),
            "items": items,
        })

    if not groups and section.get("paragraphs") and section_key in {"financing", "geopolitics", "regional_policy"}:
        title = section.get("summary") or section.get("title")
        theme = theme_for(" ".join([title, *section.get("paragraphs", [])]))
        groups = [{
            "id": f"{section_key}-structural",
            "label": "Structural Update",
            "items": [{
                "id": stable_id(report["date"], section_key, 0, 0, title),
                "title": title,
                "theme_id": theme,
                "category": CATEGORY_BY_THEME[theme],
                "status": section.get("status", "选择性更新"),
                "importance": "★★★★" if "重大" in str(section.get("status", "")) else "★★★",
                "actual": None,
                "time": {"date": report["date"]},
                "summary": section.get("summary", ""),
                "why_it_matters": section.get("paragraphs", [section.get("summary", "")])[0],
                "transmission": section.get("paragraphs", [section.get("summary", "")])[-1],
                "affected_assets": ASSET_HINTS.get(section_key, ["Cross-asset"]),
                "facts": [{"label": f"Point {index + 1}", "value": value} for index, value in enumerate(section.get("paragraphs", []))],
                "integrity": [{"label": "Source mode", "value": "native_daily"}],
                "sources": [],
                "source_mode": "native_daily",
            }],
        }]
    if not groups:
        groups = [{"id": f"{section_key}-empty", "label": "No Structured Events", "items": []}]
    return groups


def enrich_daily_reports() -> None:
    for path in sorted((DOCS / "data/daily").glob("*.json")):
        report = read_json(path)
        for item in report.get("top_catalysts", []):
            text = " ".join(str(item.get(key, "")) for key in ("event", "what_happened", "transmission"))
            theme = item.setdefault("theme_id", theme_for(text))
            item.setdefault("category", CATEGORY_BY_THEME[theme])
            item.setdefault("continuity", "active")
        for item in report.get("top_risks", []):
            text = " ".join(str(item.get(key, "")) for key in ("risk", "first_asset", "transmission"))
            theme = item.setdefault("theme_id", theme_for(text))
            item.setdefault("category", CATEGORY_BY_THEME[theme])
            item.setdefault("continuity", "active")
        report.setdefault("regime_codes", {})["overall"] = (
            "event_risk" if "event" in str(report.get("market_regime", {}).get("overall", {}).get("state", "")).lower()
            else "risk_off" if "risk-off" in str(report.get("market_regime", {}).get("overall", {}).get("state", "")).lower()
            else "risk_on" if "risk-on" in str(report.get("market_regime", {}).get("overall", {}).get("state", "")).lower()
            else "neutral"
        )
        for key in EVENT_SECTION_KEYS:
            section = report.get("sections", {}).get(key)
            if isinstance(section, dict):
                section["event_groups"] = build_event_groups(report, key, section)
        write_json(path, report)


def patch_index() -> None:
    path = DOCS / "index.html"
    text = path.read_text(encoding="utf-8")
    text = re.sub(r'\n?\s*<link rel="stylesheet" href="assets/market-lens\.css\?v=[^"]+">', "", text)
    text = re.sub(r'\n?\s*<script defer src="assets/p0\.js\?v=[^"]+"></script>', "", text)
    style_matches = list(re.finditer(r'<link rel="stylesheet" href="assets/styles\.css\?v=[^"]+">', text))
    if not style_matches:
        raise RuntimeError("Cannot locate primary stylesheet in index.html")
    match = style_matches[-1]
    text = text[:match.end()] + '\n  <link rel="stylesheet" href="assets/market-lens.css?v=2.0.0">' + text[match.end():]
    script_matches = list(re.finditer(r'<script defer src="assets/app\.js\?v=[^"]+"></script>', text))
    if not script_matches:
        raise RuntimeError("Cannot locate app.js in index.html")
    match = script_matches[-1]
    text = text[:match.end()] + '\n  <script defer src="assets/p0.js?v=2.0.0"></script>' + text[match.end():]
    text = re.sub(r'<html lang="zh-CN"(?: data-site-version="[^"]+")?>', '<html lang="zh-CN" data-site-version="2.0.0">', text, count=1)
    path.write_text(text, encoding="utf-8")


GENERIC_RENDERERS = r'''
function renderEventFacts(items, label) {
  const facts = Array.isArray(items) ? items : [];
  if (!facts.length) return null;
  const rows = facts.map((item) => [item.label, item.value]);
  return renderTable(["Field", "Value"], rows, label);
}

function renderGenericEvent(item, index) {
  const article = create("article", "structured-event");
  const header = create("header", "structured-event__header");
  const identity = create("div");
  appendText(identity, "div", "structured-event__eyebrow", `EVENT ${String(index + 1).padStart(2, "0")} · ${textOrFallback(item.category)}`);
  appendText(identity, "h5", "", textOrFallback(item.title));
  header.appendChild(identity);
  const meta = create("div", "structured-event__meta");
  [item.importance, item.status, item.actual ? `Actual ${item.actual}` : null]
    .filter(Boolean)
    .forEach((value) => appendText(meta, "span", "structured-event__chip", value));
  header.appendChild(meta);
  article.appendChild(header);

  const timeValues = Object.entries(item.time || {});
  if (timeValues.length) {
    const time = create("div", "structured-event__time");
    timeValues.forEach(([key, value]) => appendDefinition(time, key, value, "structured-event__time-item"));
    article.appendChild(time);
  }

  appendDefinition(article, "What happened / 事件摘要", item.summary, "structured-event__fact");
  appendDefinition(article, "Why it matters / 为什么重要", item.why_it_matters, "structured-event__fact");
  appendDefinition(article, "Transmission / 传导链", item.transmission, "structured-event__transmission");

  const assets = create("div", "structured-event__assets");
  appendText(assets, "span", "structured-event__assets-label", "Affected Assets");
  const chips = create("div", "structured-event__assets-list");
  (item.affected_assets || []).forEach((value) => appendText(chips, "span", "asset-chip", value));
  assets.appendChild(chips);
  article.appendChild(assets);

  const factTable = renderEventFacts(item.facts, `${item.title} facts`);
  if (factTable) article.appendChild(factTable);
  return article;
}

function renderEventCollection(section) {
  const collection = create("div", "structured-event-collection");
  (section.event_groups || []).forEach((group) => {
    const groupNode = create("section", "structured-event-group");
    const heading = create("header", "structured-event-group__header");
    appendText(heading, "h4", "", textOrFallback(group.label));
    appendText(heading, "span", "", `${(group.items || []).length} EVENT${(group.items || []).length === 1 ? "" : "S"}`);
    groupNode.appendChild(heading);
    if ((group.items || []).length) {
      group.items.forEach((item, index) => groupNode.appendChild(renderGenericEvent(item, index)));
    } else {
      appendText(groupNode, "p", "structured-event__empty", "无重大新增事件。");
    }
    collection.appendChild(groupNode);
  });
  return collection;
}

'''


def patch_app() -> None:
    path = DOCS / "assets/app.js"
    text = path.read_text(encoding="utf-8")
    if "function renderEventCollection(" not in text:
        marker = "function renderCatalyst("
        index = text.find(marker)
        if index < 0:
            raise RuntimeError("Cannot locate renderCatalyst insertion point")
        text = text[:index] + GENERIC_RENDERERS + text[index:]

    if "const hasStructuredEvents" not in text:
        pattern = re.compile(
            r'(\s+const hasStructuredEarnings = key === "earnings".*?\n\s+if \(hasStructuredEarnings\) \{\n\s+body\.appendChild\(renderEarningsCollection\(section\)\);\n\s+\})',
            re.S,
        )
        match = pattern.search(text)
        if match:
            insertion = match.group(1) + '\n\n    const hasStructuredEvents = key !== "earnings" && Array.isArray(section.event_groups);\n    if (hasStructuredEvents) {\n      body.appendChild(renderEventCollection(section));\n    }'
            text = text[:match.start()] + insertion + text[match.end():]
        else:
            # Legacy builds without the dedicated earnings renderer.
            needle = '    if (key === "top_catalysts") {'
            index = text.find(needle)
            if index < 0:
                raise RuntimeError("Cannot locate renderSections event insertion point")
            insertion = '    const hasStructuredEvents = Array.isArray(section.event_groups);\n    if (hasStructuredEvents) {\n      body.appendChild(renderEventCollection(section));\n    }\n\n'
            text = text[:index] + insertion + text[index:]

    text = re.sub(
        r'const tables = hasStructuredEarnings\s*\? \[\]\s*:\s*\(Array\.isArray\(section\.tables\) \? section\.tables : \[\]\);',
        'const tables = (hasStructuredEarnings || hasStructuredEvents)\n      ? []\n      : (Array.isArray(section.tables) ? section.tables : []);',
        text,
        count=1,
    )
    if "const tables = (hasStructuredEarnings || hasStructuredEvents)" not in text:
        text = text.replace(
            "const tables = Array.isArray(section.tables) ? section.tables : [];",
            "const tables = hasStructuredEvents ? [] : (Array.isArray(section.tables) ? section.tables : []);",
            1,
        )
    text = text.replace(
        'key !== "top_catalysts" && !hasStructuredEarnings)',
        'key !== "top_catalysts" && !hasStructuredEarnings && !hasStructuredEvents)',
        1,
    )
    text = text.replace(
        'key !== "top_catalysts") {',
        'key !== "top_catalysts" && !hasStructuredEvents) {',
        1,
    )
    path.write_text(text, encoding="utf-8")


def update_metadata() -> None:
    latest_path = DOCS / "data/latest.json"
    latest = read_json(latest_path)
    latest["trend_path"] = "data/trends/rolling-30d.json"
    latest["market_history_path"] = "data/trends/market-history.json"
    latest["lens_path"] = "trends.html"
    write_json(latest_path, latest)

    version = {
        "site_version": "2.0.0",
        "release_state": "production",
        "published_features": [
            "30d_market_regime_and_catalyst_map",
            "narrative_and_risk_lifecycle",
            "cross_asset_confirmation",
            "compact_mobile_reading_dock",
            "official_market_history_backfill",
            "explicit_native_vs_reconstructed_provenance",
            "unbounded_cross_section_event_collections",
            "unbounded_multi_company_earnings",
            "non_reloading_section_navigation"
        ]
    }
    write_json(DOCS / "version.json", version)

    readme_path = ROOT / "README.md"
    readme = readme_path.read_text(encoding="utf-8")
    marker = "<!-- MARKET_LENS_V2 -->"
    addition = f'''\n\n{marker}\n## 30-Day Market Lens (v2.0.0)\n\nThe site now includes a source-backed 30-day regime/catalyst map, persistent risk lifecycle, cross-asset confirmation panel and compact mobile reading dock. Historical dates without a native daily edition are labelled `objective_market_reconstruction`; they are never presented as contemporaneous editorial calls.\n\n- Daily homepage: `docs/index.html`\n- Full 30D Lens: `docs/trends.html`\n- Derived snapshot: `docs/data/trends/rolling-30d.json`\n- Stored market history: `docs/data/trends/market-history.json`\n- Design and methodology: `docs/product/30d-market-lens.md`\n'''
    if marker not in readme:
        readme_path.write_text(readme.rstrip() + addition + "\n", encoding="utf-8")


def main() -> None:
    patch_index()
    patch_app()
    enrich_daily_reports()
    update_metadata()
    print("Existing site migrated to P0 Market Lens v2.0.0")


if __name__ == "__main__":
    main()
