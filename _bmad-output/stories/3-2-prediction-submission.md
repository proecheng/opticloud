---
story_key: 3-2-prediction-submission
epic_num: 3
story_num: 3.2
epic_name: Optimization & Prediction Execution
status: done
priority: High (FR E2 v1 must-have; unlocks forecast submission and later Excel inventory endpoint swap)
sizing: M (~4-6 hours; backend endpoint + deterministic forecast helper + DB persistence + focused tests; no real Chronos/GPU)
type: implementation
created_by: bmad-create-story
created_at: 2026-05-27
sources:
  - _bmad-output/planning/epics.md:67 (FR E2 prediction family/algo path)
  - _bmad-output/planning/epics.md:71 (FR E6 P10/P50/P90 + drift_score + bilingual disclaimer)
  - _bmad-output/planning/epics.md:1413-1415 (Story 3.2 AC)
  - _bmad-output/planning/prd.md:1046 (POST /v1/predictions + GET /v1/predictions/{id})
  - _bmad-output/planning/prd.md:1469-1473 (E2/E6 v1 must-have)
  - _bmad-output/planning/architecture.md:119 (C2 algorithm mock abstraction; Chronos may need GPU)
  - _bmad-output/planning/architecture.md:1558 (optimizations / predictions DB boundary)
  - apps/solver-orchestrator/src/solver_orchestrator/catalog.py:300 (chronos-t5-forecast)
  - apps/solver-orchestrator/src/solver_orchestrator/catalog.py:338 (arima-forecast)
  - apps/solver-orchestrator/src/solver_orchestrator/provider_routing.py (route choke point)
  - apps/solver-orchestrator/src/solver_orchestrator/routes.py:647 (POST /v1/optimizations ordering pattern)
  - _bmad-output/stories/2-8-unaudited-block.md (self-audit gate and no-side-effect ordering)
  - _bmad-output/stories/3-e-5-inventory-template.md (inventory frontend waits for /v1/predictions)
dependencies:
  upstream:
    - 2-6-multi-provider-routing (done) - `select_provider_route("forecast", solver)` resolves ARIMA / Chronos catalog routes.
    - 2-8-unaudited-block (done) - prediction routing must not bypass the unaudited self-algorithm guard.
    - 3-1-j1-lp-solve (done) - establishes authenticated execution, persistence, idempotency, and GET-by-id patterns.
    - 3-e-5-inventory-template (done) - frontend inventory mapper documents the later endpoint swap to `/v1/predictions`.
  downstream:
    - 3-3-sync-async-mode - can add async/202/SSE later; this story stays sync-completed.
    - 3-6-prediction-quantiles - can deepen quantile semantics; this story locks minimum response shape.
    - 3-9-status-progress-eta - can expand progress/eta beyond completed GET.
    - 3-10-backtest-discount - backtest and discounted credits stay v2.
    - 3-e-5 / 3-e-9 - can switch inventory forecast submission from `/v1/optimizations/demo` to `/v1/predictions`.
---

# Story 3.2 - Prediction Submission (FR E2)

## User Story

作为 API 用户，
我希望调用 `POST /v1/predictions` 提交 `family="arima"` 或 `family="chronos"` 的时间序列预测请求，
以便同步获得可持久查询的 P10/P50/P90 预测、`drift_score`、模型版本和中英文免责声明。

## Why This Story

Epic 3 已经有 LP 优化提交路径，但预测能力仍停在 catalog 和 Excel inventory mapper 的 501 占位。FR E2 要求 v1 支持 prediction `family/{algo}` 路径，FR E6 要求预测响应必须包含 P10/P50/P90、`drift_score` 和中英文 disclaimer。

当前 catalog 已经有两个可用 forecast 路由候选：

- `arima-forecast`：`task_type="forecast"`，`status="v1"`，solver alias `arima` / `statsmodels-arima`，provider `statsmodels-arima`。
- `chronos-t5-forecast`：`task_type="forecast"`，`status="v1_late"`，solver alias `chronos-t5`，provider `chronos-t5`。

Architecture C2 明确 CI 必须使用算法 mock 抽象层，Chronos 可能需要 GPU，不能在 Story 3.2 引入真实 Chronos 推理。本 story 因此交付一个确定性、轻量的预测执行器：它验证输入、通过 provider routing 选择 forecast catalog 行、持久化 prediction 记录，并返回稳定的 P10/P50/P90 形状。`chronos` 在本 story 中只证明 family 路由和响应合同，不声明真实 Chronos 质量已上线。真实 ARIMA/Chronos 质量、回测和更完整 quantile 语义由 3.6 / 3.10 继续。

