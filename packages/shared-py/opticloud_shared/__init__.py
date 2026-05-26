"""OptiCloud shared Python utilities.

Modules (built progressively per epics.md Story 0.x):
- schemas: canonical Pydantic schemas (errors RFC 7807, common types) (Story 0.4)
- otel_setup: OpenTelemetry initialization (Story 0.7) ✅
- cost_telemetry: G3 per-tenant cost attribution (Story M2.3)
- aigc_filter: P34 + P62 + C11 AIGC output filter (Story M3.4)
- property_test_base: Hypothesis + Schemathesis fixtures (Story 0.5b)
"""

from opticloud_shared import cost_telemetry, otel_setup, schemas

__version__ = "0.0.1"
__all__ = ["cost_telemetry", "otel_setup", "schemas"]
