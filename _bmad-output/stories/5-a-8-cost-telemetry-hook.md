---
story_key: 5-a-8-cost-telemetry-hook
epic_num: 5
story_num: A.8
epic_name: Billing — Saga Cost Telemetry
status: done
priority: High
type: billing observability + cost attribution hook
created_by: bmad-create-story
created_at: 2026-05-30
sources:
  - _bmad-output/planning/epics.md (Story 5.A.8 / CM2 + G3)
  - _bmad-output/stories/m2-3-cost-attribution.md
  - _bmad-output/stories/5-a-4-per-formula-charging-capped.md
  - _bmad-output/stories/5-a-6-topup-never-expire.md
  - _bmad-output/stories/5-a-7-reconciliation-cron.md
  - packages/shared-py/opticloud_shared/cost_telemetry/__init__.py
  - infra/local-init/10-cost-attribution.sql
  - apps/billing-service/src/billing_service/routes.py
  - apps/billing-service/src/billing_service/saga_orchestrator.py
  - apps/billing-service/src/billing_service/models.py
---

# Story 5.A.8 — Cost-telemetry hook

Status: done

## Story

**As** the NFR-COST owner,
**I want** billing-service to emit a safe cost attribution row when a charge Saga is successfully finalized,
**so that** the cost telemetry substrate from M2.3 closes the Billing Saga loop and M3 cost red-line reporting can join solver usage, charge completion, and tenant ownership without scraping ledger data.

## Context

Story M2.3 already shipped the shared `opticloud_shared.cost_telemetry` package, the durable `cost_attribution` table, and a solver-orchestrator hook for terminal solve results. Story 5.A.8 is the Billing-side hook promised by the Epic 5.A plan: after the billing Saga completes a successful charge via `/v1/billing/charges/{charge_id}/finalize`, billing-service must record a cost telemetry event through the shared helper.

This is observability and attribution only. It must not change Credits, charge amounts, Saga transitions, reconciler bounds, or payment/topup behavior.

## Scope

Implement a Billing Saga cost hook for successful `/finalize` calls:

1. Map `cost_attribution` in billing-service using the same table, columns, constraints, and partial index semantics from M2.3.
2. Record one `solver_second` cost attribution row for a successful finalized charge.
3. Use `tenant_id=saga.user_id`, `service='billing-service'`, `cost_unit='solver_second'`, `value=elapsed_seconds`, and `source_id=saga.id`.
4. Keep metadata low-cardinality and safe: `saga_type`, `charge_state`, `finalize_status`, `purpose`, and optional `reference_id` only.
5. Make the hook best-effort and idempotent: attribution failure must not block billing finalization, and finalize replay must not duplicate rows.
6. Wire billing CI/test schema to apply `infra/local-init/10-cost-attribution.sql`.

## Out of Scope

- Removing or changing the existing solver-orchestrator M2.3 cost hook.
- Recording billing amount, reserved amount, actual amount, balance, Credits bucket, payment refs, topup refs, raw solver payloads, prompt/input/output, JWTs, or PII in cost telemetry metadata.
- Recording failed/refunded Saga outcomes in billing-service. Solver-orchestrator remains the source for terminal solve attempts; this story only records successful Billing charge completion.
- Grafana dashboards, Prometheus alert rules, DingTalk/Linear automation, revenue joins, provider share, GPU idle computation, or monthly investor reporting.
- Changing Saga state machine transitions, reconciler expected bounds, or ledger sign semantics.
- Adding new external dependencies.

## Acceptance Criteria

1. Billing-service exposes a local `CostAttribution` ORM model mapped to the existing `cost_attribution` table with column names and constraints aligned to `infra/local-init/10-cost-attribution.sql`.
2. Billing CI and local test setup for billing-service apply `infra/local-init/10-cost-attribution.sql` before billing tests that touch the hook.
3. On successful first-run `POST /v1/billing/charges/{charge_id}/finalize`, after the Saga reaches `charged`, billing-service records exactly one cost attribution row:
   - `tenant_id = saga.user_id`
   - `service = 'billing-service'`
   - `cost_unit = 'solver_second'`
   - `value = Decimal(str(body.elapsed_seconds))`
   - `source_id = saga.id`
