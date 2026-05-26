# Contract Tests

Story M3.2 adds the PR-gated Schemathesis contract test harness. Story M3.4b
adds shared-module contract tests in this folder so service contracts and
module contracts share one PR gate.

## What This Checks

Contract tests validate actual FastAPI behavior against the app OpenAPI schema through in-process ASGI calls using `schemathesis_from_asgi_app()`. They are separate from static OpenAPI drift checks:

- `scripts/generate_openapi.py` writes checked-in OpenAPI files.
- `scripts/check_openapi_drift.py` verifies checked-in OpenAPI files match generated output.
- `tests/contract/` validates selected app endpoints behave according to their OpenAPI schema.

Module contract tests validate non-HTTP shared library APIs with Python
introspection plus committed JSON snapshots. `aigc_filter_contract.json` locks
`aigc_filter.filter(text, tier="strict", context=None) -> Filtered`, result
fields, public exports, the major contract version, and the 183-day minimum
deprecation notice window. These tests intentionally do not use Schemathesis
because `aigc_filter` is not an OpenAPI service.

## Current Required Services

| Service | Mode | Required paths |
|---|---|---|
| `auth-service` | in-process ASGI | `/healthz` |
| `aigc_filter` | Python module snapshot | `filter`, `Filtered`, watermark metadata |

The first PR gate intentionally targets the non-mutating no-DB `/healthz` endpoint so it does not need Postgres, Redis, Docker, Kubernetes, network access, or secrets. `/readyz` remains a future target once the contract harness owns a DB fixture or dependency override.

## Add A Service

1. Add a `ContractService` entry in `tests/contract/registry.py`.
2. Start with non-mutating health/readiness endpoints.
3. Add endpoint-specific tests with small `max_examples` for PR speed; reuse `CONTRACT_MAX_EXAMPLES` unless a story explicitly justifies a different bound.
4. Promote broader endpoint fuzzing to nightly before making it a PR blocker.

## Local Commands

```powershell
$env:PYTHONPATH='apps/auth-service/src;packages/shared-py'
uv run pytest tests/contract -q
```

For broader ad-hoc coverage against a running service:

```bash
uv run schemathesis run http://localhost:8001/openapi.json --checks all
```

Do not replace the static OpenAPI drift check with contract tests; both gates catch different failures.