## Out of Scope

- 不引入 `statsmodels`、Chronos、GPU runtime、模型下载或外部推理服务。
- 不实现 async `202 + Location`、SSE progress、取消、退款或 eta；这些属于 3.3 / 3.8 / 3.9。
- 不接入 billing reserve/finalize；若请求带 `X-Billing-Charge-Id`，本 story 应返回 422 而不是静默忽略。
- 不创建 reproducibility voucher，不复用 `Optimization` / `ReproductionVoucher`。
- 不改公开 catalog 语义，不重新发布任何 unaudited self algorithm。
- 不改 Excel 前端提交路径；本 story 只建立后端 `/v1/predictions` 合同，前端 endpoint swap 可在后续 story 做。

## Acceptance Criteria

### AC1: 请求/响应 schema 明确且最小

新增 Pydantic schema 到 `apps/solver-orchestrator/src/solver_orchestrator/schemas.py`：

```python
class PredictionRequest(BaseModel):
    family: str
    data: list[float]
    horizon: int = 3

class PredictionQuantiles(BaseModel):
    p10: list[float]
    p50: list[float]
    p90: list[float]

class PredictionDisclaimer(BaseModel):
    zh: Literal["本预测仅供参考"]
    en: Literal["This forecast is for reference only"]
    bilingual: Literal["本预测仅供参考 / This forecast is for reference only"]

class PredictionResponse(BaseModel):
    prediction_id: uuid.UUID
    status: Literal["completed"]
    family: str
    horizon: int
    prediction: PredictionQuantiles
    drift_score: float = Field(ge=0.0, le=1.0)
    disclaimer: PredictionDisclaimer
    model_version: ModelVersionSchema
    predict_seconds: float
    created_at: datetime
    completed_at: datetime
```

Validation rules:

- `family` accepted values: `arima`, `chronos`. Map to forecast solver aliases:
  - `arima` -> `select_provider_route("forecast", "arima")`
  - `chronos` -> `select_provider_route("forecast", "chronos-t5")`
- `data` must contain at least 3 and at most 10,000 finite numeric points.
- `horizon` must be 1..90.
- Unsupported `family` returns RFC 7807 title `Unsupported Prediction Family`, status 422, `errors[0].field_path == "family"`, and must not persist a DB row.
- Invalid data length, non-finite values, and invalid horizon return RFC 7807 title `Invalid Prediction Data`, status 422, and identify `data`, `data[i]`, or `horizon`.
- Keep `PredictionRequest.family` as `str` and `horizon` without `Field(ge/le)` so route code can render the same RFC 7807 schema instead of FastAPI's default validation body for semantic validation failures.

### AC2: Add `predictions` persistence without disturbing optimization tables

Update `apps/solver-orchestrator/src/solver_orchestrator/models.py` and `infra/local-init/02-solver-schema.sql`.

Table `predictions`:

- `id UUID PRIMARY KEY DEFAULT gen_random_uuid()`
- `user_id UUID NOT NULL`
- `api_key_id UUID NOT NULL`
- `family VARCHAR(64) NOT NULL`
- `status VARCHAR(50) NOT NULL DEFAULT 'queued'`
- `input_payload JSONB NOT NULL`
- `prediction JSONB NULL`
- `drift_score NUMERIC NULL`
- `model_version JSONB NULL`
- `error JSONB NULL`
- `predict_seconds NUMERIC NULL`
- `idempotency_key VARCHAR(255) NULL`
- `created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`
- `completed_at TIMESTAMPTZ NULL`

Indexes:

- `idx_predictions_user_id_created_at ON predictions(user_id, created_at DESC)`
- `idx_predictions_status ON predictions(status) WHERE status IN ('queued', 'in_progress')`

Add a separate `prediction_idempotency_keys` table rather than modifying `idempotency_keys`, so existing optimization idempotency and voucher tests remain untouched:

- primary key `(user_id, key)`
- `prediction_id UUID NOT NULL REFERENCES predictions(id) ON DELETE CASCADE`
- `request_body_hash TEXT NOT NULL`
- `expires_at TIMESTAMPTZ NOT NULL`
- `created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`
- `idx_prediction_idempotency_keys_expires_at`

Stored JSON shape:

- `predictions.input_payload` stores the normalized request body after Pydantic parsing, including default `horizon=3`.
- `predictions.prediction` stores exactly `{"p10": [...], "p50": [...], "p90": [...]}`.
- `predictions.family` stores the canonical public family (`arima` or `chronos`), not the internal solver alias.
- `prediction_idempotency_keys.request_body_hash` uses the same normalized request body so omitted `horizon` and explicit `"horizon": 3` are treated as the same request.

### AC3: POST `/v1/predictions` follows the existing authenticated execution ordering

Add route in `apps/solver-orchestrator/src/solver_orchestrator/routes.py`:

- Auth: `Authorization: Bearer sk-...`.
- Scope: reuse existing `optimize:write` in v1. Do not invent `predict:write` before auth-service supports it.
- Idempotency: support `Idempotency-Key` with 24h dedup via `prediction_idempotency_keys`.
- Billing header: if `X-Billing-Charge-Id` is present, return 422 title `Billing Not Supported For Predictions`; do not call `billing_client.reserve/finalize`.
- Provider routing must happen before idempotency row creation, prediction persistence, deterministic forecast execution, or any future side effect.
- Execution order after auth/scope: normalize + semantic validation -> family-to-solver mapping -> `select_provider_route("forecast", mapped_solver)` -> route/governance errors -> billing-header unsupported check -> idempotency lookup -> persistence -> deterministic forecast.
- Use existing route error semantics, but remember prediction requests expose `family`, not `solver`: if route status is `UNAUDITED_SELF_ALGORITHM`, render `_unaudited_self_algorithm_error(..., field_path="family")`.
- Store `_system.provider_route` in `input_payload` by reusing `provider_route_to_system_metadata(route, task_type="forecast", requested_solver=mapped_solver)`. Do not hand-build a second metadata shape.
- On success persist `status="completed"`, `prediction`, `drift_score`, `model_version`, `predict_seconds`, `completed_at`.
- If an existing prediction idempotency key points to a missing or non-completed prediction row, return 409 `Idempotency Conflict`; do not continue into a second execution path.
- If inserting a prediction idempotency row races with another request and violates `(user_id, key)`, return 409 `Idempotency Conflict` rather than surfacing a database error.
- Response must not expose `_system`, route internals beyond `model_version`, API key data, billing ids, or user ids.

### AC4: Deterministic forecast helper, no real ARIMA/Chronos runtime

Create a small pure module, for example `apps/solver-orchestrator/src/solver_orchestrator/forecasting.py`.

Required behavior:

- Function signature may be:
  `predict_quantiles(data: list[float], horizon: int) -> ForecastResult`.
- It must be deterministic for the same input and fast enough for CI.
- It must return exactly horizon-length `p10`, `p50`, `p90` arrays.
- It must guarantee `p10[i] <= p50[i] <= p90[i]`.
- It must return `drift_score` clamped to `[0.0, 1.0]`.
- Use a simple local trend/spread heuristic only, e.g. last-value plus average recent delta and a spread based on recent absolute deltas or variance.
- It must not import or call `statsmodels`, `chronos`, `torch`, `tensorflow`, `transformers`, or any network/file model loader.

### AC5: GET `/v1/predictions/{prediction_id}` returns owner-visible records

Add authenticated GET route:

- Auth: `Authorization: Bearer sk-...`.
- Only the owner can read the prediction. Missing or cross-user ids return RFC 7807 `404 Not Found`.
- Completed rows return the same `PredictionResponse` shape as POST.
- Failed rows return a compact status payload with `prediction_id`, `status`, `error`, `model_version`, `created_at`, `completed_at`, matching the existing `GET /v1/optimizations/{id}` style.

### AC6: Tests cover schema, routing, persistence, idempotency, and no-side-effect failures

Add focused tests, preferably in `apps/solver-orchestrator/tests/test_prediction_submission.py`:

1. `POST /v1/predictions` with `{"family":"arima","data":[1,2,3,4]}` returns 200, `status=completed`, `prediction.p10/p50/p90` length 3, `drift_score` in `[0,1]`, exact bilingual disclaimer, and `model_version.provider_id == "statsmodels-arima"`.
2. The persisted `predictions.input_payload._system.provider_route` records task_type `forecast`, requested solver `arima`, selected solver `arima`, and provider id `statsmodels-arima`.
3. `family="chronos"` returns 200 with provider id `chronos-t5` and does not require any Chronos/GPU dependency.
4. `GET /v1/predictions/{id}` returns the same completed response for the owner.
5. Reusing the same `Idempotency-Key` and same body replays the same `prediction_id` without creating duplicate rows.
6. Reusing the same `Idempotency-Key` with a different body returns 409 `Idempotency Conflict`.
7. A stale idempotency row pointing to a missing or non-completed prediction returns 409 `Idempotency Conflict` and does not execute forecasting.
8. Unsupported family returns 422 and creates no prediction or prediction-idempotency row.
9. Invalid data length, invalid horizon, or non-finite value returns 422 and creates no prediction row.
10. Billing header returns 422 and does not call billing reserve/finalize or create prediction rows.
11. A monkeypatched `arima-forecast` clone whose `model_version.kind` is `self` and whose self-audit metadata fails returns 403 `Unaudited Self Algorithm` with `errors[0].field_path == "family"` before prediction persistence/idempotency/execution.
12. Pure helper tests verify determinism and `p10 <= p50 <= p90` for constant, increasing, decreasing, and noisy series.

