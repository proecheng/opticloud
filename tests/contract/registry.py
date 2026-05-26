from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from opticloud_shared.property_test_base.fixtures import schemathesis_from_asgi_app

CONTRACT_MAX_EXAMPLES = 5
REQUIRED_CONTRACT_SERVICES = ("auth-service",)


@dataclass(frozen=True)
class ContractService:
    name: str
    app_import_path: str
    openapi_path: str = "/openapi.json"
    required: bool = False

    @property
    def app(self) -> Any:
        module_name, app_name = self.app_import_path.split(":", maxsplit=1)
        module = __import__(module_name, fromlist=[app_name])
        if hasattr(module, "otel_setup"):
            module.otel_setup.init = lambda *args, **kwargs: None
        return getattr(module, app_name)

    @property
    def schema(self) -> Any:
        return schemathesis_from_asgi_app(self.app)

    @property
    def openapi_paths(self) -> dict[str, dict[str, Any]]:
        return self.app.openapi()["paths"]


CONTRACT_SERVICES: dict[str, ContractService] = {
    "auth-service": ContractService(
        name="auth-service",
        app_import_path="auth_service.main:app",
        required=True,
    ),
}

FUTURE_CONTRACT_PATHS: dict[str, tuple[str, ...]] = {
    "auth-service": ("/readyz",),
}


def get_contract_service(name: str) -> ContractService:
    try:
        return CONTRACT_SERVICES[name]
    except KeyError as exc:
        raise AssertionError(f"Unknown contract service: {name}") from exc
