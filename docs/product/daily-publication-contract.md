# Global Market Daily — Twice-Daily Publication Contract

- Timezone: Asia/Singapore
- Morning edition: 09:00 SGT; refreshes the current website edition.
- Evening edition: 18:00 SGT; becomes the official daily archive for that date.
- Morning and evening runs independently repeat web research, verification, analysis, JSON, Markdown, sources and quality gates.
- The 18:00 edition overwrites the same date key and is the only edition retained in `archive.json` as the official daily record.
- A failed partial publication must not advance `latest.json`.
- GitHub Actions cannot invoke an interactive ChatGPT conversation. Automated research requires a callable model API credential in repository secrets.
- Model is configurable through repository variable `GMD_MODEL`; reasoning effort through `GMD_REASONING_EFFORT`.
