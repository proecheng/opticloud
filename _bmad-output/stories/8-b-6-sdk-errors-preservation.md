---
story_key: 8-b-6-sdk-errors-preservation
epic_num: 8
story_num: B.6
epic_name: AIGC Filter + Rate Limit + Error Codes RFC 7807
status: code-review
baseline_commit: befdb701a758fb4688021a5de130705a744f8040
priority: High
type: FG1.3 SDK RFC7807 errors preservation
created_by: bmad-create-story
created_at: 2026-06-03
sources:
  - _bmad-output/planning/epics.md (Epic 8.B / Story 8.B.6)
  - _bmad-output/planning/prd.md (Error Codes RFC 7807 / SDK contract)
  - _bmad-output/planning/architecture.md (RFC 7807 / SDK error handling)
  - _bmad-output/planning/ux-design-specification.md (Chen architect SDK surface)
  - _bmad-output/stories/8-b-3-errors-next-action-url.md
  - _bmad-output/stories/8-b-4-rfc7807-error-panel.md
  - _bmad-output/stories/8-b-5-error-i18n-eslint.md
  - packages/python-sdk/src/opticloud/errors.py
  - packages/python-sdk/src/opticloud/client.py
  - packages/python-sdk/tests/test_error_locate.py
  - packages/python-sdk/pyproject.toml
  - packages/shared-py/opticloud_shared/schemas/errors.py
  - packages/shared-py/opticloud_shared/errors/rfc7807.py
  - packages/shared-ts/package.json
  - packages/shared-ts/tsconfig.json
  - pnpm-workspace.yaml
  - package.json
  - .github/workflows/ci.yml
---

# Story 8.B.6 - SDK Contract 保留 errors[]

Status: code-review

## Story

**作为** Python/Node SDK 用户和平台集成方，
**我希望** SDK 解析 RFC 7807 错误响应时 100% 保留 `errors[]` detail object 原结构，并通过 `error.errors` 暴露给客户端，
**从而** 客户端可以稳定 inspect `field_path`、`value`、`constraint`、`remediation_hint_key`，并继续使用 `locate()` 精确定位错误输入。

## Context

Epic 8.B.6 的原始 AC 是：Given Python/Node SDK / When parse error response / Then 100% 保留 `errors[]` 原结构 + 暴露 `error.errors` 字段给客户端。

当前仓库状态：

- `packages/python-sdk` 已存在 alpha stub，`OptiCloudHTTPError` 已有 `errors`、`raw`、`next_action_url`、`locate()`、`locate_all()`、`find_constraint()`、`remediation_keys()`。
- Python SDK tests 已覆盖基本 `locate()`、`from_response()` 和 `raw == body`，但没有证明 `errors[]` 中额外字段、嵌套值、多个 detail object、非 RFC 7807 fallback 路径和原始 detail dict 不被重写。
- `packages/node-sdk` 不存在；`pnpm-workspace.yaml` 当前只包含 `apps/web`、`packages/shared-ts`、`packages/ui`、`e2e`。
- CI 已有 `python_sdk` path filter 和 `python-sdk-test` job；TypeScript CI 只覆盖 `web/ui/shared-ts`，没有 Node SDK path filter 或 Node SDK test job。
- Story 8.B.3 已统一 `next_action_url`，Story 8.B.4 已展示 preserved RFC7807 shape，Story 8.B.5 已把 error i18n 字典与 hard-coded string gate 闭合。

本 story 的正确方向是加固 Python SDK preservation，并新增最小 Node SDK error contract 包。不要实现完整 Node API client、OpenAPI generator、Go SDK 或 runtime i18n 查表。

## Scope

1. 加固 `packages/python-sdk` 的 RFC7807 error parser，使 `errors[]` 原始 detail object 不被 schema 化、删字段、重命名、排序、字符串化或丢弃。
2. 新增 `packages/node-sdk` workspace package，导出 `OptiCloudError` / `OptiCloudHTTPError` 和 `parseOptiCloudErrorResponse()`，提供 `error.errors`、`raw`、`next_action_url`、`request_id`、`trace_id`、`locate()`、`locateAll()`、`findConstraint()`、`remediationKeys()`。
3. Python 与 Node 使用同一 canonical RFC7807 fixture：`tests/fixtures/sdk-rfc7807-preservation.json`，断言 `errors[]` 结构、顺序、嵌套 `value`、额外字段和 metadata 都被保留。
4. CI 增加 Node SDK path filter/test job，并确保 `pnpm -r typecheck` 覆盖 Node SDK。
5. 本地验证、实施后代码审查、GitHub PR/CI/merge/branch cleanup/local main sync 后，才允许标记 `done`。

