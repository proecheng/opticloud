"""Tests for OptiCloudHTTPError.locate() helper (FG1.3 + L1)."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from opticloud.client import OptiCloudClient
from opticloud.errors import OptiCloudHTTPError

REPO_ROOT = Path(__file__).resolve().parents[3]
PRESERVATION_FIXTURE = REPO_ROOT / "tests" / "fixtures" / "sdk-rfc7807-preservation.json"


def load_preservation_fixture() -> dict[str, object]:
    return json.loads(PRESERVATION_FIXTURE.read_text(encoding="utf-8"))


def test_locate_returns_matching_value() -> None:
    """e.locate('st.A[2][1]') returns the value of matching ErrorDetail."""
    error = OptiCloudHTTPError(
        status=422,
        title="Validation Error",
        detail="constraint violation in st.A",
        errors=[
            {
                "field_path": "st.A[2][1]",
                "value": -1.5,
                "constraint": "must be >= 0",
                "remediation_hint_key": "errors.422.non_negative",
            },
            {
                "field_path": "options.max_solve_seconds",
                "value": 0,
                "constraint": "must be > 0",
                "remediation_hint_key": "errors.422.positive_int",
            },
        ],
    )

    assert error.locate("st.A[2][1]") == -1.5
    assert error.locate("options.max_solve_seconds") == 0
    assert error.locate("nonexistent.field") is None


def test_locate_all_returns_all_matching() -> None:
    error = OptiCloudHTTPError(
        status=422,
        title="Validation Error",
        detail="multiple violations on same field",
        errors=[
            {"field_path": "options.tags[0]", "value": "invalid"},
            {"field_path": "options.tags[0]", "value": "duplicate"},
            {"field_path": "options.tags[1]", "value": "ok"},
        ],
    )
    assert error.locate_all("options.tags[0]") == ["invalid", "duplicate"]
    assert error.locate_all("options.tags[1]") == ["ok"]


def test_find_constraint_matches_regex() -> None:
    error = OptiCloudHTTPError(
        status=422,
        title="Validation Error",
        detail="infeasible LP",
        errors=[
            {"field_path": "st", "constraint": "infeasible_lp", "value": None},
            {"field_path": "obj", "constraint": "unbounded_lp", "value": None},
        ],
    )
    matches = error.find_constraint(r"infeasible")
    assert len(matches) == 1
    assert matches[0]["field_path"] == "st"


def test_find_constraint_ignores_non_string_constraint_values() -> None:
    error = OptiCloudHTTPError(
        status=422,
        title="Validation Error",
        detail="malformed constraint details",
        errors=[
            {"field_path": "st", "constraint": {"code": "infeasible_lp"}, "value": None},
            {"field_path": "obj", "constraint": "infeasible_lp", "value": None},
        ],
    )

    assert error.find_constraint(r"infeasible") == [
        {"field_path": "obj", "constraint": "infeasible_lp", "value": None}
    ]


def test_remediation_keys() -> None:
    error = OptiCloudHTTPError(
        status=402,
        title="Insufficient Credits",
        detail="balance too low",
        errors=[
            {
                "field_path": "options.max_solve_seconds",
                "value": 600,
                "constraint": "estimated_credits > balance",
                "remediation_hint_key": "errors.402.topup",
            }
        ],
    )
    assert error.remediation_keys() == ["errors.402.topup"]


def test_from_response_constructs_from_rfc7807_body() -> None:
    body = {
        "type": "https://api.opticloud.cn/errors/insufficient_credits",
        "title": "Insufficient Credits",
        "status": 402,
        "detail": "余额不足。当前 50 Credits，本次预估消耗 605 Credits。",
        "errors": [
            {
                "field_path": "options.max_solve_seconds",
                "value": 600,
                "constraint": "estimated_credits > balance",
                "remediation_hint_key": "errors.402.topup",
            }
        ],
        "next_action_url": "https://console.opticloud.cn/topup?suggested_amount=10",
        "instance": "/v1/optimizations",
        "request_id": "req_xyz",
        "trace_id": "trc_abc",
    }
    error = OptiCloudHTTPError.from_response(402, body)
    assert error.status == 402
    assert error.title == "Insufficient Credits"
    assert error.next_action_url == "https://console.opticloud.cn/topup?suggested_amount=10"
    assert error.locate("options.max_solve_seconds") == 600
    assert error.remediation_keys() == ["errors.402.topup"]
    assert error.raw == body  # Full preservation (FG1.3 SDK contract)


def test_from_response_preserves_errors_without_mutable_aliasing() -> None:
    body = load_preservation_fixture()
    expected_errors = copy.deepcopy(body["errors"])
    expected_raw = copy.deepcopy(body)

    error = OptiCloudHTTPError.from_response(422, body)

    assert error.errors == expected_errors
    assert error.raw == expected_raw
    assert error.next_action_url == expected_raw["next_action_url"]
    assert error.request_id == expected_raw["request_id"]
    assert error.trace_id == expected_raw["trace_id"]
    assert error.locate("series[0].values") == {
        "observed": [12.5, None, 13.1],
        "metadata": {"source": "csv", "row": 7},
    }
    assert error.locate("options.horizon") is None
    assert error.errors[0]["debug_metadata"] == {
        "parser": "csv-v1",
        "columns": ["timestamp", "value"],
    }

    body["request_id"] = "mutated-request"
    body["errors"][0]["value"]["metadata"]["row"] = 999
    body["errors"].append({"field_path": "mutated", "value": "late"})

    assert error.raw == expected_raw
    assert error.errors == expected_errors
    assert error.locate("series[0].values") == {
        "observed": [12.5, None, 13.1],
        "metadata": {"source": "csv", "row": 7},
    }


@pytest.mark.parametrize("bad_errors", [{"field_path": "x"}, "not-an-array", 123, None])
def test_from_response_treats_non_array_errors_as_empty(
    bad_errors: object,
) -> None:
    body = {
        "type": "https://api.opticloud.cn/errors/bad_errors",
        "title": "Bad errors payload",
        "status": 422,
        "detail": "errors must be an array",
        "errors": bad_errors,
    }

    error = OptiCloudHTTPError.from_response(422, body)

    assert error.errors == []
    assert error.locate("x") is None
    assert error.remediation_keys() == []


def test_client_request_non_json_error_falls_back_to_empty_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class TextOnlyErrorResponse:
        status_code = 502
        text = "upstream provider failed"

        def json(self) -> dict[str, object]:
            raise ValueError("not json")

    client = OptiCloudClient(api_key="sk-test")

    def fake_request(method: str, path: str, **kwargs: object) -> TextOnlyErrorResponse:
        return TextOnlyErrorResponse()

    monkeypatch.setattr(client._client, "request", fake_request)
    try:
        with pytest.raises(OptiCloudHTTPError) as raised:
            client._request("GET", "/v1/anything")
    finally:
        client.close()

    error = raised.value
    assert error.status == 502
    assert error.title == "Unknown Error"
    assert error.detail == "upstream provider failed"
    assert error.errors == []
    assert error.raw == {
        "title": "Unknown Error",
        "detail": "upstream provider failed",
        "status": 502,
    }
