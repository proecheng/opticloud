"""OpenTelemetry setup — single source of truth for tracing + metrics.

Story 0.7 — bootstrap OTel SDK with OTLP exporter to Grafana Tempo.

Architecture references:
- P48 OpenTelemetry init shared-py/otel_setup
- R11 Cloud Lock-in mitigation: OpenTelemetry 业务层抽象 (vendor-agnostic)
- D9 Grafana Tempo (阿里云) + Jaeger (local dev fallback)

Usage:
    from opticloud_shared import otel_setup
    otel_setup.init(service_name="auth-service")
    # In FastAPI: FastAPIInstrumentor.instrument_app(app)
"""

from __future__ import annotations

import logging
import os

from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import SERVICE_NAME, SERVICE_NAMESPACE, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

logger = logging.getLogger(__name__)


def init(
    service_name: str,
    service_namespace: str = "opticloud",
    otlp_endpoint: str | None = None,
    enable_console: bool = False,
) -> None:
    """Initialize OpenTelemetry SDK once per process.

    Args:
        service_name: e.g. "auth-service", "solver-orchestrator"
        service_namespace: defaults to "opticloud"
        otlp_endpoint: defaults to env var OTEL_EXPORTER_OTLP_ENDPOINT or http://localhost:4317
        enable_console: also export spans to console (dev only)
    """
    endpoint = otlp_endpoint or os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")

    resource = Resource.create(
        {
            SERVICE_NAME: service_name,
            SERVICE_NAMESPACE: service_namespace,
        }
    )

    # ===== Tracer =====
    tracer_provider = TracerProvider(resource=resource)
    try:
        span_exporter = OTLPSpanExporter(endpoint=endpoint, insecure=True)
        tracer_provider.add_span_processor(BatchSpanProcessor(span_exporter))
    except Exception as e:
        # Don't fail boot if OTel collector is down; just warn
        logger.warning(f"OTel span exporter init failed (will not export traces): {e}")
    trace.set_tracer_provider(tracer_provider)

    # ===== Meter =====
    try:
        metric_exporter = OTLPMetricExporter(endpoint=endpoint, insecure=True)
        metric_reader = PeriodicExportingMetricReader(
            metric_exporter, export_interval_millis=15000
        )
        meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
        metrics.set_meter_provider(meter_provider)
    except Exception as e:
        logger.warning(f"OTel metric exporter init failed: {e}")

    logger.info(f"OTel initialized: service={service_name}, endpoint={endpoint}")


def get_tracer(name: str) -> trace.Tracer:
    """Get a tracer (call after init())."""
    return trace.get_tracer(name)


def get_meter(name: str) -> metrics.Meter:
    """Get a meter (call after init())."""
    return metrics.get_meter(name)
