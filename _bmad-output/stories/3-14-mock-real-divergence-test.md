# Story 3.14: Mock-Real Divergence Test Suite

Status: done

owner: QA / Solver Lead

## Story

作为 QA / 后端开发者，
我希望把 LP stub/mock 与真实 HiGHS 求解路径的响应合同做成专门的 mock-real divergence 测试套件，
以便早期 vertical-slice mock 不会和真实 solver / API 响应 schema 漂移，后续 SDK、Console 和批量任务都能依赖同一个稳定合同。

## Acceptance Criteria

1. 建立 Story 3.14 专用测试文件，覆盖 solver 层 mock-vs-real schema parity。
   - 新增 `apps/solver-orchestrator/tests/test_mock_real_divergence.py`。
   - 保留 `apps/solver-orchestrator/tests/test_solvers.py` 的基础 HiGHS 单元测试语义，但把 Q-T1 专项 divergence 覆盖迁移/扩展到新文件，避免一个单点 smoke test 伪装成完整套件。
   - 测试必须离线、确定性、无需网络、无需真实 Postgres、无需 billing/auth service。
   - 不新增生产 endpoint、DB table、worker、队列、外部 solver 或前端 UI。

2. 明确定义 LP mock contract，并与真实 `LPSolveResult` 对齐。
   - 在测试文件内定义最小 deterministic `mock_solver.solve(payload)` 或等价 test double；不要把 mock solver 提升为生产代码。
   - Mock contract 的 ordered top-level keys 必须为：`status`、`objective`、`solution`、`solve_seconds`、`error_field_path`、`error_constraint`、`alternatives`。
   - `solution` 为 `None` 或 `{"x": list[float]}`；`objective` 为 `float | None`；`solve_seconds` 为非负 `float`。
   - `status` 只允许真实 solver 当前公共集合：`optimal`、`infeasible`、`unbounded`、`timeout`、`error`。
   - 错误类状态必须允许 `error_field_path` / `error_constraint` 非空，成功类状态不得要求错误字段非空。

3. Property-based LP inputs 复用共享基础设施。
   - 使用 `opticloud_shared.property_test_base.strategies.lp_inputs(...)`，不得在 solver 测试里重新定义随机 LP strategy。
   - Hypothesis settings 要控制 `max_examples` 和 `deadline`，使本地/CI 可稳定通过。
   - Property 测试只断言 schema/shape/order/type parity，不断言 mock 与真实 solver 的数值解相同；mock 不是优化算法 oracle。
   - 覆盖 minimize payload；如加入 maximize/top-k，只能作为明确子用例，不能扩大为新 solver 功能。

4. 覆盖 HTTP completed response 的 mock-real contract parity。
   - 对真实 completed optimization public payload，复用现有 `_build_response_content(...)` / `_build_success_response(...)` 路径，不手写另一份 API schema。
   - 测试 API public key order 和字段集合，至少覆盖：`optimization_id`、`status`、`solution`、`objective`、`model_version`、`solve_seconds`、`created_at`、`completed_at`、`citation`、`ip_attribution`、`progress_pct`、`eta_seconds`。
   - `model_version` 必须保持 `provider_id`、`kind`、`version`、`provider_url` 四字段，不接受内部 `provider_kind` alias。
   - API parity 测试不得暴露 `_system`、`provider_route`、billing metadata、API key 或 internal route metadata。

5. 覆盖 terminal/error shape parity 和边界。
   - 至少覆盖真实 `optimal`、`infeasible` 和 malformed-shape `error` 的 solver result shape。
   - 对 timeout/unbounded 可用 deterministic fake `LPSolveResult` 做 contract validation；不得引入慢速 solver 构造或依赖 wall-clock race。
   - 覆盖 `top_k_alternatives` metadata 的 shape/order：当真实 result 含 alternatives 时，每项必须含 `rank`、`score`、`objective`、`solution`、`source`，且 `solution.x` 为 `list[float]`。
   - 字段顺序检查必须使用 Python dict insertion order 或 JSON roundtrip 后的 key order；不要用 `set(...)` 代替顺序断言。