4. The cost metadata is pointer-safe and low-cardinality. It may include `saga_type`, `charge_state`, `finalize_status`, `purpose`, and `reference_id`. It must not include monetary fields, balance/Credits fields, payment/topup refs, raw payloads, solver input, auth secrets, phone/email, or user PII.
5. Finalize replay on an already terminal successful charge returns the existing finalization response and does not add another cost attribution row.
6. Failed finalization paths (`status='failure'`, refunded/net-zero Saga outcome) do not create billing-service cost attribution rows.
7. Cost attribution failures are best-effort. If validation or DB insert fails, `/finalize` still commits the billing Saga and ledger changes and returns the original successful response.
8. Transaction safety is proven: a failed cost insert must not roll back the charge ledger rows, partial refund rows, Saga state update, or outbox event. Use a nested transaction/savepoint or equivalent tested isolation.
9. Existing billing behavior remains unchanged:
   - successful charge still debits only the actual amount after partial refund;
   - finalize replay remains idempotent;
   - topup confirmation and reconciler semantics stay green.
10. Quality gates pass:
   - focused billing cost telemetry tests;
   - full billing-service tests;
   - `uv run ruff check apps/billing-service`;
   - `uv run ruff format --check apps/billing-service`;
   - `$env:PYTHONPATH='packages/shared-py;apps/billing-service/src'; uv run mypy apps/billing-service`;
   - `git diff --check`.

## Tasks / Subtasks

- [x] T1: Billing model and CI schema wiring (AC: 1, 2)
  - [x] Add `CostAttribution` to `apps/billing-service/src/billing_service/models.py`.
  - [x] Align check constraints and partial `source_id` index with M2.3.
  - [x] Add `infra/local-init/10-cost-attribution.sql` to billing-service path filter and schema apply steps.

- [x] T2: Billing cost hook implementation (AC: 3, 4, 7, 8)
  - [x] Add a small billing-local cost hook helper that calls shared `record_cost_event`.
  - [x] Use `Decimal(str(elapsed_seconds))`, not `Decimal(float)`.
  - [x] Insert under a nested transaction/savepoint.
  - [x] Log and swallow hook failures without hiding the original finalize result.

- [x] T3: Route integration and idempotency (AC: 3, 5, 6, 9)
  - [x] Call the hook only after successful `/finalize` charge path computes the final response.
  - [x] Do not call it for terminal replay responses.
  - [x] Do not call it for failure/refund finalization.
  - [x] Do not call it from deprecated `/confirm` or topup routes.

- [x] T4: Tests (AC: 3-9)
  - [x] Test successful finalize inserts one billing-service `solver_second` cost row.
  - [x] Test replay does not duplicate the row.
  - [x] Test failure finalize inserts no billing-service row.
  - [x] Test hook failure still returns successful finalize and preserves ledger state.
  - [x] Test pre-insert query failure is savepoint-isolated and preserves successful finalize.
  - [x] Test metadata has no blocked monetary/payment/raw/auth/PII fields.

- [x] T5: Quality gates and tracking (AC: 10)
  - [x] Run focused tests.
  - [x] Run full billing-service tests.
  - [x] Run ruff, format check, mypy, and diff check.
  - [x] Update Dev Agent Record, File List, Change Log, and sprint status.

## Pre-Implementation Adversarial Review

### Round 1 — Boundary And Semantics Review

Findings:

1. Billing charge amount is revenue/credit movement, not platform cost. Recording `actual_amount`, `reserved_amount`, balance, or bucket data into cost telemetry would corrupt G3 cost analytics.
2. Solver-orchestrator already writes a `solver_second` row in M2.3. Billing-service must be clearly labeled as a Billing Saga hook to prevent accidental aggregation as the same service cost.
3. Deprecated `/confirm` has no elapsed-seconds input, so forcing it into the hook would invent data.
4. Failed/refunded billing finalization is a ledger outcome, not a successful charge completion.

Revision after Round 1:

