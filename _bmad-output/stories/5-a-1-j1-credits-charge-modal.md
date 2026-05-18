---
story_key: 5-a-1-j1-credits-charge-modal
epic_num: 5
story_num: A.1
epic_name: Billing — Credits & Saga
status: done
priority: 🔴 Critical (J1 Vertical Slice 第 4 段 — completes the signup → algorithms → solve → CHARGE end-to-end demo)
sizing: M-L (5-7 hours; billing HTTP API + ChargeModal UI + dev demo wiring)
type: implementation
created_by: bmad-create-story
created_at: 2026-05-18
sources:
  - _bmad-output/planning/epics.md (Story 5.A.1)
  - _bmad-output/planning/prd.md v1.1 (FR B1 charge intent / FR B5 balance display / FG1.1 J1 anchor)
  - _bmad-output/planning/ux-design-specification.md (ChargeModal pattern; Tier 1 component)
  - docs/adr/0001-saga-pattern.md (Hybrid Saga; orchestrator API)
  - apps/billing-service/src/billing_service/saga_orchestrator.py (the engine 5.A.1 calls)
  - apps/auth-service/src/auth_service/routes.py (FastAPI route conventions to copy)
  - packages/ui/src/components/ConfirmationModal/index.tsx (modal pattern to mirror)
dependencies:
  upstream:
    - 5-a-0a-saga-implementation (done) — SagaOrchestrator is the engine
    - 0-9-ui-tier1-stubs (done) — packages/ui components scaffolded
    - 0-6-auth-scaffold (done) — JWT/API-Key auth middleware pattern
    - 1-1a-j1-signup-api-key (done) — user has token to call charges
  downstream:
    - 5-a-2-credits-balance-buckets — buckets refine balance display
    - 5-a-5-p5-warning-modal — warning when balance < threshold
    - m2-2a-billing-critical-tests — 50 scenarios target this API
---

# Story 5.A.1 — J1 Credits Charge Modal (HTTP API + UI)

## User Story

**As** a logged-in user who has just submitted an LP problem
**I want** to see a confirmation modal showing the cost + my current balance and explicitly confirm before being charged
**so that** I never get surprise debits and I know how much each solve will cost me.

## Why this story

