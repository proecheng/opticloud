---
story_key: 8-c-1-mode-teaching-explain
epic_num: 8
story_num: C.1
epic_name: Teaching + Provider Routing + Legal + Algorithm Library
status: done
baseline_commit: 11c106d49a61b667fcfe1386219754cf7623f70b
priority: High
type: FR O8 teaching mode
created_by: bmad-create-story
created_at: 2026-06-04
sources:
  - _bmad-output/planning/epics.md (Epic 8.C / Story 8.C.1)
  - _bmad-output/planning/prd.md (FR O8)
  - _bmad-output/planning/architecture.md (FR -> service mapping O8)
  - docs/academic-provider-handbook.md (teaching / research / production vocabulary)
  - _bmad-output/stories/3-10-backtest-discount.md
  - apps/solver-orchestrator/src/solver_orchestrator/routes.py
  - apps/solver-orchestrator/src/solver_orchestrator/schemas.py
  - apps/solver-orchestrator/src/solver_orchestrator/billing_client.py
  - apps/solver-orchestrator/tests/test_backtest_discount.py
  - apps/solver-orchestrator/tests/test_sync_async_mode.py
  - apps/web/src/lib/api.ts
---

# Story 8.C.1 - mode=teaching + 原理讲解

Status: done

## Story

**作为** 教学场景下的优化算法用户，
**我希望** 在提交优化任务时可以通过 `mode=teaching` 请求教学模式，
**从而** 同一次 API 响应能返回算法原理讲解、Notebook Colab 链接，并在 Credits 计费路径使用 50% 教学折扣。

## Context

Epic 8.C.1 的原始 AC 是：Given `mode=teaching` query / When 用户 / Then 返回含原理讲解 + 50% Credits 折扣 + Notebook Colab 链接。

当前仓库状态：

- `POST /v1/optimizations` 已存在 query `mode=sync|async`，用于执行模式。`mode=teaching` 不能破坏现有 sync/async 行为，也不能让 omitted mode 与 explicit sync 的幂等语义漂移。
- `options.backtest=true` 已在 Story 3.10 实现 50% Credits 折扣，关键路径包括 solver-orchestrator discount metadata、billing-client optional `discount_multiplier`、billing-service finalize 合同和 reconciler retry context。
- `OptimizationResponse` 目前没有教学字段，但 route 实际通过 `_build_response_content()` 组装 dict，已有 reproducibility/top-k 等附加 response metadata 模式。
- 当前 catalog 至少有 LP / HiGHS 可执行同步路径，其他 task type 在 authenticated route 仍可能 501；本 story 应优先闭合 LP teaching vertical slice，不承诺所有算法都有完整 Notebook。
- repo 当前没有 committed Notebook 文件；如果 response 暴露 Colab 链接，必须指向本 repo 内真实存在的 deterministic notebook path，不能返回虚假或需要在线生成的链接。

## Scope

1. 在 `POST /v1/optimizations?mode=teaching` 支持教学模式。
   - `mode=sync`、`mode=async`、omitted mode 行为保持兼容。
   - `mode=teaching` 表示教学 profile，默认使用现有 sync execution mode，并保留现有 large LP auto-async 逻辑。
   - 教学 profile 必须写入 `_system.teaching` metadata，GET completed/status replay 和 idempotency replay 能返回同一教学信息。
   - Public response 的 `mode` 字段仍表示 execution mode（`sync` 不显式返回，`async` status 返回 `mode="async"`）；教学语义只通过 `teaching.mode="teaching"` 表达，避免一个字段同时承担两个状态机。

2. 返回教学信息。
   - Response 顶层新增稳定字段，例如 `teaching`。
   - `teaching.mode` 固定为 `teaching`。
   - `teaching.principle_explanation` 至少覆盖 LP/HiGHS，包含中文标题、简明原理、建模步骤和局限说明。
   - `teaching.credits_discount` 明确 `discount_multiplier=0.5` 和 `label_zh="50% Credits 折扣"`。
   - `teaching.notebook` 返回 Colab URL 和 repo path，URL 指向 committed notebook。

