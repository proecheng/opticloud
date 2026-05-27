---
story_key: 3-6-prediction-quantiles
epic_num: 3
story_num: 3.6
epic_name: Optimization & Prediction Execution
status: done
priority: High (FR E6 v1 must-have; hardens public prediction confidence-band contract)
sizing: S-M (~3-5 hours; response-boundary validation + persistence replay hardening + focused tests)
type: implementation
created_by: bmad-create-story
created_at: 2026-05-27
sources:
  - _bmad-output/planning/epics.md:71 (FR E6 P10/P50/P90 + drift_score + bilingual disclaimer)
  - _bmad-output/planning/epics.md:373 (Epic 3 goal includes prediction quantiles/drift/disclaimer)
  - _bmad-output/planning/epics.md:1429-1431 (Story 3.6 AC)
  - _bmad-output/planning/prd.md:852-856 (why P10/P50/P90 vs point estimates)
  - _bmad-output/planning/prd.md:1473 (E6 v1 must-have)
  - _bmad-output/planning/architecture.md:711-714 (Python naming/file conventions)
  - _bmad-output/stories/3-2-prediction-submission.md (minimum prediction endpoint, persistence, idempotency, GET)
  - apps/solver-orchestrator/src/solver_orchestrator/forecasting.py (deterministic forecast helper)
  - apps/solver-orchestrator/src/solver_orchestrator/schemas.py (PredictionResponse contract)
  - apps/solver-orchestrator/src/solver_orchestrator/routes.py (POST/GET prediction response builders)
  - apps/solver-orchestrator/tests/test_prediction_submission.py (current prediction regression suite)
dependencies:
  upstream:
    - 3-2-prediction-submission (done) - created `/v1/predictions`, deterministic forecast helper, persistence, GET, idempotency, and minimum E6 fields.
    - 2-6-multi-provider-routing (done) - forecast provider route metadata and model version contract.
    - 2-8-unaudited-block (done) - prediction governance guard must remain side-effect-free.
  downstream:
    - 3-7-rfc7807-errors-detail - can deepen public error payload fields and next_action_url.
    - 3-9-status-progress-eta - can add queued/progress/eta states for prediction jobs later.
    - 3-10-backtest-discount - can add discounted backtest scoring; must reuse the hardened quantile contract.
    - 3-14-mock-real-divergence-test - can compare mock/real prediction contract parity.
---

# Story 3.6 - Prediction P10/P50/P90 + drift_score + bilingual disclaimer (FR E6)

## User Story

作为 API 用户，
我希望每个 completed prediction 响应都被强制校验为完整的 P10/P50/P90 分位数、`drift_score` 和中英双语免责声明，
以便前端、SDK 和业务报表可以稳定消费预测区间，而不会因为 helper 异常或历史脏数据拿到漂移响应或 500。

## Why This Story

Story 3.2 已经交付 `/v1/predictions` 的最小合同：ARIMA / Chronos family、确定性 mock forecast、P10/P50/P90、`drift_score`、免责声明、持久化、GET 和 idempotency replay。Story 3.6 不重复创建预测接口，也不引入真实 ARIMA/Chronos 推理。

本 story 的目标是把 FR E6 从“字段存在”加固为“合同不可漂移”：

- completed POST/GET/idempotency replay 必须强制返回 horizon 长度的 `p10/p50/p90`。
- 每个 step 必须满足有限值和 `p10 <= p50 <= p90`。
- `drift_score` 必须是有限数且处于 `[0.0, 1.0]`。
- 免责声明文本必须单源化，并且永远使用固定中英双语文案。
- 如果 forecast helper 或历史 completed row 违反合同，系统必须进入受控失败语义，不能写入/返回 malformed completed payload，也不能暴露 500。

## Out of Scope

- 不引入 `statsmodels`、Chronos、torch、transformers、GPU runtime、模型下载或外部推理服务。
- 不改变 `POST /v1/predictions` 或 `GET /v1/predictions/{id}` 的公开路径、认证、scope、provider routing、idempotency TTL 或 billing-header 拒绝语义。
- 不新增 DB column；必要的合同元数据只允许写入 `predictions.input_payload._system`。
- 不改变公开 response 顶层字段名称；仍使用 `prediction.p10/p50/p90`、`drift_score`、`disclaimer`。
- 不为 prediction 增加 async、cancel/refund、progress/eta、backtest 或 voucher。
- 不宣称真实 ARIMA/Chronos 质量上线；`forecasting.py` 仍是 CI-safe deterministic helper。
- 不修改 optimization、top-k alternatives、billing、voucher 或 cost attribution 行为。

