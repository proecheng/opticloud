---
story_key: 5-a-5-p5-warning-modal
epic_num: 5
story_num: A.5
epic_name: Billing — Credits & Saga
status: ready-for-dev
priority: 🟢 High (FR B6 必上, v1 必须; naturally unblocked by 5.A.4 2-phase split — guard sits between charges/create and charges/{id}/reserve)
sizing: M (~5h; billing estimate endpoint + web demo gating + tests; no new packages/ui component)
type: implementation
created_by: bmad-create-story
created_at: 2026-05-19
sources:
  - _bmad-output/planning/epics.md L1641 (Story 5.A.5: Modal P5 警示 + 余额 < 预估警示 (B6))
  - _bmad-output/planning/prd.md L1510 (FR B6 — 系统 can warn via Modal when P5 调用 OR 余额 < 预估)
  - _bmad-output/planning/architecture.md L1114 (P51 Notification — blocking Modal for P5 警示)
  - _bmad-output/planning/ux-design-specification.md L376+L404 (EP5 / CF2 — non-blocking Toast for streaming; blocking Modal for confirmation contexts ONLY)
  - packages/ui/src/components/ConfirmationModal/index.tsx (existing Tier1 component with 5 variant branches incl. balance_warn + p5_alert)
  - apps/billing-service/src/billing_service/routes.py (5.A.1 + 5.A.4 — POST /charges + /reserve + /finalize where the new estimate gates)
  - apps/web/src/app/demo/charge/page.tsx (5.A.1 demo page to extend)
dependencies:
  upstream:
    - 5-a-1-j1-credits-charge-modal (done) — ChargeModal + /demo/charge baseline
    - 5-a-4-per-formula-charging-capped (done) — 2-phase reserve/finalize; guard sits between create and reserve
    - 0-9-ui-tier1-stubs (done) — ConfirmationModal scaffolded with 5 variants
  downstream:
    - 5-a-6-topup-flow — topup will trigger p5_alert variant when buying expensive packs
    - 4-A-x-chat-warnings — chat uses Toast (not Modal) per CF2; this story locks the Modal-vs-Toast contract
---

# Story 5.A.5 — Modal P5 警示 + 余额 < 预估警示 (FR B6)

## User Story

**As** a user about to submit a paid LP solve
**I want** the system to warn me with an explicit confirmation modal when (a) my balance is lower than the maximum possible cost, OR (b) I'm submitting a known-expensive "P5 调用" — and require me to explicitly confirm before billing reserves any credits
**so that** I never get charged for a solve I would have cancelled, and high-cost calls are paywall-gated by user attention, not silent debit.

## Why this story

PRD FR B6 is **v1 必上** (mandatory ship). Today (post-5.A.4) the demo path is:
1. User clicks "Try a charge"
2. App calls `POST /v1/billing/charges` (creates Saga, balance check)
3. App calls `POST /v1/billing/charges/{id}/reserve`
4. App calls `POST /v1/billing/charges/{id}/finalize`

There's no point where the user sees "this could cost up to ¥6 vs your ¥3 balance, are you sure?" — they just get a 422 after step 2 if balance is insufficient. That's reactive, not preventive. 5.A.5 adds a **preview + explicit confirm** step BEFORE step 2.

5.A.4 split confirm into 2 phases specifically to make room for this guard. The natural insertion point is **before `POST /charges`** — i.e., a new `POST /charges/estimate` returns the projected max cost + balance + warnings, and the UI decides whether to gate the user behind ConfirmationModal.

## Out of scope

- **Non-blocking Toast** for streaming contexts (chat / NL) → 4.A.x chat warnings (CF2 lock — streaming MUST use Toast, never Modal; recorded in ADR or note here for future stories)
- **Tier 2 `BalanceWarningModal`** wrapper component → v1.5+ per epics.md L191; v1 reuses ConfirmationModal directly with `variant="balance_warn" | "p5_alert"`
- **P5 调用 specific business rules** — what exactly counts as "P5"? For v1 it's a server-classified threshold (any single charge ≥ `settings.p5_call_threshold`, default ¥3). Per-SKU / per-provider P5 classification → 5.B.1 plan-based pricing
- **Monthly budget alert** (FR B12) → separate Story 5.D.x
- **Refund-after-confirm flows** → 5.C.1
- **Persisting "user explicitly confirmed" audit trail** — v1 returns `confirmed: true` in the create body and billing logs `metadata_json.user_explicitly_confirmed_at`; full audit table in M3