3. 教学折扣接入现有 billing finalize。
   - 有 `X-Billing-Charge-Id` 的教学 sync 成功/timeout finalize 调用必须传 `discount_multiplier=0.5`。
   - 无 billing header 时不得调用 reserve/finalize，但 response 仍返回教学折扣资格说明。
   - billing finalize 失败时，solver 继续返回结果，并在 `opt.error` retry context 中保存教学折扣 metadata。
   - 若请求同时满足 teaching 和 `options.backtest=true`，effective billing discount 仍只能是单个 0.5，不得叠加为 0.25；metadata 必须显式记录单一 effective discount kind，例如 `teaching` 优先，public response 仍只展示一个 50% Credits 折扣。

4. TypeScript API contract 同步。
   - `apps/web/src/lib/api.ts` 的 LP request/optimization response 类型要接受教学模式字段。
   - 不需要新增 UI 页面；本 story 是 API/SDK contract vertical slice。

5. Notebook artifact。
   - 新增一个小型 deterministic notebook，例如 `docs/notebooks/teaching-lp.ipynb`。
   - Notebook 内容应能解释 LP 教学模式和示例 payload，但不要求在 CI 中执行。
   - 增加 lightweight validator/test 确认 notebook path 存在、JSON 可解析、包含至少一个 code cell 和一个 markdown explanation cell，Colab URL 由 repo path deterministic 生成。

6. CI/path-filter 闭环。
   - solver-orchestrator path filter 已覆盖 solver tests；新增 docs/notebooks path 时必须确保 PR 至少触发 solver/web 或 CI 根级验证，不能让 notebook-only 变更绕过 tests。
   - 若只新增 docs path 不触发相关 CI，应通过同时修改 solver/web tests 或 CI path filter 闭合。

## Out Of Scope

- 不新增 capability-registry runtime、Provider teaching cohort、Classroom Plan、grading API、LMS/LTI、教师 master account 或学生名单管理。
- 不做在线 Notebook 生成、Colab API 调用、LLM 原理讲解生成、外部网络请求或用户自定义教学内容生成。
- 不新增数据库 migration、pricing table、促销码、可配置折扣比例或叠加折扣策略。
- 不修改 billing-service 的折扣数学；复用 Story 3.10 已有 `discount_multiplier` 合同。
- 不改 `/v1/predictions`、batch endpoint、rerun endpoint、Chat service、Critic service 或 AIGC filter。

## Acceptance Criteria