## Out Of Scope

- 不实现完整 Node SDK API client、HTTP request wrapper、auth headers、retry/idempotency helper、OpenAPI generated operations 或 package publish pipeline。
- 不实现 Go SDK；PRD/Architecture 提到 Go，但本 story AC 只点名 Python/Node，Go 仍属于后续 SDK expansion。
- 不修改后端 RFC7807 builders、OpenAPI schema、`packages/i18n` 字典或 `error-message-i18n-single-source` gate。
- 不改变 `apps/web/src/lib/api.ts` 的 browser client；它不是 SDK package，本 story 只可参考其 preservation shape。
- 不新增外部 npm/pip runtime dependency；Node SDK 应使用 TypeScript + Node built-in `node:test`。

## Acceptance Criteria

1. Python SDK `OptiCloudHTTPError.from_response(status, body)` 对合法 RFC7807 body 保留 `body["errors"]` 的原始数组结构，包括 detail object 顺序、所有标准字段、额外字段、嵌套 object/list `value` 和 `null` value。
2. Python SDK `error.errors` 暴露的是 preserved `errors[]`；`error.raw` 保留完整原始 body；`next_action_url`、`request_id`、`trace_id` 继续透传；`error.errors` / `error.raw` 必须是解析时快照，不能和输入 `body` 共用可变 list/dict 引用。
3. Python SDK `locate(field_path)` 和 `locate_all(field_path)` 从 preserved `errors[]` 中读取 `value`，不要求 detail object 被转换为 Pydantic model。
4. Python SDK `_request()` 处理非 JSON / 非 RFC7807 fallback error response 不抛二次异常，仍创建 `OptiCloudHTTPError`，`errors` 默认为空列表，`raw` 保留 fallback body；如果响应 body 的 `errors` 不是数组，也必须降级为空列表而不是把 string/object 当成 detail array。
5. 新增 `packages/node-sdk` workspace package，包名 `@opticloud/sdk`，Node >=18，TypeScript 源码，无外部 runtime dependency。
6. Node SDK 导出 `OptiCloudHTTPError`，实例字段至少包含 `status`、`type`、`title`、`detail`、`instance`、`errors`、`next_action_url`、`request_id`、`trace_id`、`raw`。
7. Node SDK `parseOptiCloudErrorResponse(status, body)` 对合法 RFC7807 body 100% 保留 `errors[]` 原结构，行为与 Python fixture 断言一致；`error.errors` / `error.raw` 必须是解析时快照，不能和输入 body 共用可变 object/array 引用。
8. Node SDK `locate(fieldPath)`、`locateAll(fieldPath)`、`findConstraint(pattern)`、`remediationKeys()` 与 Python API 语义一致；Node 采用 camelCase helper 名称，字段名保留 wire format `next_action_url`。
9. `tests/fixtures/sdk-rfc7807-preservation.json` 包含至少两个 detail object，其中一个 `value` 为嵌套 object/list，另一个含额外未知字段；Python/Node 两端测试都从该文件读取并断言额外字段未丢失。
10. `pnpm-workspace.yaml` 包含 `packages/node-sdk`；root `pnpm -r typecheck` 覆盖 Node SDK，且 Node SDK 自己的 `test` script 会先 build 再运行 tests。
11. CI path filter 包含 `node_sdk`；新增 `node-sdk-test` validation job 会在 `packages/node-sdk/**` 或 `tests/fixtures/sdk-rfc7807-preservation.json` 变化时运行，并且不得使用 `continue-on-error`。
12. `packages/python-sdk` 或 `tests/fixtures/sdk-rfc7807-preservation.json` 变化仍触发 `python-sdk-test`；共享 parity fixture 或 CI 配置变化也能触发相关 SDK gates。
13. README 文档说明 Python 和 Node 如何 inspect `error.errors` 与使用 locate helper，不承诺 Go 或 full generated SDK 已完成。
14. 本 story 不新增 runtime dependency；Node SDK 可复用根 `typescript` devDependency 或声明同版本 devDependency，不能新增测试/clone/HTTP library；如 `pnpm-lock.yaml` 因新增 workspace importer 变化，必须在 Dev Agent Record 说明。
15. 本地验证至少运行：Python SDK tests、Node SDK tests、root `pnpm -r typecheck`、full pre-commit 或相关 hooks、`git diff --check`。
16. 实施后代码审查覆盖边界问题、漂移问题、数据一致性、依赖一致性、CI 闭环和测试充分性；发现必须修复或记录。
17. PR 通过 GitHub CI、合并到 `main`、远程分支删除、本地 `main` 同步后，才能把 story 与 sprint status 标记为 `done` 并推送状态同步 commit。

