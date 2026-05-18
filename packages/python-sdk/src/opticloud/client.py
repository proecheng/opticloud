"""Minimal OptiCloud client stub (Story 0.4 alpha).

Real implementation will be auto-generated from OpenAPI spec in M1.
This file is a hand-written placeholder demonstrating the error handling contract.
"""

from __future__ import annotations

from typing import Any

import httpx

from opticloud.errors import OptiCloudHTTPError


class OptiCloudClient:
    """Synchronous OptiCloud SDK client (alpha stub)."""

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.opticloud.cn",
        timeout: float = 30.0,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self._client = httpx.Client(
            base_url=self.base_url,
            timeout=timeout,
            headers={"Authorization": f"Bearer {api_key}"},
        )

    def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        response = self._client.request(method, path, **kwargs)
        if response.status_code >= 400:
            try:
                body = response.json()
            except Exception:
                body = {"title": "Unknown Error", "detail": response.text, "status": response.status_code}
            raise OptiCloudHTTPError.from_response(response.status_code, body)
        return response.json()  # type: ignore[no-any-return]

    def list_algorithms(self) -> dict[str, Any]:
        """GET /v1/algorithms (FR C1, no auth)."""
        return self._request("GET", "/v1/algorithms")

    def close(self) -> None:
        self._client.close()