1. `POST /v1/optimizations?mode=teaching` 对 authenticated 小型 LP 请求返回 200 completed，并包含顶层 `teaching` 字段。
2. `teaching.mode == "teaching"`，且 `teaching.principle_explanation` 包含 LP/HiGHS 的中文原理讲解、建模步骤和局限说明。
3. `teaching.credits_discount.discount_multiplier == 0.5`，并显示 `50% Credits 折扣`。
4. `teaching.notebook.colab_url` 指向 repo 内 committed notebook，且 `teaching.notebook.repo_path` 对应实际存在文件。
5. `mode=sync`、`mode=async` 和 omitted mode 的现有 tests 继续通过；`mode=later` 仍返回 RFC 7807 invalid execution mode。
6. 有 billing header 的 teaching sync 成功路径调用 reserve + finalize，并向 finalize 传 `discount_multiplier=0.5`；`solve_seconds` 仍是真实求解耗时，不得通过折半 elapsed seconds 实现折扣。
7. 无 billing header 的 teaching 请求不调用 billing，但 response 仍包含教学折扣资格说明。
8. teaching billing finalize 失败时仍返回求解结果，并持久化 `billing_discount_kind="teaching"` 与 `billing_discount_multiplier=0.5` retry context。
9. `GET /v1/optimizations/{id}` 对 completed teaching optimization 返回同一 `teaching` metadata，不暴露 `_system` 或 billing charge id。
10. `mode=teaching` 对大型 LP auto-async 或未来 async-equivalent 路径不会把 response `mode` 改成 teaching；status response 必须保留 execution `mode="async"` 并同时返回 `teaching.mode="teaching"`。
11. 同时传 `mode=teaching` 与 `options.backtest=true` 时，billing finalize 仍只传一次 `discount_multiplier=0.5`，retry context 不得出现两个 discount multiplier 或 0.25 stacked effective value。
12. Idempotency replay 对同一 teaching request 返回同一 optimization 和同一 teaching metadata；同一 idempotency key 下 teaching 与 plain sync 不得互相 replay 成错误形状。
13. Web API 类型覆盖 query teaching mode request contract，并包含 `OptimizationResponse.teaching` 类型。
14. 新增 tests 覆盖 teaching response、billing discount、non-stacking with backtest、no-billing path、finalize failure retry context、GET replay、idempotency boundary、auto-async teaching metadata retention、legacy mode compatibility 和 notebook path existence。
15. Notebook test 必须解析 committed `.ipynb` JSON，不允许只检查字符串常量；Colab URL 必须从 repo path 派生，避免链接漂移。
16. CI/path filter 必须覆盖本 story 改动，使 solver-orchestrator/web/typecheck/lint 相关验证在 PR 中运行。
17. 本地验证至少运行：solver-orchestrator teaching tests、相关 sync/async/backtest/billing tests、web API client tests、ruff/mypy/diff-check。
18. 实施后代码审查覆盖边界问题、漂移问题、数据一致性、依赖一致性、CI 闭环、no fake Colab、billing non-stacking 和测试充分性；发现必须修复或记录。
19. PR 通过 GitHub CI、合并到 `main`、远程分支删除、本地 `main` 同步后，才能把 story 与 sprint status 标记为 `done` 并推送 status-sync commit。

## Tasks / Subtasks

- [x] T1: 解析教学模式并保持 execution mode 兼容（AC: 1, 5, 10, 11）
  - [x] 将 query `mode=teaching` 映射为 teaching profile + existing sync execution default。
  - [x] 保持 `mode=sync|async|None` 行为和 invalid mode error 兼容。
  - [x] 让 idempotency hash 区分 teaching 与 plain sync。
  - [x] 对 auto-async teaching path 保留 execution `mode="async"` 与 public `teaching` metadata。

- [x] T2: 返回 deterministic teaching metadata（AC: 1-4, 7, 9）
  - [x] 增加 helper 生成 LP/HiGHS 原理讲解、50% discount display 和 Notebook link。
  - [x] completed response、GET response、queued/status response 均从 `_system.teaching` 返回 public teaching metadata。
  - [x] 确保 response 不暴露 `_system`、billing charge id 或内部 retry context。

- [x] T3: 接入 teaching billing discount（AC: 6-8, 11）
  - [x] 扩展 discount helper，支持 teaching 50% 折扣。
  - [x] sync finalize 传 `discount_multiplier=0.5`。
  - [x] finalize failure retry context 保存 teaching discount metadata。
  - [x] 明确 teaching 与 backtest 同时存在时不叠加，只保留单一 effective discount。

- [x] T4: Notebook artifact 与 TS contract（AC: 4, 13, 15-16）
  - [x] 新增 committed teaching LP notebook。
  - [x] 增加 notebook JSON/path/Colab URL validator test。
  - [x] 更新 `apps/web/src/lib/api.ts` types。
  - [x] 增加 web API type/request tests。

- [ ] T5: Tests, validation, review and GitHub sync（AC: 14, 16-19）
  - [x] 增加 solver-orchestrator teaching tests。
  - [x] 确认 CI path filter 覆盖 story 改动。
  - [x] 运行本地验证并记录。
  - [x] 完成 post-implementation code review 并修复 findings。
  - [ ] Commit、push、创建 PR、等待 CI、merge、删除远端分支、同步 local main。
  - [ ] 合并同步后更新 story/sprint status 为 done 并推送 status-sync commit。

