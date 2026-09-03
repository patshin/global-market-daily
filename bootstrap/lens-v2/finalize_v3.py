#!/usr/bin/env python3
"""Idempotent production finalizer for the Global Market Daily P0 release."""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BOOT = ROOT / "bootstrap/lens-v2"
DOCS = ROOT / "docs"


def run(*args: str) -> None:
    subprocess.run(args, cwd=ROOT, check=True)


def copy(source: str, destination: str, executable: bool = False) -> None:
    src = BOOT / source
    dst = ROOT / destination
    if not src.exists():
        if dst.exists():
            return
        raise FileNotFoundError(f"Missing both source and destination for {destination}")
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)
    dst.chmod(0o755 if executable else 0o644)


def fix_fred_parser() -> None:
    for path in (BOOT / "build_market_lens.py", ROOT / "scripts/build_market_lens.py"):
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        if "date_column = next(" in text:
            continue
        pattern = re.compile(
            r'(?P<i>\s*)reader = csv\.DictReader\(body\.splitlines\(\)\)\n'
            r'(?P=i)value_column = next\(\(name for name in \(reader\.fieldnames or \[\]\) if name != "DATE"\), None\)\n'
            r'(?P=i)if not value_column:\n'
            r'(?P=i)    raise ValueError\(f"FRED response for \{series_id\} has no value column"\)\n'
            r'(?P=i)for row in reader:\n'
            r'(?P=i)    value = parse_number\(row\.get\(value_column\)\)\n'
            r'(?P=i)    if value is not None:\n'
            r'(?P=i)        rows\[row\["DATE"\]\] = value'
        )
        match = pattern.search(text)
        if not match:
            raise RuntimeError(f"Unable to patch FRED parser in {path}")
        i = match.group("i")
        replacement = (
            f'{i}reader = csv.DictReader(body.splitlines())\n'
            f'{i}fieldnames = reader.fieldnames or []\n'
            f'{i}date_column = next((name for name in fieldnames if name.lower() in {{"date", "observation_date"}}), fieldnames[0] if fieldnames else None)\n'
            f'{i}value_column = next((name for name in fieldnames if name != date_column), None)\n'
            f'{i}if not date_column or not value_column:\n'
            f'{i}    raise ValueError(f"FRED response for {{series_id}} has no date/value columns")\n'
            f'{i}for row in reader:\n'
            f'{i}    value = parse_number(row.get(value_column))\n'
            f'{i}    if value is not None and row.get(date_column):\n'
            f'{i}        rows[row[date_column]] = value'
        )
        path.write_text(text[:match.start()] + replacement + text[match.end():], encoding="utf-8")


def install_files() -> None:
    fix_fred_parser()
    copy("build_market_lens.py", "scripts/build_market_lens.py", True)
    fix_fred_parser()
    copy("validate_market_lens.py", "scripts/validate_market_lens.py", True)
    copy("validate_frontend_v2.py", "scripts/validate_frontend.py", True)
    copy("browser_smoke.sh", "scripts/browser_smoke.sh", True)
    copy("trends.html", "docs/trends.html")
    copy("trends.js", "docs/assets/trends.js")
    copy("p0.js", "docs/assets/p0.js")
    copy("market-lens.css", "docs/assets/market-lens.css")
    copy("theme-registry.json", "docs/data/trends/theme-registry.json")
    copy("market-lens.schema.json", "schemas/market-lens.schema.json")
    copy("30d-market-lens.md", "docs/product/30d-market-lens.md")


def integrate_existing() -> None:
    script = BOOT / "migrate_existing.py"
    if script.exists():
        run("python3", str(script))
    required = [
        DOCS / "index.html",
        DOCS / "assets/app.js",
        DOCS / "assets/p0.js",
        DOCS / "assets/trends.js",
        DOCS / "assets/market-lens.css",
        DOCS / "trends.html",
    ]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise RuntimeError(f"Missing integrated frontend files: {missing}")


