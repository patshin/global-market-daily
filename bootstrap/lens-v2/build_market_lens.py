#!/usr/bin/env python3
"""Build the source-backed 30-day Market Lens for Global Market Daily.

The builder deliberately separates three evidence modes:
- native_daily: judgments actually published in a daily edition;
- objective_market_reconstruction: deterministic reconstruction from dated market series;
- unavailable: no reliable observation.

It never backfills a historical editorial judgment as though it existed on that day.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import re
import statistics
import sys
import time
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

SERIES = {
    "sp500": {
        "id": "SP500",
        "label": "S&P 500",
        "unit": "index",
        "kind": "level",
        "required": True,
    },
    "nasdaq": {
        "id": "NASDAQCOM",
        "label": "Nasdaq Composite",
        "unit": "index",
        "kind": "level",
        "required": True,
    },
    "vix": {
        "id": "VIXCLS",
        "label": "VIX",
        "unit": "index",
        "kind": "level",
        "required": True,
    },
    "ust2y": {
        "id": "DGS2",
        "label": "US 2Y Treasury Yield",
        "unit": "%",
        "kind": "yield",
        "required": True,
    },
    "ust10y": {
        "id": "DGS10",
        "label": "US 10Y Treasury Yield",
        "unit": "%",
        "kind": "yield",
        "required": True,
    },
    "brent": {
        "id": "DCOILBRENTEU",
        "label": "Brent Crude",
        "unit": "USD/bbl",
        "kind": "level",
        "required": True,
    },
    "broad_usd": {
        "id": "DTWEXBGS",
        "label": "Broad Trade-Weighted U.S. Dollar Index",
        "unit": "index",
        "kind": "level",
        "required": False,
    },
    "hy_spread": {
        "id": "BAMLH0A0HYM2",
        "label": "ICE BofA U.S. High Yield OAS",
        "unit": "%",
        "kind": "spread",
        "required": False,
    },
}

CATEGORY_LABELS = {
    "growth_macro": "Growth / Macro",
    "inflation_rates": "Inflation / Rates",
    "central_banks_fiscal": "Central Banks / Fiscal",
    "earnings_ai_semis": "Earnings / AI / Semiconductors",
    "geopolitics_energy": "Geopolitics / Energy",
    "china_trade_policy": "China / Trade / Industrial Policy",
    "liquidity_credit_financing": "Liquidity / Credit / Financing",
    "market_structure": "Market Structure / Index / Options",
}

THEMES: dict[str, dict[str, Any]] = {
    "equity_risk_appetite": {
        "label": "Equity risk appetite",
        "label_zh": "权益风险偏好",
        "category": "growth_macro",
        "risk_label": "权益风险偏好继续恶化",
        "primary_asset": "Nasdaq Composite",
        "transmission": "Equities ↓ → wealth/risk appetite ↓ → financial conditions tighten",
        "flip": "Nasdaq and S&P recover while VIX retraces.",
        "expected": {"nasdaq": "down", "sp500": "down", "vix": "up"},
    },
    "volatility_event_risk": {
        "label": "Volatility / event risk",
        "label_zh": "波动率与事件风险",
        "category": "market_structure",
        "risk_label": "波动率冲击从单日跳升演变为持续风险",
        "primary_asset": "VIX",
        "transmission": "VIX ↑ → risk limits tighten → de-risking → equities/credit ↓",
        "flip": "VIX falls back below its pre-shock range.",
        "expected": {"vix": "up", "nasdaq": "down", "sp500": "down"},
    },
    "global_duration": {
        "label": "Global duration / term premium",
        "label_zh": "全球久期与期限溢价",
        "category": "inflation_rates",
        "risk_label": "长端收益率继续上行并压缩风险资产估值",
        "primary_asset": "US 10Y",
        "transmission": "10Y ↑ → discount rate ↑ → long-duration equity multiples ↓",
        "flip": "US 10Y reverses lower and holds below the prior five-session range.",
        "expected": {"ust10y": "up", "nasdaq": "down", "sp500": "down", "broad_usd": "up"},
    },
    "fed_policy_path": {
        "label": "Fed policy-path repricing",
        "label_zh": "Fed政策路径重定价",
        "category": "central_banks_fiscal",
        "risk_label": "前端利率重新定价推高融资成本",
        "primary_asset": "US 2Y",
        "transmission": "2Y ↑ → policy path tighter → funding cost ↑ → risk assets ↓",
        "flip": "US 2Y gives back the repricing after softer inflation or labour data.",
        "expected": {"ust2y": "up", "broad_usd": "up", "nasdaq": "down"},
    },
    "energy_inflation": {
        "label": "Energy inflation impulse",
        "label_zh": "能源通胀冲击",
        "category": "geopolitics_energy",
        "risk_label": "油价上行重新抬升通胀和央行紧缩风险",
        "primary_asset": "Brent",
        "transmission": "Oil ↑ → inflation expectations ↑ → yields ↑ → risk-asset valuation ↓",
        "flip": "Brent returns to its pre-shock range and rates stop rising.",
        "expected": {"brent": "up", "ust10y": "up", "nasdaq": "down", "broad_usd": "up"},
    },
    "usd_financial_conditions": {
        "label": "Dollar financial conditions",
        "label_zh": "美元金融条件",
        "category": "liquidity_credit_financing",
        "risk_label": "美元走强收紧全球金融条件",
        "primary_asset": "Broad USD",
        "transmission": "USD ↑ → global liquidity tightens → EM/CNH/commodities and risk assets ↓",
        "flip": "Broad USD weakens alongside lower front-end yields.",
        "expected": {"broad_usd": "up", "nasdaq": "down", "sp500": "down"},
    },
    "credit_conditions": {
        "label": "Credit conditions",
        "label_zh": "信用条件",
        "category": "liquidity_credit_financing",
        "risk_label": "高收益信用利差扩大并向权益市场传导",
        "primary_asset": "US HY OAS",
        "transmission": "Credit spreads ↑ → refinancing cost ↑ → earnings/capex pressure ↑",
        "flip": "High-yield spreads compress and equity breadth improves.",
        "expected": {"hy_spread": "up", "nasdaq": "down", "sp500": "down", "vix": "up"},
    },
    "growth_duration_rotation": {
        "label": "Growth-duration rotation",
        "label_zh": "成长久期轮动",
        "category": "earnings_ai_semis",
        "risk_label": "成长股相对表现恶化，盈利上修不足以抵消折现率",
        "primary_asset": "Nasdaq vs S&P 500",
        "transmission": "Nasdaq relative ↓ → duration premium unwinds → AI/growth leadership narrows",
        "flip": "Nasdaq resumes outperformance while long-end yields stabilise.",
        "expected": {"nasdaq": "down", "sp500": "flat", "ust10y": "up"},
    },
    "geopolitics_energy": {
        "label": "Geopolitical energy disruption",
        "label_zh": "地缘能源扰动",
        "category": "geopolitics_energy",
        "risk_label": "地缘冲突升级为持续性能源与航运中断",
        "primary_asset": "Brent / shipping",
        "transmission": "Physical disruption → oil/freight ↑ → inflation ↑ → yields ↑ → Nasdaq multiples ↓",
        "flip": "Physical flows normalise, official escalation stops and oil retraces.",
        "expected": {"brent": "up", "ust10y": "up", "vix": "up", "nasdaq": "down"},
    },
    "ai_earnings": {
        "label": "AI earnings / capex validation",
        "label_zh": "AI盈利与资本开支验证",
        "category": "earnings_ai_semis",
        "risk_label": "AI基本面强劲但资本成本与投资回报错配",
        "primary_asset": "Nasdaq / semiconductors",
        "transmission": "AI orders/guidance ↑ → earnings revisions ↑; yields ↑ → valuation offset",
        "flip": "AI guidance disappoints or margins deteriorate; alternatively rates fall enough to relieve valuation pressure.",
        "expected": {"nasdaq": "up", "sp500": "up", "ust10y": "flat"},
    },
    "market_structure": {
        "label": "Market structure / passive flow",
        "label_zh": "市场结构与被动资金",
        "category": "market_structure",
        "risk_label": "市场结构事件放大短期价格波动",
        "primary_asset": "VIX / index futures",
        "transmission": "Expiry/rebalance/positioning → mechanical flow → index volatility",
        "flip": "The mechanical flow window passes without persistent dislocation.",
        "expected": {"vix": "up"},
    },
}

NATIVE_THEME_RULES = [
    (re.compile(r"Hormuz|Iran|伊朗|航运|油价|原油|中东", re.I), "geopolitics_energy"),
    (re.compile(r"Treasury|10Y|JGB|收益率|主权债|债券|term premium|期限溢价", re.I), "global_duration"),
    (re.compile(r"Fed|2Y|加息|降息|政策利率", re.I), "fed_policy_path"),
    (re.compile(r"Dell|Broadcom|NVIDIA|NVDA|AVGO|AI|Semiconductor|半导体|财报", re.I), "ai_earnings"),
    (re.compile(r"VIX|波动率|OPEX|期权", re.I), "volatility_event_risk"),
    (re.compile(r"美元|DXY|USD|流动性|融资|credit|信用", re.I), "usd_financial_conditions"),
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_number(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip().replace(",", "")
    if not text or text in {".", "—", "-", "待公布", "尚无法可靠确认"}:
        return None
    match = re.search(r"[-+]?\d+(?:\.\d+)?", text)
    return float(match.group()) if match else None


def fred_url(series_id: str, start: date, end: date) -> str:
    query = urlencode({"id": series_id, "cosd": start.isoformat(), "coed": end.isoformat()})
    return f"https://fred.stlouisfed.org/graph/fredgraph.csv?{query}"


def fetch_fred(series_id: str, start: date, end: date, retries: int = 3) -> dict[str, float]:
    url = fred_url(series_id, start, end)
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            request = Request(url, headers={"User-Agent": "GlobalMarketDaily/2.0 github.com/patshin/global-market-daily"})
            with urlopen(request, timeout=35) as response:
                body = response.read().decode("utf-8-sig")
            rows: dict[str, float] = {}
            reader = csv.DictReader(body.splitlines())
            value_column = next((name for name in (reader.fieldnames or []) if name != "DATE"), None)
            if not value_column:
                raise ValueError(f"FRED response for {series_id} has no value column")
            for row in reader:
                value = parse_number(row.get(value_column))
                if value is not None:
                    rows[row["DATE"]] = value
            if not rows:
                raise ValueError(f"FRED response for {series_id} contains no observations")
            return rows
        except (URLError, TimeoutError, ValueError, OSError) as exc:
            last_error = exc
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"Unable to fetch FRED {series_id}: {last_error}")


def load_latest_report(root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    docs = root / "docs"
    latest = read_json(docs / "data/latest.json")
    report_path = docs / latest["daily_json_path"]
    return latest, read_json(report_path)


def source_metadata(key: str, start: date, end: date) -> dict[str, Any]:
    spec = SERIES[key]
    return {
        "id": f"FRED_{spec['id']}",
        "provider": "Federal Reserve Bank of St. Louis (FRED)",
        "series_id": spec["id"],
        "title": spec["label"],
        "source_url": fred_url(spec["id"], start, end),
        "unit": spec["unit"],
        "frequency": "Daily / business-day observations where available",
        "source_tier": "Primary/official-series distributor",
    }


def load_or_fetch_history(root: Path, as_of: date, use_network: bool) -> dict[str, Any]:
    path = root / "docs/data/trends/market-history.json"
    existing: dict[str, Any] = read_json(path) if path.exists() else {}
    history_start = as_of - timedelta(days=210)
    series_payload: dict[str, list[dict[str, Any]]] = {}
    warnings: list[str] = []

    existing_series = existing.get("series", {}) if isinstance(existing, dict) else {}
    for key, spec in SERIES.items():
        values: dict[str, float] = {}
        if use_network:
            try:
                values = fetch_fred(spec["id"], history_start, as_of)
            except Exception as exc:  # fallback is deliberate; validation checks coverage
                warnings.append(str(exc))
        if not values:
            for row in existing_series.get(key, []):
                if isinstance(row, dict) and parse_number(row.get("value")) is not None:
                    values[str(row["date"])] = float(row["value"])
        if spec["required"] and len(values) < 25:
            raise RuntimeError(f"Required history {key} has only {len(values)} observations")
        series_payload[key] = [
            {"date": day, "value": values[day]}
            for day in sorted(values)
            if history_start.isoformat() <= day <= as_of.isoformat()
        ]

    result = {
        "schema_version": "2.0.0",
        "as_of": as_of.isoformat(),
        "history_start": history_start.isoformat(),
        "retrieved_at": utc_now() if use_network else existing.get("retrieved_at", utc_now()),
        "window_purpose": "210 calendar days retained to support a 30-day display window and rolling normalisation.",
        "series": series_payload,
        "sources": [source_metadata(key, history_start, as_of) for key in SERIES],
        "warnings": warnings,
    }
    write_json(path, result)
    return result


def to_map(history: dict[str, Any]) -> dict[str, dict[str, float]]:
    return {
        key: {str(row["date"]): float(row["value"]) for row in rows}
        for key, rows in history.get("series", {}).items()
    }


def inject_native_snapshot(series: dict[str, dict[str, float]], report: dict[str, Any]) -> list[dict[str, Any]]:
    mapping = {
        "S&P 500": "sp500",
        "Nasdaq Composite": "nasdaq",
        "VIX": "vix",
        "UST 2Y": "ust2y",
        "UST 10Y": "ust10y",
        "Brent": "brent",
    }
    overrides = []
    for item in report.get("market_tape", []):
        key = mapping.get(item.get("asset"))
        value = parse_number(item.get("level"))
        if key and value is not None:
            series.setdefault(key, {})[report["date"]] = value
            overrides.append({"series": key, "date": report["date"], "value": value, "source": "native_daily.market_tape"})
    return overrides


def previous_value(values: dict[str, float], day: str, maximum_gap: int = 5) -> tuple[float | None, int | None]:
    target = date.fromisoformat(day)
    for gap in range(maximum_gap + 1):
        candidate = (target - timedelta(days=gap)).isoformat()
        if candidate in values:
            return values[candidate], gap
    return None, None


def aligned_sessions(series: dict[str, dict[str, float]], as_of: date) -> list[dict[str, Any]]:
    dates = sorted(
        day for day in set(series.get("sp500", {})) | set(series.get("nasdaq", {}))
        if day <= as_of.isoformat()
    )
    sessions = []
    for day in dates:
        row: dict[str, Any] = {"date": day, "values": {}, "stale_days": {}}
        for key, values in series.items():
            value, gap = previous_value(values, day)
            row["values"][key] = value
            row["stale_days"][key] = gap
        if row["values"].get("sp500") is not None or row["values"].get("nasdaq") is not None:
            sessions.append(row)
    return sessions


def pct_change(current: float | None, previous: float | None) -> float | None:
    if current is None or previous in (None, 0):
        return None
    return (current / previous - 1.0) * 100.0


def difference(current: float | None, previous: float | None, multiplier: float = 1.0) -> float | None:
    if current is None or previous is None:
        return None
    return (current - previous) * multiplier


def rolling_std(values: list[float | None], end_index: int, window: int, fallback: float) -> float:
    sample = [value for value in values[max(0, end_index - window):end_index] if value is not None]
    if len(sample) < 5:
        return fallback
    result = statistics.pstdev(sample)
    return result if result > 1e-9 else fallback


def five_session_change(rows: list[dict[str, Any]], index: int, key: str, kind: str) -> float | None:
    if index < 1:
        return None
    previous_index = max(0, index - 5)
    current = rows[index]["values"].get(key)
    previous = rows[previous_index]["values"].get(key)
    return difference(current, previous, 100.0) if kind in {"yield", "spread"} else pct_change(current, previous)


def arrow(value: float | None, positive: float, negative: float) -> str:
    if value is None:
        return "—"
    if value >= positive:
        return "↑"
    if value <= negative:
        return "↓"
    return "→"


def strength_label(score: float) -> str:
    if score >= 2.4:
        return "high"
    if score >= 1.35:
        return "medium"
    return "low"


def importance(score: float) -> str:
    if score >= 2.4:
        return "★★★★★"
    if score >= 1.35:
        return "★★★★"
    return "★★★"


def candidate(
    theme_id: str,
    score: float,
    title: str,
    evidence: str,
    market_bias: str,
    move: float | None,
    asset_key: str,
) -> dict[str, Any]:
    theme = THEMES[theme_id]
    return {
        "theme_id": theme_id,
        "theme": theme["label_zh"],
        "category": theme["category"],
        "category_label": CATEGORY_LABELS[theme["category"]],
        "title": title,
        "importance": importance(score),
        "evidence_strength": strength_label(score),
        "market_bias": market_bias,
        "primary_asset": theme["primary_asset"],
        "observed_move": move,
        "evidence": evidence,
        "transmission": theme["transmission"],
        "confirmation": f"{theme['primary_asset']}及其预期传导资产继续沿同方向运行。",
        "invalidation": theme["flip"],
        "source_mode": "objective_market_reconstruction",
        "source_ids": [f"FRED_{SERIES[asset_key]['id']}"] if asset_key in SERIES else [],
        "_score": round(score, 4),
    }


def reconstructed_candidates(rows: list[dict[str, Any]], index: int, change_history: dict[str, list[float | None]]) -> list[dict[str, Any]]:
    current = rows[index]
    previous = rows[index - 1] if index else None
    if not previous:
        return []
    values = current["values"]
    prev = previous["values"]
    moves = {
        "sp500": pct_change(values.get("sp500"), prev.get("sp500")),
        "nasdaq": pct_change(values.get("nasdaq"), prev.get("nasdaq")),
        "vix": pct_change(values.get("vix"), prev.get("vix")),
        "ust2y": difference(values.get("ust2y"), prev.get("ust2y"), 100.0),
        "ust10y": difference(values.get("ust10y"), prev.get("ust10y"), 100.0),
        "brent": pct_change(values.get("brent"), prev.get("brent")),
        "broad_usd": pct_change(values.get("broad_usd"), prev.get("broad_usd")),
        "hy_spread": difference(values.get("hy_spread"), prev.get("hy_spread"), 100.0),
    }
    candidates: list[dict[str, Any]] = []

    def z(key: str, fallback: float) -> float:
        move = moves.get(key)
        if move is None:
            return 0.0
        return abs(move) / rolling_std(change_history[key], index, 20, fallback)

    move = moves["nasdaq"]
    if move is not None:
        direction = "走强" if move >= 0 else "走弱"
        candidates.append(candidate(
            "equity_risk_appetite", z("nasdaq", 0.8),
            f"Nasdaq单日{direction} {move:+.2f}%",
            f"Nasdaq Composite {move:+.2f}%；S&P 500 {moves['sp500']:+.2f}%" if moves["sp500"] is not None else f"Nasdaq Composite {move:+.2f}%",
            "risk_on" if move >= 0 else "risk_off", move, "nasdaq"
        ))

    move = moves["vix"]
    if move is not None:
        candidates.append(candidate(
            "volatility_event_risk", z("vix", 7.0),
            f"VIX单日{'上升' if move >= 0 else '回落'} {move:+.1f}%",
            f"VIX {move:+.1f}% 至 {values.get('vix'):.2f}",
            "risk_off" if move >= 0 else "risk_on", move, "vix"
        ))

    for key, theme_id, label in (
        ("ust10y", "global_duration", "US 10Y"),
        ("ust2y", "fed_policy_path", "US 2Y"),
    ):
        move = moves[key]
        if move is not None:
            candidates.append(candidate(
                theme_id, z(key, 5.0),
                f"{label}收益率单日{'上行' if move >= 0 else '下行'} {move:+.1f}bp",
                f"{label} {move:+.1f}bp 至 {values.get(key):.3f}%",
                "risk_off" if move >= 0 else "risk_on", move, key
            ))

    move = moves["brent"]
    if move is not None:
        candidates.append(candidate(
            "energy_inflation", z("brent", 1.6),
            f"Brent单日{'上涨' if move >= 0 else '下跌'} {move:+.2f}%",
            f"Brent {move:+.2f}% 至 ${values.get('brent'):.2f}/bbl",
            "risk_off" if move >= 0 else "risk_on", move, "brent"
        ))

    move = moves["broad_usd"]
    if move is not None:
        candidates.append(candidate(
            "usd_financial_conditions", z("broad_usd", 0.35),
            f"广义美元指数单日{'走强' if move >= 0 else '走弱'} {move:+.2f}%",
            f"Broad USD {move:+.2f}% 至 {values.get('broad_usd'):.2f}",
            "risk_off" if move >= 0 else "risk_on", move, "broad_usd"
        ))

    move = moves["hy_spread"]
    if move is not None:
        candidates.append(candidate(
            "credit_conditions", z("hy_spread", 5.0),
            f"高收益信用利差单日{'扩大' if move >= 0 else '收窄'} {move:+.1f}bp",
            f"US HY OAS {move:+.1f}bp 至 {values.get('hy_spread'):.2f}%",
            "risk_off" if move >= 0 else "risk_on", move, "hy_spread"
        ))

    if moves["nasdaq"] is not None and moves["sp500"] is not None:
        relative = moves["nasdaq"] - moves["sp500"]
        score = abs(relative) / 0.45
        candidates.append(candidate(
            "growth_duration_rotation", score,
            f"Nasdaq相对S&P 500{'跑赢' if relative >= 0 else '跑输'} {relative:+.2f}个百分点",
            f"Nasdaq {moves['nasdaq']:+.2f}%；S&P 500 {moves['sp500']:+.2f}%",
            "risk_on" if relative >= 0 else "risk_off", relative, "nasdaq"
        ))

    candidates.sort(key=lambda item: item["_score"], reverse=True)
    selected: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in candidates:
        if item["theme_id"] in seen:
            continue
        seen.add(item["theme_id"])
        item["rank"] = len(selected) + 1
        item.pop("_score", None)
        selected.append(item)
        if len(selected) == 3:
            break
    return selected


def infer_native_theme(text: str) -> str:
    for pattern, theme_id in NATIVE_THEME_RULES:
        if pattern.search(text):
            return theme_id
    return "market_structure"


def native_catalysts(report: dict[str, Any]) -> list[dict[str, Any]]:
    output = []
    for index, item in enumerate(report.get("top_catalysts", [])[:3]):
        combined = " ".join(str(item.get(key, "")) for key in ("event", "what_happened", "transmission", "affected_assets"))
        theme_id = item.get("theme_id") or infer_native_theme(combined)
        theme = THEMES.get(theme_id, THEMES["market_structure"])
        output.append({
            "rank": int(item.get("rank") or index + 1),
            "theme_id": theme_id,
            "theme": theme["label_zh"],
            "category": theme["category"],
            "category_label": CATEGORY_LABELS[theme["category"]],
            "title": item.get("event", "尚无法可靠确认"),
            "importance": item.get("importance", "★★★★"),
            "evidence_strength": "native",
            "market_bias": str(item.get("direction", "mixed")),
            "primary_asset": theme["primary_asset"],
            "evidence": item.get("what_happened", ""),
            "transmission": item.get("transmission", theme["transmission"]),
            "confirmation": item.get("confirmation", ""),
            "invalidation": item.get("invalidation", theme["flip"]),
            "source_mode": "native_daily",
            "source_ids": item.get("sources", []),
        })
    return output


def native_risks(report: dict[str, Any]) -> list[dict[str, Any]]:
    output = []
    for index, item in enumerate(report.get("top_risks", [])[:3]):
        combined = " ".join(str(item.get(key, "")) for key in ("risk", "transmission", "first_asset"))
        theme_id = item.get("theme_id") or infer_native_theme(combined)
        output.append({
            "rank": index + 1,
            "theme_id": theme_id,
            "risk": item.get("risk", "尚无法可靠确认"),
            "state": item.get("continuity", "native_assessment"),
            "first_asset": item.get("first_asset", THEMES[theme_id]["primary_asset"]),
            "trigger": item.get("trigger", ""),
            "transmission": item.get("transmission", THEMES[theme_id]["transmission"]),
            "source_mode": "native_daily",
        })
    return output


def reconstruct_risks(catalysts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "rank": index + 1,
            "theme_id": item["theme_id"],
            "risk": THEMES[item["theme_id"]]["risk_label"],
            "state": "market_implied",
            "first_asset": item["primary_asset"],
            "trigger": item["confirmation"],
            "transmission": item["transmission"],
            "source_mode": "objective_market_reconstruction",
        }
        for index, item in enumerate(catalysts)
    ]


def native_signals(report: dict[str, Any]) -> dict[str, str]:
    aliases = {
        "growth_impulse": "growth",
        "inflation_impulse": "inflation",
        "rates_pressure": "rates",
        "earnings_revision": "earnings",
        "liquidity": "liquidity",
        "geopolitical_risk": "geopolitics",
    }
    result = {}
    for key, output_key in aliases.items():
        value = str(report.get("signal_panel", {}).get(key, {}).get("current", "—"))
        result[output_key] = next((symbol for symbol in ("↑", "↓", "→") if symbol in value), "—")
    return result


def reconstruct_signals(rows: list[dict[str, Any]], index: int) -> dict[str, str]:
    sp5 = five_session_change(rows, index, "sp500", "level")
    nas5 = five_session_change(rows, index, "nasdaq", "level")
    vix5 = five_session_change(rows, index, "vix", "level")
    d2_5 = five_session_change(rows, index, "ust2y", "yield")
    d10_5 = five_session_change(rows, index, "ust10y", "yield")
    oil5 = five_session_change(rows, index, "brent", "level")
    usd5 = five_session_change(rows, index, "broad_usd", "level")
    growth_proxy = None if sp5 is None and nas5 is None else statistics.mean([value for value in (sp5, nas5) if value is not None])
    earnings_proxy = None if sp5 is None or nas5 is None else nas5 - sp5
    liquidity_proxy = None if usd5 is None and d2_5 is None else sum([
        (usd5 or 0.0) * 4.0,
        (d2_5 or 0.0) / 5.0,
    ])
    geopolitics_proxy = None if oil5 is None or vix5 is None else (oil5 / 3.0) + (vix5 / 10.0)
    return {
        "growth": arrow(growth_proxy, 1.0, -1.0),
        "inflation": arrow(oil5, 2.5, -2.5),
        "rates": arrow(d10_5, 7.0, -7.0),
        "earnings": arrow(earnings_proxy, 0.8, -0.8),
        "liquidity": "↓" if liquidity_proxy is not None and liquidity_proxy >= 1.2 else ("↑" if liquidity_proxy is not None and liquidity_proxy <= -1.2 else "→"),
        "geopolitics": arrow(geopolitics_proxy, 1.2, -1.0),
    }


def infer_regime(rows: list[dict[str, Any]], index: int, catalysts: list[dict[str, Any]]) -> str:
    if index < 1:
        return "neutral"
    nas5 = five_session_change(rows, index, "nasdaq", "level")
    vix5 = five_session_change(rows, index, "vix", "level")
    d10_5 = five_session_change(rows, index, "ust10y", "yield")
    oil5 = five_session_change(rows, index, "brent", "level")
    high_shocks = sum(item.get("evidence_strength") == "high" for item in catalysts)
    risk_off_catalysts = sum("risk_off" in str(item.get("market_bias")) for item in catalysts)
    if high_shocks >= 2 or (high_shocks >= 1 and risk_off_catalysts >= 2):
        return "event_risk"
    if nas5 is not None and vix5 is not None and nas5 <= -1.4 and vix5 >= 5.0:
        return "risk_off"
    if (d10_5 or 0) >= 15 or (oil5 or 0) >= 7:
        return "risk_off"
    if nas5 is not None and vix5 is not None and nas5 >= 1.4 and vix5 <= -5.0 and (d10_5 or 0) < 12:
        return "risk_on"
    return "neutral"


def regime_code(value: Any) -> str:
    text = str(value or "").lower().replace("-", "_").replace(" ", "_")
    if "event" in text or "事件" in text:
        return "event_risk"
    if "risk_off" in text or "riskoff" in text:
        return "risk_off"
    if "risk_on" in text or "riskon" in text:
        return "risk_on"
    return "neutral"


def regime_label(code: str) -> str:
    return {
        "risk_on": "Risk-On",
        "neutral": "Neutral",
        "risk_off": "Risk-Off",
        "event_risk": "Event Risk",
    }.get(code, "Neutral")


def build_session_days(rows: list[dict[str, Any]], report: dict[str, Any], window_start: date, as_of: date) -> list[dict[str, Any]]:
    change_history = {key: [] for key in SERIES}
    for index, row in enumerate(rows):
        previous = rows[index - 1] if index else None
        for key, spec in SERIES.items():
            value = None
            if previous:
                value = difference(row["values"].get(key), previous["values"].get(key), 100.0) if spec["kind"] in {"yield", "spread"} else pct_change(row["values"].get(key), previous["values"].get(key))
            change_history[key].append(value)

    output = []
    for index, row in enumerate(rows):
        day = date.fromisoformat(row["date"])
        if day < window_start or day > as_of:
            continue
        is_native = row["date"] == report.get("date")
        catalysts = native_catalysts(report) if is_native else reconstructed_candidates(rows, index, change_history)
        risks = native_risks(report) if is_native else reconstruct_risks(catalysts)
        signals = native_signals(report) if is_native else reconstruct_signals(rows, index)
        code = regime_code(report.get("market_regime", {}).get("overall", {}).get("state")) if is_native else infer_regime(rows, index, catalysts)
        dominant_theme = catalysts[0]["theme_id"] if catalysts else None
        output.append({
            "date": row["date"],
            "regime_code": code,
            "regime_label": regime_label(code),
            "source_mode": "native_daily" if is_native else "objective_market_reconstruction",
            "dominant_theme_id": dominant_theme,
            "dominant_theme": THEMES.get(dominant_theme, {}).get("label_zh") if dominant_theme else "尚无法可靠确认",
            "signals": signals,
            "catalysts": catalysts,
            "risks": risks,
            "market": row["values"],
            "stale_days": row["stale_days"],
        })
    return output


def lifecycle(days: list[dict[str, Any]]) -> list[dict[str, Any]]:
    occurrences: dict[str, list[tuple[int, int, dict[str, Any]]]] = defaultdict(list)
    for day_index, day in enumerate(days):
        for item in day.get("catalysts", []):
            occurrences[item["theme_id"]].append((day_index, int(item["rank"]), item))
    latest_index = len(days) - 1
    result = []
    for theme_id, entries in occurrences.items():
        first_index, _, _ = entries[0]
        last_index, last_rank, last_item = entries[-1]
        trailing = [entry for entry in entries if latest_index - entry[0] <= 4]
        present_now = last_index == latest_index
        prior_ranks = [rank for idx, rank, _ in entries[:-1] if latest_index - idx <= 7]
        if present_now and len(trailing) == 1:
            state = "new"
        elif present_now and prior_ranks and last_rank < statistics.mean(prior_ranks):
            state = "escalating"
        elif present_now and len(trailing) >= 3:
            state = "persistent"
        elif present_now:
            state = "active"
        elif latest_index - last_index <= 3:
            state = "easing"
        else:
            state = "resolved"
        theme = THEMES[theme_id]
        result.append({
            "theme_id": theme_id,
            "theme": theme["label_zh"],
            "category": theme["category"],
            "category_label": CATEGORY_LABELS[theme["category"]],
            "state": state,
            "days_in_top3": len(entries),
            "sessions_covered": len(days),
            "best_rank": min(rank for _, rank, _ in entries),
            "first_seen": days[first_index]["date"],
            "last_seen": days[last_index]["date"],
            "latest_rank": last_rank if present_now else None,
            "first_asset": theme["primary_asset"],
            "latest_transmission": last_item.get("transmission", theme["transmission"]),
            "source_modes": sorted({item.get("source_mode", "unavailable") for _, _, item in entries}),
        })
    state_order = {"escalating": 0, "persistent": 1, "new": 2, "active": 3, "easing": 4, "resolved": 5}
    return sorted(result, key=lambda item: (state_order.get(item["state"], 9), -item["days_in_top3"], item["theme"]))


def regime_transitions(days: list[dict[str, Any]]) -> list[dict[str, Any]]:
    transitions = []
    previous = None
    for day in days:
        if previous and day["regime_code"] != previous["regime_code"]:
            transitions.append({
                "date": day["date"],
                "from": previous["regime_code"],
                "to": day["regime_code"],
                "from_label": previous["regime_label"],
                "to_label": day["regime_label"],
                "dominant_theme_id": day["dominant_theme_id"],
                "dominant_theme": day["dominant_theme"],
                "source_mode": day["source_mode"],
            })
        previous = day
    return transitions


def latest_changes(days: list[dict[str, Any]]) -> dict[str, float | None]:
    if len(days) < 2:
        return {key: None for key in SERIES}
    current, previous = days[-1], days[-2]
    output = {}
    for key, spec in SERIES.items():
        output[key] = difference(current["market"].get(key), previous["market"].get(key), 100.0) if spec["kind"] in {"yield", "spread"} else pct_change(current["market"].get(key), previous["market"].get(key))
    return output


def cross_asset_validation(days: list[dict[str, Any]], report: dict[str, Any]) -> dict[str, Any]:
    latest = days[-1]
    current_theme_id = latest.get("dominant_theme_id") or "market_structure"
    theme = THEMES[current_theme_id]
    changes = latest_changes(days)
    confirming, diverging, unavailable = [], [], []
    labels = {key: spec["label"] for key, spec in SERIES.items()}
    for key, expected in theme.get("expected", {}).items():
        move = changes.get(key)
        if move is None:
            unavailable.append(labels.get(key, key))
            continue
        tolerance = 0.02 if SERIES.get(key, {}).get("kind") == "level" else 0.5
        observed = "up" if move > tolerance else ("down" if move < -tolerance else "flat")
        item = {
            "asset": labels.get(key, key),
            "expected": expected,
            "observed": observed,
            "move": round(move, 3),
            "unit": "bp" if SERIES.get(key, {}).get("kind") in {"yield", "spread"} else "%",
        }
        if observed == expected or expected == "flat" and observed == "flat":
            confirming.append(item)
        else:
            diverging.append(item)
    native_first = (report.get("top_catalysts") or [{}])[0]
    return {
        "theme_id": current_theme_id,
        "theme": theme["label_zh"],
        "narrative": report.get("dominant_narrative", latest.get("dominant_theme")),
        "data_as_of": latest["date"],
        "confirming": confirming,
        "diverging": diverging,
        "unavailable": unavailable,
        "what_would_flip_it": native_first.get("invalidation") or theme["flip"],
        "interpretation": "价格验证只检验市场传导是否沿预期方向运行，不证明事件因果。",
    }


def asset_series(days: list[dict[str, Any]]) -> list[dict[str, Any]]:
    selected = ["nasdaq", "sp500", "ust10y", "brent", "vix", "broad_usd", "hy_spread"]
    output = []
    for key in selected:
        observations = [
            {"date": day["date"], "value": day["market"].get(key)}
            for day in days if day["market"].get(key) is not None
        ]
        if not observations:
            continue
        first = observations[0]["value"]
        for row in observations:
            row["indexed"] = round(row["value"] / first * 100.0, 3) if first else None
        latest = observations[-1]["value"]
        previous = observations[-2]["value"] if len(observations) > 1 else None
        kind = SERIES[key]["kind"]
        change = difference(latest, previous, 100.0) if kind in {"yield", "spread"} else pct_change(latest, previous)
        output.append({
            "key": key,
            "label": SERIES[key]["label"],
            "unit": SERIES[key]["unit"],
            "kind": kind,
            "latest": latest,
            "latest_change": round(change, 3) if change is not None else None,
            "change_unit": "bp" if kind in {"yield", "spread"} else "%",
            "observations": observations,
            "source_id": f"FRED_{SERIES[key]['id']}",
        })
    return output


def current_regime_since(days: list[dict[str, Any]]) -> str:
    current = days[-1]["regime_code"]
    start = days[-1]["date"]
    for day in reversed(days[:-1]):
        if day["regime_code"] != current:
            break
        start = day["date"]
    return start


def build(root: Path, use_network: bool) -> dict[str, Any]:
    latest, report = load_latest_report(root)
    as_of = date.fromisoformat(report["date"])
    window_start = as_of - timedelta(days=29)
    history = load_or_fetch_history(root, as_of, use_network)
    series = to_map(history)
    overrides = inject_native_snapshot(series, report)
    rows = aligned_sessions(series, as_of)
    days = build_session_days(rows, report, window_start, as_of)
    if len(days) < 12:
        raise RuntimeError(f"Only {len(days)} market sessions available in 30-day window")
    themes = lifecycle(days)
    transitions = regime_transitions(days)
    counts = Counter(day["regime_code"] for day in days)
    recurring = max(themes, key=lambda item: item["days_in_top3"]) if themes else None
    current = days[-1]
    native_count = sum(day["source_mode"] == "native_daily" for day in days)
    reconstructed_count = sum(day["source_mode"] == "objective_market_reconstruction" for day in days)
    output = {
        "schema_version": "2.0.0",
        "generated_at": utc_now(),
        "as_of": as_of.isoformat(),
        "window_start": window_start.isoformat(),
        "window_end": as_of.isoformat(),
        "window_calendar_days": 30,
        "coverage": {
            "market_sessions": len(days),
            "native_daily_days": native_count,
            "objective_reconstruction_days": reconstructed_count,
            "history_observations_start": history["history_start"],
            "history_days_retained": (as_of - date.fromisoformat(history["history_start"])).days + 1,
            "day1_ready": True,
            "methodology": "Native published judgments override deterministic market-price reconstruction. Reconstruction ranks observed cross-asset moves and is never represented as a contemporaneous editorial call.",
        },
        "current": {
            "regime_code": current["regime_code"],
            "regime_label": current["regime_label"],
            "regime_since": current_regime_since(days),
            "dominant_theme_id": current["dominant_theme_id"],
            "dominant_theme": current["dominant_theme"],
            "dominant_narrative": report.get("dominant_narrative", ""),
            "most_recurring_theme": recurring["theme"] if recurring else "尚无法可靠确认",
            "most_recurring_theme_id": recurring["theme_id"] if recurring else None,
            "most_recurring_days": recurring["days_in_top3"] if recurring else 0,
        },
        "regime_distribution": [
            {"code": code, "label": regime_label(code), "sessions": counts.get(code, 0)}
            for code in ("risk_on", "neutral", "risk_off", "event_risk")
        ],
        "days": days,
        "regime_transitions": transitions,
        "persistent_themes": themes,
        "cross_asset_validation": cross_asset_validation(days, report),
        "asset_series": asset_series(days),
        "theme_registry": {
            "categories": CATEGORY_LABELS,
            "themes": THEMES,
        },
        "provenance": {
            "native_daily_path": latest["daily_json_path"],
            "market_history_path": "data/trends/market-history.json",
            "native_snapshot_overrides": overrides,
            "source_modes": {
                "native_daily": "Analysis actually published in that day's edition.",
                "objective_market_reconstruction": "Transparent reconstruction from dated market observations; not a historical editorial claim.",
            },
            "sources": history["sources"],
            "warnings": history.get("warnings", []),
        },
    }
    write_json(root / "docs/data/trends/rolling-30d.json", output)
    return output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--network", action="store_true", help="Refresh FRED history before building")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    result = build(root, args.network)
    print(
        f"MARKET LENS BUILT — {result['coverage']['market_sessions']} sessions, "
        f"{result['coverage']['native_daily_days']} native, "
        f"{result['coverage']['objective_reconstruction_days']} reconstructed"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