6. 现有业务行为保持不变。
   - 不改变 `solver_orchestrator.solvers.solve_lp(...)` / `solve_from_request(...)` 的数学求解逻辑。
   - 不改变 `/v1/optimizations`、`/v1/optimizations/demo`、batch endpoint、prediction endpoint、billing/repro/cancel/status 行为。
   - 不改变 `OptimizationResponse`、`ModelVersionSchema`、`LPSolveResult` 的生产字段，除非测试发现真实 bug 且通过代码审查确认必须修复。
   - 不引入新的 runtime dependency；`hypothesis` 已存在于 solver dev extra，`lp_inputs` 已由 Story 0.5b 提供。

7. 验证闭环。
   - Focused: `uv run pytest apps/solver-orchestrator/tests/test_mock_real_divergence.py -q`
   - Adjacent: `uv run pytest apps/solver-orchestrator/tests/test_solvers.py apps/solver-orchestrator/tests/test_top_k_alternatives.py apps/solver-orchestrator/tests/test_sync_async_mode.py apps/solver-orchestrator/tests/test_status_progress_eta.py -q`
   - Full solver suite: `uv run pytest apps/solver-orchestrator/tests -q`
   - Static checks: `uv run mypy apps packages`、`uv tool run pre-commit run --all-files --show-diff-on-failure`、`git diff --check`

## Tasks / Subtasks

- [x] Task 1: Add dedicated mock-real divergence test suite. (AC: 1, 2, 3, 5)
  - [x] Create `apps/solver-orchestrator/tests/test_mock_real_divergence.py`.
  - [x] Define test-only deterministic mock result builder and ordered contract assertions.
  - [x] Add Hypothesis property test using shared `lp_inputs(...)`.
- [x] Task 2: Add API completed-response contract parity coverage. (AC: 4, 6)
  - [x] Build completed `Optimization` rows/objects through existing model/helper patterns.
  - [x] Assert public response field order and model_version shape through existing response builders.
  - [x] Assert no internal `_system`, provider route, billing or secret metadata leaks.
- [x] Task 3: Cover terminal/error/top-k edge shapes. (AC: 2, 5, 6)
  - [x] Cover optimal, infeasible and malformed LP result shapes.
  - [x] Cover timeout/unbounded via deterministic `LPSolveResult` instances.
  - [x] Cover alternatives item shape/order without asserting solver numerical equivalence to mock.
- [x] Task 4: Validate and update BMad bookkeeping. (AC: 7)
  - [x] Run focused, adjacent, full and static validation commands.
  - [x] Update Dev Agent Record, File List and Change Log.
  - [x] Move sprint status through `in-progress`, `code-review`, then `done` only after code review fixes pass.

### Review Findings

- [x] [Review][Patch] Lock `LPSolveResult` dataclass field order, not only the manual canonicalized dict [apps/solver-orchestrator/tests/test_mock_real_divergence.py:68] — fixed by asserting `dataclasses.fields(LPSolveResult)` matches the mock contract order.
- [x] [Review][Patch] Strengthen public payload no-leak assertions for generic billing/API-key metadata, not only charge-id strings [apps/solver-orchestrator/tests/test_mock_real_divergence.py:127] — fixed by rejecting `billing`, `api_key` and `authorization` substrings in serialized public payloads.

## Dev Notes

### Source Context

- `_bmad-output/planning/epics.md` Story 3.14 requires: Given mock mode, When `mock_solver.solve()` vs real `HiGHS.solve()`, Then schema 100% consistent and field order consistent.
- `_bmad-output/planning/epics.md` Q-T1 says all stub-using stories need mock-real divergence AC to prevent vertical-slice mock drift.
- `_bmad-output/planning/architecture.md` Constraint C2 requires LLM mock + algorithm mock abstraction in test environments because CI must not depend on paid APIs or heavy compute.
- `_bmad-output/planning/architecture.md` Version Catalog pins Python 3.12 intent, FastAPI/Pydantic v2/SQLAlchemy 2 stack, pytest + pytest-asyncio, Hypothesis, and HiGHS 1.7+.
- `_bmad-output/stories/0-5b-property-test-framework.md` created shared `lp_inputs(...)` specifically for 3-14 mock-real divergence.
- Existing `apps/solver-orchestrator/tests/test_solvers.py` has only a single Q-T1 schema smoke test; 3.14 turns this into a dedicated suite.

### Current Repository Reality

- Real LP solver entry points live in `apps/solver-orchestrator/src/solver_orchestrator/solvers.py`:
  - `solve_lp(...)`
  - `solve_from_request(...)`
  - `LPSolveResult`
  - `TOP_K_STRATEGY`