## Acceptance Criteria

### AC1: completed response quantile contract is enforced at the boundary

For every completed prediction response built from POST success, GET completed row, or idempotency replay:

- `prediction` contains exactly `p10`, `p50`, and `p90`.
- `p10`, `p50`, and `p90` are lists of finite floats.
- Values must be JSON-safe finite numbers after float conversion. Reject `Decimal`, string, bool, or other values if they cannot be converted to finite non-bool floats without ambiguity.
- All three lists have length equal to the normalized request `horizon` stored at `predictions.input_payload.horizon`; do not infer horizon from quantile length.
- Ignore `_system` metadata when reading the public input payload, and never read horizon from `_system`.
- For every index, `p10[i] <= p50[i] <= p90[i]`.
- The public response must not include `NaN`, `Infinity`, missing quantile arrays, extra quantile keys, scalar quantiles, or mismatched list lengths.
- Add a small route/helper boundary function rather than scattering checks across POST and GET.
- Validation must happen before `PredictionResponse` serialization so malformed data is converted into controlled prediction failure handling, not an uncaught Pydantic/JSON exception.

### AC2: drift_score contract is enforced consistently

- `drift_score` must be a finite float in `[0.0, 1.0]` before a completed prediction row is persisted or returned.
- Do not silently clamp invalid helper output at the route boundary; if helper output is outside the contract, mark the prediction failed with a clear internal error payload.
- Existing helper-level clamping in `forecasting.py` may remain.
- Completed historical rows with missing, non-finite, or out-of-range `drift_score` must not return a malformed completed response.

### AC3: bilingual disclaimer is single-source and durable

- Move the fixed disclaimer text into a single source near the prediction schema or a dedicated helper:
  - `zh`: `本预测仅供参考`
  - `en`: `This forecast is for reference only`
  - `bilingual`: `本预测仅供参考 / This forecast is for reference only`
- `routes.py` must import/reuse this single source rather than hand-building a duplicate mutable object.
- Prefer a factory/helper that returns a fresh `PredictionDisclaimer` or plain dict to avoid sharing a mutable Pydantic instance across responses.
- POST, GET, and idempotency replay must return byte-identical disclaimer content.
- Persisted rows must not be trusted as the source of disclaimer text; response builders always attach the canonical disclaimer.
- Tests must fail if any of the three disclaimer strings drifts.

### AC4: malformed forecast output fails closed before completed persistence

If `predict_quantiles(...)` returns invalid contract data or raises during completed sync execution:

- Keep the route-level `predict_quantiles` import path monkeypatchable as `solver_orchestrator.routes.predict_quantiles`, because existing governance/idempotency tests already patch that symbol to assert no side effects.
- The route must persist a `Prediction` row with `status="failed"`, `error.title == "Prediction Contract Violation"` or `error.title == "Prediction Execution Failed"` as appropriate, `model_version`, `completed_at`, and no completed `prediction` payload.
- The POST response must be a compact status payload for that failed row with HTTP 200, matching existing failed-row GET style for predictions:
  - `prediction_id`
  - `status: "failed"`
  - `error`
  - `model_version`
  - `created_at`
  - `completed_at`
  - no `prediction`, `drift_score`, `disclaimer`, `family`, `horizon`, or `_system`
- No prediction idempotency row should be inserted for newly failed execution; only newly completed predictions are inserted into `prediction_idempotency_keys`. A retry with the same idempotency key may execute again and create another failed row until a completed row is cached.
- Billing remains unsupported and must not be called.
- Provider route metadata in `input_payload._system.provider_route` must still be present on the failed row so operators can debug which forecast route produced invalid output.
- `predict_seconds` on failed execution should be the elapsed route runtime when available, never a non-finite helper value.
- Persist the failed row inside a contained transaction block or by flushing without rolling back the outer request/session state. Do not use a broad `session.rollback()` for helper contract failures, because that can erase the failed-row audit trail in the request dependency transaction.
- The failure payload must not leak raw stack traces, API keys, user ids, billing ids, or `_system`.

### AC5: malformed historical completed rows replay as controlled compact failures

For owner-visible `GET /v1/predictions/{id}` and idempotency replay of an existing completed row:

- If the persisted completed row has malformed quantiles, invalid horizon, invalid `drift_score`, invalid `model_version`, or missing timestamps, the response builder must not raise 500.
- Return a compact status payload with:
  - `prediction_id`
  - `status: "failed"`
  - `error.title: "Prediction Contract Violation"`
  - `error.detail` identifying the high-level invalid area without exposing internals
  - `model_version` when it can be safely serialized, else `null`
  - `created_at` serialized to ISO string when available, else `null`
  - `completed_at` serialized to ISO string when available, else `created_at` when available, else `null`
- Do not mutate the historical row during GET/replay; this story hardens response behavior without a migration.
- If an existing idempotency key points to a historical row whose DB status is `completed` but whose contract is malformed, replay the compact contract-violation payload for that row. Do not treat this as a missing/incomplete idempotency row and do not execute a second forecast.
- Cross-user GET remains 404.

### AC6: deterministic helper remains ordered, finite, and horizon-aware

- Keep `apps/solver-orchestrator/src/solver_orchestrator/forecasting.py` dependency-free beyond stdlib.
- Helper output for constant, increasing, decreasing, noisy, negative, and high-magnitude finite series must stay deterministic.
- Helper output must be finite for accepted request ranges: `data` length 3..10,000, all finite values, `horizon` 1..90.
- Helper output must preserve `p10 <= p50 <= p90` and exact horizon length.
- If helper math ever cannot produce finite values, it should fail explicitly instead of returning invalid floats.
- Add and document an explicit safe numeric envelope for request `data`, for example `abs(value) <= 1e12`, using the existing RFC 7807 `Invalid Prediction Data` path with `field_path="data[i]"`. The threshold must be high enough for normal business forecasts and low enough to prevent helper overflow or meaningless bands.

### AC7: tests cover boundary validation, persistence, replay, and drift protection

Add focused tests to `apps/solver-orchestrator/tests/test_prediction_submission.py` or a new prediction quantiles test file:

1. Helper deterministic finite/ordered output for constant, increasing, decreasing, noisy, negative, and high-magnitude series.
2. POST success returns exact horizon-length `p10/p50/p90`, finite values, ordered quantiles, finite bounded `drift_score`, and canonical disclaimer.
3. GET completed response equals POST response for valid rows and keeps canonical disclaimer.
4. Idempotency replay returns byte-identical quantiles, drift score, and disclaimer for valid completed rows.
5. Monkeypatched helper returning mismatched quantile lengths persists a failed row and returns compact failed status, with no idempotency row inserted.
6. Monkeypatched helper returning non-finite quantile or unordered quantiles fails closed before completed persistence.
7. Monkeypatched helper returning non-finite or out-of-range `drift_score` fails closed before completed persistence.
8. Retrying the same idempotency key after a failed helper execution does not replay the failed row; it creates another failed row until a completed response is produced.
9. Historical completed row with malformed quantiles returns compact contract-violation payload on GET, not 500.
10. Historical completed row with invalid `drift_score` returns compact contract-violation payload on GET, not 500.
11. Idempotency replay of a historical malformed completed row returns the same compact contract-violation payload and does not execute forecasting.
12. Request data outside the documented safe numeric envelope returns RFC 7807 `Invalid Prediction Data` before provider route side effects that depend on execution.
13. Existing invalid input, unaudited self forecast, billing-header rejection, and failed-row compact GET tests remain green.

### AC8: quality gates pass

Run before commit:

- `uv run pytest apps/solver-orchestrator/tests/test_prediction_submission.py -q`
- `uv run pytest apps/solver-orchestrator/tests/test_provider_routing.py apps/solver-orchestrator/tests/test_unaudited_self_block.py -q`
- `uv run pytest apps/solver-orchestrator/tests -q`
- `uv run mypy apps packages`
- `uv tool run pre-commit run --all-files --show-diff-on-failure`
- `git diff --check`

## Tasks / Subtasks

- [x] Task 1: Single-source disclaimer and response-boundary validator (AC: 1, 2, 3)
  - [x] Add canonical prediction disclaimer helper/source and reuse it in routes.
  - [x] Add a prediction contract validator for horizon, finite quantiles, ordering, drift_score, model_version, and timestamps.
  - [x] Keep response serialization JSON-safe and never expose `_system`.

- [x] Task 2: Fail closed on invalid helper output (AC: 4)
  - [x] Wrap forecast execution and contract validation before marking completed.
  - [x] Persist failed rows with provider route metadata and sanitized error payload.
  - [x] Ensure failed execution does not insert prediction idempotency keys.

