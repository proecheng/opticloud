# Story 3.10: Backtest 50% Credits 折扣

Status: done

## Story

作为一个已接入 Credits 计费的优化 API 用户，
我希望在提交历史回测任务时通过 `options.backtest=true` 获得 50% Credits 折扣，
以便在不扭曲真实求解耗时和成本归因的前提下，以半价成本验证历史数据方案。

## Acceptance Criteria

1. `POST /v1/optimizations` 的请求 schema 支持 `options.backtest: boolean`，默认 `false`；该字段作为用户 payload 的一部分持久化在 `optimizations.input_payload.options.backtest`，并参与现有幂等性 body hash。缺省和显式 `false` 必须等价，显式 `true` 必须与同一个 `Idempotency-Key` 下的 `false` 请求冲突。
2. 当同步 optimization 请求携带 `X-Billing-Charge-Id` 且 `options.backtest=true`，solver-orchestrator 仍按真实求解结果返回 `solve_seconds`、持久化 `Optimization.solve_seconds`、记录 solver cost attribution，不得把真实耗时除以二写入响应或成本事件。
3. 对 AC2 的 billing-backed 成功或 timeout finalize，billing-service 实际扣费为折扣后计费：`clamp(round_half_up(min(elapsed_seconds, max_solve_seconds) * rate_per_second * 0.5), charge_min_amount, reserved_amount)`。这表示常规非 floor 场景扣费 50%，但仍受 `max_solve_seconds`、`reserved_amount`、`charge_min_amount` 约束保护。
4. 对 `options.backtest=false` 或缺省的 billing-backed 同步 optimization，现有 reserve/finalize 行为、实际扣费、响应结构和测试语义保持不变。
5. 对无 billing header 的 backtest optimization，求解照常执行并持久化 `options.backtest=true`，但不得调用 billing reserve/finalize，也不得在响应中暴露折扣计费字段。
6. 对 billing finalize 失败的 backtest optimization，solver-orchestrator 仍返回求解结果并持久化现有 `error.billing_finalize_failed=true` 重试上下文；重试上下文必须包含足够信息让 billing reconciler 使用同一 50% 折扣完成补偿 finalize。
7. 对 async/auto-async optimization，`options.backtest=true` 可以入队并持久化；当前无 worker finalize，因此入队时只允许 reserve，不能提前扣费或伪造折扣扣费。将来 worker 应复用同一折扣元数据。
8. `/v1/predictions` 继续保持当前 Story 3.2 行为：`X-Billing-Charge-Id` 对 predictions 不支持并返回现有 Problem Details。Story 3.10 不实现 prediction backtest API、不改变 prediction billing header 拒绝规则、不添加预测结果字段。
9. billing-service `POST /v1/billing/charges/{id}/finalize` 合同向后兼容：未提供折扣参数时按 1.0 常规定价；提供 `discount_multiplier=0.5` 时以折扣后金额写 ledger 和 response；非法折扣系数被 schema 拒绝。
10. 对已完成 optimization 的幂等 replay，包含 backtest 的请求必须返回缓存结果，不得再次 reserve、finalize、issue voucher 或写 cost attribution；同一 `Idempotency-Key` 下 `backtest=true` 与 `false` 的请求必须按现有 409 conflict 处理。
11. 回归覆盖包括：schema 默认值和显式 backtest；sync billing backtest finalize 传递 0.5 折扣且响应保留真实 `solve_seconds`；非 backtest 不传折扣且扣费不变；无 billing header 不触发 billing；finalize 失败持久化折扣重试上下文；reconciler 重试保留折扣；billing-service finalize 0.5 ledger；prediction billing header 仍被拒绝；async backtest 只 reserve 不 finalize；幂等 replay 不重复扣费且 backtest true/false 冲突。

## Tasks / Subtasks

