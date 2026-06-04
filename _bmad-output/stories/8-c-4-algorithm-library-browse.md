---
story_key: 8-c-4-algorithm-library-browse
epic_num: 8
story_num: C.4
epic_name: Teaching + Provider Routing + Legal + Algorithm Library
status: in-progress
baseline_commit: 50c5e6e8642449e29afde00733d6664f1f297f9b
priority: High
type: FR O11 benchmark library browse
created_by: bmad-create-story
created_at: 2026-06-04
sources:
  - _bmad-output/planning/epics.md (Epic 8.C / Story 8.C.4)
  - _bmad-output/planning/prd.md (FR O11 / J4 academic user path)
  - _bmad-output/planning/architecture.md (O11 service mapping / capability-registry evolution)
  - _bmad-output/stories/3-10-backtest-discount.md
  - _bmad-output/stories/8-c-1-mode-teaching-explain.md
  - _bmad-output/stories/8-c-2-provider-routing-history.md
  - apps/solver-orchestrator/src/solver_orchestrator/catalog.py
  - apps/solver-orchestrator/src/solver_orchestrator/routes.py
  - apps/solver-orchestrator/src/solver_orchestrator/schemas.py
  - apps/solver-orchestrator/tests/test_algorithm_details.py
  - apps/solver-orchestrator/tests/test_backtest_discount.py
  - apps/solver-orchestrator/tests/test_teaching_mode.py
  - apps/web/src/lib/api.ts
  - apps/web/src/app/algorithms/page.tsx
  - apps/web/src/app/algorithms/[k_algo]/page.tsx
---

# Story 8.C.4 - 经典算例库浏览

Status: in-progress

## Story

**作为** 学术用户、教学用户或算法评估用户，
**我希望** 可以在公开算法目录旁浏览 IEEE/CVRPLIB/OR-Lib/M5/UCI/NAB 经典算例库，并一键生成可提交的 OptiCloud import payload，
**从而** 能用经典 benchmark 模板复现实验、教学演示或评估算法，并在实际优化任务计费时获得单一 50% Credits 折扣。

## Context

Epic 8.C.4 的原始 AC 是：Given IEEE/CVRPLIB/OR-Lib/M5/UCI/NAB / When 浏览 / Then 50% Credits 折扣 + 一键 import。PRD O11 把经典算例库列为 v2 学术用户能力，J4 吕教授+小赵路径覆盖 O11。

当前仓库状态：

- 公开算法目录已由 solver-orchestrator `GET /v1/algorithms` 和 web `/algorithms` 承载；没有 benchmark library API 或页面。
- 架构把 O11 标到 capability-registry，但当前公开 catalog 实际仍在 solver-orchestrator 静态 catalog 上；capability-registry 现有 `benchmark_suite` 字段用于 Provider shadow/evaluation，不是用户浏览的经典算例库。
- Story 3.10 已实现 `options.backtest=true` 的 50% billing discount；Story 8.C.1 已实现 `mode=teaching` 的 50% discount，并明确折扣不能叠加。
- `/v1/predictions` 当前不支持 billing header；优化 billing discount 只在 `/v1/optimizations` 路径闭合。
- 现有 web `/algorithms` 是公开免鉴权页面，没有 Console auth 或 API key storage。

因此本 story 的最小闭环是：在 solver-orchestrator 增加公开静态 benchmark library API，web 增加公开浏览页，import 端点返回 deterministic request payload 和 discount metadata；同时为可执行优化 import payload 增加 `options.benchmark_library=true`，让实际 `/v1/optimizations` billing finalize 使用单一 50% benchmark-library discount。预测类 benchmark 只返回预测 payload 模板和折扣资格说明，不在本 story 改造 `/v1/predictions` 计费。

## Scope

