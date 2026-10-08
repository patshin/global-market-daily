# Global Market Daily

A source-backed Chinese institutional market-intelligence publication covering global macro, U.S. equities and Nasdaq, AI and semiconductors, rates, FX, commodities, regional policy, geopolitics and the next 24–72 hours of catalysts.

The live site is an editorial dashboard with a warm-paper visual system, serif-led analysis, sans-serif market data, fine rules and restrained burgundy accents.

## Production architecture

```text
09:00 Beijing / SGT connected scheduled agent (morning only)
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

## Daily morning schedule

Effective **2026-10-08**, the only active publication is **09:00 Beijing time, Asia/Shanghai** every day (`01:00 UTC`). This is also 09:00 SGT; existing JSON `Asia/Singapore` and SGT-named fields remain unchanged for renderer compatibility.

- Mode: `morning`
- Status: official/final and the canonical daily edition
- Formal archive: exactly one entry for the date
- Native 30D: eligible when genuinely contemporaneous; retrospective reconstructions remain excluded
- Evening: retired, with no 18:00 publication or fallback expectation

Canonical task definitions:

- `prompts/automation-registry.json`
- `prompts/automation-morning.md` (complete standalone research and PR handoff prompt)
- `prompts/automation-transaction.md` (candidate transaction and downstream ownership)

`prompts/automation-close.md` is retained solely as a retired historical reference. The morning task does not depend on conversation history, a separate master prompt or an evening run.

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
5. `docs/data/archive.json`, with one same-date official morning entry
6. `docs/data/latest.json` last

The complete bundle is submitted on one idempotent `publish/gmd-YYYY-MM-DD-morning` PR after Quality-parity preflight; ordinary scheduled runs never push directly to `main`. The agent reports `SUBMITTED_FOR_VALIDATION` at PR handoff. GitHub validates and promotes the exact candidate head, deploys Pages and verifies the live result.

Pre-2026-10-08 provisional morning editions retain their historical meaning and may be absent from formal archive. The new policy does not relabel them or erase explicit Morning Fallback Final provenance.

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
python3 scripts/validate_editorial_ui.py .
python3 scripts/validate_automation_contract.py .
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


## Recovery and provenance

Historical backfills carry `reconstruction.is_reconstructed`, the actual reconstruction time, the historical information cutoff and explicit evidence gaps. They are displayed as historical backfills and counted separately from contemporaneous native daily reports. An unavailable historical fact must remain unavailable.

A delayed FRED release may leave fewer than three observed drivers or missing signal inputs. The lens exposes partial observation coverage and an unavailable regime rather than inventing a third catalyst or treating missing values as neutral. Run `python scripts/test_market_lens_native_accumulation.py` for offline regression coverage.

The legacy `scripts/scheduled_publish.py` API entrypoint is retired. Production research runs only through the connected scheduled-agent prompts. Core daily publication checks and derived lens freshness checks are separate; a delayed lens triggers its own refresh and must not be described as missing research. Scheduled promotion rejects stale dates and official-to-provisional downgrades, pins the validated head, and rechecks main before merge. A current official morning needs no evening final. Lossless historical fallback recovery is limited to pre-2026-10-08 snapshots and preserves their factual content and original cutoff.