- [x] Task 1: 扩展请求与 billing finalize 合同（AC: 1, 3, 4, 9）
  - [x] 在 `apps/solver-orchestrator/src/solver_orchestrator/schemas.py::OptimizationOptions` 增加 `backtest: bool = False`。
  - [x] 在 `apps/billing-service/src/billing_service/schemas.py::FinalizeChargeRequest` 增加向后兼容的 `discount_multiplier`，默认 `1.0`，有效范围 `0 < x <= 1`。
  - [x] 在 `apps/billing-service/src/billing_service/pricing.py::compute_charge_amount` 支持折扣系数；未传折扣时保持现有计算完全不变；折扣计算必须在秒数 cap 之后、金额 quantize/min/reserved clamp 之前发生。
  - [x] 在 `apps/billing-service/src/billing_service/routes.py::finalize_charge` 将折扣系数传入 pricing，并在 Saga context / refund_partial metadata 中记录折扣信息。
- [x] Task 2: 在 solver-orchestrator 同步计费路径接入 backtest 折扣（AC: 2, 3, 4, 5, 6）
  - [x] 添加小 helper 计算 billing 折扣元数据，例如 `{"kind":"backtest","discount_multiplier":0.5}`；默认非 backtest 不产生折扣 metadata。
  - [x] 在 sync billing finalize 成功路径中，仅当 `payload.options.backtest=true` 时向 `billing_client.finalize()` 传 `discount_multiplier=0.5`；非 backtest 路径必须保持现有 finalize 调用形状，不传新 kwarg。
  - [x] 保留真实 `result.solve_seconds` 给 API 响应、`opt.solve_seconds` 和 cost attribution；不得通过折半 elapsed_seconds 实现折扣。
  - [x] finalize 失败时，在 `Optimization.error` 中保留现有 reconciler keys，并额外保存 `billing_discount_multiplier=0.5` 和 `billing_discount_kind="backtest"`。
  - [x] 无 billing header 时不调用 billing，但仍持久化 `input_payload.options.backtest=true`。
- [x] Task 3: 保持 async、prediction、幂等和重试边界闭环（AC: 6, 7, 8, 10）
  - [x] async/auto-async row 的 `_system.billing` metadata 如有 billing charge，应包含 backtest 折扣元数据供未来 worker 使用；当前仅 reserve，不 finalize。
  - [x] `billing_reconciler.retry_pending_finalizes()` 读取 `error.billing_discount_multiplier` 并在 retry finalize 时传回 billing client。
  - [x] 确认 `/v1/predictions` 的 billing header 拒绝路径不变；不要把 `backtest` 加到 `PredictionRequest`。
  - [x] 覆盖完成态 idempotency replay：同 body/backtest 返回缓存结果且不重复 billing，true/false body 差异返回 409。
- [x] Task 4: 添加聚焦测试和回归验证（AC: 1-10）
  - [x] 新增 `apps/solver-orchestrator/tests/test_backtest_discount.py`，覆盖 sync billing backtest、非 backtest、无 billing header、finalize failure metadata、async reserve-only、prediction unchanged、idempotency replay/conflict。
  - [x] 扩展 `apps/solver-orchestrator/tests/test_billing_reconciler.py` 覆盖 discount retry 参数。
  - [x] 扩展 `apps/billing-service/tests/test_charge_routes.py` 覆盖 `discount_multiplier=0.5` ledger 和非法折扣 schema。
  - [x] 运行 `uv run pytest apps/solver-orchestrator/tests/test_backtest_discount.py -q`、相关 reconciler/billing tests、`uv run pytest apps/solver-orchestrator/tests -q`、`uv run pytest apps/billing-service/tests -q`、`uv run mypy apps packages`、`uv tool run pre-commit run --all-files --show-diff-on-failure`、`git diff --check`。
- [x] Task 5: BMAD bookkeeping 与审查闭环（AC: 10）
  - [x] 更新本 story 的 Dev Agent Record、File List、Change Log 和 sprint status。
  - [x] 实施完成后运行代码审查，修复审查发现，再进入 GitHub 同步。

