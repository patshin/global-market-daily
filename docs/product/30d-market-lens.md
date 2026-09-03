# 30-Day Market Lens & P0 Intelligence — Product / Engineering Design

## Objective

Add market memory without weakening the daily report. The daily page remains the canonical current-edition surface; the 30D lens is a derived historical intelligence layer.

## P0 Product Contract

1. **Narrative / Risk Lifecycle** — stable `theme_id`, category, persistence, first/last seen, days in Top 3, and lifecycle state (`New / Escalating / Persistent / Easing / Resolved`).
2. **Cross-Asset Confirmation** — current narrative is checked against directionally relevant asset moves. Confirmation is evidence of co-movement, never a causal proof.
3. **Mobile Compact Reader Bar** — once the reader reaches the 15 Core Sections, large sticky controls collapse into a compact date / section / reading-progress bar. It never hides report content.
4. **30D Market Lens** — regime ribbon, six-signal matrix, Top Catalyst map, persistent-risk table, and independent cross-asset sparklines.

## Historical Integrity

The repo initially contains only one authentic published daily assessment. Historical market data is therefore split into:

- `native_daily`: the original assessment published on that date.
- `objective_market_reconstruction`: a deterministic driver proxy built from contemporaneous price/rate/spread moves. It is not described as a retroactive reconstruction of that day's news narrative.

Native days automatically replace reconstructed days as the archive grows.

## Data Sources

The market-history layer stores 2026 YTD observations used for rolling statistics and the current 30D display window:

- NASDAQCOM — Nasdaq Composite via FRED
- SP500 — S&P 500 via FRED
- VIXCLS — VIX via FRED
- DGS2 / DGS10 — Federal Reserve H.15 via FRED
- DCOILBRENTEU — EIA Brent spot via FRED
- DTWEXBGS — Federal Reserve broad trade-weighted USD via FRED
- BAMLH0A0HYM2 — ICE BofA US High Yield OAS via FRED

## Derived Data

`docs/data/trends/market-history.json` stores the retained YTD market history. `docs/data/trends/rolling-30d.json` is the lightweight browser rendering source. Browsers do not download 30 complete daily editions to construct trends.

## Regime Reconstruction

Historical reconstructed sessions use standardized 20-session changes across equities, volatility, Treasury yields, Brent, USD and high-yield spreads. The output is deliberately discrete (`Risk-On / Neutral / Risk-Off / Event Risk`) and does not expose a false 0–100 composite score.

## Theme Registry

Stable themes include `global_duration`, `fed_policy_path`, `energy_inflation`, `geopolitics_energy`, `ai_earnings`, `credit_conditions`, `volatility_event_risk`, `usd_financial_conditions`, `growth_duration_rotation`, `equity_risk_appetite`, and `market_structure`.

## Failure Isolation

The P0 homepage module fetches `rolling-30d.json` independently. If it fails, the existing daily report continues to render unchanged. The standalone trends page shows a clear unavailable state rather than fabricated data.

## Release Gates

- `validate_publish.py`: original publication integrity
- `validate_frontend.py`: original continuous-report / section-navigation integrity
- `validate_market_lens.py`: 30D coverage, provenance, themes, lifecycle, cross-asset data, homepage hooks, and standalone page structure
- JavaScript syntax checks for `app.js`, `p0.js`, and `trends.js`

## Daily Operation

A daily edition publish remains the source event. After new daily JSON is added, the trend-refresh workflow pulls current official/public market series, rebuilds `market-history.json` and `rolling-30d.json`, validates them, commits the derived trend files, and the normal Pages workflow publishes them.