1. Backend benchmark library catalog。
   - 新增静态 benchmark library module，例如 `apps/solver-orchestrator/src/solver_orchestrator/benchmark_library.py`。
   - 至少包含 6 条 published entries，分别覆盖 `ieee`、`cvrplib`、`or-lib`、`m5`、`uci`、`nab`。
   - 每条 entry 必须有 stable `benchmark_id`、`suite`、`domain`、`task_type`、`title_zh`、`title_en`、`source_name`、`source_url`、`license_note_zh`、`import_kind`、`discount`、`sample_payload`、`dataset_ref`。
   - `discount` 必须包含 `billing_supported`：optimization entries 为 `true`，prediction entries 为 `false`，避免把 prediction import 的资格说明误读成已经落地的扣费能力。
   - `sample_payload` 只能是小型 synthetic/minimal payload，不下载、不缓存、不内嵌真实 benchmark 数据集。
2. Public browse API。
   - 新增 `GET /v1/benchmark-library`，公开免鉴权，支持可组合 filter：`suite`、`domain`、`task_type`。
   - 新增 `GET /v1/benchmark-library/{benchmark_id}`，公开免鉴权，未知 id 返回 404。
   - Response 包含 import metadata 和 discount metadata，但不得返回 raw external dataset content。
3. One-click import API。
   - 新增 `POST /v1/benchmark-library/{benchmark_id}/import`，公开免鉴权且无副作用。
   - 返回 `benchmark_id`、`import_kind`、`target_endpoint`、`request_payload`、`discount`、`disclaimer_zh`。
   - 对 `import_kind="optimization_request"` 的 entry，`request_payload.options.benchmark_library=true` 且 `request_payload.options.benchmark_id=<benchmark_id>`。
   - 对 `import_kind="prediction_request"` 的 entry，返回 `/v1/predictions` payload 模板和折扣资格说明，但明确本 story 不改变 prediction billing。
   - Import response 必须 deep-copy payload；不得让调用方或 route 修改静态 catalog 内的 `sample_payload`。
4. Benchmark-library billing discount。
   - `OptimizationOptions` 新增 `benchmark_library: bool = false` 和 `benchmark_id: str | None = None`。
   - `benchmark_library=true` 必须带有效 `benchmark_id`，且该 id 必须来自 published benchmark library、`import_kind="optimization_request"`、`target_endpoint="/v1/optimizations"`，并且 entry `task_type` 与请求 `task_type` 一致。
   - 缺失、未知、prediction-only 或 task_type 不匹配的 benchmark id 必须在任何 billing reserve、idempotency row 或 optimization row 副作用前返回 RFC 7807 400。
   - `benchmark_id` 在 `benchmark_library=false` 时也必须返回 RFC 7807 400，避免持久化一个看似来自 benchmark library 但不享受折扣的请求。
   - `/v1/optimizations` 的 billing discount helper 识别 `benchmark_library=true`，effective discount kind 为 `benchmark_library`，multiplier 固定 `0.5`。
   - benchmark-library、teaching、backtest 三种 50% 折扣不得叠加。优先级必须稳定：`teaching` > `benchmark_library` > `backtest`。
   - Public response 不需要新增 billing proof 字段；实际账单仍以后端 finalize/reconciler metadata 为准。
5. Web API client。
   - 在 `apps/web/src/lib/api.ts` 增加 Benchmark Library TypeScript types。
   - 增加 `listBenchmarkLibrary(options?)`、`getBenchmarkLibraryItem(benchmarkId)`、`importBenchmarkLibraryItem(benchmarkId)`。
   - API client 使用 `SOLVER_SERVICE_URL`，公开接口不发送 Authorization、billing header、idempotency key 或 internal service auth。
6. Web browse page。
   - 新增 `/algorithms/benchmarks` 页面，并从 `/algorithms` 增加可发现入口。
   - `/algorithms/benchmarks` 必须是静态 route，不得被 `/algorithms/[k_algo]` 动态详情页吞掉；测试需覆盖该 page module。
   - 页面显示 6 个 suite 的 benchmark cards、filter controls、50% Credits 折扣 badge、一键 import。
   - 一键 import 在页面内显示可复制 JSON payload 和目标 endpoint；不得自动提交优化/预测任务、不得存储到 localStorage/sessionStorage。
   - 设计保持公开算法目录的朴素信息页风格，不实现 Story 8.C.5 的 reusable CapabilityCard。