## Dev Notes

### Current Implementation Reality

- `OptimizationOptions` 当前只有 `max_solve_seconds`、`top_k_alternatives`、`reproducible`、`anonymous`。新增 `backtest` 应沿用 Pydantic option 字段模式，不需要 migration。
- `post_optimization()` 使用 `payload.model_dump(by_alias=True)` 形成 `body_dict`，并把该 payload 存入 `Optimization.input_payload`。因此 `options.backtest` 默认会随 payload 持久化并参与 idempotency hash。
- sync billing 当前流程在 solver-orchestrator 中是 `billing_client.reserve()` 后求解，再调用 `billing_client.finalize(elapsed_seconds=result.solve_seconds, status=...)`。
- billing-service finalize 目前只根据 `elapsed_seconds`、`max_solve_seconds`、`lp_rate_per_second`、`charge_min_amount`、`reserved_amount` 计算实际扣费。Story 3.10 应在 billing 合同中加入折扣系数，不能让 solver 传伪造的半数 elapsed_seconds。
- async 路径当前可带 `X-Billing-Charge-Id` reserve 并返回 queued，但无 worker finalize。Story 3.10 不能新增 worker，也不能在 queue 阶段扣费。
- `/v1/predictions` 当前显式拒绝 `X-Billing-Charge-Id`，并有 `test_prediction_billing_header_is_rejected_without_billing_calls_or_rows` 覆盖。PRD 的 "backtest predictions" 属于 E10 v2 业务目标，但本 sprint story 的 epics AC 写的是 optimization task with `backtest: true`；本 story 只落最小计费闭环。

### Discount Contract

使用 billing-service 的可选字段表达折扣：

```json
{
  "elapsed_seconds": 10.0,
  "status": "success",
  "failure_reason": null,
  "discount_multiplier": 0.5
}
```

语义：

- `discount_multiplier` 缺省为 `1.0`，所以现有调用不变。
- 合法范围为 `0 < discount_multiplier <= 1.0`；不允许 `0`、负数或大于 1 的放大收费。
- backtest 固定使用 `0.5`，不要开放用户自定义折扣比例。
- `elapsed_seconds` 始终表示真实求解耗时；折扣只影响 billing-service 的 `actual_amount`。
- 金额公式为 `clamped_seconds = min(max(elapsed_seconds, 0), max_solve_seconds)`，`raw = clamped_seconds * rate_per_second * discount_multiplier`，再按现有 `ROUND_HALF_UP` 到 0.01，并套用现有 min/reserved clamp。
- billing response 不需要新增公开字段；ledger metadata / Saga context 可记录 `discount_multiplier` 和 `discount_kind` 供审计。
- solver-orchestrator `billing_client.finalize()` 可以新增可选参数，但调用方必须只在折扣存在时传该参数，避免破坏现有测试 monkeypatch 和非折扣调用形状。

### Existing Code to Reuse

- solver schema: `apps/solver-orchestrator/src/solver_orchestrator/schemas.py::OptimizationOptions`。
- solver billing integration: `apps/solver-orchestrator/src/solver_orchestrator/routes.py` 中 Story 5.A.4 reserve/finalize block。
- async billing metadata helper: `_set_optimization_billing_metadata()` 和 `_attach_system_metadata()`。
- failed finalize retry: `apps/solver-orchestrator/src/solver_orchestrator/billing_reconciler.py::retry_pending_finalizes`。
- billing client: `apps/solver-orchestrator/src/solver_orchestrator/billing_client.py::finalize`。
- billing pricing: `apps/billing-service/src/billing_service/pricing.py::compute_charge_amount`。
- billing finalize route: `apps/billing-service/src/billing_service/routes.py::finalize_charge`。

### Boundary Rules

