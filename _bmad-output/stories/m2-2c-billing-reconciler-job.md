---
story_key: m2-2c-billing-reconciler-job
epic_num: 0
story_num: M2.2c
epic_name: Foundation — Billing Reliability
status: ready-for-dev
priority: 🟢 High (auto-remediation counterpart to 5.A.7 detection; closes the 5.A.4 Q4 single-attempt loop)
sizing: M-L (~5 hours; reconciler + CLI + tests; touches solver-orchestrator schema/code)
type: implementation + observability
created_by: bmad-create-story
created_at: 2026-05-19
sources:
  - 5.A.4 story L246 (Q4 decision: single attempt, no inline retry — `billing_finalize_failed=true` written to opt.error)
  - 5.A.7 story (reconciler pattern: pure module + CLI + tests + M3 scheduling)
  - apps/solver-orchestrator/src/solver_orchestrator/routes.py (the source of billing_finalize_failed=true)
  - apps/solver-orchestrator/src/solver_orchestrator/billing_client.py (the retry target)
dependencies:
  upstream:
    - 5-a-4-per-formula-charging-capped (done) — single-attempt finalize semantics + flag write
    - 5-a-7-reconciliation-cron (done) — pattern to mirror (pure module + CLI + RECONCILER.md)
    - ci-add-solver-orchestrator-test-job (done) — CI now runs solver tests
---

# Story M2.2c — Billing Finalize Retry Reconciler

## User Story

**As** the SRE on call seeing daily reconciler reports (5.A.7) that flag drift due to missing billing-finalize calls
**I want** a scheduled background job that scans solver-orchestrator's `optimizations` table for rows where `error.billing_finalize_failed=true`, re-attempts the finalize call against billing-service, and clears the flag on success
**so that** the 5.A.4 Q4 "single attempt + log + move on" tradeoff doesn't accumulate stuck sagas — billing outages auto-heal within one reconciler cycle once billing is back up.

## Why this story

5.A.4 Q4 chose **single-attempt** for solver-side billing calls so a billing outage can't slow the solver response P95. The cost: rows with `error.billing_finalize_failed=true` accumulate in `optimizations` until manually replayed. 5.A.7 detects the resulting ledger drift but doesn't fix it.

M2.2c closes the loop: a separate reconciler job retries those failed finalizes. Successful retries clear the flag. Failed retries (after N attempts) escalate to ops via structured log. Combined with 5.A.7, this gives auto-remediation + detection for the canonical NFR-R4 path.

## Out of scope

- **In-process scheduling** — M3.3 will wire to K8s CronJob / Dramatiq; for v1 we ship a runnable CLI
- **Slack / PagerDuty webhook** — M3.6c (same as 5.A.7)
- **Auto-remediation of detected drift** (write compensation rows from reconciler) → never; humans only
- **Reserve retry** (POST /reserve failures) — out of scope; reserve failures bubble back to caller as 422 immediately (no opt.error flag)
- **Cross-org reconciliation** (M3+ multi-tenant scope)

## Acceptance Criteria

### AC1: Persist retry context in `opt.error` on failed finalize

Extend `routes.post_optimization` in solver-orchestrator (where the single-attempt failure flag is set):

```python
if not finalize_outcome.ok:
    existing_error = opt.error or {}
    existing_error["billing_finalize_failed"] = True
    existing_error["billing_finalize_error"] = finalize_outcome.error_message
    # NEW for M2.2c — store retry context so reconciler knows what to retry
    existing_error["billing_charge_id"] = str(billing_uuid)
    existing_error["billing_elapsed_seconds"] = result.solve_seconds
    existing_error["billing_status"] = finalize_status     # "success" | "failure"
    existing_error["billing_failure_reason"] = failure_reason
    existing_error["billing_retry_count"] = 0
    opt.error = existing_error
```

No schema migration — `optimizations.error` is JSONB; the new keys ride along.

### AC2: New module `apps/solver-orchestrator/src/solver_orchestrator/billing_reconciler.py`

