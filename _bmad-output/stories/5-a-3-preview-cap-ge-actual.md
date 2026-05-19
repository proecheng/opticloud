---
story_key: 5-a-3-preview-cap-ge-actual
epic_num: 5
story_num: A.3
epic_name: Billing — Credits & Saga
status: ready-for-dev
priority: 🟢 Medium-High (FR B2 必上; small scope — most of the math already shipped via 5.A.4)
sizing: S (~2-3 hours; mostly tests + tiny UX copy change; no new endpoint)
type: implementation + verification
created_by: bmad-create-story
created_at: 2026-05-19
sources:
  - _bmad-output/planning/epics.md L1633 (Story 5.A.3 — 预览封顶值 ≥ 实际 B2)
  - _bmad-output/planning/prd.md L1506 (FR B2 — 用户 can preview max Credits 封顶值 ≥ 实际)
  - apps/billing-service/src/billing_service/pricing.py (compute_charge_amount caps at reserved/max — invariant already in code)
  - apps/billing-service/src/billing_service/routes.py (POST /charges/estimate ↔ POST /charges/{id}/finalize)
  - apps/web/src/app/demo/charge/page.tsx (ChargeModal display copy — to emphasize "封顶")
  - packages/ui/src/components/ChargeModal/index.tsx (Title + amount line — needs cap clarity)
dependencies:
  upstream:
    - 5-a-4-per-formula-charging-capped (done) — compute_charge_amount math + /finalize endpoint
    - 5-a-5-p5-warning-modal (done) — /estimate endpoint returns estimated_amount
    - 5-a-2-credits-balance-buckets (done) — bucket display already shipped
    - m2-2b-saga-property-tests (done) — Hypothesis pattern to mirror
  downstream:
    - 5-a-7-billing-reconciliation — uses estimate↔actual diff for daily reconciliation alerts
---

# Story 5.A.3 — 预览封顶值 ≥ 实际 (FR B2)

## User Story

**As** a paying user who just saw "Confirm charge: ¥6.00" in the modal
**I want** absolute confidence that the displayed amount is a **maximum cap** — never less than what I'll actually pay — and the system **mathematically enforces** this invariant
**so that** I never see "you were charged ¥7" after agreeing to ¥6, and I can trust the preview number as a hard upper bound for budget planning.

## Why this story

PRD FR B2 is **v1 必上**. The math is already correct (5.A.4 `compute_charge_amount` clamps elapsed to `max_solve_seconds`), but:
1. There's no **explicit invariant test** that `actual ≤ estimated` for any (elapsed, max, rate) combination — a future refactor could silently break this
2. The ChargeModal currently shows "Confirm charge ¥6.00" with no UX hint that ¥6 is a CAP — a literal-minded user may believe ¥6 will always be debited
3. The full estimate→reserve→finalize chain has no end-to-end test asserting "the actual_amount returned by finalize is ≤ the estimated_amount returned by estimate"

5.A.3 closes all three with minimal code churn — most of the math is already in place; we add the *guarantee* layer.

## Out of scope

