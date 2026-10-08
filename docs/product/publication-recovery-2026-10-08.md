# 2026-10-08 publication incident and recovery

## What was verified

The production main branch remained at `4fd9098d68809fcfa873c4e1272df1c86a2e4d48`. Its latest edition was September 24 Morning (09:32 SGT), with formal archive and native 30D assessment through September 23. Daily/source/Markdown triplets exist continuously September 2–24. There were no older missing calendar dates in that range. September 14–23 were explicitly labeled Morning Fallback Final, not independently researched evening editions.

Missing publication records: September 25–October 7 (13 complete calendar dates), plus October 8 Morning. October 8 Close was not yet due when the audit began. An absent record does not prove that every scheduled invocation ran and failed.

## Separate failure mechanisms

1. **Research/publication handoff stopped.** The repository architecture delegates research to connected native scheduled agents at 09:00 and 18:00 Asia/Singapore, including weekends. GitHub Actions does not generate reports. Earlier run records reported a September 25 write security failure and a paused Morning task. That historical denial is not a currently reproduced GitHub permission failure: repair-branch creation, commit/ref update and draft PR creation succeeded on October 8. The accessible current scheduler listing returned no tasks; that does not prove tasks do not exist in another scope. Rebuilding the native schedules remains subject to the owner's confirmation.
2. **Partial official market releases broke 30D refresh.** [October 8 refresh run 37719946390](https://github.com/patshin/global-market-daily/actions/runs/37719946390) fetched data and built a lens, but validation required exactly three drivers for every date. Fresh retrieval reproduced the failing October 7 row: only Nasdaq and S&P observations had arrived in FRED; VIX, rates, Brent, broad USD and credit spread series lagged. Two genuine ranked drivers failed the fixed count. The workflow skipped committing all derived output.
3. **A successful deployment was mistaken for fresh content.** Refresh recovery dispatched Pages from unchanged main. Pages could successfully serve September's last valid files. Deployment success therefore did not establish either fresh research or successful derived-data refresh.
4. **Verification and instructions contained secondary defects.** A stale native-accumulation regression targeted a removed API and was not run in Quality. Close verification coupled core report existence with derived-lens completion. Standalone prompts conflicted with the transaction contract about waiting for 30D, and referenced a nonexistent market-tape validator. Old publication candidates had insufficient stale/latest downgrade protection. A retired API script retained obsolete publication semantics.

## Repairs

- Partial source releases now disclose available/missing observations. No artificial third catalyst is added. Missing signal inputs are `?`; incomplete coverage cannot be labeled a neutral regime. A descriptive historical editorial regime is unclassified rather than silently converted to Neutral.
- Native assessment, retrospective editorial reconstruction and deterministic price reconstruction have separate provenance and counts. The builder checks final/archive eligibility and membership. Original September 24 Morning factual content/cutoff was preserved exactly in a labeled Morning Fallback Final.
- Cross-asset confirmation no longer treats DXY as broad trade-weighted USD or Brent futures as EIA spot. A historical editorial snapshot cannot borrow later same-date U.S. closing observations when its own tape is unavailable.
- Core publication and derived freshness are checked separately, with an independent lens recovery dispatch. Candidate transition checks reject older latest pointers and official-to-provisional downgrades, pin the validated head and re-read main before promotion.
- Native prompts document bounded PR handoff, lossless historical Morning fallback, idempotence, truthful errors and no automatic schedule pausing. Actions remains validation/derivation/deployment only; no new credentials or API-based research service is introduced.
- Quality now runs accumulation/partial-release, transition, watchdog and reconstruction regression tests, plus real Chromium desktop/mobile rendering of the candidate tree.

## Backfill meaning and limitations

The missing original 09:00/18:00 publications and exact historical editorial judgments cannot be recovered from nonexistent repository files. Backfills are explicitly retrospective, record both the historical information cutoff and actual reconstruction time, and are excluded from contemporaneous native counts. At 18:00 SGT it is 06:00 EDT; same-calendar-day U.S. closing data or later U.S. releases must not leak into those editions.

Numeric recovery preserves instrument basis, uses prior U.S. sessions, computes returns within a consistent series and distinguishes primary Treasury/Cboe/AP evidence from secondary historical vendor references. Current downloadable historical data is not proof of the exact original vintage or SGT intraday snapshot. Conflicting continuous oil data is quarantined; futures roll dates and spot/futures differences are not hidden in return calculations. Auction when-issued yields/tails remain unavailable where official results do not supply them. Unrecovered institutional flows, ETF baskets/weights, dealer positioning and historical analyst consensus remain explicit evidence gaps rather than claims that no events occurred.

## Validation and release evidence

- Initial repair draft: [PR 39](https://github.com/patshin/global-market-daily/pull/39), head `f7b83fe1551cdf87276f439b1986e803fab31f29`.
- Initial Quality: [run 37738506314](https://github.com/patshin/global-market-daily/actions/runs/37738506314), successful. This predates final backfill integration and is not final release evidence.
- Local static publication, live/archive renderer, automation, editorial/frontend, 30D structure/freshness, Python/JavaScript syntax and targeted regression checks passed for the initial repair.
- Local subprocess Chromium was blocked by the execution sandbox's socket restriction, including an approved escalation. The PR candidate browser gate and post-deploy public browser health gates provide the required real-render evidence.
- Final backfill, exact final commit, current CI and public deployment verification are pending. A green initial draft does not mean the complete backfill is published.
