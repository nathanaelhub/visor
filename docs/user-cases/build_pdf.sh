#!/usr/bin/env bash
# Rebuild Visor-User-Cases.pdf from user-cases.html with headless Chrome. No npm or pip installs needed.
# Set CHROME=/path/to/chrome to pick a browser; otherwise the first one found below is used.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"

if [ -z "${CHROME:-}" ]; then
  for c in \
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
    "/Applications/Chromium.app/Contents/MacOS/Chromium" \
    "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser" \
    "$HOME"/Library/Caches/ms-playwright/chromium-*/chrome-mac*/"Google Chrome for Testing.app"/Contents/MacOS/"Google Chrome for Testing" \
    "$(command -v google-chrome || true)" "$(command -v chromium || true)"; do
    if [ -n "$c" ] && [ -x "$c" ]; then CHROME="$c"; break; fi
  done
fi
[ -n "${CHROME:-}" ] || { echo "No Chrome/Chromium found; set CHROME=/path/to/chrome" >&2; exit 1; }

"$CHROME" --headless --disable-gpu --no-pdf-header-footer --virtual-time-budget=8000 \
  --print-to-pdf="$here/Visor-User-Cases.pdf" "file://$here/user-cases.html" 2>/dev/null
echo "Wrote $here/Visor-User-Cases.pdf"