- Public completed optimization payload is built by `apps/solver-orchestrator/src/solver_orchestrator/routes.py::_build_response_content(...)` and `_build_success_response(...)`.
- `OptimizationResponse` in `schemas.py` controls the core completed response field order before route helpers append status/progress and optional top-k metadata.
- Provider route/model version public shape is already guarded by Story 3.9 and Story 2.6 tests; 3.14 should assert parity, not replace those tests.
- Shared Hypothesis strategy is in `packages/shared-py/opticloud_shared/property_test_base/strategies.py::lp_inputs`.

### Implementation Guidance

- Keep the mock solver test-only. A simple `OrderedDict` or normal dict literal with stable insertion order is enough.
- Prefer helper assertions such as:
  - `assert_solver_contract(payload)`
  - `assert_completed_response_contract(content)`
  - `assert_model_version_contract(model_version)`
  - `assert_alternatives_contract(alternatives)`
- For property tests, canonicalize `LPSolveResult` into a dict before checking key order. Do not compare numerical objective/solution against mock output.
- Use small LP dimensions for property tests, e.g. `lp_inputs(n_max=4, m_max=4)` and bounded `max_examples`.
- If a random LP is infeasible/unbounded/error, that is valid; the invariant is that the returned schema remains stable.
- Avoid wall-clock dependent timeout tests. Create a fake `LPSolveResult(status="timeout", ...)` for timeout shape validation.
- Do not import FastAPI app or hit HTTP unless needed. Response-builder tests can instantiate `Optimization` directly, matching existing `test_citation.py` style.

### Boundary Rules

- No production mock solver module.
- No API endpoint changes.
- No DB migration or local-init SQL change.
- No OpenAPI/codegen update.
- No frontend, SDK, Storybook, Playwright or E2E scope.
- No real provider fallback, billing, voucher, cost attribution, batch or prediction behavior changes.
- No network calls and no test dependency on external solver services beyond in-process HiGHS already used by Story 3.1.

### Previous Story Intelligence

- Story 0.5b already solved the shared property-test strategy problem. Reuse it instead of duplicating Hypothesis strategies.
- Story 3.1 already embedded HiGHS and prewarm behavior. 3.14 should not change solver internals.
- Story 3.5 added `alternatives` and `top_k_alternatives` metadata. 3.14 must include shape parity for alternatives when present.
- Story 3.9 established `progress_pct`, `eta_seconds` and model version public fields. 3.14 should assert those fields are stable on completed payloads.
- Story 3.13 added batch endpoint but explicitly excluded mock-real divergence changes. 3.14 can include batch tests only as adjacent regression, not as feature scope.

### Risks / Decisions

- Data consistency risk: using `set(keys)` would miss field-order drift. Story 3.14 requires ordered key assertions.
- Function consistency risk: putting mock solver into production code creates a second execution path. Keep it in tests.
- Drift risk: if tests assert exact numerical equality between mock and HiGHS, they will either be false or force mock to become a solver. Assert schema parity only.
- Boundary risk: timeout tests can become flaky if they rely on real time limits. Use deterministic fake result shape for timeout/unbounded coverage.
- Closure risk: focused tests alone are insufficient because response builders are shared by sync/status/top-k paths. Run adjacent and full solver tests.

## Story Review Rounds

### Round 1 - Data Consistency (2026-05-28)

Findings applied:

- Required ordered top-level keys for solver contract instead of unordered key-set checks.
- Bound `solution.x`, `objective`, `solve_seconds`, `error_field_path`, `error_constraint` and `alternatives` types to the real `LPSolveResult` shape.
- Added API completed response order and model_version four-field shape so solver-layer parity cannot drift away from public response parity.
- Clarified property tests assert schema/shape/order, not numerical equivalence between mock and real solver.

Result: mock result, real solver result and public completed response have one explicit data contract.

### Round 2 - Function / Dependency Consistency and Drift (2026-05-28)

Findings applied:

- Required reuse of shared `lp_inputs(...)` from Story 0.5b; no duplicated per-service Hypothesis strategy.
- Required response parity tests to reuse existing `_build_response_content(...)` / `_build_success_response(...)`.
- Kept mock solver as test-only to avoid creating a production execution path that would drift from HiGHS/provider routing.
- Reused existing HiGHS in-process solver and existing dev dependency set; no new runtime dependency.

Result: Story 3.14 extends the existing test architecture without duplicating solver, API schema or property-test infrastructure.

