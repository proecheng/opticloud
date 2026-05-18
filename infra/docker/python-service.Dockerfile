# OptiCloud — 通用 Python service multi-stage Dockerfile
# Story 0.8 + CRG6 supply chain hardening + RE2-9 SBOM daily diff
#
# Usage (from repo root):
#   docker build \
#     -f infra/docker/python-service.Dockerfile \
#     --build-arg SERVICE_NAME=auth-service \
#     --build-arg SERVICE_PORT=8001 \
#     -t opticloud/auth-service:dev \
#     .
#
# Multi-stage:
#   1. builder: uv + deps + wheels
#   2. runtime: distroless-style minimal Python + nonroot user

# ===== ARGs =====
ARG PYTHON_VERSION=3.12
ARG UV_VERSION=0.5.4
ARG SERVICE_NAME
ARG SERVICE_PORT=8000

# ===== Stage 1: Builder =====
FROM python:${PYTHON_VERSION}-slim-bookworm AS builder

# Pin uv version (supply chain hardening — CRG6)
ARG UV_VERSION
RUN pip install --no-cache-dir uv==${UV_VERSION}

WORKDIR /build

# Copy workspace manifests first (cache friendly)
COPY pyproject.toml uv.lock* ./
COPY packages/shared-py/pyproject.toml packages/shared-py/
COPY packages/python-sdk/pyproject.toml packages/python-sdk/

ARG SERVICE_NAME
COPY apps/${SERVICE_NAME}/pyproject.toml apps/${SERVICE_NAME}/

# Install deps (no project sources yet — maximizes cache hit on re-build)
RUN uv sync --frozen --no-install-workspace --no-dev || uv sync --no-install-workspace --no-dev

# Copy actual source
COPY packages/shared-py packages/shared-py
COPY packages/python-sdk packages/python-sdk
COPY apps/${SERVICE_NAME} apps/${SERVICE_NAME}

# Install workspace deps (incl. local packages)
RUN uv sync --no-dev

# ===== Stage 2: Runtime =====
FROM python:${PYTHON_VERSION}-slim-bookworm AS runtime

# Security hardening (NFR-S + CRG4):
#   - non-root user
#   - read-only FS where possible (compose / k8s level)
#   - no shell access in prod (we keep bash for healthcheck only)
#   - SBOM-friendly minimal image
RUN groupadd --system --gid 1000 opticloud \
    && useradd --system --uid 1000 --gid opticloud --no-create-home --shell /usr/sbin/nologin opticloud

# Update CA certs only (no curl/wget in runtime — use Python for health)
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        tini \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

ARG SERVICE_NAME
ARG SERVICE_PORT

WORKDIR /app

# Copy virtualenv from builder
COPY --from=builder /build/.venv /app/.venv

# Copy app source (read-only)
COPY --from=builder --chown=opticloud:opticloud /build/packages/shared-py /app/packages/shared-py
COPY --from=builder --chown=opticloud:opticloud /build/packages/python-sdk /app/packages/python-sdk
COPY --from=builder --chown=opticloud:opticloud /build/apps/${SERVICE_NAME} /app/apps/${SERVICE_NAME}

# Make venv binaries available
ENV PATH="/app/.venv/bin:${PATH}" \
    PYTHONPATH="/app/apps/${SERVICE_NAME}/src:/app/packages/shared-py:/app/packages/python-sdk/src" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    SERVICE_NAME=${SERVICE_NAME}

ENV SERVICE_PORT=${SERVICE_PORT}
EXPOSE ${SERVICE_PORT}

USER opticloud:opticloud

# Healthcheck via Python (no curl)
HEALTHCHECK --interval=10s --timeout=3s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:${SERVICE_PORT}/healthz', timeout=2).status==200 else 1)"

# Use tini as PID 1 (proper signal handling for graceful shutdown — P43)
ENTRYPOINT ["/usr/bin/tini", "--"]

# Default service launcher — each service can override
CMD ["sh", "-c", "exec uvicorn ${SERVICE_NAME//-/_}.main:app --host 0.0.0.0 --port ${SERVICE_PORT}"]

# ===== OCI labels (for SBOM + provenance) =====
ARG GIT_SHA=unknown
ARG BUILD_DATE=unknown
LABEL org.opencontainers.image.title="opticloud-${SERVICE_NAME}" \
      org.opencontainers.image.source="https://github.com/opticloud/opticloud" \
      org.opencontainers.image.revision="${GIT_SHA}" \
      org.opencontainers.image.created="${BUILD_DATE}" \
      org.opencontainers.image.licenses="Apache-2.0" \
      cloud.opticloud.service="${SERVICE_NAME}"