- **BalanceWarningModal Tier 2 component** (the epic AC text mentions it but per epics.md L191 it's v1.5+) — v1 keeps using existing ChargeModal + ConfirmationModal
- **Per-plan rate overrides** that could change the cap relationship — 5.B.1 scope
- **Predicted-actual telemetry** (logging estimate vs actual for analytics) — M3.6 scope
- **Refund flows for over-billing** — irrelevant; invariant prevents over-billing in the first place

## Acceptance Criteria

### AC1: Property test — actual_amount ≤ estimated_amount for ANY inputs

New test in `apps/billing-service/tests/test_property_saga_walks.py` (or a fresh `test_property_pricing.py` — TBD per file scope):

```python
@given(
    elapsed=st.floats(min_value=0.0, max_value=1000.0, allow_nan=False, allow_infinity=False),
    max_solve_seconds=st.floats(min_value=0.1, max_value=600.0, allow_nan=False, allow_infinity=False),
    rate_str=st.sampled_from(["0.01", "0.05", "0.10", "0.50", "1.00"]),
)
@settings(max_examples=50, deadline=2000, derandomize=True)
def test_actual_le_estimated_for_any_inputs(elapsed, max_solve_seconds, rate_str):
    """FR B2 — preview cap ≥ actual, for any (elapsed, max, rate)."""
    rate = Decimal(rate_str)
    # Reserved amount = "what /charges saw" = max × rate (5.A.4 ChargeCreateRequest)
    reserved = Decimal(str(max_solve_seconds)) * rate
    # Estimated amount = "what /estimate returns" = same formula
    estimated = reserved
    # Actual amount = "what /finalize computes" after solve
    actual = compute_charge_amount(
        elapsed_seconds=elapsed,
        max_solve_seconds=max_solve_seconds,
        rate_per_second=rate,
        min_amount=Decimal("0.00"),  # disable floor for pure invariant test
        reserved_amount=reserved,
    )
    # FR B2 invariant
    assert actual <= estimated, f"actual={actual} > estimated={estimated} (elapsed={elapsed}, max={max_solve_seconds}, rate={rate})"
```

The `min_amount=Decimal("0.00")` argument removes the floor (which could violate strict `actual ≤ estimated` when estimated is sub-cent — e.g., max=0.1s × 0.01/s = 0.001, floored to 0.01 > estimated). The floor is a user-friendly UX choice (charge at least 1 cent for any solve), but the strict B2 invariant only applies when both estimated and actual go through the same flooring. **AC1a below covers the with-floor case**.

### AC1a: Property test with floor — actual ≤ max(estimated, min_amount)

```python
@given(
    elapsed=st.floats(min_value=0.0, max_value=1000.0, allow_nan=False, allow_infinity=False),
    max_solve_seconds=st.floats(min_value=0.1, max_value=600.0, allow_nan=False, allow_infinity=False),
)
def test_actual_le_max_estimated_or_min_floor(elapsed, max_solve_seconds):
    """With min_amount floor active, actual <= max(estimated, min_amount)."""
    rate = Decimal("0.10")
    min_floor = Decimal("0.01")
    reserved = Decimal(str(max_solve_seconds)) * rate
    actual = compute_charge_amount(
        elapsed_seconds=elapsed,
        max_solve_seconds=max_solve_seconds,
        rate_per_second=rate,
        min_amount=min_floor,
        reserved_amount=reserved,
    )
    estimated = reserved  # what user sees in preview
    cap = max(estimated, min_floor)
    assert actual <= cap, (
        f"actual={actual} > cap={cap} (elapsed={elapsed}, max={max_solve_seconds})"
    )
```

This is the **practical** B2 invariant: the user-visible cap shown in the modal is either the rate-based max OR (in pathological sub-cent cases) the min_floor. The modal copy in AC4 will show `max(estimated, min_amount)` as the displayed cap.

### AC2: End-to-end chain test — estimate.estimated_amount ≥ finalize.actual_amount

New `test_property_estimate_finalize_chain` test:

```python
@given(elapsed_seconds=st.floats(min_value=0.1, max_value=120.0, allow_nan=False, allow_infinity=False))
@settings(max_examples=20, deadline=4000, derandomize=True, suppress_health_check=[HealthCheck.function_scoped_fixture])
async def test_estimate_amount_ge_finalize_actual(
    http_client, auth_headers, elapsed_seconds
):
    """Full HTTP chain: estimate.estimated_amount >= finalize.actual_amount."""
    # 1. Estimate
    est = await http_client.post(
        "/v1/billing/charges/estimate",
        json={"purpose": "solve", "max_solve_seconds": 60.0},
        headers=auth_headers,
    )
    estimated = Decimal(est.json()["estimated_amount"])

    # 2. Reserve
    create = await http_client.post(
        "/v1/billing/charges",
        json={"amount": str(estimated), "currency": "CNY", "purpose": "solve",
              "reference_id": str(uuid.uuid4()), "max_solve_seconds": 60.0, "confirmed": True},
        headers={**auth_headers, "Idempotency-Key": str(uuid.uuid4())},
    )
    charge_id = create.json()["charge_id"]
    await http_client.post(f"/v1/billing/charges/{charge_id}/reserve", headers=auth_headers)

    # 3. Finalize with random elapsed_seconds
    fin = await http_client.post(
        f"/v1/billing/charges/{charge_id}/finalize",
        headers=auth_headers,
        json={"elapsed_seconds": elapsed_seconds, "status": "success", "failure_reason": None},
    )
    actual = Decimal(fin.json()["actual_amount"])

    # FR B2 invariant — actual NEVER exceeds estimated
    assert actual <= estimated, (
        f"actual={actual} > estimated={estimated} (elapsed={elapsed_seconds})"
    )
```

This is the HIGH-VALUE test — it exercises the entire HTTP chain, not just the pure function. If a future refactor breaks the route layer's amount derivation, this test catches it.

### AC3: ChargeModal copy clarity — emphasize "封顶 / max"

`packages/ui/src/components/ChargeModal/index.tsx`:
- Title text changes from "Confirm charge / 确认扣费" to "Confirm charge (cap) / 确认扣费（封顶）"
- New small inline note below the amount: "Final charge ≤ this amount / 实际扣费 ≤ 此金额"
- Update Storybook with a story showing the new copy

These are pure-string changes. The component's prop signature is unchanged.

### AC4: Demo page wording — show estimate-vs-actual context

Update `apps/web/src/app/demo/charge/page.tsx`:
- The estimate body block already shows "Estimated max charge: ¥6.00" — extend with a tooltip-style note: "(actual ≤ estimated)"
- After a successful charge, the success toast already shows `"Charged ¥{actual}. New balance: ..."` — emphasize when actual < estimated by adding a "saved ¥X" suffix (e.g., "Charged ¥0.50 (saved ¥5.50 from cap). New balance: ¥44.00")

The "saved" calc: `saved = estimated - actual`. The numbers come from the demo's existing state.

### AC5: Quality gates

- `uv run ruff check apps packages` → 0 errors
- `uv run ruff format --check apps packages` → 0 changes needed
- `uv run mypy apps packages` → 0 errors
- `pnpm -C apps/web build` → 0 errors
- All Python regression tests pass; billing 124 → 127 (+3 from this story)

### AC6: NFR alignment

- **FR B2** ✅ AC1 + AC1a + AC2 enforce + verify the invariant
- **NFR-R4 (对账误差 = 0)**: property tests strengthen confidence in the math, additive to M2.2b
- **UX clarity** (no specific NFR, but inferred from "讓人 trust") — AC3 + AC4 copy improvements

## Tasks

### T1: Property test for compute_charge_amount cap invariant (1h)
1. New file `apps/billing-service/tests/test_property_pricing.py` — clean home for pricing-math properties (test_property_saga_walks.py is saga-focused)
2. Implement AC1 (strict invariant, no floor) + AC1a (practical invariant with floor)
3. Both use `@given` + `@settings(max_examples=50, derandomize=True)` per project pattern
4. Run isolated: pure function, no DB, very fast (<1s for 100 examples)

### T2: HTTP-chain estimate→finalize property test (0.5h)
1. Extend `test_property_saga_walks.py` OR add to new test_property_pricing.py with HTTP fixtures
2. Decision: keep saga-walks file pure-orchestrator; add to test_property_pricing.py (which can have HTTP fixtures)
3. Uses fresh user via `token_factory` + `_create_user_row` helper (already exists in test_charge_routes.py — move to conftest.py if reused)

### T3: ChargeModal copy update (0.5h)
1. Update title + inline note per AC3
2. Add Storybook story `CapEmphasis_5A3` showing the new copy
3. Vitest test: assert that the new "Final charge ≤" text appears in rendered output

### T4: Demo page wording (0.5h)
1. Update ConfirmationModal body to add "(actual ≤ estimated)" note
2. Compute `saved = estimated - actual` and append "(saved ¥X)" to success toast when > 0
3. `pnpm build` regression guard

### T5: Quality gates + sprint sync + PR (0.5h)
1. Run AC5 gates
2. Update sprint-status.yaml
3. Commit + push + PR
4. Wait CI green; merge with squash

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| AC1 strict invariant fails when min_amount > rate × max (sub-cent cap pathological case) | AC1 explicitly disables floor by passing `min_amount=Decimal("0.00")` to isolate the rate × cap invariant. AC1a covers the floor case with `actual ≤ max(estimated, min_amount)`. |
| AC2 HTTP chain test creates many DB rows under @given (50 examples × 3 HTTP calls = 150 inserts) | Reduce `max_examples=20` for HTTP chain test (DB I/O cost). Pure-function AC1/AC1a stays at 50. Total runtime budget < 10s. |
| ChargeModal copy change breaks Vitest a11y snapshot tests | Pre-existing `Tier1.a11y.test.tsx` 12 failures are tagged as unrelated tech-debt; I'm not adding to them. Confirm new copy still passes axe-core (no contrast violation from longer text). |
| "saved ¥X" suffix in success toast confuses users who didn't see the warning modal | Only render the "saved" suffix when `estimated_amount - actual_amount > Decimal("0.10")` (≥10 cents threshold avoids "saved ¥0.01" noise). |

## Non-Functional Requirements Mapping

- **FR B2** ✅ AC1 + AC1a + AC2 enforce; AC3 + AC4 communicate
- **NFR-R4** (对账误差 = 0): property tests add confidence
- **UX EP3** (Confidence): clearer cap language reduces "surprise" anxiety

## Definition of Ready

- ✅ compute_charge_amount exists from 5.A.4
- ✅ /estimate endpoint exists from 5.A.5
- ✅ /finalize endpoint exists from 5.A.4
- ✅ ChargeModal exists from 5.A.1
- ✅ Hypothesis pattern from M2.2b
- ✅ All 3 review rounds applied (next step)

## Definition of Done

- All 6 ACs pass
- Test counts: billing 124 → 127 (+3 = 2 pure-function + 1 HTTP-chain)
- CI green on PR
- sprint-status.yaml updated; `5-a-3-preview-cap-ge-actual: done`
- Memory updated
- Manual smoke: /demo/charge displays "(actual ≤ estimated)" hint; success toast shows "saved" suffix when applicable
- Code review with full quality gates documented in commit body

## Sign-off

| Role | Owner | Signed | Date |
|---|---|:-:|:-:|
| Billing Lead | TBA | ☐ | — |
| UX Lead | TBA | ☐ | — |

> Owner committee deferred per M0 skip.