## Dev Notes

### Existing Files And Current State

- `apps/solver-orchestrator/src/solver_orchestrator/routes.py`
  - `_validate_execution_mode(mode)` 当前只接受 `sync|async`。
  - `_execution_mode_metadata()` 保存 requested/effective/auto_async metadata。
  - `_build_response_content()` 和 `_build_optimization_status_response_content()` 是 public response augmentation 的主要位置。
  - `_backtest_billing_discount_metadata()` 当前只处理 `options.backtest`。
  - `_hash_optimization_body()` 当前把 body + mode + async billing charge id 纳入幂等 hash。

- `apps/solver-orchestrator/src/solver_orchestrator/schemas.py`
  - `OptimizationOptions` 当前有 `reproducible`、`anonymous`、`backtest`。
  - 可以把 teaching 作为 query profile 处理，不一定要新增 body options，避免把 FR O8 的 `mode=teaching query` 改成另一个接口。

- `apps/solver-orchestrator/src/solver_orchestrator/billing_client.py`
  - `finalize()` 已有 optional `discount_multiplier`，保持非折扣调用 shape，避免破坏 monkeypatch tests。

- `apps/web/src/lib/api.ts`
  - `LPRequest.options` 当前缺少 `backtest` 等后续字段，Story 8.C.1 可补 `mode?: "teaching"` 或 explicit teaching option，需与实际 query contract 对齐。

### Implementation Guardrails

- `mode=teaching` 是教学 profile，不是第三种 execution state；internal execution mode 仍只能是 sync/async。
- Public `mode` 字段不得被 teaching 复用；避免破坏现有 status/async clients。
- Teaching discount 固定 0.5，不允许用户传任意折扣。
- Teaching 和 backtest 都是 50% 折扣，但不得叠加为 25%；本 story应选择单一 effective discount metadata。
- Public `teaching.credits_discount` 是资格/display metadata，不是 billing-service ledger proof；真实扣费仍以后端 finalize/reconciler context 为准。
- Notebook link 必须 deterministic，指向本 repo committed file；不要返回不存在的 Colab path。
- Colab URL shape should use `https://colab.research.google.com/github/proecheng/opticloud/blob/main/{repo_path}` so it is stable after merge to `main`; tests should assert the repo path segment exists locally.
- 原理讲解必须是 deterministic static content；不要调用 LLM。
- Billing retry metadata 只在 `opt.error` / `_system.billing` 内部保存，public response 只暴露教学折扣说明，不暴露 charge id。
- Story/sprint status flow 必须为 `ready-for-dev -> in-progress -> code-review -> done`；`done` 只能在 PR merge/sync 后通过单独 status-sync commit 推送。

## Definition Of Done

- Story has passed exactly 3 pre-implementation adversarial review rounds with revisions recorded after each round.
- `mode=teaching` returns principle explanation, 50% Credits discount metadata and a real Notebook Colab link.
- Teaching billing discount reuses the existing billing-service `discount_multiplier` contract without double discount.
- Legacy execution mode and backtest discount regressions remain green.
- Local gates and GitHub CI pass.
- Post-implementation code review completed and findings fixed or explicitly documented.
- Story and sprint status become `done` only after PR CI green, merge, remote branch deletion, local main sync and a separate status-sync commit.

## Story Review Log

### Round 1: Boundary Semantics Review

Findings fixed:

- Initial story did not explicitly protect the public `mode` field from becoming a mixed teaching/execution state. Added a hard rule that public `mode` remains execution-only and teaching is expressed under `teaching.mode`.
- Initial story covered sync teaching but did not require auto-async/status retention. Added an AC and task to keep `teaching` metadata on auto-async/status responses while preserving `mode="async"`.
- Initial tests list did not include auto-async teaching metadata retention. Added explicit coverage.

Status: PASS after fixes.

### Round 2: Billing And Data Consistency Review

Findings fixed:

