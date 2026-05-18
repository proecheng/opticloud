# property_test_base — Property-based testing foundation

> Story 0.5b · RE5 fix · Sprint 0 N1 末

## When to use Hypothesis vs Schemathesis

| Tool | Test scope | OptiCloud use cases |
|---|---|---|
| **Hypothesis** | Unit + integration property tests; you write the input strategy | M2.2a Billing Saga 状态机 / 求解器 mock-real divergence (3-14) / Pydantic schema roundtrip / business rule invariants |
| **Schemathesis** | API contract property tests; inputs auto-derived from OpenAPI spec | M3.2 Contract Test CI gate / SDK parity tests (FG1.3) / per-endpoint boundary fuzzing |

Rule of thumb: **Hypothesis for code-level invariants, Schemathesis for HTTP-level contracts.**

## Canonical strategies (`strategies.py`)

```python
from opticloud_shared.property_test_base.strategies import (
    uuids,               # UUID v4 strings
    api_key_prefixes,    # "sk-XXX" 6-char prefixes
    error_details,       # RFC 7807 ErrorDetail (FG1.3)
    lp_inputs,           # random LP {task_type, minimize/maximize, st}
    monetary_amounts,    # 0.00 - 1M with 2 decimals
)
```

### Example 1 — RFC 7807 ErrorDetail roundtrip

```python
from hypothesis import given
from opticloud_shared.property_test_base.strategies import error_details
from opticloud_shared.schemas.errors import ErrorDetail

@given(detail=error_details())
def test_error_detail_json_roundtrip(detail: ErrorDetail) -> None:
    parsed = ErrorDetail.model_validate_json(detail.model_dump_json())
    assert parsed == detail
```

### Example 2 — LP solver mock-real divergence (Q-T1 prep)

```python
from hypothesis import given, settings
from opticloud_shared.property_test_base.strategies import lp_inputs

@given(payload=lp_inputs(n_max=5, m_max=5))
@settings(max_examples=50, deadline=2000)
def test_solver_mock_real_schema_parity(payload):
    real = solve_real(payload)  # apps/solver-orchestrator
    mock = solve_mock(payload)  # test double
    assert set(real.keys()) == set(mock.keys())  # schema invariant
```

### Example 3 — Billing Saga invariants (M2.2a prep)

```python
from hypothesis import given
from opticloud_shared.property_test_base.strategies import monetary_amounts, uuids

@given(amount=monetary_amounts(), idempotency_key=uuids())
def test_charge_idempotent(amount, idempotency_key):
    """Same idempotency key + same body → same result; never double charge."""
    first  = charge(amount, idempotency_key)
    second = charge(amount, idempotency_key)
    assert first == second
```

## Schemathesis quickstart (`fixtures.py`)

### Pattern 1 — Pytest integration (CI offline, recommended)

```python
import pytest
from opticloud_shared.property_test_base.fixtures import schemathesis_from_path

schema = schemathesis_from_path("packages/shared-ts/openapi/auth-service.json")

@schema.parametrize(endpoint="/healthz")
def test_healthz_contract(case):
    response = case.call_wsgi()  # or case.call() for HTTP
    case.validate_response(response)
```

### Pattern 2 — Schemathesis CLI (ad-hoc local testing)

```bash
# Against running auth-service
uv run schemathesis run http://localhost:8001/openapi.json --checks all

# Limit to one endpoint for speed
uv run schemathesis run http://localhost:8001/openapi.json \
  --include-path /healthz --checks all
```

## Adding a new strategy

When a downstream story (e.g. M2.2a Billing) needs a new canonical strategy:

1. Add to `strategies.py` with a docstring explaining intended use cases
2. Export from `__init__.py` if widely consumed
3. Add an example to this README
4. Add a sample property test under `packages/shared-py/tests/`

Anti-pattern: do **not** define identical strategies in per-service test files; reuse from here to keep mock-real schema parity (Q-T1) automatic.

## Related stories

- **0.5** Pre-commit + ruff + mypy + bandit (foundation; 0.5b extends with property test deps)
- **M2.0** Saga + Outbox Architectural Spike (consumer)
- **M2.2a** Billing 50 critical scenarios (consumer — Hypothesis)
- **M3.2** Contract Test framework / CI gate (consumer — Schemathesis)
- **3-14** Mock-real divergence test suite (consumer — Hypothesis lp_inputs)
- **8-b-5** Error i18n single-source ESLint audit (consumer — error_details for fixture generation)