### Round 3 - Boundary / Edge Cases / Closure (2026-05-28)

Findings applied:

- Added deterministic coverage for optimal, infeasible, malformed error, timeout, unbounded and alternatives shapes.
- Explicitly prohibited network, DB, billing, voucher, batch, prediction, frontend, SDK and OpenAPI scope.
- Added no-leak assertions for `_system`, provider route, billing and secrets on public API payloads.
- Added focused, adjacent, full solver and static validation commands before marking done.

Result: edge cases, scope boundaries and validation evidence are closed before implementation starts.

## Dev Agent Record

### Agent Model Used

GPT-5

### Debug Log References

- 2026-05-28 - Story 3.14 draft created from sprint status, Epic 3/Q-T1, Architecture C2, Story 0.5b property-test framework, existing `solvers.py`, response builders and current solver tests.
- 2026-05-28 - Story review Round 1 completed and applied: ordered solver/API data contract, model_version shape, schema-only parity boundary.
- 2026-05-28 - Story review Round 2 completed and applied: shared `lp_inputs`, response helper reuse, test-only mock, no new dependencies.
- 2026-05-28 - Story review Round 3 completed and applied: terminal/error/top-k edge coverage, no-leak assertions, no scope drift, validation closure.
- 2026-05-28 - Dev implementation started; story and sprint status moved to in-progress.
- 2026-05-28 - RED phase completed: focused test command failed because `test_mock_real_divergence.py` did not exist.
- 2026-05-28 - GREEN/REFACTOR completed: added dedicated mock-real divergence tests, migrated old Q-T1 smoke coverage out of `test_solvers.py`, and kept all changes test-only.
- 2026-05-28 - Validation passed: focused divergence tests `6 passed`; adjacent regression `41 passed`; full solver-orchestrator suite `281 passed`; `uv run mypy apps packages`; `uv tool run pre-commit run --all-files --show-diff-on-failure`; `git diff --check`.
- 2026-05-28 - Code review completed locally across Blind Hunter / Edge Case Hunter / Acceptance Auditor layers. Two patch findings were fixed: `LPSolveResult` dataclass-order drift guard and broader public payload metadata no-leak assertions.
- 2026-05-28 - Post-review validation passed: focused divergence tests `7 passed`; adjacent regression `41 passed`; full solver-orchestrator suite `282 passed`; `uv run mypy apps packages`; `uv tool run pre-commit run --all-files --show-diff-on-failure`; `git diff --check`.

### Implementation Plan

- Add a dedicated mock-real divergence test file with reusable ordered contract assertions.
- Use property-based LP payloads from shared-py to compare mock result shape and real `solve_from_request(...)` shape.
- Add direct response-builder contract tests for completed optimization payloads and top-k metadata.

### Completion Notes List

- Story 3.14 implementation and code review are complete.
- Implementation must remain in `D:\优化预测网站`; no sibling worktree directories.
- Added a test-only deterministic mock contract and ordered real solver result canonicalization; no production solver/API behavior was changed.
- Added public completed response contract checks through existing route builders, including model_version four-field shape and no internal metadata leaks.
- Added terminal/error/top-k shape coverage with deterministic timeout/unbounded fake results to avoid flaky wall-clock tests.
- Code review patches applied: dataclass field-order drift is now pinned directly, and no-leak assertions reject generic billing/API-key/authorization metadata in public payloads.
- Final validation passed after review fixes: focused `7 passed`, adjacent `41 passed`, full solver suite `282 passed`, mypy/pre-commit/diff-check all passed.

### File List

- `_bmad-output/stories/3-14-mock-real-divergence-test.md`
- `_bmad-output/stories/sprint-status.yaml`
- `apps/solver-orchestrator/tests/test_mock_real_divergence.py`
- `apps/solver-orchestrator/tests/test_solvers.py`

### Change Log

- 2026-05-28 - Initial Story 3.14 created and reviewed through three pre-implementation rounds; sprint status moved from backlog to ready-for-dev.
- 2026-05-28 - Dev implementation started; status moved to in-progress.
- 2026-05-28 - Implemented Story 3.14 mock-real divergence test suite and validation; status moved to code-review.
- 2026-05-28 - Applied post-implementation code review fixes for dataclass-order drift and metadata no-leak coverage.
- 2026-05-28 - Post-review validation passed; story status moved to done.