- Initial story said teaching and backtest must not stack in guardrails but did not require an executable AC. Added explicit non-stacking acceptance criteria and tests: simultaneous teaching + backtest must still finalize with one `0.5` multiplier and no `0.25` effective value.
- Initial story did not define which discount kind wins when multiple discount-eligible flags exist. Added a single effective discount metadata requirement, with teaching taking precedence for `mode=teaching`.
- Initial story could be read as public discount display being proof of ledger charge. Clarified that public `teaching.credits_discount` is eligibility/display metadata; billing-service finalize/reconciler metadata remains source of truth.

Status: PASS after fixes.

### Round 3: Dependency And Closure Review

Findings fixed:

- Initial story required a Notebook link but did not require JSON-level validation of the committed notebook. Added a notebook validator/test requirement to parse `.ipynb`, check markdown/code cells, and ensure the Colab URL maps to a real repo path.
- Initial story did not explicitly close CI path-filter risk for docs/notebooks. Added CI/path-filter closure requirements so notebook-related changes cannot bypass relevant validation.
- Initial story had lifecycle closure in DoD but not in the dependency review. Reaffirmed that `done` is forbidden before PR CI, merge, remote branch deletion, local main sync and separate status-sync commit.

Status: PASS after fixes. Story is ready for development.

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Debug Log References

- Baseline branch: `codex/8-c-1-mode-teaching-explain`.
- Baseline commit: `11c106d49a61b667fcfe1386219754cf7623f70b`.
- Customization resolver script absent at `_bmad/scripts/resolve_customization.py`; fallback loaded base skill instructions and project config.
- Story creation analyzed Epic 8.C.1 source AC, PRD O8, architecture O8 service mapping, academic handbook mode vocabulary, Story 3.10 discount implementation, solver-orchestrator mode/idempotency/billing paths, existing tests, and web API type surface.
- 2026-06-04 - Completed pre-implementation adversarial review round 1 and revised story boundary semantics for teaching vs execution mode.
- 2026-06-04 - Completed pre-implementation adversarial review round 2 and revised billing/data consistency requirements for non-stacking teaching discounts.
- 2026-06-04 - Completed pre-implementation adversarial review round 3 and revised notebook/CI/dependency closure requirements; story is ready for implementation.
- 2026-06-04 - Moved story to in-progress after exactly three pre-implementation adversarial review rounds.
- 2026-06-04 - RED phase confirmed: new `test_teaching_mode.py` failed because `mode=teaching` was rejected as invalid execution mode and the notebook file did not exist.
- 2026-06-04 - Implemented teaching mode as a query profile over existing sync/async execution mode, persisted public teaching metadata under `_system.teaching`, and kept public `mode` execution-only.
- 2026-06-04 - Implemented teaching discount metadata with fixed 0.5 multiplier, teaching-over-backtest non-stacking behavior, sync/timeout finalize propagation, and finalize-failure retry context.
- 2026-06-04 - Added deterministic LP teaching notebook and web API type/client support for `postOptimization(..., { mode: "teaching" })`.
- 2026-06-04 - Added CI path-filter coverage for `docs/notebooks/**` under solver-orchestrator validation.
- 2026-06-04 - Local validation passed: teaching/sync-async/backtest/billing regression tests (46 passed), web API client test (1 passed), solver ruff/format, solver mypy, web typecheck, and `git diff --check`.
- 2026-06-04 - Post-implementation adversarial code review completed in three layers; fixed web client async-mode type overexposure and stale invalid execution mode catalog constraint.
- 2026-06-04 - Post-review validation passed: teaching/sync-async/backtest/billing regression tests (46 passed), web API client test (1 passed), web typecheck, solver ruff/format, solver mypy, error-message i18n gate, and `git diff --check`.
- 2026-06-04 - GitHub PR CI failed only on `lint`: `ruff` flagged notebook `print` usage and `ruff-format`/`detect-secrets` exposed generated notebook cell-id risk.
- 2026-06-04 - Fixed notebook lint by replacing `print` output with a deterministic final expression and short deterministic cell ids; local full pre-commit, teaching-mode tests and `git diff --check` passed.
- 2026-06-04 - PR #161 passed GitHub CI, merged to `main`, remote branch deleted, and local `main` synced.