Existing tests that must remain green:

- `test_provider_routing.py` forecast route coverage.
- `test_unaudited_self_block.py` side-effect-free governance guard.
- Full solver-orchestrator suite.

### AC7: Quality gates pass

Run before commit:

- `uv run pytest apps/solver-orchestrator/tests/test_prediction_submission.py -q`
- `uv run pytest apps/solver-orchestrator/tests/test_provider_routing.py apps/solver-orchestrator/tests/test_unaudited_self_block.py -q`
- `uv run pytest apps/solver-orchestrator/tests -q`
- `uv run mypy apps packages`
- `uv tool run pre-commit run --all-files --show-diff-on-failure`
- `git diff --check`

## Tasks / Subtasks

- [x] Task 1: Add prediction schemas and deterministic forecast helper (AC: 1, 4)
  - [x] Add `PredictionRequest`, `PredictionQuantiles`, `PredictionDisclaimer`, `PredictionResponse`.
  - [x] Add `forecasting.py` with deterministic trend/spread logic and helper tests.
  - [x] Keep helper dependency-free beyond stdlib / existing numeric primitives.

- [x] Task 2: Add DB models and local init schema (AC: 2)
  - [x] Add `Prediction` SQLAlchemy model.
  - [x] Add `PredictionIdempotencyKey` SQLAlchemy model.
  - [x] Update `02-solver-schema.sql` idempotently.
  - [x] Do not alter existing `optimizations` / `idempotency_keys` semantics.

- [x] Task 3: Implement POST `/v1/predictions` (AC: 3, 6)
  - [x] Authenticate with `verify_api_key` and `require_scope("optimize:write", scopes)`.
  - [x] Reject billing header before any billing calls.
  - [x] Validate family/data with RFC 7807 errors.
  - [x] Resolve provider route before idempotency/persistence/execution.
  - [x] Persist completed prediction and idempotency row.

- [x] Task 4: Implement GET `/v1/predictions/{prediction_id}` (AC: 5)
  - [x] Owner-only lookup.
  - [x] Completed response shape parity with POST.
  - [x] 404 for missing/cross-user.

- [x] Task 5: Add focused tests and run gates (AC: 6, 7)
  - [x] Add route tests for ARIMA, Chronos, GET, idempotency, invalid inputs, billing header, unaudited self forecast guard.
  - [x] Add pure helper tests for deterministic quantile output.
  - [x] Run AC7 commands and record results in Dev Agent Record.

### Review Findings

- [x] [Review][Patch] Prediction idempotency used `expires_at` only as stored metadata and did not enforce the 24h replay window; fixed by deleting expired prediction idempotency rows before lookup reuse and adding an expiry regression.
- [x] [Review][Patch] The idempotency replay test did not prove duplicate prediction rows were absent; fixed by counting rows scoped to the current `Idempotency-Key`.
- [x] [Review][Patch] Failed prediction GET shape was specified but not covered; fixed with a compact failed-row response test.
- [x] [Review][Patch] ORM index definition did not mirror the SQL `created_at DESC` index exactly; fixed to keep model/schema consistency.

## Dev Notes

### Current Implementation Facts

- `routes.py` already has `_rfc7807_error`, `_provider_route_error_response`, `_unaudited_self_algorithm_error`, `_hash_body`, `_attach_system_metadata`, and the auth/idempotency ordering used by `/v1/optimizations`.
- `provider_routing.provider_route_to_system_metadata(...)` already creates the provider-route metadata contract; use it directly for predictions instead of importing `attempt_route_metadata` from fallback execution.
- `provider_routing.select_provider_route("forecast", "arima")` already selects `arima-forecast`; `select_provider_route("forecast", "chronos-t5")` selects `chronos-t5-forecast`.
- `catalog.find_by_task_type_and_solver()` scans all forecast algorithms, so forecast routing is already multi-row aware.
- `AlgorithmSchema` and public catalog should not change in this story.
- `models.IdempotencyKey` is tied to `Optimization`; use a separate prediction idempotency table to avoid breaking prior stories.
- `main.py` imports only `routes.router`; adding routes in `routes.py` is enough.
- CORS currently allows `Authorization`, `Content-Type`, `Accept-Language`, `Idempotency-Key`. This story does not need browser prediction calls yet; do not expand CORS unless a test proves it necessary.