## Tasks / Subtasks

- [x] T1: Add canonical SDK RFC7807 preservation fixtures and RED tests (AC: 1-4, 7-9, 12, 15)
  - [x] Add `tests/fixtures/sdk-rfc7807-preservation.json` as the single Python/Node parity fixture.
  - [x] Add/extend Python tests proving `errors[]` preserves order, nested `value`, null `value`, extra unknown fields, `raw`, `next_action_url`, request/trace IDs, and parsed snapshot isolation from later input-body mutation.
  - [x] Add Node SDK tests around the same canonical fixture before implementation.
  - [x] Cover malformed/non-RFC7807 fallback body behavior through `OptiCloudClient._request()` using a mocked HTTP response path.
  - [x] Cover non-array `errors` payloads in both Python and Node, expecting empty `error.errors`.

- [x] T2: Harden Python SDK parser without changing public API (AC: 1-4, 14)
  - [x] Keep `error.errors` as list of dict-like raw detail objects.
  - [x] Avoid schema normalization or key rewriting.
  - [x] Deep-copy JSON-compatible body/errors at parse time to avoid mutable alias drift.
  - [x] Preserve current helper semantics and exception message format.

- [x] T3: Add minimal Node SDK error contract package (AC: 5-9, 13-14)
  - [x] Create `packages/node-sdk/package.json`, `tsconfig.json`, source, tests, and README.
  - [x] Implement `OptiCloudError`, `OptiCloudHTTPError`, and `parseOptiCloudErrorResponse()`.
  - [x] Implement locate/parity helpers with wire-format field preservation.
  - [x] Snapshot JSON-compatible body/errors at parse time using internal code, not a third-party clone package.
  - [x] Ensure `pnpm --filter @opticloud/sdk test` builds TypeScript to `dist/` and executes tests via Node built-in test runner; no test-only runtime package.

- [x] T4: Wire workspace and CI closure (AC: 10-12, 15)
  - [x] Add `packages/node-sdk` to `pnpm-workspace.yaml`.
  - [x] Add CI `node_sdk` path filter output, include `tests/fixtures/sdk-rfc7807-preservation.json`, and add a hard-gated `node-sdk-test` validation job with no `continue-on-error`.
  - [x] Add `tests/fixtures/sdk-rfc7807-preservation.json` to the existing `python_sdk` filter so parity fixture changes rerun Python SDK tests.
  - [x] Ensure root `pnpm -r typecheck` includes Node SDK.
  - [x] Update `pnpm-lock.yaml` only as needed for the new workspace importer and TypeScript devDependency metadata.
  - [x] Run local validation commands and record results.

- [ ] T5: Review and GitHub sync (AC: 16-17)
  - [x] Complete post-implementation code review and fix findings.
  - [ ] Commit, push, create PR, wait CI, merge, delete remote branch, sync local `main`.
  - [ ] Only after merge/sync, mark story and sprint status `done` and push status-sync commit.

## Dev Notes

### Existing Files And Current State

- `packages/python-sdk/src/opticloud/errors.py`
  - Current state: `OptiCloudHTTPError.from_response()` assigns `errors=body.get("errors", [])`; helpers iterate dicts.
  - This story changes: add defensive handling and tests without replacing raw detail dicts with schema models.
  - Preserve: public class names, attributes, helper methods, exception message format, and `raw`.