```python
@dataclass(frozen=True)
class RetryOutcome:
    optimization_id: UUID
    user_id: UUID
    billing_charge_id: UUID
    attempt_number: int            # 1-based; was retry_count+1
    succeeded: bool
    error_message: str | None

@dataclass(frozen=True)
class RetryReport:
    pending_count: int             # rows examined
    succeeded_count: int
    failed_count: int
    exhausted_count: int           # rows that hit MAX_RETRIES and got "given_up" tagged
    results: list[RetryOutcome]    # non-empty when at least one row processed

async def retry_pending_finalizes(
    session: AsyncSession,
    max_retries: int = 5,
    batch_limit: int = 100,
) -> RetryReport:
    """Scan optimizations.error.billing_finalize_failed=true and retry.

    Steps:
    1. SELECT optimizations WHERE error->>'billing_finalize_failed' = 'true'
                            AND (error->>'billing_retry_count')::int < max_retries
       LIMIT batch_limit
    2. For each row:
       a. Parse retry context (billing_charge_id, elapsed_seconds, status, failure_reason)
       b. Call billing_client.finalize(...) with extracted args
       c. On 2xx: clear billing_finalize_failed; set billing_finalize_succeeded_at
       d. On failure: increment billing_retry_count; update billing_finalize_last_error
       e. If retry_count == max_retries after increment: tag billing_given_up_at + leave for ops review
    3. Return RetryReport
    """
```

Pure-async; caller passes session. The reconciler **does NOT need to know billing's auth bridge details** — it calls `billing_client.finalize()` which already handles `X-Internal-Service-Auth`.

### AC3: Two-class outcome semantics

After running the retry, an optimization row's error JSON looks like one of:
- **Success cleared** — `billing_finalize_failed` removed, `billing_finalize_succeeded_at` = ISO timestamp; retry context fields cleared
- **Pending more retries** — `billing_retry_count` incremented; flag still true; `billing_finalize_last_error` updated to the latest attempt's error string
- **Given up** — `billing_retry_count == max_retries`; flag still true; `billing_given_up_at` = ISO timestamp; ops must intervene

### AC4: CLI runner — `apps/solver-orchestrator/src/solver_orchestrator/billing_reconciler_cli.py`

```bash
uv run python -m solver_orchestrator.billing_reconciler_cli
uv run python -m solver_orchestrator.billing_reconciler_cli --max-retries 3 --batch-limit 50
```

Exit codes:
- 0 — pending_count == 0 (no work; healthy)
- 0 — pending_count > 0 AND all succeeded (auto-healed)
- 1 — at least one failed (will retry next cycle; transient)
- 2 — at least one given up (ops attention needed)

stdout: JSON `{"event":"billing.reconciler.report", "pending":N, "succeeded":M, "failed":F, "exhausted":G, "results":[...]}`
stderr: human summary

### AC5: Tests — `apps/solver-orchestrator/tests/test_billing_reconciler.py`

**6 cases** (uses httpx.MockTransport pattern like 5.A.4):

1. `test_retry_no_pending_rows_returns_zero_report` — empty DB → pending=0, all counts 0
2. `test_retry_succeeds_clears_flag` — seed 1 opt row with flag + retry context; mock billing returns 200; verify flag cleared + `billing_finalize_succeeded_at` populated
3. `test_retry_failure_increments_retry_count` — seed 1 row; mock billing returns 5xx; verify retry_count incremented to 1; flag still true
4. `test_retry_exhausted_after_max_attempts` — seed 1 row with retry_count=4; max_retries=5; failure; verify `billing_given_up_at` set, retry_count=5
5. `test_retry_respects_batch_limit` — seed 200 rows; batch_limit=50; only 50 processed
6. `test_retry_ignores_already_succeeded` — seed row with flag but ALREADY has `billing_finalize_succeeded_at` (defensive) → skipped (treated as "not failed anymore")

### AC6: README — `apps/solver-orchestrator/src/solver_orchestrator/BILLING_RECONCILER.md`

Mirror 5.A.7's RECONCILER.md format:
- Local run instructions
- Output format
- Exit codes
- M3 scheduling options (K8s CronJob / systemd / Dramatiq)
- Alerting integration (Slack webhook on exit 2)
- Interaction with 5.A.7 reconciler (this fixes; that detects)

### AC7: Quality gates

