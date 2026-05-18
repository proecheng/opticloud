# Docker Build Pipeline (Story 0.8)

> Multi-stage Docker images + cosign signing + syft SBOM generation.

## Files

- `python-service.Dockerfile` — Shared multi-stage template for Python services
- `cosign.pub` / `cosign.key.enc` — Cosign keypair (encrypted; password in Vault `secret/data/cosign`)

Each service has thin `Dockerfile` wrapping the shared template (e.g. `apps/auth-service/Dockerfile`).

## Build locally

```bash
# From repo root
docker build \
  -f apps/auth-service/Dockerfile \
  -t opticloud/auth-service:dev \
  --build-arg GIT_SHA=$(git rev-parse --short HEAD) \
  --build-arg BUILD_DATE=$(date -u +%Y-%m-%dT%H:%M:%SZ) \
  .

# Verify size (runtime ≤300 MB target per Architecture Concern #14)
docker images opticloud/auth-service:dev
```

## Sign image (production / staging only)

```bash
# Set up cosign once: cosign generate-key-pair (password from Vault)
export COSIGN_PASSWORD=$(vault kv get -field=password secret/cosign)
cosign sign --key infra/docker/cosign.key.enc opticloud/auth-service:dev

# Verify (any party can verify with public key)
cosign verify --key infra/docker/cosign.pub opticloud/auth-service:dev
```

## Generate SBOM (syft)

```bash
# SBOM in SPDX JSON format
syft opticloud/auth-service:dev -o spdx-json > sbom-auth-service.spdx.json

# Or human-readable table
syft opticloud/auth-service:dev
```

## RE2-9 fix: Daily SBOM diff scanning

The CI workflow `.github/workflows/sbom-daily.yml` runs daily:
1. Rebuild all service images
2. Generate fresh SBOMs
3. Diff vs previous day stored in `infra/sbom-history/`
4. Auto-Linear-ticket for any dependency version change (semver-aware)
5. Block PRs containing dependencies with **CVE ≥ 7.0** or **major version bumps without ADR**

## CRG6 supply chain hardening AC

- ✅ uv version pinned (`UV_VERSION=0.5.4`) — prevents typosquat
- ✅ `tini` PID 1 for graceful signal handling (P43)
- ✅ `nonroot` user (uid 1000) — sandbox/runtime isolation
- ✅ No `curl`/`wget` in runtime — healthcheck via Python urllib
- ✅ Read-only PYTHONPATH; venv copied; no `pip install` in runtime
- ✅ SBOM generation on every build
- 🟡 Distroless migration (v2 evaluation, currently slim-bookworm)
- 🟡 cosign keyless signing via OIDC (v1.5+, currently keypair)