### Completion Notes List

- Initial story created.
- Round 1 pre-implementation review completed and story revised.
- Round 2 pre-implementation review completed and story revised.
- Round 3 pre-implementation review completed and story revised.
- Story moved to in-progress for implementation.
- Implementation complete and story moved to code-review.
- `mode=teaching` now returns deterministic principle explanation, 50% Credits discount metadata and a real notebook Colab link.
- Teaching billing discount reuses existing `discount_multiplier` without stacking with backtest.
- Legacy sync/async, backtest and billing regressions remain green locally.
- Post-implementation code review completed; two findings fixed and verified.

### File List

- `_bmad-output/stories/8-c-1-mode-teaching-explain.md`
- `_bmad-output/stories/sprint-status.yaml`
- `.github/workflows/ci.yml`
- `apps/solver-orchestrator/src/solver_orchestrator/routes.py`
- `apps/solver-orchestrator/tests/test_teaching_mode.py`
- `apps/web/src/lib/api.ts`
- `apps/web/src/lib/api-optimization.test.ts`
- `docs/notebooks/teaching-lp.ipynb`

## Post-Implementation Code Review

### Blind Hunter - Boundary And Regression Review

Findings:

- P2 fixed: `apps/web/src/lib/api.ts` exposed `PostOptimizationOptions.mode` as `"sync" | "async" | "teaching"` while `postOptimization()` still returns the synchronous `OptimizationResponse` shape. That would encourage callers to use async mode through a client that cannot type queued responses. Fixed by limiting the web helper to `"sync" | "teaching"` for this story.
- No remaining issue found with the backend public `mode` field: execution mode remains sync/async-only, and teaching is expressed under `teaching.mode`.

### Edge Case Hunter - Data Consistency And Drift Review

Findings:

- P3 fixed: `solver_orchestrator.error_catalog` still described invalid execution mode as `sync, async` only, while the route now accepts `teaching`. Fixed the catalog constraint to include `teaching`; reran error-message single-source gate.
- No remaining issue found in billing non-stacking: teaching takes precedence over backtest and only passes one `0.5` multiplier.
- No remaining issue found in notebook closure: committed `.ipynb` is parsed by test, and Colab URL maps to the repo path.

### Acceptance Auditor - AC Closure Review

Findings:

- No remaining issue found against AC 1-15: teaching response, principle explanation, 50% discount metadata, real notebook, GET/idempotency/auto-async retention and tests are present.
- No remaining issue found against AC 16: `docs/notebooks/**` now triggers solver-orchestrator CI path.
- AC 17 local validation passed after review fixes.
- AC 18 code review is complete after fixes.
- AC 19 remains open by design until PR CI passes, branch is merged, remote branch deleted, local `main` synced, and a separate status-sync commit marks story/sprint `done`.

Outcome: PASS after fixes.

## Change Log

- 2026-06-04 - Story created for 8.C.1 teaching mode API vertical slice.
- 2026-06-04 - Round 1 pre-implementation review revised teaching/execution mode boundary and auto-async metadata requirements.
- 2026-06-04 - Round 2 pre-implementation review revised billing non-stacking and discount source-of-truth requirements.
- 2026-06-04 - Round 3 pre-implementation review revised notebook validation, CI path-filter and lifecycle closure requirements.
- 2026-06-04 - Story status moved to in-progress after pre-implementation review closure.
- 2026-06-04 - Implemented teaching mode API vertical slice and moved story to code-review after local validation.
- 2026-06-04 - Completed post-implementation code review; fixed web async-mode type overexposure and stale error catalog constraint.
- 2026-06-04 - Fixed GitHub lint failure in the teaching notebook and reran local lint/security gates.
- 2026-06-04 - Marked story done after PR #161 merge/sync closure.
