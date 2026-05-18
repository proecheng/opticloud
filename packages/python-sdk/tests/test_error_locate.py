"""Tests for OptiCloudHTTPError.locate() helper (FG1.3 + L1)."""

from __future__ import annotations

from opticloud.errors import OptiCloudHTTPError


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