## Acceptance Criteria

### AC1: New billing-service endpoint — `POST /v1/billing/charges/estimate`

Request body (no charge created; pure preview):
```json
{
  "purpose": "solve" | "predict" | "chat" | "demo",
  "max_solve_seconds": 60.0
}
```

Response (200):
```json
{
  "estimated_amount": "6.00",        // max possible charge = max_solve_seconds × lp_rate_per_second
  "currency": "CNY",
  "balance": "3.50",                 // current user balance (pure read, no seed)
  "warnings": [
    {
      "kind": "balance_low",          // "balance_low" | "p5_call" | "p5_call_and_balance_low"
      "message": "Balance ¥3.50 is below estimated max charge ¥6.00",
      "remediation_hint_key": "warnings.balance_low"
    }
  ],
  "requires_explicit_confirm": true   // true iff warnings is non-empty
}
```

- Auth: Bearer JWT OR `X-Internal-Service-Auth` (re-uses 5.A.4 `require_user`)
- **NO seeding side effect** — this is a pure GET-shaped POST (POST chosen because body parameters are payable-context-specific and we don't want them in URL query strings; matches REST sensibility for "calculate" operations)
- **NO Saga created** — distinct from `POST /charges` which DOES create a PENDING Saga; estimate is stateless
- 401 if missing/invalid auth; 422 if `max_solve_seconds > 600` (matches solver upper bound)

### AC2: Warning classification rules (server-side)

In billing config (Settings additions per AC2c below):
- `p5_call_threshold: Decimal = Decimal("3.00")` — any estimate ≥ this triggers `p5_call` warning
- `balance_low_ratio: Decimal = Decimal("1.00")` — balance < (estimate × ratio) triggers `balance_low` (default = balance < estimate exactly)

Classification logic (pure function, new module `pricing.classify_warnings`):
```python
def classify_warnings(
    estimated_amount: Decimal,
    balance: Decimal,
    *,
    p5_call_threshold: Decimal,
    balance_low_ratio: Decimal,
) -> list[Warning]:
    """Returns 0-2 warnings; same shape as AC1 response.warnings[]."""
```

Cases (verified by AC8 tests):
| estimated | balance | p5_threshold | warnings |
|---:|---:|---:|---|
| 1.00 | 50.00 | 3.00 | `[]` — no warnings |
| 6.00 | 50.00 | 3.00 | `[{p5_call}]` — high cost, balance fine |
| 1.00 | 0.50 | 3.00 | `[{balance_low}]` — low balance, cheap call |
| 6.00 | 3.00 | 3.00 | `[{p5_call_and_balance_low}]` — both — merged into ONE warning so UI shows one block, not two |

The "merged" 3rd warning kind keeps the UI simple — at most one warning row in the Modal.

**A4 fix — message templates (server-side, English; M3 will add i18n)**:
```python
_MESSAGE_TEMPLATES = {
    "balance_low": "Balance ¥{balance:.2f} is below estimated max charge ¥{estimated:.2f}",
    "p5_call": "Estimated max charge ¥{estimated:.2f} exceeds the high-cost threshold ¥{threshold:.2f}",
    "p5_call_and_balance_low": (
        "Estimated max charge ¥{estimated:.2f} exceeds the high-cost threshold ¥{threshold:.2f} "
        "AND your balance ¥{balance:.2f} is insufficient"
    ),
}
```
The `remediation_hint_key` (used by clients for i18n M3) maps 1:1 with `kind`: `warnings.{kind}`.

### AC3: Auth-equal-trust enforcement

The estimate endpoint MUST use the same auth-precedence pattern as `/charges` (5.A.4 R1.2): try `X-Internal-Service-Auth` bridge first, fall back to Bearer JWT. Solver-orchestrator can call estimate inline before a solve if needed in future stories (e.g., pre-flight check before locking compute).

### AC4: `POST /v1/billing/charges` requires `confirmed: bool` when warnings exist

Backward-compatible extension to ChargeCreateRequest:
```python
class ChargeCreateRequest:
    amount: Decimal
    currency: Literal["CNY"]
    purpose: Literal[...]
    reference_id: str
    max_solve_seconds: float = 60.0     # 5.A.4
    confirmed: bool = False              # 5.A.5 NEW — must be True when warnings exist
```

Server enforcement (`POST /charges`):
1. Compute warnings (call the same `classify_warnings` used by estimate)
2. If `warnings != [] and body.confirmed != True` → return **422 RFC 7807** with `title="Explicit Confirmation Required"`, `errors[].field_path="body.confirmed"`, `errors[].constraint="warnings exist, confirmed must be true"` (R1.5 — semantic validation, not authz)
3. If `warnings == []` → accept whether `confirmed` is true or false (back-compat — 5.A.1/5.A.4 demo doesn't set confirmed, still works for no-warning case)
4. If `warnings != [] and body.confirmed == True` → accept; pass `user_explicitly_confirmed: True` (boolean flag, NOT a timestamp — DR2 fix from implementation: timestamps break body-hash idempotency on retries) into `orch.start()` via the `payload` dict. The "when" is `SagaInstance.created_at`; the "who" is `SagaInstance.user_id`. No schema change.

This is the **server-side gate** — the web UI is the cooperator, but anyone bypassing the UI (curl, SDK) cannot silently skip the warning.

### AC5: Web demo flow — pre-charge guard

New flow on `/demo/charge`:
1. User clicks "Try a ¥6 charge" → app calls `POST /v1/billing/charges/estimate` with `{purpose: "demo", max_solve_seconds: 60.0}` (the "demo" purpose maps to a fixed amount-of-¥6 today; in future this will compute from real LP submission)
2. Show a `<ConfirmationModal variant="balance_warn"|"p5_alert">` (Tier 1 existing component) IF `requires_explicit_confirm=true`
   - Title: `"⚠ 高额扣费确认 / High-cost charge confirmation"` if `p5_call`, `"⚠ 余额不足提示 / Balance warning"` if `balance_low`, both if combined
   - Body: warning message from response + a small recap: `"Estimated max charge: ¥6.00 | Current balance: ¥3.50"`
   - Confirm label: `"我已理解，继续扣费 / I understand, proceed"`
   - Cancel label: `"取消 / Cancel"`
3. On user confirm: proceed to existing ChargeModal flow, but pass `confirmed: true` in the `/charges` body
4. If `requires_explicit_confirm=false`: skip ConfirmationModal, go directly to ChargeModal (existing flow unchanged for the happy path)
5. On user cancel from ConfirmationModal: close modal, no API call, no state change

### AC6: ConfirmationModal variant mapping in web

```typescript
function variantFor(warnings: Warning[]): ConfirmationVariant {
  if (warnings.length === 0) return "generic";        // shouldn't be shown anyway
  const kinds = new Set(warnings.map(w => w.kind));
  if (kinds.has("p5_call") || kinds.has("p5_call_and_balance_low")) return "p5_alert";
  return "balance_warn";
}
```

Note: `p5_call_and_balance_low` → `p5_alert` (the more visually-prominent warning wins; matches the "more conservative" UX principle of escalating to the highest severity).

### AC7: Cross-service Saga compatibility

Story 5.A.4 wired solver-orchestrator to call `POST /charges/reserve` after the user creates a charge. With 5.A.5, the flow becomes:
1. Web → billing `POST /charges/estimate`
2. Web → user (Modal, maybe)
3. Web → billing `POST /charges` with `confirmed=true`
4. Web → solver `POST /optimizations` with `X-Billing-Charge-Id`
5. Solver → billing `POST /charges/{id}/reserve` (5.A.4 path)
6. Solver runs LP
7. Solver → billing `POST /charges/{id}/finalize`

The guard ONLY exists between steps 1-3. Steps 4-7 are unchanged from 5.A.4. The /demo/charge page in v1 doesn't yet wire the solver step (still just /reserve + /finalize directly via the deprecated /confirm — 5.A.5 is also out-of-scope for fully migrating /demo/charge to 5.A.4's split-phase; that migration is M3 hardening).

For /demo/charge in 5.A.5: keep using the deprecated `/confirm` endpoint AFTER the estimate gate — minimal UI change.

### AC8: Backend tests (billing-service)

**New: `apps/billing-service/tests/test_classify_warnings.py`** (6 pure-function cases per AC2 table)
1. `classify_warnings(Decimal("1.00"), Decimal("50.00"), p5=3, ratio=1.0) == []`
2. `classify_warnings(Decimal("6.00"), Decimal("50.00"), p5=3, ratio=1.0)` → 1 warning kind=`p5_call`
3. `classify_warnings(Decimal("1.00"), Decimal("0.50"), p5=3, ratio=1.0)` → 1 warning kind=`balance_low`
4. `classify_warnings(Decimal("6.00"), Decimal("3.00"), p5=3, ratio=1.0)` → 1 warning kind=`p5_call_and_balance_low`
5. `classify_warnings(Decimal("3.00"), Decimal("50.00"), p5=3, ratio=1.0)` → 1 warning kind=`p5_call` (at threshold, INCLUSIVE)
6. `classify_warnings(Decimal("0.50"), Decimal("0.50"), p5=3, ratio=1.0) == []` (balance equals estimate, not below — exclusive)

**Extend: `apps/billing-service/tests/test_charge_routes.py`** (4 new cases)
7. `POST /charges/estimate` happy path, no warnings → 200 + warnings=[] + requires_explicit_confirm=false
8. `POST /charges/estimate` insufficient balance → 200 + warnings=[balance_low] + requires_explicit_confirm=true (does NOT 422 — it's preview)
9. `POST /charges` with warnings + confirmed=false → **422** RFC 7807 with `body.confirmed` field_path (R1.5)
10. `POST /charges` with warnings + confirmed=true → 201 (Saga PENDING created) + `payload_ref.user_explicitly_confirmed_at` ISO-timestamp persisted on `SagaInstance` row (R1.3 — query SagaInstance via session.get, NOT credit_transactions)

### AC9: Frontend tests

**Extend: `apps/web/src/app/demo/charge/page.tsx` integration test** (manual smoke — no automated browser test required for 5.A.5 unless trivial; defer full E2E to M3)
- Local manual: visit /demo/charge, click "Try a ¥6 charge", with seeded balance ¥50 (default, no warnings) → ConfirmationModal does NOT appear, ChargeModal opens directly
- Local manual: drain balance to ¥3 first (post a low-amount charge), then click "Try a ¥6 charge" → ConfirmationModal appears with `balance_low` text; confirm → ChargeModal opens; cancel → nothing happens

**Storybook story** — add 2 new stories to existing ConfirmationModal.stories.tsx:
- "5.A.5 — Balance Low Warning" (variant=balance_warn, body has `Estimated: ¥6.00 | Balance: ¥3.50`)
- "5.A.5 — P5 High-Cost Warning" (variant=p5_alert, body has `Estimated: ¥6.00 (above ¥3.00 P5 threshold)`)

### AC10: Quality gates (per `feedback_full_quality_gates`)

Run BEFORE committing:
- `uv run ruff check apps packages` → 0 errors
- `uv run ruff format --check apps packages` → 0 changes needed
- `uv run mypy apps packages` → 0 errors
- `uv tool run pre-commit run --all-files` → all hooks pass except license-check (Windows env issue)
- `pnpm -C apps/web build` → 0 errors
- ALL Python regression tests pass per-service + 4 new tests + 6 new classify_warnings tests + Vitest still passes

### AC11a: Prometheus metric (SRE1)

Billing-service adds:
- `billing_estimate_total{warnings_kind="none"|"balance_low"|"p5_call"|"p5_call_and_balance_low"}` Counter — increments per /estimate call labelled with the warning shape (cardinality bounded = 4 + 1 for "none"). Lets ops dashboards observe how often users hit pre-charge guard vs sail through.

### AC11: NFR alignment

- **FR B6** (system can warn via Modal when P5 调用 OR 余额 < 预估): AC1 + AC2 + AC5
- **NFR-P1** (HTTP P95 < 300ms): estimate < 80ms P95 (single SELECT for balance + pure function classify; no SELECT FOR UPDATE, no transaction)
- **NFR-S2** (user_id always from auth context): AC3 — same `require_user` dep as /charges
- **NFR-A1** (PIPL): estimate response contains no PII (just amounts + user_id implicit in auth)
- **UX EP5 / CF2**: this story's Modal is the **confirmation context** (user-submission gate), NOT streaming context. Modal usage is consistent with the UX-spec CF2 rule. Documented in story so future readers understand why Modal is correct here despite UX-spec preferring Toast in chat scenarios.

## Tasks

### T1: Backend — classify_warnings + config additions (1h)
1. Extend `apps/billing-service/src/billing_service/pricing.py` (add to existing module, not new file):
   - New `Warning` dataclass with fields `kind`, `message`, `remediation_hint_key`
   - New `classify_warnings(estimated_amount, balance, *, p5_call_threshold, balance_low_ratio) -> list[Warning]` per AC2
2. Add to `config.py` Settings: `p5_call_threshold: Decimal = Decimal("3.00")` + `balance_low_ratio: Decimal = Decimal("1.00")`
3. mypy strict pass

### T2: Backend — estimate endpoint + /charges guard (1.5h)
1. Extend `schemas.py`:
   - New `EstimateRequest` (`purpose: Literal[...]`, `max_solve_seconds: float = 60.0 ge=0.1 le=600.0`)
   - New `EstimateResponse` (`estimated_amount`, `currency`, `balance`, `warnings: list[Warning]`, `requires_explicit_confirm: bool`)
   - New `Warning` Pydantic model (str fields)
   - Add `confirmed: bool = False` to `ChargeCreateRequest`
2. New route `POST /v1/billing/charges/estimate` in `routes.py`:
   - Auth: `Depends(require_user)` (re-uses internal-service bridge from 5.A.4)
   - Computes `estimated = max_solve_seconds × lp_rate_per_second` (uses `pricing.compute_charge_amount` with elapsed=max_solve_seconds, reserved=∞)
   - Reads balance via existing `_balance_for` helper
   - Calls `classify_warnings` with config thresholds
   - Returns 200 EstimateResponse
3. Extend `POST /v1/billing/charges` route:
   - After balance check, before Saga.start: if `warnings = classify_warnings(amount, balance)` is non-empty AND `body.confirmed != True` → return **422** RFC 7807 (R1.5)
   - If accepted with warnings: include `user_explicitly_confirmed_at=<datetime.now(UTC).isoformat()>` in the `payload` dict passed to `orch.start()` — this becomes `saga.payload_ref["user_explicitly_confirmed_at"]` auditable on the SagaInstance row. No new column, no orchestrator change (R1.1).
4. mypy strict pass

### T3: Backend tests (1h)
1. New `test_classify_warnings.py` — 6 cases per AC8
2. Extend `test_charge_routes.py` — 4 new cases (rows 7-10)
3. Verify all 99+ billing tests still pass (regression)

### T4: Web demo wiring (1h)
1. Extend `apps/web/src/lib/api.ts`:
   - New `estimateCharge(args) → Promise<EstimateResponse>` HTTP helper
   - Update `createCharge(...)` signature to accept optional `confirmed: boolean` and include it in body
2. Extend `apps/web/src/app/demo/charge/page.tsx`:
   - Wrap "Try a ¥6 charge" click handler with estimate call first
   - State machine: `idle → estimating → (showWarning|showCharge)`
   - If `requires_explicit_confirm=true` → render ConfirmationModal first; on confirm → close warning + open ChargeModal with `confirmed=true` threading; on cancel → reset to idle
   - If false → open ChargeModal directly (today's flow)
3. Import `ConfirmationModal` from `@opticloud/ui` (already exported)

### T5: Frontend Storybook + manual smoke (0.5h)
1. Extend `packages/ui/src/components/ConfirmationModal/index.stories.tsx` with 2 new stories per AC9
2. Manual browser check at /demo/charge — both warning and no-warning paths

### T6: Quality gates + sprint sync + PR (0.5h)
1. Run full quality gate sequence per AC10
2. Update sprint-status.yaml + memory file
3. Commit + push + PR
4. Wait CI green → squash merge

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Server-side guard can be bypassed by callers setting `confirmed=true` blindly | This is **acceptable** for v1 — `confirmed=true` is an explicit user-agent attestation. The bigger goal is the *honest UI* gates the warning visually. A malicious script bypassing it gets exactly the same outcome it would get today (charge without warning) — no new attack surface. M3 may add additional CAPTCHA / signed attestation for high-value charges. |
| Estimate endpoint is a write-shaped POST without write side effects — could confuse cache layers | Returns standard 200 with no `Cache-Control: max-age` — clients should not cache by HTTP convention. Documented in OpenAPI description. |
| Concurrent: user gets estimate (no warning), spends balance in another tab, then submits → balance now low but `confirmed=false` was OK at estimate time | Server re-evaluates warnings at `/charges` time — if balance has dropped between estimate and submit, the 403 fires and user must re-estimate. Two RTTs in pathological case, acceptable. Documented in OpenAPI. |
| Two thresholds (`p5_call_threshold` ¥3, `balance_low_ratio` 1.0) are global config — what if Free vs Pro plans want different thresholds? | Per-plan thresholds = 5.B.1 scope. v1 global defaults make sense because LP is the only paid surface. Documented in story body. |
| "Merged" warning kind `p5_call_and_balance_low` proliferates string enums | Single enum entry, finite combinatorial space (2² - 1 = 3 non-trivial states). Acceptable for v1. If new warning kinds appear in M3, refactor to `list[Warning]` with no merging. |
| /demo/charge UI rendering 2 modals back-to-back could feel laggy | ConfirmationModal close + ChargeModal open both fire on the same React render commit; should appear instantaneous on local hardware. If real users report jank in M3, add a 100ms transition; deferred. |

## Non-Functional Requirements Mapping

- **FR B6**: AC1 + AC2 + AC4 + AC5 — the warning Modal IS the v1 implementation of FR B6
- **NFR-P1** (HTTP P95 < 300ms): AC11 — estimate < 80ms target
- **NFR-S2** (user_id from JWT only): AC3 — `require_user` enforced; user can't pass user_id in body/query
- **UX EP5/CF2**: documented in AC11 (Modal correct for confirmation context; Toast deferred to chat in 4.A.x)

## Definition of Ready

- ✅ ConfirmationModal Tier 1 already exists with 5 variants (Story 0.9 stub + later refinement)
- ✅ /charges endpoint exists from 5.A.1 (extending, not adding new for primary flow)
- ✅ 5.A.4 split-phase + auth bridge means we know exactly where guard sits
- ✅ pricing.py module exists from 5.A.4 (extending, not creating)
- ✅ All 3 review rounds applied (next step)

## Definition of Done

- All 11 ACs pass
- Test counts: billing +10 (6 classify_warnings unit + 4 route tests); solver unchanged; total active tests = 156 + 10 = **166** (no Vitest changes — Storybook stories don't run tests)
- CI green on PR
- Sprint-status.yaml updated
- Memory updated with new commit + test counts
- Manual smoke: /demo/charge browser flow tested both with and without warning
- Code review with full quality gates documented in commit body

## Sign-off (story-level)

| Role | Owner | Signed | Date |
|---|---|:-:|:-:|
| Architect | proposed by AI | ☐ | — |
| Billing Lead | TBA | ☐ | — |
| UX Lead | TBA | ☐ | — |

> Owner committee deferred per M0 skip.