### Implementation Guidance

- Keep route helper names explicit, e.g. `_prediction_family_to_solver`, `_validate_prediction_data`, `_build_prediction_response_content`.
- Use `json.loads(payload.model_dump_json())` or existing response-model serialization pattern to keep datetime/UUID JSON-safe.
- For idempotency replay, only return cached completed rows. If a cached row is missing or not completed, return 409; do not create duplicate idempotency rows for the same `(user_id, key)`.
- Insert the idempotency row only after successful completed prediction, mirroring the current optimization success behavior.
- Treat unsupported family and route errors as pre-side-effect validation failures.
- Do not add fallback-chain support to predictions in this story; prediction requests have no `solver` or `fallback_chain` public fields.
- Keep exact disclaimer text stable:
  - `zh`: `本预测仅供参考`
  - `en`: `This forecast is for reference only`
  - `bilingual`: `本预测仅供参考 / This forecast is for reference only`
- Do not return a `citation` field yet; Story 6.A citation response path currently belongs to algorithm and optimization surfaces.

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Developer imports real statsmodels/Chronos and breaks CI or GPU-less local runs | AC4 forbids real model runtimes and requires deterministic helper tests. |
| Prediction route bypasses Story 2.8 governance | AC3 and AC6 require provider route before idempotency/persistence/execution and an unaudited self forecast regression. |
| Existing optimization idempotency/voucher tests break | AC2 requires separate prediction idempotency table and no mutation of `idempotency_keys`. |
| Response shape drifts before Story 3.6 | AC1 locks a minimal `prediction.p10/p50/p90` contract and disclaimer shape; 3.6 can deepen semantics without removing fields. |
| Billing header is silently ignored | AC3/AC6 require explicit 422 and no billing calls. |
| Invalid request creates partial rows | AC1/AC3/AC6 require validation and route checks before DB side effects. |
| Chronos catalog row is `v1_late` but FR E2 wants 2 prediction classes | Use deterministic mock for `chronos` now, with model_version from the catalog; response proves contract/routing only and must not claim real Chronos quality. |

## Definition of Done

- Story file has passed three pre-implementation reviews and all resulting patches are applied.
- `/v1/predictions` and `/v1/predictions/{id}` are implemented with focused tests.
- ARIMA and Chronos family submissions return completed predictions with P10/P50/P90, drift_score, model_version, and bilingual disclaimer.
- Unsupported/invalid/billing/unaudited-self cases are side-effect-free.
- AC7 quality gates pass or any inability to run them is documented.
- Sprint status and Dev Agent Record are updated.

## Dev Agent Record

### Agent Model Used

GPT-5

### Debug Log References

- 2026-05-27 - Created Story 3.2 and completed three pre-implementation review rounds with patches applied before coding.
- 2026-05-27 - Applied local DB schema for test environment with `infra/local-init/02-solver-schema.sql`.
- 2026-05-27 - TDD red confirmed on missing `solver_orchestrator.forecasting`; implementation then added schemas, models, DB tables, forecast helper, and routes.
- 2026-05-27 - Validation: `uv run pytest apps/solver-orchestrator/tests/test_prediction_submission.py -q` -> 19 passed.
- 2026-05-27 - Validation: `uv run pytest apps/solver-orchestrator/tests/test_provider_routing.py apps/solver-orchestrator/tests/test_unaudited_self_block.py -q` -> 21 passed.
- 2026-05-27 - Validation: `uv run pytest apps/solver-orchestrator/tests -q` -> 176 passed.
- 2026-05-27 - Validation: `uv run mypy apps packages` -> success, no issues in 88 source files.
- 2026-05-27 - Validation: `uv tool run pre-commit run --all-files --show-diff-on-failure` -> all hooks passed.
- 2026-05-27 - Validation: `git diff --check` -> passed.

### Completion Notes List

