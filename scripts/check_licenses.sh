#!/usr/bin/env bash
# OptiCloud License check (Story 0.5 + CRG9 fix)
# Verify package dependencies use only licenses in license-allowed.txt
# GPL-3.0 has special handling: only allowed for "ecos" package (NFR-PI3)

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

echo "OptiCloud license check..."

# ----- Python (uv) -----
if [ -f "uv.lock" ]; then
  if command -v uv &> /dev/null; then
    # uv tree 输出 license; 检查每个 dependency license 是否在白名单
    echo "  Python (uv): scanning dependencies..."
    # Placeholder; actual implementation needs uv tree --format=json + license-allowed.txt parse + ECOS exception
    # For now, just warn that this script needs implementation
    echo "  ⚠️  License scan logic pending implementation (Sprint 0 W2 task)."
  fi
fi

# ----- Node (pnpm) -----
if [ -f "pnpm-lock.yaml" ]; then
  if command -v pnpm &> /dev/null; then
    echo "  Node (pnpm): scanning dependencies..."
    # Placeholder; needs pnpm licenses + license-allowed.txt cross-check
    echo "  ⚠️  License scan logic pending implementation (Sprint 0 W2 task)."
  fi
fi

echo "✅ License check complete (placeholder pass)."
exit 0