## Out Of Scope

- 不下载 IEEE/CVRPLIB/OR-Lib/M5/UCI/NAB 真实数据，不访问外部网络，不新增 dataset mirror、S3/OSS bucket、cache、worker、cron、DB table 或 migration。
- 不声称真实 benchmark 已在 OptiCloud 上跑完，不展示 leaderboard、score、baseline 结果、SOTA 名次、论文复现实验结果或 Provider 评测结果。
- 不新增或修改 capability-registry runtime endpoint，不改 Provider shadow/evaluation `benchmark_suite` 语义，不实现 8.C.5 CapabilityCard，不改 `packages/ui` 组件库。
- 不改 `/v1/predictions` billing；M5/UCI/NAB 的 prediction imports 只生成模板和折扣资格说明。
- 不新增 npm/Python runtime dependency、图表库、clipboard dependency、下载 SDK 或外部 API client。
- 不修改现有 `/v1/algorithms` response schema，避免破坏 FR C1-C8 algorithm catalog clients。

## Acceptance Criteria

1. `GET /v1/benchmark-library` exists in solver-orchestrator and is public unauthenticated.
2. `GET /v1/benchmark-library` returns at least six published entries covering suites exactly: `ieee`, `cvrplib`, `or-lib`, `m5`, `uci`, `nab`.
3. Every entry has stable `benchmark_id`, `suite`, `domain`, `task_type`, `title_zh`, `title_en`, `source_name`, `source_url`, `license_note_zh`, `import_kind`, `target_endpoint`, `discount`, `dataset_ref`, and `sample_payload`.
4. `discount.kind == "benchmark_library"`, `discount.label_zh == "50% Credits 折扣"`, and `discount.discount_multiplier == 0.5` for every entry.
5. `discount.billing_supported == true` for optimization entries and `false` for prediction entries.
6. `dataset_ref` is pointer-only and uses a safe scheme such as `benchmark://...`; response does not embed external raw dataset rows/files.
7. `GET /v1/benchmark-library?suite=cvrplib` filters to CVRPLIB entries only.
8. `GET /v1/benchmark-library?domain=forecast&task_type=forecast` composes filters with AND semantics.
9. Unknown filter values return `[]` with 200, mirroring permissive `/v1/algorithms` filter behavior.
10. `GET /v1/benchmark-library/{benchmark_id}` returns the matching entry and unknown ids return 404.
11. `POST /v1/benchmark-library/{benchmark_id}/import` exists, is public unauthenticated, and has no DB writes or external network calls.
12. Import response for optimization entries includes `target_endpoint="/v1/optimizations"` and `request_payload.options.benchmark_library=true`.
13. Import response for optimization entries includes `request_payload.options.benchmark_id` equal to the imported `benchmark_id`.
14. Import response for prediction entries includes `target_endpoint="/v1/predictions"` and `discount.billing_supported=false`.
15. Import response for prediction entries explicitly says prediction billing discount is not implemented in this story.
16. Import response includes a Chinese disclaimer that the payload is a minimal template, not a full dataset mirror.
17. Import response is deterministic for repeated calls to the same `benchmark_id`.
18. Import response payload is deep-copied; mutating one returned payload in code/tests cannot mutate the static catalog or later import responses.
19. `OptimizationOptions` accepts `benchmark_library` default `false` and `benchmark_id` default `null`.
20. Optimization requests with `options.benchmark_library=true` require a non-empty `options.benchmark_id`.
21. Optimization requests with `options.benchmark_id` but `benchmark_library=false` return RFC 7807 400 before side effects.
22. The `benchmark_id` must exist in the published benchmark library and must be an `optimization_request` entry targeting `/v1/optimizations`.
23. The optimization request `task_type` must match the benchmark library entry `task_type`.
24. Missing, unknown, prediction-only, unpublished, or task-type-mismatched benchmark ids return RFC 7807 400 before billing reserve, idempotency row creation, or optimization row creation.
25. Existing optimization requests without `benchmark_library=true`, `mode=teaching`, or `backtest=true` keep the old no-discount finalize call shape.
26. Authenticated optimization with billing header and valid `options.benchmark_library=true` calls billing finalize with `discount_multiplier=0.5` and real `solve_seconds`, not half elapsed seconds.
27. Async optimization with billing header and valid `options.benchmark_library=true` reserves only and persists `_system.billing.discount_kind="benchmark_library"` with `discount_multiplier=0.5`.
28. Billing finalize failure with benchmark-library discount preserves retry context `billing_discount_kind="benchmark_library"` and `billing_discount_multiplier=0.5`.
29. `mode=teaching` plus valid `benchmark_library=true` uses a single 0.5 teaching discount; no 0.25 stacked discount appears in finalize args, `_system.billing`, or retry context.
30. Valid `benchmark_library=true` plus `backtest=true` uses a single 0.5 benchmark-library discount; no 0.25 stacked discount appears.
31. Idempotency hash distinguishes `benchmark_library=true` from `false`; same key with changed benchmark option returns 409.
32. Backend tests cover list/detail/import/filter/no-raw-data, import deep-copy behavior, prediction billing-supported=false metadata, benchmark-id validation before side effects, discount finalize, async persistence, finalize failure retry context, non-stacking with teaching/backtest, no-discount compatibility, and idempotency boundary.
33. Web API types mirror backend snake_case fields for benchmark library entries/import response.
34. `listBenchmarkLibrary()` calls `GET /v1/benchmark-library` against `SOLVER_SERVICE_URL` and sends no auth/billing/internal/idempotency headers.
35. `importBenchmarkLibraryItem()` calls `POST /v1/benchmark-library/{encodeURIComponent(id)}/import` and sends no body or auth/billing/internal/idempotency headers.
36. `/algorithms/benchmarks` loads and renders benchmark cards for IEEE/CVRPLIB/OR-Lib/M5/UCI/NAB.
37. `/algorithms/benchmarks` provides suite/domain/task filters that call the API with query params and render empty/error states.
38. Clicking one-click import renders target endpoint and formatted JSON payload on-page.
39. The page does not auto-submit to `/v1/optimizations` or `/v1/predictions`.
40. The page does not write benchmark payloads or user credentials to localStorage/sessionStorage.
41. The page shows 50% Credits discount metadata as eligibility/display text and does not present it as invoice proof.
42. Prediction entries visibly distinguish import template availability from actual billing support.
43. `/algorithms` exposes a visible link to `/algorithms/benchmarks`.
44. The new `/algorithms/benchmarks` static route is covered by a page test and is not implemented by overloading `/algorithms/[k_algo]`.
45. Implementation does not modify `apps/capability-registry/**`, Provider shadow/evaluation `benchmark_suite` semantics, `packages/ui/**`, or add a reusable CapabilityCard abstraction.
46. Implementation introduces no new Python/npm dependency, no migration, no worker, no queue, no external API call.
47. Local gates pass: targeted solver tests, targeted web tests, web typecheck, solver ruff/format, solver mypy if touched, and `git diff --check`.
48. Post-implementation code review is completed and findings are fixed or explicitly documented.
49. GitHub CI passes, PR is merged, remote branch is deleted, local `main` is synced, and only then this story and sprint status are marked `done` through a separate status-sync commit.

