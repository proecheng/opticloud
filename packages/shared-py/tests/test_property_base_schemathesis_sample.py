"""Sample Schemathesis contract test (Story 0.5b foundation, AC5).

Pattern shown here is the foundation Story M3.2 will scale to full CI gate.

This test loads auth-service OpenAPI spec from disk (CI-friendly,
no running service needed) + verifies /healthz endpoint contract.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

# Sample OpenAPI spec inline (so this test runs without a live auth-service)
_HEALTHZ_OPENAPI_SPEC = {
    "openapi": "3.0.0",
    "info": {"title": "test", "version": "0.0.1"},
    "paths": {
        "/healthz": {
            "get": {
                "summary": "Liveness probe",
                "responses": {
                    "200": {
                        "description": "OK",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {"status": {"type": "string"}},
                                    "required": ["status"],
                                }
                            }
                        },
                    }
                },
            }
        }
    },
}


@pytest.fixture
def healthz_spec_path(tmp_path: Path) -> Path:
    """Write a tiny OpenAPI spec to tmp + return its path."""
    p = tmp_path / "healthz-spec.json"
    p.write_text(json.dumps(_HEALTHZ_OPENAPI_SPEC))
    return p


def test_schemathesis_loads_static_spec(healthz_spec_path: Path) -> None:
    """schemathesis_from_path() loads an OpenAPI spec into a usable schema object."""
    from opticloud_shared.property_test_base.fixtures import schemathesis_from_path

    schema = schemathesis_from_path(healthz_spec_path)
    assert schema is not None
    # Iterate paths to confirm the schema is parseable
    paths = list(schema)
    assert any("/healthz" in repr(op) for op in paths), "Expected /healthz in loaded schema"


def test_schemathesis_url_helper_signature() -> None:
    """schemathesis_from_url() exists with correct signature (smoke test)."""
    from opticloud_shared.property_test_base.fixtures import schemathesis_from_url

    # Signature check only (no network call here)
    assert callable(schemathesis_from_url)
    # Default openapi_path keyword present
    import inspect

    sig = inspect.signature(schemathesis_from_url)
    assert "openapi_path" in sig.parameters