- [x] Task 3: Harden GET/idempotency replay of historical rows (AC: 5)
  - [x] Convert malformed completed rows into compact contract-violation status payloads.
  - [x] Preserve owner-only 404 behavior and avoid mutating historical rows during GET/replay.
  - [x] Keep valid completed POST/GET/replay byte-identical.

- [x] Task 4: Strengthen helper and focused tests (AC: 6, 7)
  - [x] Extend helper tests for negative/high-magnitude accepted series.
  - [x] Add malformed helper output tests for lengths, non-finite values, ordering, and drift score.
  - [x] Add malformed historical row GET/replay tests.

- [x] Task 5: Run validation gates (AC: 8)
  - [x] Run focused prediction tests.
  - [x] Run adjacent provider/governance tests.
  - [x] Run full solver-orchestrator tests, mypy, pre-commit, and diff check.

### Review Findings

- [x] [Review][Patch] Completed prediction `completed_at` was captured before forecast execution and contract validation, so the completion timestamp could precede actual completion. Fixed by assigning `completed_at` after forecast output passes contract validation. [apps/solver-orchestrator/src/solver_orchestrator/routes.py]

## Dev Notes

### Current Implementation Facts

- `PredictionRequest`, `PredictionQuantiles`, `PredictionDisclaimer`, and `PredictionResponse` live in `apps/solver-orchestrator/src/solver_orchestrator/schemas.py`.
- `routes.py` currently defines `PREDICTION_DISCLAIMER` locally and passes it into every completed response.
- `post_prediction()` validates public request data, resolves forecast provider route, rejects billing headers, checks idempotency, calls `predict_quantiles()`, persists a completed row, then optionally inserts `prediction_idempotency_keys`.
- `_build_prediction_response_content()` currently returns compact payloads for non-completed rows, but for completed rows it directly model-validates persisted JSON. Malformed completed rows can therefore escape as uncaught validation errors.
- `PredictionResponse.drift_score` has Pydantic bounds, but route code should not rely on an uncaught schema error for runtime/DB boundary validation.
- `forecasting.py` already returns deterministic `ForecastResult(p10, p50, p90, drift_score, predict_seconds)` and constructs ordered bands.
- Existing prediction tests already cover success, Chronos route without GPU dependency, owner GET, idempotency replay/conflict/default horizon/expiry/stale row, invalid inputs, billing header, unaudited self forecast, and compact failed-row GET.

### Implementation Guidance

- Prefer names such as `CANONICAL_PREDICTION_DISCLAIMER`, `prediction_disclaimer()`, `_validate_prediction_contract`, `_prediction_contract_violation_payload`, and `_build_prediction_contract_failure`.
- Keep `PredictionDisclaimer`, `PredictionQuantiles`, and `PredictionResponse` in `schemas.py`; do not create a second response schema in routes.
- Keep the validator pure and small. It should accept the persisted row fields or helper result plus horizon and return normalized JSON-safe quantiles/drift/model_version or a sanitized failure reason.
- Use `math.isfinite(float(value))` for numeric checks and avoid accepting bools as meaningful forecast values if practical.
- Treat horizon as invalid if it is missing, not an integer, or outside 1..90 on a completed row.
- Treat `model_version` as invalid if `ModelVersionSchema.model_validate(...)` fails; do not return completed response with an invalid model version.
- Do not silently repair malformed persisted quantiles by sorting, padding, truncating, filtering, or clamping. Invalid completed data must fail closed.
- For helper execution failures, catch broad exceptions only around `predict_quantiles` and contract validation, log a warning with ids and exception type, and store a sanitized error payload.
- Be explicit about transaction boundaries: failed helper/contract execution should flush and return the failed `Prediction` row without a full-session rollback, while duplicate idempotency-key insert conflicts should continue to roll back the attempted completed-row/idempotency insert as they do today.
- Prefer a small internal exception/value object such as `_PredictionContractViolation(field: str, detail: str)` so public `error.detail` is stable and tests do not depend on raw Pydantic exception text.
- Preserve the existing response shape for valid completed predictions exactly.
- Keep idempotency semantics from Story 3.2: only completed rows are cached/replayed; failed helper execution should not create a prediction idempotency key.
- Do not expand request schema with new public fields; this is a contract-hardening story.
- Do not move provider routing, unaudited-self checks, billing-header rejection, or idempotency lookup after forecast execution. The Story 3.2 side-effect ordering remains authoritative.

### Previous Story Intelligence