## Tasks / Subtasks

- [x] T1: Backend benchmark catalog and browse/import API (AC: 1-18, 32, 45-46)
  - [x] Add static benchmark library module with 6 suite entries.
  - [x] Add Pydantic schemas for library item, discount metadata and import response.
  - [x] Add `GET /v1/benchmark-library`, `GET /v1/benchmark-library/{benchmark_id}`, and `POST /v1/benchmark-library/{benchmark_id}/import`.
  - [x] Add tests for list/detail/filter/import/no raw dataset embedding/determinism.

- [x] T2: Benchmark-library billing discount on optimization path (AC: 19-32, 45-46)
  - [x] Extend `OptimizationOptions` with `benchmark_library` and `benchmark_id`.
  - [x] Extend billing discount helper with priority `teaching > benchmark_library > backtest`.
  - [x] Cover sync finalize, async reserve metadata, finalize failure retry context, non-stacking and idempotency boundary.

- [x] T3: Web API client (AC: 33-35, 45-46)
  - [x] Add benchmark library types and API helpers in `apps/web/src/lib/api.ts`.
  - [x] Add Vitest coverage for URL, query params, path encoding and forbidden headers/body.

- [x] T4: Public benchmark browse page (AC: 36-46)
  - [x] Add `/algorithms/benchmarks/page.tsx`.
  - [x] Add suite/domain/task filters, card list, loading/error/empty states and import payload view.
  - [x] Add discoverability link from `/algorithms`.
  - [x] Add page tests for rendering, filter calls, import payload display, no auto-submit and no storage writes.

