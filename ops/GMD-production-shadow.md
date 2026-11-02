# Read-only production shadow (v1)

Run **Actions → GMD Production Shadow — Read Only → Run workflow** on `main`.
This workflow runs as a **read-only 11:17 SGT diagnostic** (and by manual dispatch); it has **no production writes**.
It does not call AI services, create a candidate, recover a checkpoint, create a PR,
merge a report, or deploy Pages.

The run:

- inspects the exact same-date publish PR and its authoritative GitHub Quality outcome with a read-only Actions token, distinguishing missing candidate, pending/failing Quality and successful promotion;

- checks the repository's canonical latest/archive/daily consistency and distinguishes `CURRENT_NATIVE_OFFICIAL`, `CURRENT_HISTORICAL_BACKFILL_NOT_NATIVE` and `STALE_MAIN`;
- optionally compares Pages `latest.json` to main and distinguishes `PUBLIC_LAGS_MAIN` or `PUBLIC_DRIFT` from a consistent-but-stale public site;
- replays **every run command in the live `.github/workflows/quality.yml`** on the actual GitHub checkout, including real Chrome/Chromium; it refuses to omit mandatory validators or silently skip unknown formats;
- writes a structured, non-sensitive receipt plus separate command-output logs into an Actions artifact (not a private candidate checkpoint).

To run locally from a complete repo checkout:

```sh
python scripts/test_gmd_shadow_preflight.py
python scripts/gmd_shadow_preflight.py --root . --out /tmp/gmd-shadow --run-quality --check-public
```

If no complete checkout/Chromium is available, do **not** pretend these commands
passed. They must actually execute in the GitHub-hosted workflow.

## Publication boundary

This is stage 1 of the zero-extra-cost stabilisation plan. It does **not** replace
the existing ChatGPT 09:00 Morning Edition or 10:30 Recovery tasks. Both task IDs,
active state, schedule and prompts are unchanged. Do not add a second daily publisher.

A scheduled stale/non-native/publicly stale result fails visibly, while manual shadow runs may inspect known reconstructed data without claiming publication.

Stage 2 requires a real, approved model/data source and an authorized private
checkpoint destination that can be used by a full-repository runner. Until those
inputs exist, neither GitHub Actions nor a ChatGPT temporary shell can safely
produce and validate a new institutional-grade report unattended. Do not expose
API keys in workflow files, use login/session cookies as credentials, or enable
auto top-ups just to make the model work.

Stage 3 after an approved shadow implementation is to add a **single-producer**
engine with verified source data, the existing five-file bundle and private
checkpoint readback, original full preflight, one publish branch/PR per date,
fail-closed safety/permission classification, and exact public freshness checks.
Only after repeated green shadow runs and owner sign-off should the existing
09:00/10:30 workflow responsibility be changed; keep their IDs, timezone, times
and enabled status unchanged. Never backfill a retrospective report as native.