- Story 3.2 deliberately kept prediction execution deterministic and dependency-free; do not import real model runtimes in 3.6.
- Story 3.2 review fixed idempotency TTL, duplicate-row coverage, failed GET shape, and ORM/SQL index consistency. Do not regress those tests.
- Story 3.5 established a useful pattern for contract metadata and replay: attach metadata under `_system`, but do not expose `_system` in public responses.
- Recent solver stories use focused tests first, then adjacent regression suites, then full suite/mypy/pre-commit/diff-check before commit.

### Project Structure Notes

- Keep backend code under `apps/solver-orchestrator/src/solver_orchestrator/`.
- Keep tests under `apps/solver-orchestrator/tests/`.
- Use Python `snake_case` names and `test_<name>.py` conventions.
- Avoid new dependencies; use stdlib/Pydantic/SQLAlchemy already present in the service.

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Story duplicates 3.2 by rebuilding prediction endpoints | Scope is response/persistence contract hardening only; no new endpoint shape. |
| Invalid helper output is persisted as completed | Validate before completed persistence; failed rows use compact status payload. |
| Historical malformed completed rows crash GET/idempotency replay | Response builder catches contract violations and returns compact failed status. |
| Boundary code silently repairs bad forecasts and hides model bugs | Do not clamp/sort/pad/truncate at route boundary; fail closed. |
| Disclaimer text drifts between schemas/routes/tests | Single-source canonical disclaimer and exact-string tests. |
| Failed helper execution becomes idempotently cached | Insert prediction idempotency keys only for completed rows. |
| Contract hardening exposes internals in errors | Store sanitized error payloads and public compact failed responses only. |

## Definition of Done

- Story file has passed three pre-implementation reviews and all resulting patches are applied.
- Completed prediction responses enforce horizon-length finite ordered P10/P50/P90, finite bounded `drift_score`, and canonical disclaimer.
- Invalid helper output persists a controlled failed prediction row and does not create prediction idempotency keys.
- Malformed historical completed rows return compact contract-violation status payloads on GET/replay instead of 500.
- Existing prediction route validation, governance, billing-header rejection, and idempotency behavior remain green.
- AC8 quality gates pass or any inability to run them is documented.
- Sprint status and Dev Agent Record are updated.

## Dev Agent Record

### Agent Model Used

GPT-5

### Debug Log References

- 2026-05-27 - Story moved to in-progress after three pre-implementation review rounds; starting RED phase for prediction quantile contract hardening.
- 2026-05-27 - RED phase confirmed: focused prediction tests failed on missing canonical `prediction_disclaimer` helper.
- 2026-05-27 - Implemented canonical disclaimer factory, prediction contract validator, failed helper execution rows, malformed completed-row compact replay, and safe numeric envelope.
- 2026-05-27 - Focused prediction tests passed: `uv run pytest apps/solver-orchestrator/tests/test_prediction_submission.py -q` -> 33 passed.
- 2026-05-27 - Adjacent regression passed: provider routing + unaudited self block -> 21 passed.
- 2026-05-27 - Full validation before code review passed: solver-orchestrator suite 226 passed; `uv run mypy apps packages` passed; `uv tool run pre-commit run --all-files --show-diff-on-failure` passed; `git diff --check` passed.
- 2026-05-27 - Post-implementation code review found one patch item: completed prediction `completed_at` was captured before forecast execution finished. Moved completion timestamp assignment after contract validation.
- 2026-05-27 - Final validation passed after code-review patch: focused prediction tests 33 passed; adjacent provider/governance tests 21 passed; full solver-orchestrator suite 226 passed; mypy/pre-commit/diff-check passed.

### Completion Notes List

- Added single-source canonical prediction disclaimer factory in schemas and reused it for completed responses.
- Added shared prediction contract validation for horizon-length finite ordered P10/P50/P90, bounded finite drift score, valid model version, and timestamps.
- Invalid forecast helper output or execution exceptions now persist sanitized failed prediction rows with provider route metadata and no idempotency cache row.
- Malformed historical completed rows now return compact contract-violation payloads on GET/idempotency replay instead of raising 500.
- Added safe numeric envelope validation for prediction data to prevent helper overflow.
- Validation passed before post-implementation code review: focused prediction tests, adjacent regressions, full solver-orchestrator tests, mypy, pre-commit, and diff check.
- Post-implementation code review completed; the completed-at timing finding was fixed and will be revalidated before marking done.
- Final validation passed after post-review patch: focused prediction tests, adjacent regressions, full solver-orchestrator tests, mypy, pre-commit, and diff check.

