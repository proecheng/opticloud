"""Canonical Hypothesis strategies for OptiCloud schemas (Story 0.5b).

Each strategy produces inputs that satisfy OptiCloud Pydantic schema constraints,
so downstream property tests can focus on business invariants instead of
re-deriving valid inputs.

5 strategies covering ~80% of expected M2.2a/M3.2/3-14 test surface:
- uuids()              — UUID v4 (idempotency keys, optimization_id, user_id)
- api_key_prefixes()   — "sk-" + 3 base64-safe chars (matches D7 spec)
- error_details()      — RFC 7807 ErrorDetail (FG1.3)
- lp_inputs()          — random small LP problems (c, A, b) for solver tests
- monetary_amounts()   — 0.00 to 1_000_000.00 with 2 decimals (Credits / 元)
"""

from __future__ import annotations

import string
import uuid
from typing import Final

from hypothesis import strategies as st

from opticloud_shared.schemas.errors import ErrorDetail

_KEY_CHAR_ALPHABET: Final[str] = string.ascii_letters + string.digits + "-_"


def uuids() -> st.SearchStrategy[str]:
    """UUID v4 as string (canonical OptiCloud ID format)."""
    return st.builds(lambda: str(uuid.uuid4()))


def api_key_prefixes() -> st.SearchStrategy[str]:
    """'sk-' + 3 base64-safe chars (matches D7 spec; prefix is 6 visible chars).

    Returns the first-6-chars portion that is persisted to DB
    (PRD §1079: 前缀 6 位可见).
    """
    return st.builds(
        lambda triplet: f"sk-{triplet}",
        triplet=st.text(alphabet=_KEY_CHAR_ALPHABET, min_size=3, max_size=3),
    )


# ===== ErrorDetail (FG1.3 + RFC 7807) =====

_FIELD_PATH_ATOM = st.text(
    alphabet=string.ascii_lowercase + string.digits + "_", min_size=1, max_size=12
).filter(lambda s: not s[0].isdigit())

_FIELD_PATH_INDEX = st.integers(min_value=0, max_value=50).map(lambda n: f"[{n}]")


def _field_paths() -> st.SearchStrategy[str]:
    """Realistic field_path: atom or atom.atom or atom[0].atom etc."""
    return st.lists(
        st.one_of(_FIELD_PATH_ATOM, _FIELD_PATH_INDEX),
        min_size=1,
        max_size=4,
    ).map(_join_path)


def _join_path(parts: list[str]) -> str:
    """Join path parts: 'st' + '.A' + '[2]' + '[1]' → 'st.A[2][1]'."""
    out: list[str] = []
    for part in parts:
        if part.startswith("["):
            out.append(part)
        else:
            if out:
                out.append(".")
            out.append(part)
    return "".join(out) or "x"


def _scalar_values() -> st.SearchStrategy[object]:
    """Realistic error-context values."""
    return st.one_of(
        st.none(),
        st.booleans(),
        st.integers(min_value=-(10**9), max_value=10**9),
        st.floats(allow_nan=False, allow_infinity=False, min_value=-1e9, max_value=1e9),
        st.text(min_size=0, max_size=20),
    )


_CONSTRAINT_TEXT = st.sampled_from(
    [
        "must be >= 0",
        "must be > 0",
        "must be number",
        "infeasible_lp",
        "estimated_credits > balance",
        "max_solve_seconds × estimated_credit_per_second > balance",
        "type_mismatch",
    ]
)

_REMEDIATION_HINT_KEYS = st.sampled_from(
    [
        "errors.402.topup",
        "errors.422.non_negative",
        "errors.422.infeasible",
        "errors.422.positive_int",
        "errors.422.type_mismatch",
        "errors.409.idempotency_body_mismatch",
        "errors.504.solver_timeout",
    ]
)


def error_details() -> st.SearchStrategy[ErrorDetail]:
    """RFC 7807 ErrorDetail (FG1.3).

    Useful for: roundtrip tests, SDK error.locate() helper tests, i18n key
    consistency lint, Saga error payload validation.
    """
    return st.builds(
        ErrorDetail,
        field_path=_field_paths(),
        value=_scalar_values(),
        constraint=_CONSTRAINT_TEXT,
        remediation_hint_key=_REMEDIATION_HINT_KEYS,
    )


# ===== LP inputs (Story 3.14 mock-real divergence + future solver tests) =====


def lp_inputs(n_max: int = 6, m_max: int = 6) -> st.SearchStrategy[dict[str, object]]:
    """Random small LP: min c·x s.t. A·x ≤ b, x ≥ 0.

    Produces inputs in OptiCloud `POST /v1/optimizations` schema.
    Used by 3-14 (mock-real divergence) + future solver behavior tests.
    """
    return st.integers(min_value=1, max_value=n_max).flatmap(
        lambda n: st.integers(min_value=1, max_value=m_max).flatmap(
            lambda m: st.builds(
                lambda c, a, b: {
                    "task_type": "lp",
                    "minimize": {"c": c},
                    "st": {"A": a, "b": b},
                },
                c=st.lists(
                    st.floats(
                        min_value=-100.0, max_value=100.0, allow_nan=False, allow_infinity=False
                    ),
                    min_size=n,
                    max_size=n,
                ),
                a=st.lists(
                    st.lists(
                        st.floats(
                            min_value=-10.0, max_value=10.0, allow_nan=False, allow_infinity=False
                        ),
                        min_size=n,
                        max_size=n,
                    ),
                    min_size=m,
                    max_size=m,
                ),
                b=st.lists(
                    st.floats(
                        min_value=-100.0, max_value=1000.0, allow_nan=False, allow_infinity=False
                    ),
                    min_size=m,
                    max_size=m,
                ),
            )
        )
    )


# ===== Monetary amounts (Credits / 元, M2.2a Billing) =====


def monetary_amounts() -> st.SearchStrategy[float]:
    """Decimal amount 0.00 to 1_000_000.00 with 2 decimal places.

    Used by M2.2a Billing Saga state machine property tests:
    - reserve / charge / commit / refund consistency
    - idempotency key body hash invariance under whitespace
    """
    return st.decimals(
        min_value=0,
        max_value=1_000_000,
        allow_nan=False,
        allow_infinity=False,
        places=2,
    ).map(float)
