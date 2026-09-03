# Twice-Daily Research Automation Setup

The repository contains a scheduled workflow at `.github/workflows/daily-research.yml`.

## Schedule

- 09:00 Asia/Singapore — morning edition; visible as the current report but not added to the official daily archive.
- 18:00 Asia/Singapore — evening edition; overwrites the same date and becomes the sole official daily archive used by historical analysis.

GitHub Actions cron uses UTC:

- `0 1 * * *` = 09:00 SGT
- `0 10 * * *` = 18:00 SGT

## Required repository configuration

Open **Settings → Secrets and variables → Actions**.

### Repository secret

- `OPENAI_API_KEY` — a callable API key for the research model. Never commit this value to the repository.

### Repository variables

- `GMD_MODEL` — the exact model ID that is callable through the configured API account.
- `GMD_REASONING_EFFORT` — set to `xhigh` when supported by that model.

A label displayed in the ChatGPT web product is not automatically an API model ID. `GMD_MODEL` must use the exact ID exposed to the API account.

## Failure behavior

If either `OPENAI_API_KEY` or `GMD_MODEL` is missing, the scheduled run fails at the configuration preflight and does not modify `latest.json` or pretend that a report was published.

A complete run independently repeats web research, verification, all report modules, JSON/Markdown/source generation, quality validation and GitHub publication. The 18:00 run additionally rebuilds the official 30-day market history.