- `packages/python-sdk/src/opticloud/client.py`
  - Current state: `_request()` parses JSON for HTTP errors; fallback body contains `title`, `detail`, `status`.
  - This story changes: only if tests reveal a preservation/fallback gap.
  - Preserve: minimal alpha client stub; do not add new API operations.

- `packages/python-sdk/tests/test_error_locate.py`
  - Current state: covers simple locate helpers and a basic RFC7807 body.
  - This story changes: extend with preservation/parity fixtures.

- `packages/shared-py/opticloud_shared/schemas/errors.py`
  - Current state: documents canonical RFC7807 `Problem`, `ErrorResponse`, and `ErrorDetail`.
  - This story changes: no code change expected; use as source of field names.

- `packages/shared-ts`
  - Current state: placeholder shared TS package with `tsconfig.json`; root `pnpm -r typecheck` can now run.
  - This story changes: no direct change expected unless reusable types are strictly needed.

- `.github/workflows/ci.yml`
  - Current state: `python_sdk` filter/job exists; no `node_sdk` filter/job.
  - This story changes: add `node_sdk` output/filter and hard-gated validation job; include `tests/fixtures/sdk-rfc7807-preservation.json` in both Python and Node SDK filters; include Node SDK in typecheck trigger or run typecheck inside Node SDK job.
  - Preserve: the existing broad `ts-typecheck` job currently has `continue-on-error`; Node SDK correctness must be enforced by the new dedicated job, not only by the broad optional typecheck job.

### Implementation Guardrails

- Treat `errors[]` as wire data. Do not coerce it into a model that drops unknown fields.
- Use `tests/fixtures/sdk-rfc7807-preservation.json` as the canonical parity fixture. Do not duplicate subtly different Python and Node fixtures.
- Preserve values, not object identity. SDK error instances should be stable snapshots even if the caller mutates the source response body after parsing.
- If `errors` is absent or not an array/list, expose `error.errors == []`; do not accept a single object/string as a detail collection.
- Preserve snake_case wire keys (`next_action_url`, `remediation_hint_key`) in SDK error objects. Helpers may use Python snake_case / Node camelCase method names.
- Do not make Node package depend on `apps/web` or browser-only code. SDK must be a standalone package.
- Do not add runtime dependencies. TypeScript and Node built-in `node:test` are sufficient.
- If adding `pnpm-lock.yaml` importer entries, record that this is workspace metadata, not a new third-party dependency.
- Avoid duplicating RFC7807 builders. SDK parses error responses; services build them.
- Do not rely on the existing `ts-typecheck` job as the only TypeScript gate because it is currently `continue-on-error`. `node-sdk-test` must hard fail on build/test failures.

### Previous Story Intelligence

- Story 8.B.3 made `next_action_url` canonical and removed legacy `next_action`; SDK must not revive `next_action`.
- Story 8.B.4 renders the preserved shape and relies on `errors[]` / `next_action_url` remaining intact.
- Story 8.B.5 created i18n dictionaries and a static gate; SDK must preserve `remediation_hint_key` strings but must not validate dictionary membership at runtime.
- Story 8.B.5 added `packages/shared-ts/tsconfig.json`, so root `pnpm -r typecheck` should be kept green when adding a new TS workspace.

### Suggested Commands

```powershell
$env:PYTHONPATH='packages/python-sdk/src'; uv run pytest packages/python-sdk/tests/ -v
pnpm --filter @opticloud/sdk test
pnpm -r typecheck
uv run pre-commit run --all-files --show-diff-on-failure
git diff --check
```

## Definition Of Done

- Story has passed 3 pre-implementation adversarial review rounds with revisions recorded.
- Python SDK tests prove full `errors[]` preservation and helper compatibility.
- Node SDK minimal error contract package exists, preserves `errors[]`, exposes `error.errors`, and passes tests.
- Workspace/CI path filters close the Node SDK and Python SDK validation loop.
- Local gates listed above pass.
- Post-implementation code review is complete and findings are fixed or explicitly documented.
- PR merge, remote branch deletion, and local `main` sync complete before story/sprint status becomes `done`.

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Debug Log References