J1 Vertical Slice (5 anchors) is the demo flow:
1. ✅ Signup + get API key (1.1a/b)
2. ✅ Browse algorithms (2.1)
3. ✅ Submit LP problem + solve (3.1)
4. ⏳ **Charge confirmation modal + balance display ← THIS STORY**
5. (Combined with #3) See solution

Without 5.A.1 the demo is "we charge you silently" — a non-starter for trust + PRD FR B1.

This story wraps the **existing** SagaOrchestrator (5.A.0a) behind HTTP, and adds the user-facing confirmation step. It's deliberately **scoped before** real cross-service billing integration with solver-orchestrator (deferred to 5.A.4 / M2.2a) — for 5.A.1, the web app calls billing **directly** for the charge, then calls solver for the solve. The two calls are not (yet) in one transactional Saga across services.

## Out of scope

- **Solver-orchestrator → billing-service** in-call charge (cross-service Saga) → 5.A.4
- **Pre-charge guard rules** (balance < min, monthly cap, etc.) → 5.A.5
- **Topup / payment** (how balance gets ≥ 0) → 5.A.6
- **Plan-based pricing** (different tiers pay different ¥/call) → 5.B.1
- **Credit buckets** (different buckets for promo / topup / refund) → 5.A.2

## Acceptance Criteria

### AC1: billing-service exposes 3 HTTP endpoints
- `POST /v1/billing/charges`
  - Body: `{ amount: string-decimal e.g. "6.00", currency: "CNY", purpose: "solve" | "predict" | "chat", reference_id: UUID }` (D3 fix: amount as **string** in JSON for precision; Pydantic converts to Decimal server-side; response also serializes as string)
  - Headers: `Authorization: Bearer <JWT>`, `Idempotency-Key: <UUID>` (S3 fix: must match `^[0-9a-f-]{36}$` regex; 400 otherwise)
  - **All user_id is extracted from JWT** (S2 lock — never from path/query/body)
  - Creates Saga (PENDING), returns `{ charge_id, current_state, amount, balance_after_reserve, expires_at }`
- `POST /v1/billing/charges/{id}/confirm` **(5.A.1 simplification — R1.2 lock)**
  - Applies BOTH `reserve` AND `service_success` transitions in one server call (no separate /reserve step)
  - This shortcut exists because 5.A.1 has no cross-service Saga (no real downstream solver in the same Saga). In 5.A.4 / M2.2a this will be split into proper 2-phase.
  - Returns `{ charge_id, current_state, balance_after }`
- `GET /v1/billing/balance`
  - Returns `{ user_id, balance: Decimal, currency: "CNY", last_transaction_at }`
- All require valid JWT (Bearer) — re-uses auth-service token verification

### AC2: Balance computation from ledger
- `balance` = `SUM(credit_transactions.amount WHERE user_id = X)`
- **Lazy seeding (A2 fix — POST only)**: when `POST /v1/billing/charges` is called for a user with **zero** `credit_transactions` rows, billing-service inserts a `topup` row of `+50.00` CNY (kind=`topup`, metadata={"source": "j1_demo_seed"}) BEFORE the Saga's start(). `GET /v1/billing/balance` is a **pure read** — returns 0 for unseeded users (no side effects).
- Edge case: user with prior transactions but balance=0 → no auto-topup; balance reported as `Decimal("0.00")`

### AC3: ChargeModal UI component
- New: `packages/ui/src/components/ChargeModal/index.tsx`
- Props (R1.3 lock — `error` prop for parent-driven error display):
  ```typescript
  interface ChargeModalProps {
    open: boolean;
    amount: number;            // ¥ to charge
    currency: string;          // "CNY"
    balance: number;           // current balance
    purpose: string;           // human description, e.g. "Solve LP problem"
    referenceId: string;       // for idempotency (UUID)
    onConfirm: () => Promise<void>;   // async — parent handles HTTP + errors
    onCancel: () => void;
    isLoading?: boolean;       // disables Confirm during pending request
    error?: string;            // shown inline if parent sets it (R1.3)
  }
  ```
- Visible elements:
  - Title: "Confirm charge" / "确认扣费"
  - Amount line: large/bold, with currency
  - Balance-before-charge line: "Current balance: ¥X.XX"
  - Balance-after-charge line: "After this charge: ¥(X-Y).XX" — RED if negative
  - Two buttons: "Cancel" / "Confirm and charge"
  - Loading state on Confirm click; disable during pending request
- Accessible: aria-label "charge confirmation", focus trap (uses existing `useA11y` hook), ESC to close
- Tier 1 (packages/ui) component → exportable to other apps

### AC4: Web app demo page (R1.4 lock)
- **No `/algorithms/lp` page exists yet** → create a new self-contained demo page: `apps/web/src/app/demo/charge/page.tsx`
- Layout:
  - Title: "Demo: charge confirmation"
  - One button: "Try a ¥6 charge"
  - Below: live balance display ("Your balance: ¥X.XX")
- On button click:
  - Fetch balance (`GET /v1/billing/balance`)
  - Show ChargeModal with amount=6, purpose="Demo charge"
  - On confirm: `POST /v1/billing/charges` + `POST /v1/billing/charges/{id}/confirm`
  - On success: refresh balance, close modal, show success toast
  - On error (422 insufficient): keep modal open, set `error` prop
- Solver integration intentionally NOT included (deferred to 5.A.4)
- Add a Nav link to `/demo/charge` for easy access during sales demo

### AC5: Idempotency-Key end-to-end
- Web generates a UUID once per "submit click" — used as both `Idempotency-Key` to billing AND `reference_id` in charge body
- Re-submitting the same form (double-click) → billing returns the same charge_id (no duplicate debit)
- Cross-service: `reference_id` is also passed to `POST /v1/optimizations` so the solve is tied to the charge (audit trail)

### AC6: Insufficient balance handling
- `POST /v1/billing/charges` with `amount > balance` → 422 with RFC 7807 error
  - `title: "Insufficient balance"`
  - `detail: "Required: ¥6.00, available: ¥3.50"`
  - `errors: [{ field_path: "body.amount", constraint: "amount > balance", remediation_hint_key: "errors.422.insufficient_balance" }]`
- ChargeModal recognizes 422 and shows the message inline (Confirm stays disabled, only Cancel works)

### AC7: Backend tests (billing-service)
- New test file `apps/billing-service/tests/test_charge_routes.py`:
  - POST /v1/billing/charges with valid JWT → 201 + charge_id in body
  - POST without auth → 401
  - POST with insufficient balance → 422 RFC 7807
  - POST same Idempotency-Key + same body → returns same charge_id (no duplicate)
  - POST same Idempotency-Key + different body → 409 IdempotencyConflict
  - POST /v1/billing/charges/{id}/confirm → transitions PENDING → CHARGED, balance debited
  - GET /v1/billing/balance → 200 with current balance
  - GET /v1/billing/balance for new user (no tx) → balance = 0

### AC8: Frontend tests (Storybook + smoke)
- New Storybook story: `ChargeModal.stories.tsx` with 4 variants (Q3 fix):
  - Default (¥6, balance ¥50)
  - Edge: balance = exactly amount (¥6 = ¥6; "After: ¥0.00")
  - Edge: balance < amount (¥3, balance after = -¥3, RED warning, Confirm disabled)
  - **Loading**: after Confirm clicked, isLoading=true, button shows spinner, Cancel still works
- Unit test (Vitest, R1.6 lock): ChargeModal renders with prop combinations; onConfirm fires; onCancel fires; ESC closes; `error` prop displays
- **DR5 reduced scope** — E2E (Playwright): minimal smoke test only:
  - Navigate to `/demo/charge` (no auth needed for page load; mock auth header for API)
  - Click "Try a ¥6 charge" → ChargeModal appears (assertion: dialog visible)
  - Click "Cancel" → modal closes (assertion: dialog not visible)
  - Full happy-path with real signup + balance refresh → deferred to 5.A.4

### AC9: Quality gates (per `feedback_full_quality_gates`)
Run BEFORE committing:
- `uv run ruff check .` → 0 errors
- `uv run ruff format --check .` → 0 changes needed
- `uv run mypy apps packages` → 0 errors
- `uv tool run pre-commit run --all-files` → 0 failures
- `pnpm -C apps/web build` → 0 errors (uses ChargeModal export from packages/ui)
- All Python regression tests pass + new billing route tests pass

### AC10: NFR-P alignment
- `POST /v1/billing/charges` P95 < 200ms (single Saga.start + DB writes)
- `POST /v1/billing/charges/{id}/confirm` P95 < 200ms (2 SELECT FOR UPDATE + 2 transitions)
- `GET /v1/billing/balance` P95 < 50ms (single sum aggregate)
- Tests assert via timestamp instrumentation OR deferred to M2.2a

## Tasks

### T1: shared JWT verifier + billing auth middleware (1.5 hour)
1. **Move JWT verify to shared (D1 fix)**: create `packages/shared-py/opticloud_shared/auth/jwt_verify.py` with `verify_jwt(token: str, public_key_pem: bytes) -> dict[str, str]` — verifies Ed25519 signature, returns claims dict
2. Update auth-service `security.py` to import from shared (no duplicate)
3. **DR2 lock**: billing-service `config.py` adds `jwt_public_key_path: str = Field(default="secrets/jwt_public.pem", alias="JWT_PUBLIC_KEY_PATH")` — **same default path as auth-service**. Both services read the same `.pem` file (auth generates on first run; billing reads on first call). Local docker-compose mounts `./secrets/` to both.
4. billing-service `auth_dep.py`: `async def require_user(authorization: str = Header(...)) -> UUID` returns user_id; raises 401 on bad token
5. **S1 fix**: on first call, if PEM file is missing OR empty, raise 503 with `detail: "auth not ready — auth-service must run first to generate keys"`. Do NOT silently accept tokens.
6. Test middleware against happy path + missing header + invalid token + expired token

### T2: shared RFC 7807 helper + billing routes (1.5 hour)
1. **Move RFC 7807 to shared (D2 fix)**: create `packages/shared-py/opticloud_shared/errors/rfc7807.py` with `rfc7807_error(title, status, detail, errors=None, request_id=None)` returning a FastAPI-compatible JSONResponse + `ErrorDetail` model
2. **DR1: solver-orchestrator refactor OUT OF SCOPE** — solver keeps its existing inline _rfc7807_error helper; only NEW billing-service code uses the shared module. Track as tech-debt in story body.
3. Create `apps/billing-service/src/billing_service/routes.py` with 3 endpoints
4. Wire routes into `main.py` via `app.include_router(billing_router)`
5. Pydantic schemas in `schemas.py` (ChargeCreateRequest / ChargeResponse / BalanceResponse — amount as str)
6. Type-safe response models

### T3: Backend tests (1 hour)
1. `apps/billing-service/tests/test_charge_routes.py` per AC7
2. Re-use the existing test_user_id fixture from conftest
3. Seed test user with topup row in setup
4. Use httpx AsyncClient with app dependency override (no need for live HTTP)

### T4: ChargeModal UI (1.5 hour)
1. `packages/ui/src/components/ChargeModal/index.tsx` per AC3
2. Use `useA11y` hook (existing) for focus trap + ESC handler + ARIA labels
3. **DR4 lock**: use `DialogPrimitive.*` (Portal + Overlay + Content + Title) directly — NOT shadcn's DialogHeader/DialogTitle exports (those broke during Story 0.13 build)
4. Export from `packages/ui/src/index.ts`
5. Mirror the working pattern from `ConfirmationModal/index.tsx` lines 75-89 (DialogPrimitive.Root + Portal + Overlay + Content asChild)

### T5: Storybook + unit tests (0.5 hour)
1. `packages/ui/src/components/ChargeModal/ChargeModal.stories.tsx` per AC8
2. Vitest unit test (or jest) for prop combinations + handlers

### T6: Web demo page (1.5 hour)
1. Create `apps/web/src/app/demo/charge/page.tsx` per AC4
2. Use ChargeModal from @opticloud/ui
3. Add `lib/api.ts` helpers: `getBalance()`, `createCharge()`, `confirmCharge()`
4. Loading + error states
5. Error path: 422 insufficient → keep modal open, pass error to ChargeModal `error` prop (R1.3)
6. **DR3 lock**: NO Nav link required — direct URL `/demo/charge` is fine for v1 (sales demo navigates manually)
7. Test in browser locally: docker-compose up, signup, navigate to /demo/charge, click button, see modal, confirm, balance refreshes

### T7: E2E + Quality gates + Sprint sync (0.5 hour)
1. Extend Playwright spec to cover full flow (or add new spec)
2. Run AC9 quality gates locally
3. Update sprint-status.yaml
4. Commit + push + PR

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Web + 2 backend services concurrency — race window between charge and solve | Acceptable for v1 (no cross-service Saga yet); 5.A.4 introduces atomicity |
| User signup doesn't seed balance → all signups have 0 → can't demo | T1 adds seeding step to either signup flow OR a billing init endpoint |
| ChargeModal differs from ConfirmationModal — duplication risk | Both use shared `useA11y` hook + DialogPrimitive; share Tier 1 design tokens; minimal duplication |
| Balance race: concurrent charges by same user | Acceptable for v1 (single human user, not concurrent); production hardening in 5.A.4 |
| Frontend hardcoded amount=6 — breaks if billing changes pricing | Acceptable; 5.B.1 introduces dynamic pricing per plan |

## Non-Functional Requirements Mapping

- **NFR-P1** (HTTP P95 < 300ms): all 3 endpoints budget < 200ms (AC10)
- **NFR-R4** (对账误差 = 0): SagaOrchestrator from 5.A.0a still source of truth; HTTP is just wrapper
- **NFR-A1** (PIPL): no PII in charge endpoints (just user_id from JWT)
- **NFR-S1** (TLS): all endpoints require Bearer JWT
- **FR B1** (charge intent + RFC 7807 error model): AC1 + AC6

## Definition of Ready

- ✅ SagaOrchestrator from 5.A.0a is the engine (no API to build, just wrap)
- ✅ auth-service JWT verify pattern exists to copy
- ✅ ConfirmationModal exists in packages/ui as a template for ChargeModal
- ✅ Existing /algorithms/lp Web page exists to extend
- ✅ All 4 review rounds applied

## Definition of Done

- All 10 ACs pass
- CI green on PR
- Sprint-status.yaml updated to `done`
- E2E test covers full J1 flow (signup → submit → charge modal → confirm → result)
- Code-review with FULL quality gates documented in commit body

## Sign-off (story-level)

| Role | Owner | Signed | Date |
|---|---|:-:|:-:|
| Architect | proposed by AI | ☐ | — |
| UX Lead | proposed by AI | ☐ | — |
| Billing Lead | TBA | ☐ | — |

> Owner committee deferred per M0 skip.
