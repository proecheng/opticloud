#!/usr/bin/env bash
# Story 0.13 — Redact sk-XXX API keys from Playwright artifacts before CI upload
# (Round 2 S2 fix).
#
# Replaces any `sk-[A-Za-z0-9_-]{30,}` pattern with `sk-REDACTED` in:
# - test-results/**/*.json (Playwright trace metadata)
# - test-results/**/*.txt
# - playwright-report/**/*.html
# - playwright-report/**/*.json
#
# Note: PNG screenshots and WebM videos cannot be text-replaced.
# Those will show masked keys (the web app shows `sk-XXX_•••` by default
# when `revealed=false`; reveal toggle would only persist in trace if user clicked it).

set -euo pipefail

REGEX='sk-[A-Za-z0-9_-]\{30,\}'
REPL='sk-REDACTED'

ROOT="${1:-.}"
echo "🔒 Redacting sk-XXX patterns in $ROOT (test-results/ + playwright-report/)..."

count=0
for f in $(find "$ROOT/test-results" "$ROOT/playwright-report" \
              -type f \( -name '*.json' -o -name '*.txt' -o -name '*.html' -o -name '*.md' \) 2>/dev/null); do
  if grep -lE "$REGEX" "$f" > /dev/null 2>&1; then
    sed -i "s/${REGEX}/${REPL}/g" "$f"
    count=$((count + 1))
  fi
done

echo "✅ Redacted $count files."
