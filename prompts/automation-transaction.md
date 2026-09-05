# GMD Scheduled Publication Transaction v1.1

This transaction contract is authoritative for ChatGPT-native scheduled runs and **supersedes any conflicting direct-to-main / wait-for-CI wording** in `automation-morning.md` or `automation-close.md`.

## Goal

Keep the ChatGPT scheduled run bounded. ChatGPT owns research and creation of a complete candidate publication bundle. GitHub owns validation, promotion to `main`, derived-data refresh, Pages deployment and public health checks after the candidate PR exists.

## Required flow

1. At actual task start, record `scheduled_for_sgt` and `started_at_sgt`. Use the true research completion time as `research_cutoff_sgt` / `data_cutoff_sgt`; never substitute the scheduled time.
2. Read the applicable edition prompt (`automation-morning.md` or `automation-close.md`) plus current repository contracts before research.
3. Research and verify the full edition independently.
4. Use exactly **one idempotent publication branch** per date/cycle:
   - morning: `publish/gmd-YYYY-MM-DD-morning`
   - close: `publish/gmd-YYYY-MM-DD-close`
   Reuse/update that branch on retry; do not create `-1826`, `-1900`, `-retry2` variants.
5. Build the complete candidate bundle before repository writes. Prefer one Git tree/commit or the fewest possible commits. Do not serialize one commit per file when batching is available.
6. Candidate branch must already contain all user-authored publication artifacts needed for the edition, including `latest.json`. For close it must also contain the single formal archive entry for the date. Morning must remain excluded from formal archive. Derived 30D files may be rebuilt by GitHub after merge; the candidate must still carry all source fields needed for deterministic rebuilding.
7. Run fast deterministic preflight checks that can be completed inside the task. Fix thin or malformed content before opening the PR. Do not lower gate thresholds to make a candidate pass.
   - `docs/data/daily/YYYY-MM-DD.json` must contain a non-empty `sources_path` equal to `data/sources/YYYY-MM-DD.json`, and that target must be a JSON file in the candidate branch.
   - `docs/data/latest.json` must contain valid `daily_json_path`, `report_path`, and `sources_path` values resolving under `docs/`.
   - Daily JSON, Markdown, source archive and `latest.json` must agree on the publication date and edition semantics before PR creation.
   - Treat a missing/empty path field, a path resolving to a directory, or a missing target file as a blocking malformed-candidate error.
8. Open exactly one PR to `main` with title:
   - `GMD Publish YYYY-MM-DD Morning`
   - `GMD Publish YYYY-MM-DD Close`
   The PR branch must start with `publish/gmd-`.
9. **Do not wait synchronously for CI, merge, Pages or public browser checks.** The scheduled task ends successfully once the complete PR exists and its head SHA is recorded. Waiting for downstream infrastructure inside the ChatGPT task risks task timeout.
10. GitHub `Publication Quality Gate` runs on the PR. `.github/workflows/publication-promote.yml` automatically merges only successful `publish/gmd-*` PRs whose head SHA matches the validated run. A failed gate leaves the PR open and keeps `main` unchanged.
11. After merge, GitHub owns the full downstream chain. This handoff is intentionally explicit rather than dependent on recursive `push` events:
    - `publication-promote.yml` dispatches `trends-refresh.yml` on `main`;
    - `trends-refresh.yml` rebuilds/validates 30D derived data, commits it when changed, then dispatches `pages.yml`;
    - successful Pages deployment triggers Public Site Health and Editorial UI Health through their existing `workflow_run` hooks.
    Keep these `workflow_dispatch` handoffs intact: a merge or commit authored with the repository `GITHUB_TOKEN` must not be assumed to trigger another push-based workflow.
12. Never bypass the chain by pushing a scheduled publication directly to `main`.

## Failure safety

- If research or candidate construction fails: do not open a PR.
- If candidate preflight fails: fix within the one branch or leave it unpromoted; never touch `main`.
- If PR Quality fails: do not merge manually from a scheduled task. Leave the PR as a diagnostic artifact.
- If a prior same-date/cycle PR exists, update/reuse it rather than creating a new attempt PR.
- Never advance production `main` from a partial branch.
- The twice-daily publication watchdog must verify both repository state and the public Pages state. If repository state is current but public Pages is stale, it may dispatch the recovery chain and must fail visibly so the incident is not silent.

## Run receipt

Before the ChatGPT task exits, report/store at minimum:
- scheduled_for_sgt
- started_at_sgt
- research_cutoff_sgt
- candidate_branch
- candidate_head_sha
- pr_number / pr_url
- data-quality coverage summary
- status = `SUBMITTED_FOR_VALIDATION`

`PUBLISHED` is reserved for GitHub/public-health confirmation, not merely PR creation.