def insert_once(path: Path, old: str, replacement_marker: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if replacement_marker in text:
        return
    if old not in text:
        raise RuntimeError(f"Cannot insert QA hook into {path}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def add_qa_hooks() -> None:
    insert_once(
        DOCS / "assets/trends.js",
        '    document.body.dataset.lensReady = "true";',
        "dataset.catalystQa",
        '''    document.body.dataset.lensReady = "true";
    requestAnimationFrame(() => {
      document.body.dataset.horizontalOverflow = String(document.documentElement.scrollWidth > window.innerWidth + 1);
      if (new URLSearchParams(window.location.search).get("qa") === "1") {
        const point = document.querySelector(".catalyst-point");
        if (point) point.dispatchEvent(new MouseEvent("click", { bubbles: true }));
        document.body.dataset.catalystQa = point && document.querySelector("#catalyst-detail h3") ? "passed" : "failed";
      }
    });''',
    )
    insert_once(
        DOCS / "assets/p0.js",
        '  document.body.dataset.p0Ready = "true";',
        "dataset.navigationQa",
        '''  document.body.dataset.p0Ready = "true";
  requestAnimationFrame(() => {
    document.body.dataset.horizontalOverflow = String(document.documentElement.scrollWidth > window.innerWidth + 1);
    if (new URLSearchParams(window.location.search).get("qa") === "1") {
      const button = document.querySelectorAll(".section-jump__button")[3];
      const pathBefore = window.location.pathname;
      if (button) button.click();
      document.body.dataset.navigationQa = button && window.location.pathname === pathBefore ? "passed" : "failed";
    }
  });''',
    )

    smoke = ROOT / "scripts/browser_smoke.sh"
    text = smoke.read_text(encoding="utf-8")
    if 'data-navigation-qa="passed"' not in text:
        text = text.replace(
            "  grep -q 'id=\"reading-dock\"' \"$TMP/${file}.html\"",
            "  grep -q 'id=\"reading-dock\"' \"$TMP/${file}.html\"\n  grep -q 'data-horizontal-overflow=\"false\"' \"$TMP/${file}.html\"\n  grep -q 'data-navigation-qa=\"passed\"' \"$TMP/${file}.html\"",
        )
        text = text.replace(
            "  grep -q 'class=\"asset-chart' \"$TMP/${file}.html\"",
            "  grep -q 'class=\"asset-chart' \"$TMP/${file}.html\"\n  grep -q 'data-horizontal-overflow=\"false\"' \"$TMP/${file}.html\"\n  grep -q 'data-catalyst-qa=\"passed\"' \"$TMP/${file}.html\"",
        )
        smoke.write_text(text, encoding="utf-8")


def append_structured_event_css() -> None:
    path = DOCS / "assets/market-lens.css"
    text = path.read_text(encoding="utf-8")
    marker = "Structured cross-section event collections retained from v1.3"
    if marker in text:
        return
    addition = r'''

/* Structured cross-section event collections retained from v1.3. */
.structured-event-collection { margin-top: 28px; }
.structured-event-group { margin-top: 26px; border-top: 1px solid var(--lens-ink); }
.structured-event-group__header { display: flex; justify-content: space-between; gap: 18px; align-items: baseline; padding: 10px 0; }
.structured-event-group__header h4 { margin: 0; font-family: var(--serif, Georgia, serif); font-size: 1.08rem; text-transform: none; letter-spacing: 0; }
.structured-event-group__header span { color: var(--lens-muted); font-family: var(--mono, monospace); font-size: .68rem; }
.structured-event { padding: 20px 0 24px; border-top: 1px solid var(--lens-hairline); }
.structured-event__header { display: flex; justify-content: space-between; gap: 24px; align-items: flex-start; }
.structured-event__eyebrow { color: var(--lens-accent); font-size: .69rem; font-weight: 800; letter-spacing: .055em; }
.structured-event h5 { margin: 5px 0 0; font-family: var(--serif, Georgia, serif); font-size: 1.12rem; line-height: 1.35; }
.structured-event__meta { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: 6px; }
.structured-event__chip { padding: 3px 6px; border: 1px solid var(--lens-hairline); color: var(--lens-charcoal); font-size: .68rem; }
.structured-event__time { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); margin-top: 13px; border-top: 1px solid var(--lens-hairline); border-left: 1px solid var(--lens-hairline); }
.structured-event__time-item { padding: 9px; border-right: 1px solid var(--lens-hairline); border-bottom: 1px solid var(--lens-hairline); }
.structured-event__time-item__label,
.structured-event__fact__label,
.structured-event__transmission__label,
.structured-event__assets-label { color: var(--lens-accent); font-size: .69rem; font-weight: 800; letter-spacing: .04em; text-transform: uppercase; }
.structured-event__time-item__value,
.structured-event__fact__value,
.structured-event__transmission__value { margin: 5px 0 0; color: var(--lens-charcoal); font-size: .86rem; line-height: 1.58; }
.structured-event__fact { padding: 12px 0; border-bottom: 1px solid var(--lens-hairline); }
.structured-event__transmission { margin: 14px 0; padding: 13px 15px; border-left: 4px solid var(--lens-accent); background: var(--lens-paper-deep); }
.structured-event__assets { padding: 4px 0 14px; }
.structured-event__assets-list { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 7px; }
.structured-event__empty { padding: 13px 0; color: var(--lens-muted); font-style: italic; }
@media (max-width: 900px) {
  .structured-event__header { display: block; }
  .structured-event__meta { justify-content: flex-start; margin-top: 10px; }
  .structured-event__time { grid-template-columns: 1fr; }
}
'''
    path.write_text(text.rstrip() + addition + "\n", encoding="utf-8")


QUALITY = r'''name: Publication Quality Gate
on:
  push:
    branches: [main]
  pull_request:
  workflow_dispatch:
permissions:
  contents: read
jobs:
  validate:
    name: Validate publication, Market Lens and rendered UX
    runs-on: ubuntu-latest
    timeout-minutes: 12
    steps:
      - uses: actions/checkout@v7
      - uses: actions/setup-python@v7
        with:
          python-version: "3.12"
      - run: python scripts/build_market_lens.py --root .
      - run: |
          python scripts/validate_publish.py --root .
          python scripts/validate_frontend.py --root .
          python scripts/validate_market_lens.py --root .
          node --check docs/assets/app.js
          node --check docs/assets/p0.js
          node --check docs/assets/trends.js
          python -m json.tool docs/data/trends/market-history.json >/dev/null
          python -m json.tool docs/data/trends/rolling-30d.json >/dev/null
          git diff --check
      - run: bash scripts/browser_smoke.sh .
'''

PAGES = r'''name: Deploy Global Market Daily
on:
  push:
    branches: [main]
    paths:
      - "docs/**"
      - "scripts/**"
      - "schemas/**"
      - ".github/workflows/pages.yml"
  workflow_dispatch:
permissions:
  contents: read
  pages: write
  id-token: write
concurrency:
  group: pages
  cancel-in-progress: false
jobs:
  validate:
    name: Build and validate publication bundle
    runs-on: ubuntu-latest
    timeout-minutes: 15
    steps:
      - uses: actions/checkout@v7
      - uses: actions/setup-python@v7
        with:
          python-version: "3.12"
      - run: python scripts/build_market_lens.py --root . --network
      - run: |
          python scripts/validate_publish.py --root .
          python scripts/validate_frontend.py --root .
          python scripts/validate_market_lens.py --root .
          node --check docs/assets/app.js
          node --check docs/assets/p0.js
          node --check docs/assets/trends.js
      - run: bash scripts/browser_smoke.sh .
      - uses: actions/upload-pages-artifact@v5
        with:
          path: ./docs
  deploy:
    name: Deploy GitHub Pages
    needs: validate
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/configure-pages@v6
      - id: deployment
        uses: actions/deploy-pages@v5
'''

REFRESH = r'''name: Refresh 30D Market Lens Data
on:
  push:
    branches: [main]
    paths:
      - "docs/data/daily/**"
      - "docs/data/latest.json"
  schedule:
    - cron: "30 4 * * 1-6"
  workflow_dispatch:
permissions:
  contents: write
concurrency:
  group: trends-refresh
  cancel-in-progress: false
jobs:
  refresh:
    runs-on: ubuntu-latest
    timeout-minutes: 12
    steps:
      - uses: actions/checkout@v7
        with:
          fetch-depth: 0
      - uses: actions/setup-python@v7
        with:
          python-version: "3.12"
      - run: python scripts/build_market_lens.py --root . --network
      - run: python scripts/validate_market_lens.py --root .
      - shell: bash
        run: |
          set -euo pipefail
          git config user.name "github-actions[bot]"
          git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
          git add docs/data/trends/market-history.json docs/data/trends/rolling-30d.json
          if git diff --cached --quiet; then exit 0; fi
          git commit -m "data: refresh 30-day market lens"
          git pull --rebase origin main
          git push origin HEAD:main
'''


def write_workflows() -> None:
    directory = ROOT / ".github/workflows"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "quality.yml").write_text(QUALITY, encoding="utf-8")
    (directory / "pages.yml").write_text(PAGES, encoding="utf-8")
    (directory / "trends-refresh.yml").write_text(REFRESH, encoding="utf-8")


def build_and_validate() -> None:
    run("python3", "scripts/build_market_lens.py", "--root", ".", "--network")
    run("python3", "scripts/validate_publish.py", "--root", ".")
    run("python3", "scripts/validate_frontend.py", "--root", ".")
    run("python3", "scripts/validate_market_lens.py", "--root", ".")
    run("node", "--check", "docs/assets/app.js")
    run("node", "--check", "docs/assets/p0.js")
    run("node", "--check", "docs/assets/trends.js")
    run("python3", "-m", "json.tool", "docs/data/trends/market-history.json")
    run("python3", "-m", "json.tool", "docs/data/trends/rolling-30d.json")
    run("python3", "-m", "json.tool", "schemas/market-lens.schema.json")


def main() -> None:
    install_files()
    integrate_existing()
    add_qa_hooks()
    append_structured_event_css()
    write_workflows()
    build_and_validate()
    print("P0 Market Lens v2 finalization passed deterministic gates")


if __name__ == "__main__":
    main()