- `uv run ruff check apps packages` → 0 errors
- `uv run ruff format --check apps packages` → 0 changes needed
- `uv run mypy apps packages` → 0 errors
- `pnpm -C apps/web build` → 0 errors (regression guard; no FE)
- All Python tests pass; solver 13 → 19 (+6)

### AC8: NFR alignment

- **NFR-R4** ✅ AC2 + AC3 close the auto-heal loop
- **NFR-O3** ✅ structured log per attempt; given-up rows are searchable
- **NFR-P1** ✅ off-path batch job; no impact on HTTP P95

## Tasks

### T1: Routes update — persist retry context (0.5h)
1. Extend `routes.post_optimization` per AC1 — add the 5 new keys to `opt.error` when finalize fails
2. Existing test `test_billing_header_finalize_5xx_records_failure_flag` already asserts the failure flag; extend to also check the new keys

### T2: Reconciler module (1.5h)
1. Create `billing_reconciler.py` per AC2
2. Pure-async; queries `optimizations` table directly; calls `billing_client.finalize` for retry
3. mypy strict pass

### T3: CLI runner (0.5h)
1. Create `billing_reconciler_cli.py` per AC4 — argparse + asyncio + JSON output
2. Exit codes 0/1/2 per AC4

### T4: Tests (1.5h)
1. New `test_billing_reconciler.py` per AC5 (6 cases)
2. Reuse `httpx.MockTransport` pattern from test_billing_integration.py for the billing mock
3. Seed `optimizations` rows via direct INSERT (raw SQL or ORM); query back to verify state

### T5: README (0.5h)
1. Create `BILLING_RECONCILER.md` per AC6 — mirrors 5.A.7's structure

### T6: Quality gates + sprint sync + PR (0.5h)
1. Run AC7 gates
2. Update sprint-status.yaml + memory
3. Commit + push + PR
4. CI green → squash merge

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Reconciler runs concurrently with a normal HTTP /optimizations call that ALSO fails finalize → double retry race | Each row has its own `billing_retry_count`; concurrent UPDATEs would just both increment. No corruption — at worst one extra retry. |
| Reconciler gets stuck on a row that always fails (e.g., billing returns 404 because charge_id was deleted) | After `max_retries`, row gets `billing_given_up_at`. Reconciler stops touching it. Ops investigates. |
| Retry succeeds but billing was already CHARGED via another path (idempotent replay) | The /finalize endpoint's idempotent-replay logic (5.A.4 R1.3) handles this — returns the same response shape, treated as success. |
| Large batch (10K+ pending rows) under continuous outage | `batch_limit=100` per run prevents one cycle from blocking the DB; cron runs every minute means rapid drain once billing recovers. |
| `opt.error.billing_charge_id` is JSON-serialized as string — must parse to UUID before passing to billing_client | Reconciler handles in AC2 step 2a: `UUID(opt.error["billing_charge_id"])` |
| Reconciler module imports billing_client which uses asyncio + httpx — same dependencies as solver app | ✓ No new deps. Both already in solver-orchestrator pyproject.toml |

## Non-Functional Requirements Mapping

- **NFR-R4** ✅ AC2 implements auto-remediation; AC3 makes outcomes auditable
- **NFR-O3** ✅ AC4 structured log per attempt
- **NFR-P1** ✅ off-path batch job
- **5.A.4 Q4 tradeoff resolution** ✅ this story addresses it without compromising solver P95

## Definition of Ready

- ✅ `billing_client.finalize` exists from 5.A.4
- ✅ 5.A.7 reconciler pattern to mirror
- ✅ Solver-orchestrator-test CI job from PR #14
- ✅ All 3 review rounds applied (next step)

## Definition of Done

- All 8 ACs pass
- Test counts: solver-orchestrator 13 → 19 (+6)
- CI green on PR
- sprint-status.yaml: `m2-2c-billing-reconciler-job: done`
- Memory updated
- Code review with full quality gates documented in commit body

## Sign-off

| Role | Owner | Signed | Date |
|---|---|:-:|:-:|
| SRE | TBA | ☐ | — |
| Billing Lead | TBA | ☐ | — |
| Solver Lead | TBA | ☐ | — |

> Owner committee deferred per M0 skip.
