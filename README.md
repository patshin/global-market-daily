# Global Market Daily

A source-backed Chinese institutional market-intelligence publication covering global macro, U.S. equities and Nasdaq, AI and semiconductors, rates, FX, commodities, regional policy, geopolitics and the next 24–72 hours of catalysts.

The live site is an editorial dashboard with a warm-paper visual system, serif-led analysis, sans-serif market data, fine rules and restrained burgundy accents.

## Production architecture

```text
09:00 / 18:00 SGT connected scheduled agent
        ↓ independent web research and source verification
standalone cycle prompt + canonical renderer contract
        ↓
daily JSON → Markdown → sources → derived data → archive when eligible
        ↓
latest.json updated last
        ↓
GitHub Actions quality gates
        ↓
GitHub Pages deployment
        ↓
real Chromium desktop/mobile verification
```

GitHub Actions does **not** generate the report and does not call an LLM. It validates, derives existing trend products, deploys Pages, checks the public browser result and detects missing scheduled publications.

## Twice-daily schedule

- **09:00 Asia/Singapore** — `morning`; full provisional edition, visible as latest, excluded from formal archive and native 30D history.
- **18:00 Asia/Singapore** — `close`; independently researched final edition, formal archive entry and native 30D observation.

Canonical task definitions:

- `prompts/automation-registry.json`
- `prompts/automation-morning.md`
- `prompts/automation-close.md`

Both cycle prompts are complete and standalone. They must not rely on conversation history, another prompt or unstated context.

## Repository structure

```text
docs/
  index.html
  trends.html
  assets/
    app.js
    publication-compat.js
    editorial-v2.js
    styles.css
    editorial-v2.css
    p0.js
    trends.js
    market-lens.css
  data/
    latest.json
    archive.json
    daily/YYYY-MM-DD.json
    sources/YYYY-MM-DD.json
    trends/
  reports/YYYY/MM/YYYY-MM-DD.md
  product/

prompts/
  global-market-daily-master.md
  automation-morning.md
  automation-close.md
  automation-registry.json

schemas/
  daily.schema.json

scripts/
  validate_publish_v2.py
  validate_live_contract.py
  validate_archive_live_contract.py
  validate_frontend.py
  validate_editorial_ui.py
  validate_automation_contract.py
  validate_market_lens.py
  verify_scheduled_publication.py

.github/workflows/
  quality.yml
  pages.yml
  site-health.yml
  editorial-health.yml
  publication-watchdog.yml
  trends-refresh.yml
```

## Publication transaction

The write order is fixed:

1. `docs/data/daily/YYYY-MM-DD.json`
2. `docs/reports/YYYY/MM/YYYY-MM-DD.md`
3. `docs/data/sources/YYYY-MM-DD.json`
4. trend-derived data and necessary indexes
5. `docs/data/archive.json` only for the final close edition
6. `docs/data/latest.json` last

A provisional morning edition may be the live `latest` without appearing in formal `archive.json`.

## Core data and renderer contract

The website renders directly from daily JSON. Nested keys used by the browser are an API, not writing suggestions. In particular:

- `signal_panel` has exactly six canonical dimensions and separates current state, previous state, change reason and evidence without repeating the same sentence.
- `scenario_matrix` uses canonical expected-reaction, sensitive-assets, confirmation and invalidation fields.
- `next_catalyst.watch_first` contains two or three concrete monitoring instructions.
- repeated events, including earnings, are arrays and are never reduced to a single-company slot.
- future releases retain `actual: "待公布"`.
- unavailable values are marked `尚无法可靠确认`; they are not invented to fill a UI.

## Validation

The main gates run automatically on `main` and can also be run locally:

```bash
python3 scripts/validate_publish_v2.py --root .
python3 scripts/validate_live_contract.py --root .
python3 scripts/validate_archive_live_contract.py --root .
python3 scripts/validate_frontend.py --root .
python3 scripts/validate_editorial_ui.py --root .
python3 scripts/validate_automation_contract.py --root .
python3 scripts/validate_market_lens.py
```

Deployment is allowed only after deterministic validation succeeds. Public health then executes the real site JavaScript in Chromium. The editorial browser gate checks six signal cards, nonduplicative evidence, two or three Watch First items and no horizontal overflow at desktop and mobile widths.

## Local preview

```bash
python3 -m http.server 8000 --directory docs
```

Open `http://localhost:8000` rather than double-clicking the HTML file, because the application fetches JSON.

## Editorial rules

Primary sources take priority. Major events require a primary source plus independent high-quality confirmation when available. Market pricing is not an official policy decision. Announcement, implementation and effective dates are distinct. Article time and actual event time are distinct. Every important claim is traceable to the source archive.

This publication is market intelligence, not investment advice.