- 不新增 `/v1/backtests`、prediction backtest endpoint、UI、DB migration、pricing table 或用户可配置折扣。
- 不改变 `OptimizationResponse.solve_seconds` 的含义。
- 不改变 cost attribution 的真实 solver-second 记录。
- 不改变 no billing header 的执行路径：没有 charge id 就没有 reserve/finalize。
- 不改变 failure finalize 的 status 语义：infeasible/unbounded 仍是 `status="failure"`，通常净扣费为 0；折扣只需随 retry context 保留，避免未来重试时语义漂移。
- 区分 solver 失败和 billing finalize 调用失败：solver 的 infeasible/unbounded 仍走 `status="failure"`，不会产生实际扣费；只有 billing finalize 调用自身失败时才写 `error.billing_finalize_failed=true` 和折扣 retry metadata。
- 已完成 optimization 的 idempotency replay 是只读缓存返回，不得因为请求携带 billing header 或 backtest 标志再次调用 reserve/finalize。
- 不把 `_system.billing`、billing charge id、折扣 metadata 直接暴露到公开 response。
- 不改变 prediction billing header 拒绝规则，避免在缺少 prediction charge 设计时造成跨域计费漂移。
- 不直接从 solver-orchestrator import billing-service 模块；跨服务调用仍只能通过 `billing_client.py`。

### Previous Story Intelligence

- Story 3.8 已建立 async billing reserve metadata、cancel refund finalize 和 billing reconciler retry keys。Story 3.10 应复用这些 keys，并只在需要时增加折扣字段。
- Story 3.9 强调 public response 与 internal `_system` metadata 分离。Story 3.10 的折扣 metadata 同样保持内部可审计、公开响应不泄露。
- 近期 solver stories 的验证节奏是先跑聚焦测试，再跑 solver-orchestrator 全套、billing-service 全套、mypy、pre-commit、diff-check。

### Testing Standards

- solver-orchestrator 测试使用现有 async HTTP style 和 monkeypatch billing client，不需要 live billing-service。
- billing-service ledger 行为在 `apps/billing-service/tests/test_charge_routes.py` 中扩展，直接验证 `actual_amount`、`refund_partial_amount` 和余额净变化。
- 对 backtest billing 的 solver 测试应同时断言 `body["solve_seconds"]` 等于真实 solver result 耗时，且 finalize 参数的 `discount_multiplier` 为 `0.5`。
- 对 non-backtest 测试应断言 finalize 调用不携带折扣参数，避免默认路径破坏现有 monkeypatch 签名。

### References

- `_bmad-output/planning/epics.md` Story 3.10: `Given task with backtest: true (v2) ... Credits 折半 50%`。
- `_bmad-output/planning/prd.md` FR E10: `用户 can backtest predictions at 50% Credits 折扣`。
- `_bmad-output/planning/architecture.md` FR → Service Mapping: E1-E10 由 `solver-orchestrator` 主、`billing-service` 配合。
- `_bmad-output/stories/3-8-cancel-refund.md` billing metadata、reconciler keys、cross-service boundary。
- `_bmad-output/stories/3-9-status-progress-eta.md` public/internal metadata 分离和三轮审查格式。
- `apps/solver-orchestrator/src/solver_orchestrator/routes.py` sync/async billing flow。
- `apps/billing-service/src/billing_service/routes.py` finalize ledger flow。

## Story Review Rounds

### Round 1 - Data Consistency (2026-05-27)

Findings applied:

- AC1 now states idempotency semantics for default `backtest=false`: omitted and explicit false are identical, while explicit true is a distinct request body and must conflict under the same `Idempotency-Key`.
- AC3 now defines the exact billing formula and ordering. Discount is applied after elapsed-second capping and before quantize/min/reserved clamps, so normal cases charge 50% while `charge_min_amount` and `reserved_amount` remain authoritative.
- Task 1 and the Discount Contract now repeat the same formula so implementation and tests cannot diverge on whether to halve elapsed time, halve final amount, or bypass the floor.