- Lock event shape to `service='billing-service'`, `cost_unit='solver_second'`, `value=elapsed_seconds`, `source_id=saga.id`.
- Exclude monetary, bucket, balance, payment, topup, raw payload, and PII fields from metadata.
- Scope route integration to successful `/finalize` only.
- Keep deprecated `/confirm`, topup, and failure/refund flows out of this story.

### Round 2 — Drift And Data Consistency Review

Findings:

1. Billing-service currently has no `CostAttribution` ORM model and billing CI does not apply `10-cost-attribution.sql`.
2. The shared helper expects model kwargs named `metadata_json`, so the billing model must mirror solver's mapping to the SQL `metadata` column.
3. Using `Decimal(body.elapsed_seconds)` would preserve binary float artifacts.
4. Metadata key names such as `actual_amount` or `billing_amount_cny` would be rejected by shared validation and also violate the story boundary.

Revision after Round 2:

- Add billing-local ORM mapping with the same check constraints and partial source index as solver.
- Add billing CI path/schema wiring for `10-cost-attribution.sql`.
- Require `Decimal(str(body.elapsed_seconds))`.
- Restrict metadata keys to safe pointer/status fields and add tests for blocked-fragment absence.

### Round 3 — Closure And Failure-Mode Review

Findings:

1. If the cost insert shares the same transaction without savepoint isolation, a validation or DB failure can poison the transaction and roll back the actual billing charge.
2. A replay of `/finalize` on a terminal charge could double-write cost attribution if the hook is placed in the terminal rebuild path.
3. Adding a unique DB constraint would exceed story scope and could collide with solver's M2.3 assumptions; idempotency can be route-level.
4. Reconciler must remain ledger-focused and should not treat cost rows as ledger rows.

Revision after Round 3:

- Use a nested transaction/savepoint inside the hook and swallow/log failures.
- Place the hook only on the first-run success path after ledger rows are prepared and before final commit.
- Check existing billing-service rows for the same `source_id` before insert.
- Leave reconciler code unchanged unless tests reveal a direct regression.

## Dev Notes

### Existing Patterns To Reuse

- Shared helper: `opticloud_shared.cost_telemetry.record_cost_event`.
- Shared schema: `infra/local-init/10-cost-attribution.sql`.
- Solver reference model: `apps/solver-orchestrator/src/solver_orchestrator/models.py::CostAttribution`.
- Billing finalize path: `apps/billing-service/src/billing_service/routes.py::finalize_charge`.
- Existing route tests and DI override: `apps/billing-service/tests/test_charge_routes.py`.

### Hard Boundaries

- Do not change `packages/shared-py/opticloud_shared/cost_telemetry` unless a test proves a shared bug.
- Do not change `opticloud_shared.saga` state machine.
- Do not write cost rows for topup, failed finalize, refunded finalize, or deprecated confirm.
- Do not record money, balances, payment refs, or raw payloads in cost metadata.
- Do not let cost telemetry failure change the user-visible billing response.

### Suggested Test Commands

```powershell
$env:PYTHONPATH='packages/shared-py;apps/billing-service/src'; uv run pytest apps/billing-service/tests/test_cost_telemetry_hook.py apps/billing-service/tests/test_charge_routes.py -q
$env:PYTHONPATH='packages/shared-py;apps/billing-service/src'; uv run pytest apps/billing-service/tests/ -q
uv run ruff check apps/billing-service
uv run ruff format --check apps/billing-service
$env:PYTHONPATH='packages/shared-py;apps/billing-service/src'; uv run mypy apps/billing-service
git diff --check
```

## Dev Agent Record

### Implementation Plan

1. Mirror the existing solver `CostAttribution` ORM mapping inside billing-service.
2. Add billing CI wiring so tests load `10-cost-attribution.sql`.
3. Add a best-effort `_record_billing_cost_attribution()` helper using the shared cost telemetry package.
4. Call the hook only in first-run successful `/finalize`, after ledger rows are flushed and before final commit.
5. Prove no duplicate row on replay, no row on failure finalize, no user-visible impact when the hook fails, and no unsafe metadata.

### Debug Log

