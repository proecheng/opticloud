# outbox-relayer Dockerfile (Story M2.1)
# Mirrors apps/auth-service/Dockerfile two-stage pattern.

# syntax=docker/dockerfile:1.7

# ===== Stage 1: Builder =====
FROM python:3.12-slim-bookworm AS builder
ARG UV_VERSION=0.5.4
RUN pip install --no-cache-dir uv==${UV_VERSION}
WORKDIR /build
COPY pyproject.toml uv.lock* ./
COPY packages/shared-py/pyproject.toml packages/shared-py/
COPY packages/python-sdk/pyproject.toml packages/python-sdk/
COPY apps/outbox-relayer/pyproject.toml apps/outbox-relayer/
RUN uv sync --frozen --no-install-workspace --no-dev || uv sync --no-install-workspace --no-dev
COPY packages/shared-py packages/shared-py
COPY packages/python-sdk packages/python-sdk
COPY apps/outbox-relayer apps/outbox-relayer
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
COPY --from=builder --chown=opticloud:opticloud /build/apps/outbox-relayer /app/apps/outbox-relayer
ENV PATH="/app/.venv/bin:${PATH}" \
    PYTHONPATH="/app/apps/outbox-relayer/src:/app/packages/shared-py" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    SERVICE_NAME=outbox-relayer \
    HEALTH_PORT=9101
EXPOSE 9101
USER opticloud:opticloud
HEALTHCHECK --interval=10s --timeout=3s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:9101/healthz', timeout=2).status==200 else 1)"
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["python", "-m", "outbox_relayer.main"]

ARG GIT_SHA=unknown
ARG BUILD_DATE=unknown
LABEL org.opencontainers.image.title="opticloud-outbox-relayer" \
      org.opencontainers.image.source="https://github.com/opticloud/opticloud" \
      org.opencontainers.image.revision="${GIT_SHA}" \
      org.opencontainers.image.created="${BUILD_DATE}" \
      org.opencontainers.image.licenses="Apache-2.0" \
      cloud.opticloud.service="outbox-relayer"
