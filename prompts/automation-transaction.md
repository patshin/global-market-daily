# GMD Scheduled Publication Transaction v1.2

This transaction contract is authoritative for ChatGPT-native scheduled runs and **supersedes any conflicting direct-to-main / wait-for-CI wording** in `automation-morning.md` or `automation-close.md`.

## Goal

Keep the ChatGPT scheduled run bounded without submitting a candidate that is already known to fail deterministic repository gates. ChatGPT owns research, creation of a complete candidate publication bundle and a Quality-parity preflight. GitHub owns authoritative validation, promotion to `main`, derived-data refresh, Pages deployment and public health checks after the candidate PR exists.

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
7. **Run a Quality-parity deterministic preflight before opening or updating the publication PR.** This is stronger than a subjective content review and is mandatory.
   - Read the current `main` version of `.github/workflows/quality.yml` immediately before preflight. Treat that workflow as the authoritative list of deterministic candidate gates.
   - Read every validator/contract currently invoked by Quality. At minimum this includes `scripts/validate_publish_v2.py`, the schema validator and `schemas/daily.schema.json`, `scripts/validate_frontend.py`, `scripts/validate_live_contract.py`, `scripts/validate_archive_live_contract.py`, `scripts/validate_market_lens.py`, `scripts/validate_automation_contract.py`, and `scripts/validate_market_tape_coverage.py`. If `quality.yml` later adds or replaces a gate, the scheduled publisher must follow the current workflow rather than this static list.
   - When the execution environment can run the repository validators against the complete candidate tree, run them. When it cannot, read the current validator source and mirror its candidate-relevant assertions directly. Do not infer thresholds from memory.
   - In particular, inspect all frontend-visible minimum-length and shape assertions in `scripts/validate_frontend.py` for thesis, narrative, Market Tape fields, `what_changed`, all three `top_catalysts`, six signal cards, scenario matrix, exactly three risks, `next_catalyst.watch_first`, section summaries/paragraphs and any later-added renderer-visible fields. A field that is non-empty but below the current minimum length is still a blocking thin-field failure.
   - `docs/data/daily/YYYY-MM-DD.json` must contain a non-empty `sources_path` equal to `data/sources/YYYY-MM-DD.json`, and that target must be a JSON file in the candidate branch.
   - `docs/data/latest.json` must contain valid `daily_json_path`, `report_path`, and `sources_path` values resolving under `docs/`.
   - Daily JSON, Markdown, source archive and `latest.json` must agree on the publication date and edition semantics before PR creation.
   - Close must contain exactly one same-date formal archive record; Morning must remain isolated from formal archive/native 30D semantics.
   - Market Tape coverage must satisfy the current `scripts/validate_market_tape_coverage.py` contract or be marked exactly as the repository contract requires when a target cannot be met without fabrication.
   - Treat a missing/empty path field, a path resolving to a directory, a missing target file, an unresolved source reference, a malformed required array/object, or any known deterministic Quality failure as a blocking candidate error.
   - Fix all deterministically repairable thin/malformed fields on the same idempotent candidate branch before PR creation/update. **Never lower repository gate thresholds and never knowingly submit a candidate that the current deterministic Quality Gate will reject.**
8. Open exactly one PR to `main` with title:
   - `GMD Publish YYYY-MM-DD Morning`
   - `GMD Publish YYYY-MM-DD Close`
   The PR branch must start with `publish/gmd-`.
9. **Do not wait synchronously for CI, merge, Pages or public browser checks.** The scheduled task ends successfully once the complete PR exists and its head SHA is recorded. Waiting for downstream infrastructure inside the ChatGPT task risks task timeout.
10. GitHub `Publication Quality Gate` remains authoritative and runs on the PR even after Quality-parity preflight. `.github/workflows/publication-promote.yml` automatically merges only successful `publish/gmd-*` PRs whose head SHA matches the validated run. A failed gate leaves the PR open and keeps `main` unchanged.
11. After merge, GitHub owns the full downstream chain. This handoff is intentionally explicit rather than dependent on recursive `push` events:
    - `publication-promote.yml` dispatches `trends-refresh.yml` on `main`;
    - `trends-refresh.yml` rebuilds/validates 30D derived data, commits it when changed, then dispatches `pages.yml`;
    - successful Pages deployment triggers Public Site Health and Editorial UI Health through their existing `workflow_run` hooks.
    Keep these `workflow_dispatch` handoffs intact: a merge or commit authored with the repository `GITHUB_TOKEN` must not be assumed to trigger another push-based workflow.
12. Never bypass the chain by pushing a scheduled publication directly to `main`.

## Failure safety

- If research or candidate construction fails: do not open a PR.
- If Quality-parity candidate preflight fails: fix within the one branch or leave it unpromoted; never touch `main`.
- If PR Quality still fails despite preflight: do not merge manually from a scheduled task. Leave the PR as a diagnostic artifact. The failure must be treated as evidence that preflight and CI are out of parity and the contract should be repaired rather than bypassed.
- If a prior same-date/cycle PR exists, update/reuse it rather than creating a new attempt PR.
- Never advance production `main` from a partial branch.
- The twice-daily publication watchdog must verify both repository state and the public Pages state. If repository state is current but public Pages is stale, it may dispatch the recovery chain and must fail visibly so the incident is not silent. The watchdog does not justify bypassing an editorial Quality failure.

## Run receipt

Before the ChatGPT task exits, report/store at minimum:
- scheduled_for_sgt
- started_at_sgt
- research_cutoff_sgt
- candidate_branch
- candidate_head_sha
- pr_number / pr_url
- data-quality coverage summary
- Quality-parity preflight result
- status = `SUBMITTED_FOR_VALIDATION`

`PUBLISHED` is reserved for GitHub/public-health confirmation, not merely PR creation.
