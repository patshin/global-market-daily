# Global Market Daily — Official Morning Publication Contract

## Effective schedule and ownership

Effective **2026-10-08**, publish once every day at **09:00 Beijing time, Asia/Shanghai** (`01:00 UTC`, also `09:00 SGT`). There is no active evening schedule and no expected evening final. Weekends and market holidays remain publication days; use the latest verified market close with an explicit session and timestamp.

The connected scheduled agent independently researches, verifies and analyzes the complete edition. GitHub Actions does not call an LLM and needs no research-model API key. It owns authoritative validation, promotion, deterministic derivation, Pages deployment, browser health and missing-publication detection.

The canonical standalone prompt is `prompts/automation-morning.md`. `prompts/automation-registry.json` describes the one active task; `prompts/automation-transaction.md` defines the bounded candidate-PR handoff. `prompts/automation-close.md` is retired historical reference.

## Data and archive semantics

For a genuinely contemporaneous morning edition dated on or after 2026-10-08:

- `edition="Morning Official"` and `edition_status="official"`;
- `publication_cycle.status="official"` and `publication_cycle.cycle="morning"`;
- `publication_cycle.is_final=true`;
- `publication_cycle.archive_eligible=true`;
- `publication_cycle.market_lens_native_eligible=true`;
- exactly one same-date formal archive record, plus the canonical daily/Markdown/source bundle and latest pointer.

The schema retains `timezone="Asia/Singapore"` and SGT-named fields for renderer compatibility. These use the same UTC+08:00 clock as Beijing; scheduler timezone is `Asia/Shanghai`. Keep actual start, actual research cutoff and scheduled time distinct. Never substitute the planned 09:00 time for delayed research completion.

Eligibility allows downstream native 30D accumulation; it does not assert that derived files are already refreshed. A valid core publication and a delayed lens are separate outcomes.

## Historical provenance

The effective-date change is not a historical rewrite. Preserve earlier provisional mornings, independent official close editions and explicit **Morning Fallback Final** records with their original factual content and cutoffs. A historical fallback is a lossless promotion of an already published morning snapshot, not independent evening research. Any separately authorized fallback recovery is restricted to dates before 2026-10-08 and must verify the absence of a valid matching Close PR.

Retrospective reconstructions must retain their visible historical-backfill label, `reconstruction.is_reconstructed=true`, actual reconstruction time, historical cutoff and evidence gaps. They remain `publication_cycle.market_lens_native_eligible=false`, including when their date is on or after the effective date and they are official/final and archive eligible. No label or schedule change may fabricate contemporaneous provenance.

## Atomic candidate and release evidence

Prepare daily JSON, canonical Markdown, sources, required derived/index files and archive before latest. Validate all paths, source IDs, renderer shapes, date/cycle/provenance consistency and exact JSON-to-Markdown canonical literals against current Quality gates. An incomplete or known-invalid candidate must never advance latest or main.

Use exactly one `publish/gmd-YYYY-MM-DD-morning` branch and one `GMD Publish YYYY-MM-DD Morning` PR per edition. Reuse it on retry, reject stale/latest downgrades, re-read main before handoff and treat an already merged matching official edition as an idempotent no-op. Same-date official corrections need separate reviewed authorization.

The scheduled agent exits at a complete validated PR with its head SHA and `SUBMITTED_FOR_VALIDATION` receipt. It does not wait synchronously for CI or push directly to main. GitHub validates and promotes only the validated unchanged candidate head, explicitly dispatches derivation/deployment/health, and reserves `PUBLISHED_AND_VERIFIED` for successful public real-browser verification. Preserve truthful failure stages; never pause or recreate schedules automatically because a write failed.
