"""Property-based testing foundation (Story 0.5b — RE5 fix).

Shared Hypothesis + Schemathesis infrastructure for OptiCloud services.

Downstream consumers:
- Story M2.2a Billing 一致性 critical 50 scenarios
- Story M3.2 Contract Test framework
- Story 3-14 mock-real divergence test
- Business Epic stories (per-service property tests)

Usage:
    from opticloud_shared.property_test_base import strategies, fixtures

    @hypothesis.given(strategies.error_details())
    def test_error_detail_roundtrip(detail): ...
"""

from opticloud_shared.property_test_base import fixtures, strategies

__all__ = ["fixtures", "strategies"]