- Red phase: `test_cost_telemetry_hook.py` initially failed because no cost row was written and the route had no `record_cost_event` integration.
- `$env:PYTHONPATH='packages/shared-py;apps/billing-service/src'; uv run pytest apps/billing-service/tests/test_cost_telemetry_hook.py -q` — 5 passed before review patch
- `$env:PYTHONPATH='packages/shared-py;apps/billing-service/src'; uv run pytest apps/billing-service/tests/test_cost_telemetry_hook.py apps/billing-service/tests/test_charge_routes.py -q` — 30 passed, 2 warnings
- `$env:PYTHONPATH='packages/shared-py;apps/billing-service/src'; uv run pytest apps/billing-service/tests/ -q` — 209 passed, 2 warnings
- `uv run ruff check apps/billing-service` — passed
- `uv run ruff format --check apps/billing-service` — passed
- `$env:PYTHONPATH='packages/shared-py;apps/billing-service/src'; uv run mypy apps/billing-service` — passed
- `git diff --check` — passed

### Completion Notes

- Added billing-service `CostAttribution` ORM mapping aligned with M2.3 SQL.
- Wired billing CI to apply `infra/local-init/10-cost-attribution.sql`.
- Added best-effort Billing Saga cost telemetry hook for successful first-run `/finalize` only.
- Cost event records `service='billing-service'`, `cost_unit='solver_second'`, elapsed seconds as Decimal-safe value, and `source_id=charge_id`.
- Hook failures are isolated with a nested transaction and do not roll back Saga, ledger, or outbox changes.
- Post-review patch moved the existence query inside the nested transaction so query-level DB failures are also savepoint-isolated.
- Replay, failed finalize, topup, and deprecated confirm paths remain attribution-free.

### File List

- `.github/workflows/ci.yml`
- `_bmad-output/stories/5-a-8-cost-telemetry-hook.md`
- `_bmad-output/stories/sprint-status.yaml`
- `apps/billing-service/src/billing_service/models.py`
- `apps/billing-service/src/billing_service/routes.py`
- `apps/billing-service/tests/test_cost_telemetry_hook.py`

## Change Log

- 2026-05-30 — Story created and revised through three pre-implementation adversarial review rounds.
- 2026-05-30 — Implemented billing cost telemetry hook, tests, CI schema wiring, and quality gates; status set to code-review.
- 2026-05-30 — Completed post-implementation code review; fixed savepoint isolation gap for pre-insert cost queries; status set to done.

## Senior Developer Review (AI)

Outcome: Approved after patch.

Review layers:

- Blind Hunter: diff-level correctness, import/schema drift, and likely integration failures.
- Edge Case Hunter: transaction failure modes, idempotency replay, failure finalize, and metadata leakage.
- Acceptance Auditor: checked implementation against AC1-AC10.

Findings and resolution:

- [x] [High] `_billing_cost_attribution_exists()` originally ran before `session.begin_nested()`. A database error in the existence query could poison the outer transaction and violate AC7/AC8. Fixed by moving the existence query inside the nested transaction and adding `test_cost_hook_query_failure_savepoint_preserves_successful_finalize`.

Residual risk:

- This story intentionally does not add a DB uniqueness constraint on `(service, cost_unit, source_id)`. Route-level idempotency and terminal replay tests close the current HTTP path; a future out-of-band writer should add a migration if it needs hard uniqueness.

## Verification

- `$env:PYTHONPATH='packages/shared-py;apps/billing-service/src'; uv run pytest apps/billing-service/tests/test_cost_telemetry_hook.py apps/billing-service/tests/test_charge_routes.py -q` — 30 passed, 2 warnings
- `$env:PYTHONPATH='packages/shared-py;apps/billing-service/src'; uv run pytest apps/billing-service/tests/ -q` — 209 passed, 2 warnings
- `uv run ruff check apps/billing-service` — passed
- `uv run ruff format --check apps/billing-service` — passed
- `$env:PYTHONPATH='packages/shared-py;apps/billing-service/src'; uv run mypy apps/billing-service` — passed
- `git diff --check` — passed