- [ ] T5: Review, gates and GitHub sync (AC: 47-49)
  - [x] Run local quality gates and fix failures.
  - [x] Run post-implementation code review and fix/document findings.
  - [ ] Commit, push, create PR, wait for CI, merge, delete remote branch, sync local `main`.
  - [ ] Mark story/sprint status `done` only after merge/sync via separate status-sync commit.

## Dev Notes

### Existing Backend Facts

- `routes.py` already hosts public `GET /v1/algorithms` and `GET /v1/algorithms/{k_algo}` near the top of the router. Add benchmark-library browse endpoints near that catalog section.
- `catalog.py` is static and public-safe. A new `benchmark_library.py` should mirror this static pattern and return copies rather than mutable global references.
- `AlgorithmSchema` should not be widened for O11; keep `/v1/algorithms` contract stable.
- `OptimizationOptions` currently has `backtest`, `reproducible`, `anonymous`, `top_k_alternatives`, and `max_solve_seconds`. Add benchmark fields there rather than accepting unknown option keys that Pydantic would silently ignore.
- `_optimization_billing_discount_metadata()` is the central discount helper. Extend it rather than scattering discount decisions in route branches.
- `billing_client.finalize()` accepts only `discount_multiplier`, not a public kind; discount kind is tracked in solver `_system.billing` and retry context.
- Existing tests in `test_backtest_discount.py` and `test_teaching_mode.py` show expected discount, async and non-stacking patterns.

### Existing Web Facts

- `apps/web/src/lib/api.ts` already has `SOLVER_SERVICE_URL`, `listAlgorithms()`, `getAlgorithm()`, `postOptimization()`, and `getOptimization()`.
- Current public `/algorithms` page uses `listAlgorithms`, tier chips, `StatusCard`, `EmptyState`, and `LoadingShimmer`.
- There are no existing tests under `apps/web/src/app/algorithms`; add focused Vitest page tests for the new page instead of adding broad E2E unless needed.
- Keep the page public. Do not require JWT or API key for browsing/import payload generation.
- Do not add a shared `CapabilityCard` or change `packages/ui`; Story 8.C.5 owns that abstraction.
- `app/algorithms/benchmarks/page.tsx` should be its own static App Router page. Do not route benchmark library through `[k_algo]` detail logic.

### Data Semantics