Result: request data, idempotency identity, actual solver seconds, and discounted billing amount are now data-consistent.

### Round 2 - Function / Dependency Consistency and Drift (2026-05-27)

Findings applied:

- Existing solver tests monkeypatch `billing_client.finalize()` with signatures that do not accept future kwargs. Task 2 and the Discount Contract now require the route and reconciler to pass `discount_multiplier` only when a discount exists; ordinary non-backtest finalize calls keep the old call shape.
- The billing-service pricing function is used by existing unit and property tests. The story requires a default `discount_multiplier=1.0` path so existing pricing tests remain valid and only new discount tests cover the new branch.
- Cross-service boundaries remain intact: solver-orchestrator changes the HTTP client body only through `billing_client.py`; it must not import billing-service schemas, routes, or pricing helpers.

Result: new discount support is additive, preserves existing monkeypatch/test contracts, and avoids dependency drift across service boundaries.

### Round 3 - Boundary / Edge Cases / Closure (2026-05-27)

Findings applied:

- Completed idempotency replay could otherwise accidentally re-run billing for a backtest request with a billing header. AC10 and Task 3 now require replay to return the cached optimization without reserve/finalize/cost/voucher side effects.
- Backtest true/false identity was under-tested. AC10/AC11 now require same-key true-vs-false conflict coverage so a discounted run cannot replay a non-discounted row or vice versa.
- Solver failure and billing finalize call failure are now explicitly separated. Infeasible/unbounded still uses billing `status="failure"` and normally nets zero; retry metadata is only for failed finalize calls.
- Async closure is constrained to persisted future-worker metadata plus reserve only. The story still forbids queue-time finalize or invented worker behavior.

Result: duplicate billing, idempotency drift, failed-solve semantics, and async future-worker boundaries are closed before implementation.

## Dev Agent Record

### Agent Model Used

GPT-5

### Debug Log References

- 2026-05-27 - Initial Story 3.10 draft created from sprint status, Epics/PRD/Architecture/UX, Story 3.8/3.9 learnings, current solver billing flow, billing-service finalize/pricing code, and existing test patterns.
- 2026-05-27 - Story review Round 1 completed and applied: data consistency for idempotency default semantics and discount amount formula/order.
- 2026-05-27 - Story review Round 2 completed and applied: function/dependency consistency for optional finalize kwargs and additive pricing defaults.
- 2026-05-27 - Story review Round 3 completed and applied: idempotency replay, failure/finalize distinction, async boundary, and closure coverage.
- 2026-05-27 - Dev implementation started; sprint/story status moved to in-progress.
- 2026-05-27 - RED phase confirmed: Story 3.10 focused tests failed on missing `options.backtest`, missing finalize discount kwarg, missing persisted discount metadata, and missing reconciler retry discount.
- 2026-05-27 - Implemented `options.backtest`, optional billing `discount_multiplier`, billing-service discounted charge math, solver sync/async discount metadata, and reconciler discount retry.
- 2026-05-27 - Focused Story 3.10 tests passed: `uv run pytest apps/solver-orchestrator/tests/test_backtest_discount.py -q` -> 9 passed.
- 2026-05-27 - Billing pricing/finalize and reconciler focused tests passed.
- 2026-05-27 - Full validation passed before code review: solver-orchestrator suite 263 passed; billing-service suite 139 passed; `uv run mypy apps packages`, pre-commit, and `git diff --check` passed.
- 2026-05-27 - Post-implementation code review completed; patched non-backtest internal billing metadata drift and added refund metadata regression coverage.
- 2026-05-27 - Final validation after code-review patch passed: Story 3.10 focused tests 9 passed; solver-orchestrator suite 263 passed; billing-service suite 139 passed; `uv run mypy apps packages`, pre-commit, and `git diff --check` passed.

