# Global Market Daily

A source-backed, Chinese-language institutional market intelligence publication covering global macro, U.S. equities, Nasdaq, AI and semiconductors, rates, FX, commodities, regional policy, geopolitics and the next 24–72 hours of catalysts.

The live site is designed as an **editorial institutional dashboard**: high information density, serif-led analysis, sans-serif market data, warm paper background, fine rules and restrained burgundy accents. It does not copy Wall Street Journal logos, proprietary fonts, code or brand assets.

## Publication architecture

```text
Research and verification
        ↓
docs/data/daily/YYYY-MM-DD.json
        ↓
docs/reports/YYYY/MM/YYYY-MM-DD.md
        ↓
docs/data/sources/YYYY-MM-DD.json
        ↓
docs/data/archive.json
        ↓
docs/data/latest.json  (updated last)
        ↓
GitHub Actions quality gate
        ↓
GitHub Pages deployment
```

The website renders from the daily JSON. Markdown is the human-readable long-term archive. The separate source archive preserves publication time, event time, retrieval time, source tier and confidence.

### Collection contract for repeated events

A numbered report section is a category, not a single-event slot. In particular, `sections.earnings.reported` and `sections.earnings.upcoming_72h` are unbounded arrays of independent company earnings events. The renderer and validators must iterate every event and must never assume a single company at index `0`. The same collection principle applies to central banks, geopolitics, auctions, index changes and financing events; only `top_catalysts` is deliberately capped at three.

## Repository structure

```text
docs/
  index.html
  trends.html
  .nojekyll
  assets/
    styles.css
    app.js
    p0.js
    trends.js
    market-lens.css
  data/
    latest.json
    archive.json
    daily/YYYY-MM-DD.json
    sources/YYYY-MM-DD.json
    runs/YYYY/MM/YYYY-MM-DD-{0900|1800}*.json
    trends/
      market-history.json
      rolling-30d.json
      verified-events.json
      theme-registry.json
  reports/YYYY/MM/YYYY-MM-DD.md

prompts/
  global-market-daily-master.md

schemas/
  daily.schema.json

scripts/
  generate_daily_update.py
  build_market_lens.py
  validate_publish.py
  validate_frontend.py
  validate_market_lens.py

.github/workflows/
  daily-market-update.yml
  trends-refresh.yml
  quality.yml
  pages.yml
  site-health.yml
```

## Deterministic release gate

Run locally:

```bash
python3 scripts/validate_publish.py --root .
```

The gate fails when, among other checks:

- JSON is invalid or a date does not match its filename.
- the 15-section contract is incomplete or out of order.
- a future event contains an `Actual` value other than `待公布`.
- a source ID is missing or unresolved.
- daily JSON, source JSON and Markdown disagree on required content.
- `archive.json` contains duplicate dates or is not newest-first.
- `latest.json` points to a missing or non-latest edition.
- unresolved template placeholders remain.

The validator uses the Python standard library only and does not require network access.

## GitHub Actions

`Publication Quality Gate` runs on pushes and pull requests.

`Deploy Global Market Daily` validates the full publication bundle, uploads `docs/` as the Pages artifact and deploys only after validation passes.

For the first deployment, GitHub may require one repository setting:

1. Open **Settings → Pages**.
2. Under **Build and deployment**, choose **GitHub Actions** as the source.

No repository secret is required for static deployment. Automated research publication additionally requires `OPENAI_API_KEY`.

## Twice-daily research automation

The production workflow is scheduled every day at:

- **09:00 Asia/Singapore** — full morning edition; visible on the website but provisional for historical trend purposes.
- **18:00 Asia/Singapore** — full evening final edition; overwrites the same date key and becomes the canonical daily archive and native 30D Market Lens observation.

Both runs independently research and verify every required module. The runner uses the OpenAI Responses API with web search, model `gpt-5.6-sol`, and reasoning effort `xhigh`.

One repository secret is required:

```text
OPENAI_API_KEY
```

Configure it under **Settings → Secrets and variables → Actions → New repository secret**. Optional project or organization scoping can be supplied with `OPENAI_PROJECT_ID` and `OPENAI_ORG_ID`.

The workflow fails closed when credentials, research, JSON validation, source resolution, trend rebuilding, or publication gates fail. The 18:00 run is the only new native observation admitted to historical trend analysis; the 09:00 snapshot remains preserved under `docs/data/runs/` for audit.

## Local preview

Because the site fetches JSON, open it through a local HTTP server rather than double-clicking `index.html`:

```bash
python3 -m http.server 8000 --directory docs
```

Then visit `http://localhost:8000`.

## Editorial and data rules

- Primary sources take priority.
- Major events should have a primary source plus independent high-quality confirmation, or two independent high-quality sources.
- `Market Pricing` is never written as an official central-bank decision.
- announcement, implementation and effective dates are distinct.
- article time and actual event time are distinct.
- future data always uses `Actual: 待公布`.
- unavailable data is written as `尚无法可靠确认`; it is never estimated to make a table look complete.
- every market price carries an `as_of` and status.
- the report is market intelligence, not investment advice.

## Commit convention

```text
site: initialize global market daily
daily: publish market brief YYYY-MM-DD
daily: refresh market brief YYYY-MM-DD
```

## License and source rights

The repository contains original analysis and presentation code. Linked source content remains the property of its respective publisher. Do not republish paywalled articles or large verbatim excerpts.
