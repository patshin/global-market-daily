# 30-Day Market Lens & P0 Intelligence Layer

## 1. Product objective

The 30-Day Market Lens turns Global Market Daily from a sequence of isolated daily reports into a persistent market-intelligence system. It answers four questions that a single daily edition cannot answer reliably:

1. How did the current market regime form?
2. Which catalyst themes are recurring rather than merely noisy?
3. Is the current narrative being confirmed or contradicted by cross-asset prices?
4. Which risks are new, escalating, persistent, easing, or resolved?

The product deliberately avoids a black-box composite risk score. Regime is an explicit discrete state; catalyst importance is a ranked daily judgment; risk persistence is an observed occurrence count; cross-asset confirmation is a directional test.

## 2. P0 scope

### 2.1 30-Day Market Regime & Catalyst Map

A dedicated `trends.html` page contains:

- Overall Regime Ribbon
- Six-Signal Matrix
- Top Catalyst Map
- Persistent Risk Themes
- Cross-Asset Confirmation
- Separate cross-asset trend cards
- Methodology and source disclosure

A compact preview is inserted into the daily homepage after `What Changed Since Yesterday`.

### 2.2 Narrative and risk lifecycle

Every recurring theme has a stable `theme_id` and a lifecycle state:

- `new`
- `escalating`
- `persistent`
- `active`
- `easing`
- `resolved`

The state is derived from the theme’s appearance frequency, recent rank movement and time since last appearance. It is not an LLM-generated score.

### 2.3 Cross-asset confirmation

For the current dominant theme, the product stores an expected directional transmission map. Latest observed asset moves are separated into:

- confirming
- diverging
- unavailable

This is a market-transmission test, not causal proof. A visible `What Would Flip It` condition prevents a narrative from becoming unfalsifiable.

### 2.4 Compact mobile reading dock

On screens at or below 900px:

- the full utility toolbar remains available at the top of the report;
- the legacy stacked sticky bars become non-sticky while reading;
- a compact fixed dock appears after the reader enters the full report;
- the dock shows report date, active section and reading progress;
- its menu navigates to all 15 sections without hiding report content or reloading the page.

## 3. Historical data strategy

### 3.1 Dual-track evidence model

The system never pretends a historical editorial judgment existed when no daily edition was published.

| Mode | Meaning | Use |
|---|---|---|
| `native_daily` | Judgment actually published in that day’s report | Highest-priority regime, catalyst, risk and signal evidence |
| `objective_market_reconstruction` | Deterministic reconstruction from dated market observations | Day-1 historical continuity and relative driver identification |
| `unavailable` | No reliable observation | Explicit gap; never guessed |

### 3.2 Stored source history

`docs/data/trends/market-history.json` retains 210 calendar days so a 30-day display window can use stable rolling normalisation.

Current source universe:

- S&P 500 — FRED `SP500`
- Nasdaq Composite — FRED `NASDAQCOM`
- VIX — FRED `VIXCLS`
- US 2Y Treasury Yield — FRED `DGS2`
- US 10Y Treasury Yield — FRED `DGS10`
- Brent — FRED `DCOILBRENTEU`
- Broad Trade-Weighted U.S. Dollar — FRED `DTWEXBGS`
- ICE BofA U.S. High Yield OAS — FRED `BAMLH0A0HYM2` when available

The latest native daily market tape may override the same date’s FRED value where the report has a more current verified snapshot. The override is recorded in provenance.

### 3.3 Reconstruction method

For each market session, the builder calculates:

- one-session percentage moves for price indices and commodities;
- one-session basis-point moves for yields and spreads;
- rolling 20-session realised dispersion;
- five-session movement for regime and signal context;
- Nasdaq relative movement versus S&P 500.

The three largest distinct standardised moves become that session’s reconstructed Top 3 market drivers. The internal standardisation is used only for rank ordering and evidence-strength bands; the numeric score is not published.

Historical labels describe observed price behaviour, for example:

- `US 10Y收益率单日上行 +12.4bp`
- `Brent单日上涨 +3.1%`
- `Nasdaq相对S&P 500跑输 -0.8个百分点`

They do not claim a specific news cause unless a native daily report supplies that cause.

## 4. Stable taxonomy

The registry uses eight categories:

1. `growth_macro`
2. `inflation_rates`
3. `central_banks_fiscal`
4. `earnings_ai_semis`
5. `geopolitics_energy`
6. `china_trade_policy`
7. `liquidity_credit_financing`
8. `market_structure`

Initial stable themes include:

- equity risk appetite
- volatility / event risk
- global duration / term premium
- Fed policy-path repricing
- energy inflation
- dollar financial conditions
- credit conditions
- growth-duration rotation
- geopolitical energy disruption
- AI earnings / capex validation
- market structure / passive flow

Future daily research should supply explicit `theme_id` values when possible. The builder retains deterministic keyword fallback for legacy reports.

## 5. Derived contract

`docs/data/trends/rolling-30d.json` is the single rendering source for the homepage P0 layer and `trends.html`.

Core fields:

```json
{
  "as_of": "YYYY-MM-DD",
  "window_start": "YYYY-MM-DD",
  "window_end": "YYYY-MM-DD",
  "coverage": {},
  "current": {},
  "days": [],
  "regime_transitions": [],
  "persistent_themes": [],
  "cross_asset_validation": {},
  "asset_series": [],
  "theme_registry": {},
  "provenance": {}
}
```

The browser never loads 30 full daily JSON files to calculate trends. It loads one lightweight, precomputed snapshot.

## 6. Regime logic

Allowed overall regimes remain:

- `risk_on`
- `neutral`
- `risk_off`
- `event_risk`

Native daily regime overrides reconstruction for the same date.

Reconstructed regime uses transparent directional conditions:

- Event Risk: multiple unusually large cross-asset shocks, or one high shock accompanied by broad risk-off confirmation.
- Risk-Off: negative five-session equity movement with higher volatility, or a material rates/energy tightening shock.
- Risk-On: positive five-session Nasdaq movement, lower volatility and no material long-rate tightening.
- Neutral: none of the above.

The website displays the state, not a synthetic decimal score.

## 7. Six-signal matrix

Signals are stored independently:

- Growth
- Inflation
- Rates
- Earnings
- Liquidity
- Geopolitics

For historical reconstruction they are explicitly market proxies:

- Growth: five-session S&P 500 / Nasdaq direction
- Inflation: five-session Brent direction
- Rates: five-session US 10Y move
- Earnings: Nasdaq relative to S&P 500
- Liquidity: broad USD and US 2Y combination
- Geopolitics: joint VIX and Brent stress proxy

Native daily Signal Panel values take precedence.

## 8. Cross-asset validation

Each theme has an expected-move map. Example:

```text
Geopolitical energy disruption
Brent ↑
US 10Y ↑
VIX ↑
Nasdaq ↓
```

Latest market moves are classified as confirming, diverging or unavailable. Tolerance bands prevent an immaterial move from being shown as confirmation.

The panel always includes:

- current theme
- current narrative
- confirming assets
- diverging assets
- unavailable evidence
- what would invalidate or flip the narrative
- a warning that co-movement does not prove causality

## 9. UX design

### 9.1 Daily homepage

The homepage adds two permanent, always-visible blocks:

1. 30D Market Lens preview
2. Cross-Asset Confirmation

They are inserted after `What Changed Since Yesterday`, before forward-looking event sections. Neither block collapses or hides the daily report.

### 9.2 Dedicated 30D page

Desktop:

- dense editorial grid;
- full-width regime ribbon;
- 6 × N signal matrix;
- SVG catalyst map by category/date;
- lifecycle table;
- separate asset trend cards.

Mobile:

- regime cells wrap vertically;
- signal matrix becomes five-session week cards;
- catalyst map becomes weekly date lists;
- lifecycle table becomes stacked labelled records;
- asset charts remain separate cards;
- no page-level horizontal overflow.

### 9.3 Visual language

The page retains the existing WSJ-aligned system:

- warm paper background;
- near-black editorial text;
- serif analysis headlines;
- sans-serif and mono data labels;
- thin rules and restrained burgundy accent;
- muted semantic states;
- no gradients, glassmorphism or marketing hero art.

## 10. Publishing workflow

### Stored-data refresh

`.github/workflows/trends-refresh.yml` runs:

- on manual dispatch;
- on scheduled weekday refresh;
- after a daily JSON publication.

It refreshes FRED data, rebuilds the rolling snapshot, validates it and commits only changed trend data.

### Pages deployment

The Pages workflow:

1. checks out the repository;
2. refreshes the Market Lens with network fallback to stored history;
3. runs publication, frontend and Market Lens gates;
4. performs a headless-browser smoke test;
5. deploys `/docs` only after all gates pass.

### Failure behaviour

- A FRED endpoint failure falls back to the last committed valid series.
- A P0 homepage script failure leaves the existing daily report untouched.
- `rolling-30d.json` must match `latest.json.date`; stale snapshots fail the gate.
- Pages is not deployed if the source bundle or browser smoke test fails.

## 11. Quality gates

The Market Lens gate verifies:

- exact 30-calendar-day window;
- minimum Day-1 session coverage;
- at least one native daily edition;
- explicit reconstructed provenance;
- no future dates;
- valid regime codes and theme IDs;
- one to three catalysts per market session;
- complete six-signal rows;
- unique dates;
- lifecycle integrity;
- at least five separate asset series;
- 150+ retained history days;
- no `risk_score` or `composite_score` fields;
- required homepage and trends-page renderers;
- responsive mobile contract;
- production version marker.

The browser smoke test verifies the rendered DOM, not only source syntax:

- daily homepage report loads;
- 30D preview and cross-asset panel render;
- 15 section navigation remains present;
- trends page renders regime, signal, catalyst, lifecycle and asset views;
- desktop and 390px mobile screenshots complete;
- no page-level horizontal overflow.

## 12. Future daily authoring requirements

For best continuity, future Top Catalysts and Top Risks should include optional metadata:

```json
{
  "theme_id": "global_duration",
  "category": "inflation_rates",
  "continuity": "escalating"
}
```

The site remains backward-compatible if those fields are absent, but explicit identifiers reduce title-based ambiguity and improve lifecycle accuracy.