- Baseline branch: `codex/8-b-6-sdk-errors-preservation`.
- Baseline commit: `befdb701a758fb4688021a5de130705a744f8040`.
- Customization resolver script absent at `_bmad/scripts/resolve_customization.py`; fallback loaded base `bmad-create-story/customize.toml`, found no project/user overrides, and no `project-context.md`.
- Story creation analyzed Epic 8.B / Story 8.B.6, PRD Error Codes RFC7807 SDK contract, Architecture RFC7807/SDK notes, UX Chen architect SDK surface, Story 8.B.3/8.B.4/8.B.5, existing Python SDK, shared RFC7807 schemas, pnpm workspace, and CI path filters.
- Latest web research was not needed because implementation is constrained by local pinned tooling and current workspace/CI shape.
- 2026-06-03 - Added shared SDK preservation fixture plus Python and Node tests for raw `errors[]` preservation, nested/null values, unknown fields, non-array `errors`, fallback error response handling, and parse-time snapshot isolation.
- 2026-06-03 - Hardened Python SDK `OptiCloudHTTPError` to deep-copy `errors` and `raw`, preserve wire-format detail dicts, and degrade non-array `errors` to `[]`.
- 2026-06-03 - Added minimal `@opticloud/sdk` TypeScript package with no runtime dependencies, Node built-in tests, build-first test script, and README contract notes.
- 2026-06-03 - Wired `packages/node-sdk` into pnpm workspace and CI path filters; added hard-gated `node-sdk-test`; added shared fixture to Python SDK CI trigger.
- 2026-06-03 - Focused local gates passed before full validation loop: Python SDK tests with `PYTHONPATH=packages/python-sdk/src`, Node SDK tests, and root `pnpm -r typecheck`.
- 2026-06-03 - Full local validation passed: Python SDK tests, Node SDK tests, root `pnpm -r typecheck`, full pre-commit, `git diff --check`, and `pnpm install --lockfile-only --frozen-lockfile`.
- 2026-06-03 - Full local `pnpm install --frozen-lockfile` confirmed the lockfile is up to date, then failed on Windows filesystem EPERM while renaming an existing `@swc/core` node_modules directory; PR CI's clean Linux runner remains the final full frozen-install gate.
- 2026-06-03 - Post-implementation review found Python `find_constraint()` could throw on malformed preserved non-string `constraint`; fixed by ignoring non-string constraints and added regression coverage.
- 2026-06-03 - PR CI blocker found outside SDK scope: `image-build` failed while `sigstore/cosign-installer@v3` attempted to download pinned `cosign v2.4.1`; updated the installer action to `v4.1.2` and removed the stale explicit cosign release pin.

### Completion Notes List

- Initial story context created; pending three pre-implementation adversarial review rounds before implementation.
- Round 1 pre-implementation review applied: tightened story boundaries around canonical shared fixture location, Python fallback testing through `_request()`, Node build/test shape, and CI fixture triggers.
- Round 2 pre-implementation review applied: added parse-time snapshot isolation, non-array `errors` boundary handling, and dependency/lockfile guardrails.
- Round 3 pre-implementation review applied: tightened CI closure so Node SDK has a hard-gated validation job and shared fixture changes rerun both Python and Node SDK tests.
- Implemented Python SDK preservation hardening without changing public helper names or exception message format.
- Added a minimal standalone Node SDK error contract package; intentionally did not add a generated API client, HTTP wrapper, OpenAPI codegen, Go SDK, or runtime i18n lookup.
- Node SDK uses TypeScript plus Node built-in `node:test`; no external runtime dependency was added.
- `pnpm-lock.yaml` changed for the new workspace importer and TypeScript devDependency metadata only.
- Post-implementation review completed across boundary handling, drift/data consistency, dependency consistency, CI closure, and test sufficiency; the only actionable finding was fixed.
- Local gates passed after review fix: Python SDK tests (12 passed), Node SDK tests (3 passed), root `pnpm -r typecheck`, full pre-commit, `git diff --check`, and lockfile-only frozen install.

### File List