- Implemented synchronous `/v1/predictions` for `family="arima"` and `family="chronos"` using existing auth, `optimize:write` scope, provider routing, and unaudited-self governance.
- Added deterministic CI-safe quantile forecast helper with no statsmodels, Chronos, torch, transformers, GPU, network, or model-loader dependency.
- Persisted predictions and separate prediction idempotency keys without changing optimization idempotency semantics.
- Returned completed P10/P50/P90 prediction responses with bounded `drift_score`, model version, bilingual disclaimer, owner-only GET, side-effect-free invalid/billing/unaudited failures, and compact failed-row GET payload.
- Post-implementation code review completed; all findings were patched and regression tests were rerun.

### File List

- `_bmad-output/stories/3-2-prediction-submission.md`
- `_bmad-output/stories/sprint-status.yaml`
- `apps/solver-orchestrator/src/solver_orchestrator/forecasting.py`
- `apps/solver-orchestrator/src/solver_orchestrator/models.py`
- `apps/solver-orchestrator/src/solver_orchestrator/routes.py`
- `apps/solver-orchestrator/src/solver_orchestrator/schemas.py`
- `apps/solver-orchestrator/tests/test_prediction_submission.py`
- `infra/local-init/02-solver-schema.sql`

### Change Log

- 2026-05-27 - Initial Story 3.2 draft created from Epics/PRD/Architecture/current solver-orchestrator implementation.
- 2026-05-27 - Applied three pre-implementation story review rounds covering data consistency, function/dependency consistency, drift, edge cases, and closure.
- 2026-05-27 - Implemented prediction schemas, DB persistence, deterministic forecast helper, POST/GET prediction routes, and focused tests.
- 2026-05-27 - Applied post-implementation code review fixes for idempotency TTL, duplicate-row test closure, failed GET coverage, and ORM/SQL index consistency.
- 2026-05-27 - Marked Story 3.2 done after focused and full solver-orchestrator validation passed.

## Story Review Round 1 - Data Consistency (2026-05-27)

### Findings

- [x] [Patch] `PredictionResponse.status` allowed `failed` while the schema required completed-only forecast fields (`prediction`, `drift_score`, `completed_at`). Split the contract by making `PredictionResponse` completed-only and leaving failed rows to the compact GET status payload.
- [x] [Patch] `PredictionRequest.horizon = Field(ge=1, le=90)` would let FastAPI emit its default validation response instead of the story's RFC 7807 error shape. The story now requires route-level semantic validation for family, data length, finite values, and horizon.
- [x] [Patch] Persistence did not specify whether `prediction` JSON stores the quantile object and whether idempotency hashes normalized or raw request bodies. The story now locks normalized input, canonical family, quantile JSON, and omitted-vs-explicit default horizon idempotency behavior.

### Result

Round 1 passed after patches. The request/response/DB/idempotency data contract is now closed enough for implementation.

## Story Review Round 2 - Function / Dependency Consistency and Drift (2026-05-27)

### Findings

- [x] [Patch] The draft said to use `_provider_route_error_response(...)` semantics, but prediction requests do not expose `solver`; an unaudited forecast block must identify `field_path="family"` instead of leaking an internal mapped solver field.
- [x] [Patch] Provider route metadata was described structurally but did not require reuse of the existing metadata helper. The story now requires `provider_route_to_system_metadata(route, task_type="forecast", requested_solver=mapped_solver)` to avoid drift.
- [x] [Patch] The Chronos row is `status="v1_late"`, so the story needed to be explicit that `family="chronos"` proves route/contract only and must not claim real Chronos model quality.
- [x] [Patch] The draft left room for prediction fallback-chain support even though the public request has no solver/fallback fields. The story now excludes fallback-chain support for predictions in this scope.

### Result

Round 2 passed after patches. Function reuse, route metadata, family-to-solver mapping, and dependency boundaries are now aligned with existing code.

## Story Review Round 3 - Boundary / Edge Cases / Closure (2026-05-27)

### Findings

- [x] [Patch] Idempotency replay guidance said a missing or incomplete cached prediction could "continue carefully or return 409", which would allow divergent implementations and possible duplicate execution. The story now requires a fixed 409 `Idempotency Conflict`.
- [x] [Patch] The draft did not mention a `(user_id, key)` insert race on `prediction_idempotency_keys`; the story now requires converting that race into 409 instead of leaking a database error.
- [x] [Patch] Invalid horizon needed explicit test coverage alongside invalid data length and non-finite data values.

### Result

Round 3 passed after patches. Edge cases for idempotency replay, stale rows, insert races, invalid horizon, and no-side-effect failures are now closed.
