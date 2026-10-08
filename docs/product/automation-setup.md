# Global Market Daily — Morning-Only Production Automation

## Authoritative architecture

One **connected scheduled-agent task** independently researches and submits the full official daily edition. GitHub Actions does not call a research model and does not require an OpenAI API key. Its responsibilities are deterministic validation, guarded candidate promotion, trend derivation, GitHub Pages deployment, public-browser verification and missing-publication watchdog checks.

The repository is `patshin/global-market-daily`, production branch is `main`, Pages source is `docs/`, and public site is `https://patshin.github.io/global-market-daily/`.

The machine-readable schedule and canonical prompts are:

- `prompts/automation-registry.json`
- `prompts/automation-morning.md`, the full standalone execution prompt
- `prompts/automation-transaction.md`, candidate and downstream handoff contract

The scheduler must embed the complete morning prompt, without depending on chat history, earlier messages, a shared master prompt or undocumented context. `prompts/automation-close.md` is a retired historical reference and must not be installed as an active task.

## Production schedule, effective 2026-10-08

| Task | Asia/Shanghai / Beijing | UTC cron reference | Mode | Live status | Formal archive | Native 30D |
|---|---:|---:|---|---|---|---|
| Morning | 09:00 daily | `0 1 * * *` | `morning` | official/final | yes | yes, if contemporaneous |

There is no evening schedule, no evening watchdog expectation and no need to wait for an evening final. Weekends and market holidays are included. The schema and renderer retain `Asia/Singapore` and SGT-named fields, which represent the same UTC+08:00 wall-clock time. The scheduler uses `Asia/Shanghai`. Real start/cutoff and planned run time must be recorded separately.

When migrating an existing scheduler, reuse/update the matching morning task instead of creating a duplicate. The old evening task must be disabled or removed only under the user's schedule-change authorization, then the actual scheduler state must be verified. Updating this repository alone is not proof that a remote schedule was changed or will run. A write failure never authorizes silently pausing, deleting or recreating tasks.

## Publication transaction

Prepare the complete candidate tree in this order:

1. `docs/data/daily/YYYY-MM-DD.json`
2. `docs/reports/YYYY/MM/YYYY-MM-DD.md`
3. `docs/data/sources/YYYY-MM-DD.json`
4. existing required derived trend/index data
5. `docs/data/archive.json`, exactly one same-date official morning entry
6. `docs/data/latest.json` last

The current daily edition uses `edition_status="official"`, `publication_cycle.cycle="morning"`, `publication_cycle.status="official"`, `publication_cycle.is_final=true`, `publication_cycle.archive_eligible=true`, and native eligibility true for genuine contemporaneous research. Retrospective reconstructions remain native-ineligible. Preserve historical pre-policy provisional and fallback metadata.

Use a single idempotent branch `publish/gmd-YYYY-MM-DD-morning` and PR `GMD Publish YYYY-MM-DD Morning`. Reuse them on retry. The candidate includes all publication artifacts and passes a current Quality-parity preflight, including canonical Markdown exact-string parity, before the PR is created or updated. Never push scheduled publication directly to main. Re-read main, reject stale/downgrading transitions and pin the validated head before promotion. A matching already-merged official edition is an idempotent no-op; official corrections require separate reviewed authorization.

The scheduled task reports `SUBMITTED_FOR_VALIDATION` with the PR URL/head and exits without synchronously waiting for CI. GitHub owns authoritative Quality, guarded promotion, independent Pages and trend dispatch, and explicit post-deploy `site-health.yml` / `editorial-health.yml` dispatch. `latest.json` must never point at an incomplete or contract-invalid bundle.

## Required gates

Before a candidate is submitted and before production latest advances, validate the daily schema, renderer contract, source integrity, exact cross-file canonical literals, future-event status, final/archive/native provenance and stale-transition checks against the current `.github/workflows/quality.yml`. Never lower thresholds or knowingly submit a deterministic failure.

After deployment, a real Chromium run must verify that JavaScript renders the current date and thesis, the report shell is visible, the error state is hidden, all six editorial signal cards are complete and nonduplicative, `What I Would Watch First` contains two or three instructions, and desktop/mobile viewports have no horizontal overflow. Only verified downstream evidence permits `PUBLISHED_AND_VERIFIED`.

## Watchdogs and independent lens recovery

`.github/workflows/publication-watchdog.yml` makes two checks after the one expected morning window: **09:45 and 10:10 Beijing / SGT** (`01:45` and `02:10 UTC`). These are health/recovery passes, not additional publications. It verifies repository and public Pages state and does not generate research. It fails visibly when the expected official morning is missing, stale, late, in the wrong cycle, contract-invalid, incorrectly archived or incorrectly admitted to native history. It must not require an 18:00 edition.

Core report freshness and derived lens freshness are separate checks. A delayed provider observation or delayed 30D refresh must not be described as a missing core report; lens recovery may dispatch independently. No provider gaps may be replaced with fabricated observations.

`.github/workflows/editorial-health.yml` also runs after a successful Pages deployment and performs scheduled browser health checks. Deployment success alone does not establish fresh research.

## Historical and failure safeguards

Pre-2026-10-08 provisional mornings, independent close editions and Morning Fallback Final records keep their original meaning. Lossless fallback recovery, if separately authorized, is restricted to existing validated pre-policy snapshots and requires no valid matching Close PR. Historical reconstruction always carries an actual reconstruction timestamp, historical cutoff and evidence gaps, remains visibly labeled and is excluded from native 30D, even when official/archive eligible.

Research, verification, preflight or GitHub write failure leaves the candidate unpromoted and reports the exact blocked stage. A failed authoritative Quality gate leaves the PR open and main unchanged. HTTP 200 is not sufficient for success. If production has advanced to broken content, downstream recovery must restore a known-good state or repair and revalidate it before declaring recovery. Ordinary scheduled research does not authorize changes to product code or schedules.