- `dataset_ref` identifies a benchmark source pointer, not a storage location owned by OptiCloud.
- `sample_payload` is a deterministic minimal template suitable for import/testing. It is not the full benchmark dataset.
- `discount` on browse/import responses is eligibility/display metadata. The source of truth for charged optimization discount is billing finalize metadata.
- `discount.billing_supported=false` means the benchmark can be browsed/imported as a template, but this story does not implement actual billing discount for that target endpoint.
- `benchmark_id` should be stable, lowercase and path-safe, e.g. `ieee-14-opf`, `cvrplib-a-n32-k5`, `or-lib-afiro`, `m5-sku-forecast`, `uci-energy-forecast`, `nab-real-known-cause`.

### Review Constraints

- This story must pass exactly 3 pre-implementation adversarial review rounds before implementation.
- Do not move implementation status to `in-progress` until after these rounds are recorded.
- After each pre-implementation review round, revise this story before starting the next round.
- Do not mark story/sprint `done` before PR CI, merge, remote branch deletion, local main sync, and separate status-sync commit.

## Definition Of Done

- Story has passed exactly 3 pre-implementation adversarial review rounds with revisions recorded after each round.
- Users can browse IEEE/CVRPLIB/OR-Lib/M5/UCI/NAB benchmark library entries from a public page.
- One-click import returns deterministic payloads and does not fetch or mirror raw external datasets.
- Optimization imports with `options.benchmark_library=true` receive a real single 50% billing discount when submitted through `/v1/optimizations`.
- Benchmark-library discount does not stack with teaching or backtest.
- Local gates and GitHub CI pass.
- Post-implementation code review completed and findings fixed or explicitly documented.
- Story and sprint status become `done` only after PR merge/sync/status-sync closure.

## Story Review Log

### Round 1: Boundary, Ownership And Discount Eligibility Review

Findings fixed:

- Initial story allowed `options.benchmark_library=true` without proving it came from a published optimization benchmark entry. Revised the story so discount eligibility requires a valid published benchmark id, `optimization_request` import kind, `/v1/optimizations` target endpoint and matching task_type.
- Initial story did not say invalid benchmark ids must fail before billing/idempotency/optimization side effects. Added a pre-side-effect RFC 7807 400 boundary.
- Initial story did not separate capability-registry Provider `benchmark_suite` from user-facing classic benchmark library. Kept this story in solver-orchestrator public catalog surface and out of Provider shadow/evaluation semantics.

Status: PASS after fixes.

### Round 2: Data Consistency, Drift And Billing Semantics Review

Findings fixed:

- Initial story let `benchmark_id` exist when `benchmark_library=false`, creating persisted requests that look benchmark-related but receive no benchmark discount. Revised validation to reject `benchmark_id` without the flag before side effects.
- Initial discount metadata did not distinguish optimization billing support from prediction template imports. Added `discount.billing_supported`, required `false` for prediction entries and required UI wording that prediction billing discount is not implemented in this story.
- Initial import response did not require deep-copy semantics. Added catalog immutability/deep-copy requirements and tests so import payload mutation cannot drift static library data.

Status: PASS after fixes.

### Round 3: Dependency, UX Boundary And Closure Review

Findings fixed:

- Initial story named `/algorithms/benchmarks` but did not explicitly protect it from being treated as a dynamic algorithm detail route. Added a static-route requirement and page-test coverage.
- Initial story only said 8.C.5 CapabilityCard was out of scope, but did not prevent premature `packages/ui` abstraction work. Added a hard constraint not to modify `packages/ui` or create reusable CapabilityCard in this story.
- Initial architecture notes mentioned capability-registry ownership for O11, but current closure belongs to solver-orchestrator/web public catalog. Added an explicit no-change boundary for `apps/capability-registry/**` and Provider `benchmark_suite` semantics.

Status: PASS after fixes. Story is ready for development.

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Debug Log References

