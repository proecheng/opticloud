from __future__ import annotations

from fastapi.testclient import TestClient
from hypothesis import HealthCheck, settings

from tests.contract.registry import (
    CONTRACT_MAX_EXAMPLES,
    FUTURE_CONTRACT_PATHS,
    REQUIRED_CONTRACT_SERVICES,
    get_contract_service,
)

auth_service = get_contract_service("auth-service")
schema = auth_service.schema
client = TestClient(auth_service.app)


def test_auth_service_is_required_initial_contract_target() -> None:
    assert "auth-service" in REQUIRED_CONTRACT_SERVICES
    assert auth_service.openapi_path == "/openapi.json"
    assert "/healthz" in auth_service.openapi_paths
    assert "/readyz" in FUTURE_CONTRACT_PATHS["auth-service"]


@schema.include(path="/healthz", method="GET").parametrize()
@settings(
    max_examples=CONTRACT_MAX_EXAMPLES,
    derandomize=True,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
def test_auth_service_healthz_contract(case: object) -> None:
    response = case.call()
    case.validate_response(response)


def test_auth_service_healthz_payload_is_stable() -> None:
    healthz = client.get("/healthz")

    assert healthz.status_code == 200
    assert healthz.json() == {"status": "ok"}


def test_contract_tests_only_target_safe_auth_endpoints() -> None:
    tested_paths = {"/healthz"}
    mutating_paths = {
        path
        for path, methods in auth_service.openapi_paths.items()
        if any(method.lower() in {"post", "put", "patch", "delete"} for method in methods)
    }

    assert tested_paths.isdisjoint(mutating_paths)
