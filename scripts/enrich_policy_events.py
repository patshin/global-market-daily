#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LENS = ROOT / "docs/data/trends/rolling-30d.json"
POLICY = ROOT / "docs/data/trends/policy-events.json"

def load(path):
    return json.loads(path.read_text(encoding="utf-8"))

def main():
    lens = load(LENS)
    policy = load(POLICY)
    days = lens.get("days", [])
    by_date = {d.get("date"): d for d in days if isinstance(d, dict)}
    accepted = []
    for event in policy.get("events", []):
        if not isinstance(event, dict):
            continue
        date = event.get("date")
        day = by_date.get(date)
        if not day:
            continue
        item = {
            "id": event.get("id") or f"policy-{date}",
            "rank": "P",
            "marker_type": "confirmed_policy",
            "importance": event.get("importance", 4),
            "theme_id": event.get("theme_id", "china_trade_policy"),
            "category": "china_trade_policy",
            "title": event.get("title", "Policy milestone"),
            "event": event.get("title", "Policy milestone"),
            "status": event.get("status", "Confirmed / Released"),
            "market_bias": event.get("market_bias", "mixed"),
            "evidence": event.get("evidence", ""),
            "transmission": event.get("transmission", ""),
            "confirmation": event.get("confirmation", ""),
            "invalidation": event.get("invalidation", ""),
            "source_url": event.get("source_url"),
            "source_name": event.get("source_name"),
            "provenance": "primary_policy_source"
        }
        bucket = day.setdefault("catalysts", [])
        if not any(str(x.get("id")) == str(item["id"]) for x in bucket if isinstance(x, dict)):
            bucket.append(item)
        accepted.append(item)
    lens["policy_monitor"] = {
        "category": "china_trade_policy",
        "events_in_window": len(accepted),
        "empty_state": policy.get("empty_state", "本窗口无重大政策节点"),
        "marker": "P",
        "marker_label": "已确认政策节点"
    }
    LENS.write_text(json.dumps(lens, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(lens["policy_monitor"], ensure_ascii=False))

if __name__ == "__main__":
    main()