- `.github/workflows/ci.yml`
- `.github/workflows/image-build.yml`
- `_bmad-output/stories/8-b-6-sdk-errors-preservation.md`
- `_bmad-output/stories/sprint-status.yaml`
- `packages/node-sdk/README.md`
- `packages/node-sdk/package.json`
- `packages/node-sdk/src/index.ts`
- `packages/node-sdk/test/errors.test.mjs`
- `packages/node-sdk/tsconfig.json`
- `packages/python-sdk/README.md`
- `packages/python-sdk/src/opticloud/errors.py`
- `packages/python-sdk/tests/test_error_locate.py`
- `pnpm-lock.yaml`
- `pnpm-workspace.yaml`
- `tests/fixtures/sdk-rfc7807-preservation.json`

## Change Log

- 2026-06-03 - Story created for Python/Node SDK RFC7807 `errors[]` preservation, parity tests, Node SDK package, CI closure, review, and GitHub sync.
- 2026-06-03 - Implementation started; baseline commit recorded and status moved to `in-progress`.
- 2026-06-03 - Implemented SDK preservation tests, Python parser hardening, minimal Node SDK package, workspace wiring, and CI validation closure; full local validation and post-implementation review still pending.
- 2026-06-03 - Completed full local validation and post-implementation review; fixed Python malformed `constraint` helper boundary; story moved to `code-review` pending GitHub sync.

## Post-Implementation Code Review

### Findings

- [x] [Review][Patch] Python `find_constraint()` could raise a secondary exception when preserved raw detail objects contain a non-string `constraint`, while the Node helper already ignores non-string constraints. Fixed by filtering to string constraints before regex matching and adding regression coverage.

### Outcome

Changes requested internally; the finding was fixed and focused/full gates rerun. No remaining high/medium findings found across boundary behavior, drift/data consistency, dependency consistency, CI closed-loop behavior, or test sufficiency. Final `done` remains gated on GitHub PR CI, merge, remote branch deletion, local `main` sync, and the separate status-sync commit.

## Pre-Implementation Adversarial Reviews

### Round 1 - Boundary And Reinvention Review

Findings:

1. Initial scope said "same canonical fixture" but did not name its path; Python and Node tests could drift into different local fixtures while still claiming parity.
2. Python fallback behavior cannot be fully validated through `OptiCloudHTTPError.from_response()` alone because non-JSON fallback is created in `OptiCloudClient._request()`.
3. Node SDK package creation could accidentally expand into a generated/full HTTP client unless the story fixes it as a minimal error-contract package only.
4. CI filter wording did not explicitly trigger both SDK gates when the shared fixture changes.

Revision after Round 1:

- Added `tests/fixtures/sdk-rfc7807-preservation.json` as the required shared fixture, moved fallback coverage to `_request()` with a mocked response path, fixed Node test/build expectations to TypeScript `dist/` + Node built-in test, and required CI filters to include the shared fixture.

### Round 2 - Drift, Data Consistency, And Dependency Review

Findings:

1. Assigning `error.errors = body["errors"]` preserves value shape but shares mutable references; later caller mutation of `body` can silently change the parsed SDK error.
2. The story did not define behavior for malformed `errors` values such as a single object or string; SDKs could drift by exposing inconsistent types.
3. Node SDK implementation might add clone/test/helper dependencies despite the package only needing TypeScript and Node built-ins.
4. `pnpm-lock.yaml` may change when adding a workspace importer; the story needed to distinguish allowed workspace metadata from forbidden new third-party runtime dependencies.

Revision after Round 2:

- Required parse-time JSON-compatible snapshots for `raw` and `errors`, required malformed/non-array `errors` to become `[]`, and tightened dependency rules to TypeScript/Node built-ins only with any lockfile workspace metadata documented.

### Round 3 - Closed-Loop, Regression, And Test Review

Findings:

1. The existing broad `ts-typecheck` CI job is marked `continue-on-error`; relying on it alone would not create a fail-closed Node SDK gate.
2. The shared parity fixture must trigger Python SDK tests as well as Node SDK tests, otherwise fixture drift can make one side stale.
3. A Node SDK `test` script that runs only source-level tests without build/typecheck could miss export/package problems.
4. Lockfile changes from adding a workspace importer must be verified locally before PR because CI uses `pnpm install --frozen-lockfile`.

Revision after Round 3:

- Required a dedicated hard-gated `node-sdk-test` job, added shared fixture coverage to the Python SDK filter, required Node SDK `test` to build before running tests, and made lockfile workspace metadata verification part of T4.