- Baseline branch: `codex/8-c-4-algorithm-library-browse`.
- Baseline commit: `50c5e6e8642449e29afde00733d6664f1f297f9b`.
- Customization resolver script absent at `_bmad/scripts/resolve_customization.py`; fallback loaded base skill instructions and project config.
- Story creation analyzed Epic 8.C.4 source AC, PRD O11/J4, architecture O11/capability-registry evolution, existing solver algorithm catalog, existing web `/algorithms`, Story 3.10 backtest discount, Story 8.C.1 teaching discount, and Story 8.C.2 safe public metadata patterns.
- 2026-06-04 - Completed pre-implementation adversarial review round 1 and revised benchmark-library discount validation to require a valid published optimization benchmark id before any billing/idempotency/DB side effects.
- 2026-06-04 - Completed pre-implementation adversarial review round 2 and revised benchmark_id flag consistency, prediction billing support metadata, and import deep-copy requirements.
- 2026-06-04 - Completed pre-implementation adversarial review round 3 and revised static route, packages/ui/CapabilityCard, and capability-registry dependency boundaries.
- 2026-06-04 - Implemented solver-orchestrator benchmark-library catalog, public list/detail/import API, optimization benchmark discount validation, and single 50% discount priority.
- 2026-06-04 - Implemented web benchmark-library API helpers, `/algorithms/benchmarks` static public page, and `/algorithms` discoverability link.
- 2026-06-04 - Local gates passed: solver targeted pytest, web targeted Vitest, web typecheck, solver ruff check/format, solver mypy for touched source files, and `git diff --check`.
- 2026-06-04 - Post-implementation code review found missing explicit coverage for missing/unknown/task-type-mismatched benchmark ids; added tests and verified they pass.

### Completion Notes List

- Initial story created.
- Round 1 pre-implementation review completed and story revised.
- Round 2 pre-implementation review completed and story revised.
- Round 3 pre-implementation review completed and story revised.
- Story is ready for implementation.
- Story moved to in-progress for implementation.
- Backend benchmark-library API, import payload generation and optimization billing discount path implemented.
- Web benchmark-library API client and public `/algorithms/benchmarks` page implemented.
- Post-implementation code review completed; the only patch finding was missing explicit invalid benchmark-id boundary coverage, fixed in tests.
- Story remains in-progress until GitHub CI, PR merge, remote branch deletion, local main sync, and separate status-sync commit are complete.

### File List

- `_bmad-output/stories/8-c-4-algorithm-library-browse.md`
- `_bmad-output/stories/sprint-status.yaml`
- `apps/solver-orchestrator/src/solver_orchestrator/benchmark_library.py`
- `apps/solver-orchestrator/src/solver_orchestrator/error_catalog.py`
- `apps/solver-orchestrator/src/solver_orchestrator/routes.py`
- `apps/solver-orchestrator/src/solver_orchestrator/schemas.py`
- `apps/solver-orchestrator/tests/test_benchmark_library.py`
- `apps/web/src/lib/api.ts`
- `apps/web/src/lib/api-benchmark-library.test.ts`
- `apps/web/src/app/algorithms/page.tsx`
- `apps/web/src/app/algorithms/benchmarks/page.tsx`
- `apps/web/src/app/algorithms/benchmarks/page.test.tsx`

## Change Log

- 2026-06-04 - Story created for 8.C.4 classic benchmark library browse.
- 2026-06-04 - Round 1 pre-implementation review revised benchmark id validation and side-effect boundaries.
- 2026-06-04 - Round 2 pre-implementation review revised data consistency, prediction billing metadata and import immutability requirements.
- 2026-06-04 - Round 3 pre-implementation review revised static route, UI abstraction and capability-registry dependency closure.
- 2026-06-04 - Story status moved to in-progress after exactly three pre-implementation review rounds.
- 2026-06-04 - Implemented backend benchmark library catalog/API/import response, benchmark-library billing discount validation, and targeted solver tests.
- 2026-06-04 - Implemented web benchmark library API helpers, static public browse/import page, algorithms-page link, and targeted Vitest coverage.
- 2026-06-04 - Completed post-implementation code review, added missing invalid benchmark-id boundary tests, and passed local gates; GitHub sync remains pending.
