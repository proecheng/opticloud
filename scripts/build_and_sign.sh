#!/usr/bin/env bash
# OptiCloud — Build + Sign + SBOM script (Story 0.8)
# Usage: scripts/build_and_sign.sh <service-name> [tag]
#
# Steps:
#   1. docker build with GIT_SHA + BUILD_DATE labels
#   2. cosign sign (if COSIGN_KEY set, else skip)
#   3. syft SBOM generation → infra/sbom-history/<date>/<service>.spdx.json
#   4. (Optional) docker push to registry
#
# Prereqs:
#   - docker (or docker-compatible like podman)
#   - cosign (https://docs.sigstore.dev/cosign/installation/)
#   - syft (https://github.com/anchore/syft#installation)

set -euo pipefail

SERVICE_NAME="${1:?Usage: $0 <service-name> [tag]}"
TAG="${2:-dev}"
REGISTRY="${REGISTRY:-opticloud}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

GIT_SHA="$(git rev-parse --short HEAD 2>/dev/null || echo 'nogit')"
BUILD_DATE="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
TODAY="$(date -u +%Y-%m-%d)"
IMAGE="${REGISTRY}/${SERVICE_NAME}:${TAG}"
IMAGE_SHA="${REGISTRY}/${SERVICE_NAME}:${GIT_SHA}"

DOCKERFILE="apps/${SERVICE_NAME}/Dockerfile"
if [[ ! -f "$DOCKERFILE" ]]; then
  echo "❌ No Dockerfile at $DOCKERFILE"
  exit 1
fi

# ===== 1. Build =====
echo "🏗  Building ${IMAGE} (sha=${GIT_SHA})..."
docker build \
  -f "$DOCKERFILE" \
  -t "$IMAGE" \
  -t "$IMAGE_SHA" \
  --build-arg "GIT_SHA=${GIT_SHA}" \
  --build-arg "BUILD_DATE=${BUILD_DATE}" \
  .

# Image size check (Concern #14 target ≤300 MB)
SIZE_BYTES=$(docker image inspect "$IMAGE" --format='{{.Size}}')
SIZE_MB=$((SIZE_BYTES / 1024 / 1024))
echo "  Image size: ${SIZE_MB} MB (target ≤300 MB)"
if [[ $SIZE_MB -gt 300 ]]; then
  echo "  ⚠️  Image exceeds 300 MB target — investigate before prod."
fi

# ===== 2. Sign (optional, requires COSIGN_KEY + COSIGN_PASSWORD env) =====
if [[ -n "${COSIGN_KEY:-}" ]] && command -v cosign &>/dev/null; then
  echo "🔏 Signing ${IMAGE_SHA} with cosign..."
  cosign sign --key "$COSIGN_KEY" "$IMAGE_SHA"
  cosign verify --key "${COSIGN_KEY%.key*}.pub" "$IMAGE_SHA" && echo "  ✅ Signature verified."
else
  echo "  ⏭  cosign signing skipped (set COSIGN_KEY env var to enable)."
fi

# ===== 3. Generate SBOM =====
if command -v syft &>/dev/null; then
  SBOM_DIR="${REPO_ROOT}/infra/sbom-history/${TODAY}"
  mkdir -p "$SBOM_DIR"
  SBOM_FILE="${SBOM_DIR}/${SERVICE_NAME}.spdx.json"
  echo "📄 Generating SBOM → ${SBOM_FILE}..."
  syft "$IMAGE" -o spdx-json > "$SBOM_FILE"
  PKG_COUNT=$(jq '.packages | length' "$SBOM_FILE" 2>/dev/null || echo '?')
  echo "  ✅ SBOM contains ${PKG_COUNT} packages."
else
  echo "  ⏭  syft not installed — SBOM generation skipped."
  echo "     Install: https://github.com/anchore/syft#installation"
fi

echo "✅ Build complete: ${IMAGE}"
