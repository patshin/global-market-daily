# Global Market Daily — Twice-Daily Production Automation

## Authoritative architecture

Market research and publication are executed by two **connected scheduled-agent tasks**. GitHub Actions does not call a research model and does not require an OpenAI API key. Its responsibilities are deterministic validation, trend derivation, GitHub Pages deployment, public-browser verification and missing-publication watchdog checks.

The repository is `patshin/global-market-daily`, the production branch is `main`, the Pages source is `docs/`, and the public site is `https://patshin.github.io/global-market-daily/`.

The machine-readable schedule and prompt mapping live in:

- `prompts/automation-registry.json`
- `prompts/automation-morning.md`
- `prompts/automation-close.md`

The two prompt files are intentionally complete and standalone. A scheduler must use the complete prompt for its cycle; it must not depend on chat history, earlier messages, a shared master prompt or undocumented context.

## Production schedules

| Task | Asia/Singapore | UTC cron reference | Mode | Live status | Formal archive | Native 30D |
|---|---:|---:|---|---|---|---|
| Morning | 09:00 daily | `0 1 * * *` | `morning` | provisional | no | no |
| Close | 18:00 daily | `0 10 * * *` | `close` | official/final | yes | yes |

The close run is an independent research cycle. It must not merely edit the morning text.

## Publication transaction

A successful run writes in this order:

1. `docs/data/daily/YYYY-MM-DD.json`
2. `docs/reports/YYYY/MM/YYYY-MM-DD.md`
3. `docs/data/sources/YYYY-MM-DD.json`
4. existing derived trend/index data when required
5. `docs/data/archive.json` only for an archive-eligible close edition
6. `docs/data/latest.json` last

`latest.json` must never point at an incomplete or contract-invalid bundle.

## Required gates

Before `latest.json` advances, the generated edition must pass the daily schema, renderer contract, source integrity, cross-file consistency, future-event status and publication-cycle isolation checks.

After Pages deployment, a real Chromium run must verify that JavaScript renders the current date and thesis, the report shell is visible, the error state is hidden, all six editorial signal cards are complete and nonduplicative, `What I Would Watch First` contains two or three instructions, and neither the desktop nor mobile viewport has horizontal overflow.

## Watchdogs

`.github/workflows/publication-watchdog.yml` runs after the expected publication windows:

- 09:35 SGT for the morning edition
- 18:45 SGT for the close edition

The watchdog does not generate a report. It fails visibly when the expected connected-agent publication is missing, late, in the wrong cycle, contract-invalid, incorrectly archived or incorrectly admitted to native 30D history.

`.github/workflows/editorial-health.yml` runs after a successful Pages deployment and also performs a scheduled browser check.

## Credentials and ownership

Static Pages deployment requires no research-model secret. There must be no GitHub Actions workflow that calls the OpenAI API or another LLM to create the daily report.

The connected scheduled-agent environment owns research, reasoning, GitHub writes and the embedded standalone prompt. The repository owns the canonical prompt text, data contract, validators, deployment and watchdog evidence.

## Failure behavior

Research, source verification, contract validation, GitHub writes, deployment or browser rendering failure means the run is failed. Do not report success from an HTTP 200 response alone. If `latest.json` has already advanced to a broken publication, restore the last known-good live state or repair and revalidate it before declaring recovery.
