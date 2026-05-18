# auth-service Dockerfile — Story 0.8 + Story 0.6
# Wraps shared infra/docker/python-service.Dockerfile with service-specific args.
#
# Build from repo root:
#   docker build \
#     -f apps/auth-service/Dockerfile \
#     -t opticloud/auth-service:dev \
#     --build-arg GIT_SHA=$(git rev-parse --short HEAD) \
#     --build-arg BUILD_DATE=$(date -u +%Y-%m-%dT%H:%M:%SZ) \
#     .

# syntax=docker/dockerfile:1.7
# Service args
ARG SERVICE_NAME=auth-service
ARG SERVICE_PORT=8001

# Inherit shared multi-stage template
# Note: When building, use `-f apps/auth-service/Dockerfile` from repo root
# This is a thin pointer; actual logic lives in infra/docker/python-service.Dockerfile.
# For non-supporting build systems, this file is duplicated as a fallback below:

# ===== Stage 1: Builder =====
FROM python:3.12-slim-bookworm AS builder
ARG UV_VERSION=0.5.4
RUN pip install --no-cache-dir uv==${UV_VERSION}
WORKDIR /build
COPY pyproject.toml uv.lock* ./
COPY packages/shared-py/pyproject.toml packages/shared-py/
COPY packages/python-sdk/pyproject.toml packages/python-sdk/
COPY apps/auth-service/pyproject.toml apps/auth-service/
RUN uv sync --frozen --no-install-workspace --no-dev || uv sync --no-install-workspace --no-dev
COPY packages/shared-py packages/shared-py
COPY packages/python-sdk packages/python-sdk
COPY apps/auth-service apps/auth-service
RUN uv sync --no-dev

# ===== Stage 2: Runtime =====
FROM python:3.12-slim-bookworm AS runtime
RUN groupadd --system --gid 1000 opticloud \
    && useradd --system --uid 1000 --gid opticloud --no-create-home --shell /usr/sbin/nologin opticloud
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates tini \
    && apt-get clean && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY --from=builder /build/.venv /app/.venv
COPY --from=builder --chown=opticloud:opticloud /build/packages/shared-py /app/packages/shared-py
COPY --from=builder --chown=opticloud:opticloud /build/packages/python-sdk /app/packages/python-sdk
COPY --from=builder --chown=opticloud:opticloud /build/apps/auth-service /app/apps/auth-service
ENV PATH="/app/.venv/bin:${PATH}" \
    PYTHONPATH="/app/apps/auth-service/src:/app/packages/shared-py:/app/packages/python-sdk/src" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    SERVICE_NAME=auth-service \
    SERVICE_PORT=8001
EXPOSE 8001
USER opticloud:opticloud
HEALTHCHECK --interval=10s --timeout=3s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8001/healthz', timeout=2).status==200 else 1)"
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["uvicorn", "auth_service.main:app", "--host", "0.0.0.0", "--port", "8001"]

ARG GIT_SHA=unknown
ARG BUILD_DATE=unknown
LABEL org.opencontainers.image.title="opticloud-auth-service" \
      org.opencontainers.image.source="https://github.com/opticloud/opticloud" \
      org.opencontainers.image.revision="${GIT_SHA}" \
      org.opencontainers.image.created="${BUILD_DATE}" \
      org.opencontainers.image.licenses="Apache-2.0" \
      cloud.opticloud.service="auth-service"
