#!/usr/bin/env bash
set -euo pipefail

ROOT="${1:-.}"
PORT="${GMD_SMOKE_PORT:-8765}"
CHROME=""
for candidate in google-chrome google-chrome-stable chromium chromium-browser; do
  if command -v "$candidate" >/dev/null 2>&1; then
    CHROME="$(command -v "$candidate")"
    break
  fi
done

if [[ -z "$CHROME" ]]; then
  echo "No Chrome/Chromium binary found; source gates already passed, browser smoke skipped."
  exit 0
fi

TMP="$(mktemp -d)"
SERVER_PID=""
cleanup() {
  if [[ -n "$SERVER_PID" ]]; then kill "$SERVER_PID" >/dev/null 2>&1 || true; fi
  rm -rf "$TMP"
}
trap cleanup EXIT

python3 -m http.server "$PORT" --directory "$ROOT/docs" >"$TMP/server.log" 2>&1 &
SERVER_PID=$!
for _ in $(seq 1 30); do
  curl -fsS "http://127.0.0.1:${PORT}/data/trends/rolling-30d.json" >/dev/null && break
  sleep .2
done

render_dom() {
  local name="$1" url="$2" width="$3" height="$4"
  "$CHROME" \
    --headless=new \
    --no-sandbox \
    --disable-gpu \
    --disable-dev-shm-usage \
    --hide-scrollbars \
    --window-size="${width},${height}" \
    --virtual-time-budget=8000 \
    --dump-dom "$url" >"$TMP/${name}.html" 2>"$TMP/${name}.err"
  "$CHROME" \
    --headless=new \
    --no-sandbox \
    --disable-gpu \
    --disable-dev-shm-usage \
    --hide-scrollbars \
    --window-size="${width},${height}" \
    --virtual-time-budget=8000 \
    --screenshot="$TMP/${name}.png" "$url" >/dev/null 2>>"$TMP/${name}.err"
  test -s "$TMP/${name}.png"
}

render_dom daily-desktop "http://127.0.0.1:${PORT}/?qa=1" 1440 1600
render_dom daily-mobile "http://127.0.0.1:${PORT}/?qa=1" 390 844
render_dom lens-desktop "http://127.0.0.1:${PORT}/trends.html?qa=1" 1440 1600
render_dom lens-mobile "http://127.0.0.1:${PORT}/trends.html?qa=1" 390 844

for file in daily-desktop daily-mobile; do
  grep -q 'data-p0-ready="true"' "$TMP/${file}.html"
  grep -q 'id="market-lens-preview"' "$TMP/${file}.html"
  grep -q 'id="cross-asset-confirmation-preview"' "$TMP/${file}.html"
  grep -q 'id="reading-dock"' "$TMP/${file}.html"
  count="$(grep -o 'class="section-jump__button' "$TMP/${file}.html" | wc -l | tr -d ' ')"
  test "$count" -eq 15
  ! grep -qiE 'uncaught|syntaxerror|referenceerror|typeerror:' "$TMP/${file}.err"
done

for file in lens-desktop lens-mobile; do
  grep -q 'data-lens-ready="true"' "$TMP/${file}.html"
  grep -q 'class="regime-cell' "$TMP/${file}.html"
  grep -q 'signal-matrix__cell' "$TMP/${file}.html"
  grep -q 'catalyst-point' "$TMP/${file}.html"
  grep -q 'theme-table' "$TMP/${file}.html"
  grep -q 'class="asset-chart' "$TMP/${file}.html"
  ! grep -qiE 'uncaught|syntaxerror|referenceerror|typeerror:' "$TMP/${file}.err"
done

python3 - "$TMP" <<'PY'
from pathlib import Path
import re
import sys
root = Path(sys.argv[1])
for name in ("daily-mobile", "lens-mobile"):
    text = (root / f"{name}.html").read_text(encoding="utf-8", errors="ignore")
    assert "data-p0-ready=\"error\"" not in text
    assert "data-lens-ready=\"error\"" not in text
print("BROWSER SMOKE PASSED — desktop/mobile daily and 30D Lens rendered")
PY