### File List

- `_bmad-output/stories/3-6-prediction-quantiles.md`
- `_bmad-output/stories/sprint-status.yaml`
- `apps/solver-orchestrator/src/solver_orchestrator/schemas.py`
- `apps/solver-orchestrator/src/solver_orchestrator/routes.py`
- `apps/solver-orchestrator/tests/test_prediction_submission.py`

### Change Log

- 2026-05-27 - Initial Story 3.6 draft created from Epics/PRD/Architecture, Story 3.2 implementation, and current prediction code paths.
- 2026-05-27 - Applied three pre-implementation story review rounds covering data consistency, function/dependency consistency, drift, boundary cases, and closure.
- 2026-05-27 - Started Story 3.6 implementation after completing all required pre-implementation story reviews.
- 2026-05-27 - Implemented Story 3.6 prediction contract hardening and focused tests; focused prediction suite passed.
- 2026-05-27 - Marked Story 3.6 ready for post-implementation code review after all AC8 gates passed.
- 2026-05-27 - Code review patch pass completed; completed prediction timestamp now reflects post-validation completion.
- 2026-05-27 - Marked Story 3.6 done after final validation passed.

## Story Review Round 1 - Data Consistency (2026-05-27)

### Findings

- [x] [Patch] The initial draft did not pin the source of response `horizon`, which could let malformed quantile arrays redefine the expected length. AC1 now requires reading `predictions.input_payload.horizon` only and ignoring `_system`.
- [x] [Patch] Failed helper output response shape was underspecified. AC4 now locks the compact failed payload fields and explicitly excludes completed-only fields and `_system`.
- [x] [Patch] Failed execution idempotency semantics were ambiguous. AC4/AC7 now state that newly failed executions do not create prediction idempotency rows, so retrying the same key may execute again until a completed row is cached.
- [x] [Patch] Historical malformed completed-row replay needed a closed rule for existing idempotency mappings. AC5 now requires returning the compact contract-violation payload without executing a second forecast.
- [x] [Patch] Timestamp nullability in compact contract-violation payloads was too strict for malformed historical rows. AC5 now specifies ISO-or-null serialization.

### Result

Round 1 passed after patches. Response fields, persisted input horizon, compact failure shape, idempotency replay, and timestamp serialization are now data-consistent.

## Story Review Round 2 - Function / Dependency Consistency and Drift (2026-05-27)

### Findings

- [x] [Patch] Moving the disclaimer into a single source could accidentally share a mutable model instance across responses. AC3 now recommends a fresh-object factory/helper.
- [x] [Patch] Existing tests monkeypatch `solver_orchestrator.routes.predict_quantiles`; moving the import behind another module path would weaken no-side-effect tests. AC4 now requires keeping that route-level monkeypatch seam stable.
- [x] [Patch] Failed execution `predict_seconds` was unspecified and could accidentally store non-finite helper values. AC4 now requires elapsed runtime when available.
- [x] [Patch] Very large finite inputs could overflow helper math before contract validation. AC6 now allows route/request validation to reject values outside a documented safe envelope through the existing RFC 7807 invalid-data path.
- [x] [Patch] The draft allowed response schema duplication and side-effect ordering drift. Dev Notes now keep prediction schemas in `schemas.py` and preserve Story 3.2 routing/governance/billing/idempotency ordering.

### Result

Round 2 passed after patches. Function ownership, import seams, schema location, helper numeric boundary, and route side-effect ordering are now aligned with the current implementation.

## Story Review Round 3 - Boundary / Edge Cases / Closure (2026-05-27)

### Findings

- [x] [Patch] The quantile validator did not explicitly reject ambiguous numeric types such as bool or stringified values. AC1 now requires finite non-bool float conversion without ambiguity.
- [x] [Patch] The safe numeric envelope was allowed but not quantified, which could let implementation drift. AC6 now requires a documented threshold such as `abs(value) <= 1e12` and AC7 adds a regression.
- [x] [Patch] Helper contract failures could be implemented with a broad `session.rollback()`, erasing the failed audit row. AC4 and Dev Notes now require flushing the failed row without full-session rollback.
- [x] [Patch] Public contract-violation messages could accidentally depend on raw Pydantic or exception text. Dev Notes now recommend a small internal violation object with stable sanitized `field/detail`.

### Result

Round 3 passed after patches. Numeric conversion, overflow envelope, failed-row persistence, and sanitized error-message boundaries are now closed before implementation.