### Completion Notes List

- Story draft scopes E10 to the epics-defined `options.backtest=true` optimization billing discount and explicitly excludes prediction backtest API changes.
- Story draft preserves true `solve_seconds` and solver-second cost attribution by adding an explicit billing `discount_multiplier` contract instead of halving elapsed seconds.
- Round 1 clarified that the 50% discount applies to billing raw amount after elapsed-second cap, then existing quantize/min/reserved clamps still apply.
- Round 2 clarified that non-backtest billing finalize calls must keep their existing call shape; only backtest/retry discount paths pass the new optional kwarg.
- Round 3 clarified that completed idempotency replay must not repeat billing and that backtest true/false body identity must conflict under the same key.
- Implemented Story 3.10 using an explicit billing `discount_multiplier` contract, preserving true solver elapsed seconds and non-backtest finalize call shape.
- Added focused solver/billing/reconciler coverage for discount, no-billing, async reserve-only, prediction boundary, and idempotency replay/conflict.
- Resolved post-implementation review finding: non-backtest finalize no longer writes default `discount_multiplier=1.0000` into internal Saga/outbox/refund metadata, preserving legacy audit shape.
- Story 3.10 is complete after final regression, mypy, pre-commit, and diff-check validation.

### File List

- `_bmad-output/stories/3-10-backtest-discount.md`
- `_bmad-output/stories/sprint-status.yaml`
- `apps/solver-orchestrator/src/solver_orchestrator/schemas.py`
- `apps/solver-orchestrator/src/solver_orchestrator/billing_client.py`
- `apps/solver-orchestrator/src/solver_orchestrator/routes.py`
- `apps/solver-orchestrator/src/solver_orchestrator/billing_reconciler.py`
- `apps/solver-orchestrator/tests/test_backtest_discount.py`
- `apps/solver-orchestrator/tests/test_billing_reconciler.py`
- `apps/billing-service/src/billing_service/schemas.py`
- `apps/billing-service/src/billing_service/pricing.py`
- `apps/billing-service/src/billing_service/routes.py`
- `apps/billing-service/tests/test_pricing.py`
- `apps/billing-service/tests/test_charge_routes.py`

### Change Log

- 2026-05-27 - Initial Story 3.10 draft created and sprint status moved from backlog to ready-for-dev.
- 2026-05-27 - Applied Story Review Round 1 data consistency fixes.
- 2026-05-27 - Applied Story Review Round 2 function/dependency consistency fixes.
- 2026-05-27 - Applied Story Review Round 3 boundary/closure fixes.
- 2026-05-27 - Implemented Story 3.10 backtest discount contract and moved story to review after validation.
- 2026-05-27 - Completed post-implementation code review; fixed non-backtest discount metadata drift and marked story done after final validation.

## Senior Developer Review (AI) - Post-Implementation (2026-05-27)

### Review Scope

- Uncommitted branch diff against Story 3.10 spec.
- Layers covered manually in one pass due tool constraints: Blind Hunter, Edge Case Hunter, Acceptance Auditor.

### Findings

- [x] [Review][Patch] Non-backtest billing finalize wrote default `discount_multiplier=1.0000` into internal Saga context / outbox / refund metadata. This could make legacy non-discounted charges appear discount-aware in audit trails even though the public charge behavior was unchanged. Patched with `_discount_context()` so only real discounts write discount metadata.

### Fixes Applied

- Added `_discount_context()` in billing-service finalize flow and used it for Saga transition context and `refund_partial` metadata.
- Added regression assertion in `test_finalize_success_5s_writes_charge_and_refund_partial` that non-backtest refund metadata does not include `discount_multiplier`.

### Result

Approved after patch. Focused Story 3.10 tests, reconciler discount retry test, billing finalize discount tests, full solver-orchestrator suite, full billing-service suite, mypy, pre-commit, and diff-check all passed.
