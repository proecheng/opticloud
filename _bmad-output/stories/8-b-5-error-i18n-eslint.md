---
story_key: 8-b-5-error-i18n-eslint
epic_num: 8
story_num: B.5
epic_name: AIGC Filter + Rate Limit + Error Codes RFC 7807
status: code-review
baseline_commit: 4b3210d72f9c45716b736cd3269539f08ae0a3fb
priority: High
type: FG1.3 i18n single-source lint gate
created_by: bmad-create-story
created_at: 2026-06-03
sources:
  - _bmad-output/planning/epics.md (Epic 8.B / Story 8.B.5)
  - _bmad-output/planning/prd.md (Error Codes RFC 7807 / FG1.3 i18n single-source ESLint)
  - _bmad-output/planning/architecture.md (RFC 7807 / i18n / TS tooling / CI)
  - _bmad-output/planning/ux-design-specification.md (P73 status text i18n single-source / ARIA i18n lint)
  - _bmad-output/stories/8-b-3-errors-next-action-url.md
  - _bmad-output/stories/8-b-4-rfc7807-error-panel.md
  - .github/workflows/ci.yml
  - .pre-commit-config.yaml
  - package.json
  - apps/web/package.json
  - packages/ui/package.json
  - packages/shared-ts/package.json
  - apps/web/src/lib/api.ts
  - packages/ui/src/components/RFC7807ErrorPanel/index.tsx
---

# Story 8.B.5 - i18n 单源 ESLint Enforcement

Status: code-review

## Story

**作为** 平台工程师、前端开发者和 API 错误合同维护者，  
**我希望** 仓库提供名为 `error-message-i18n-single-source` 的静态 lint gate，并建立 `packages/i18n/errors.zh-CN.yaml` 错误文案单源，  
**从而** 新增 RFC 7807 错误 `title` / `detail` 硬编码时 CI 直接失败，并把开发者指向错误 i18n 单源，而不是继续散落字符串。

## Context

PRD FG1.3 要求所有 RFC 7807 `title`、`detail`、`remediation_hint_key` 字符串来自 `packages/i18n/errors.<lang>.yaml`，并要求 ESLint 规则 `error-message-i18n-single-source` 在 CI 中拒绝 hard-coded strings。

当前仓库现实与 PRD 存在差距：

- 没有 `packages/i18n` 目录，也没有 `errors.zh-CN.yaml`。
- 没有 `.eslintrc.*` 或 `eslint.config.*`；`apps/web` 的 `next lint` 曾在历史 story 中因缺少配置触发交互式提示。
- 根 `package.json` 有 `lint: pnpm -r lint`，但 `packages/ui`、`packages/shared-ts` 没有 lint script。
- CI 的常驻 `lint` job 只安装 Python/uv/pre-commit，不执行 `pnpm install`；因此直接引入依赖 `eslint`/TypeScript AST 插件会让 CI lint gate 缺依赖。
- CI 已有 `ts-typecheck` job 覆盖 web/ui/shared-ts，但没有前端 lint job。
- Story 8.B.3 已闭合 `next_action_url` 和 `errors[]` shape；Story 8.B.4 已提供 `RFC7807ErrorPanel`，并明确把 i18n enforcement 留给本 story。

本 story 的正确方向是在不制造 ESLint 基建迁移风险的前提下完成可执行 enforcement：规则 ID 必须是 `error-message-i18n-single-source`，CI/pre-commit/root lint 必须会跑，输出必须指向 `packages/i18n/errors.zh-CN.yaml`。如果未来仓库引入 ESLint flat config，可把同一规则迁入 ESLint plugin；本 story 不阻塞在不存在的 ESLint 基建上。

## Scope

1. 新增 `packages/i18n/errors.zh-CN.yaml` 作为错误文案单源，并补充 `errors.en-US.yaml` 兜底文件，覆盖 8.B.3/8.B.4 已出现的 canonical remediation keys 和前端 fallback 错误。
2. 新增零依赖 lint gate，规则名固定为 `error-message-i18n-single-source`。
3. lint gate 扫描生产 TS/TSX 错误合同 surface，拒绝 RFC 7807 problem/detail object 中 hard-coded `title` / `detail` 文案。
4. lint gate 校验 `remediation_hint_key` 字符串必须存在于 `packages/i18n/errors.zh-CN.yaml`，并检查 zh/en 字典 key parity。
5. lint gate 输出必须包含违规文件、字段名、规则名和 `packages/i18n/errors.zh-CN.yaml` 指引。
6. 接入 root lint、pre-commit CI lint job，以及 CI path filter / focused validation job，使 CI 能在相关文件变化时失败。
7. 增加自动化测试，覆盖硬编码失败、合法 remediation key 通过、缺失 key 失败、zh/en key drift 失败、扫描范围不误伤测试/storybook/i18n 字典。
8. 运行本地验证、实施后代码审查、GitHub PR/CI/merge/branch cleanup/local main sync 后，才允许标记 `done`。

## Out Of Scope

- 不一次性迁移后端 Python 服务里所有历史 `HTTPException(detail="...")` 或 `rfc7807_error(title="...")`；全仓季度审计属于 Story 9.6。
- 不修改后端 `Accept-Language` runtime 查表、中间件、OpenAPI schema 或 RFC 7807 响应 builder；本 story 是静态 enforcement 和字典单源 foundation。
- 不实现 Python/Node/Go SDK 错误 preservation 或 `error.locate()`；这是 Story 8.B.6。
- 不重写 `RFC7807ErrorPanel`、ErrorBoundary、Console 页面恢复 UX 或业务页面文案。
- 不引入新 npm/pip 依赖，不要求仓库立即迁移到 ESLint flat config。
- 不扫描生成 OpenAPI JSON、测试 fixture、Storybook stories、i18n message JSON、历史 story 文档或 YAML 字典本身。

## Acceptance Criteria

1. `packages/i18n/errors.zh-CN.yaml` 存在，并至少覆盖 `errors.402.topup`、`errors.422.invalid_prediction_data`、`errors.422.invalid_job_template`、`errors.422.source_task_not_completed`、`errors.429.rate_limit_exceeded`、`errors.503.rate_limit_unavailable`、`errors.fallback.request_failed`、`errors.fallback.network_error`。
2. `packages/i18n/errors.en-US.yaml` 存在，且与 zh-CN 字典 key 完全一致。
3. 字典条目至少包含 `title`、`detail`、`remediation` 字段；空字符串、缺字段、重复 key 或 zh/en key drift 会被 lint gate 拒绝。
4. 存在可执行规则 gate，规则 ID / hook ID / 输出名为 `error-message-i18n-single-source`。
5. 当生产 TS/TSX 代码在 RFC 7807/problem-detail object 中写入 `title: "Invalid Prediction Data"` 或 `detail: "horizon must be between 1 and 90"` 这类 hard-coded string 时，gate 返回非 0。
6. gate 失败输出包含违规路径、字段名、规则名，并明确指向 `packages/i18n/errors.zh-CN.yaml`。
7. `remediation_hint_key: "errors.422.invalid_prediction_data"` 这类 key 只有在 zh-CN 字典存在时通过；缺失 key 返回非 0。
8. `remediation_hint_key` 必须形如 `errors.<status-or-scope>.<name>`；随意字符串、空字符串或非 `errors.` 前缀失败。
9. gate 不误伤测试文件、Storybook stories、generated OpenAPI JSON、`apps/web/src/i18n/messages/*.json`、story markdown 和 `packages/i18n/errors.*.yaml`。
10. root `package.json` 暴露 `lint:error-i18n`，且 root `lint` 会运行该 gate。
11. `.pre-commit-config.yaml` 的 local hook 包含 `error-message-i18n-single-source`，CI 常驻 `lint` job 会执行它。
12. `.github/workflows/ci.yml` path filter 覆盖 `packages/i18n/**`、该 lint gate 脚本、相关测试和 package/pre-commit 配置。
13. CI 有 focused validation job 或现有 lint job 覆盖该 gate；改动相关文件时 CI 能 fail closed。
14. 现有 `apps/web/src/lib/api.ts` 中 RFC 7807 fallback 文案不再以裸 `title` / `detail` hard-coded problem string 形式散落；若保留 fallback，必须引用/对齐 i18n 字典 key 或被显式纳入 gate 允许边界。
15. 自动化测试覆盖 AC 3、5、6、7、8、9、12。
16. 本 story 不新增 runtime dependency，不修改 pnpm lock 除非确有必要；若 lock 变化必须在 Dev Agent Record 说明原因。
17. 本地验证至少运行：focused lint gate tests、lint gate 正常扫描、root lint 或等价 pre-commit hook、`pnpm -r typecheck`、`git diff --check`。
18. 实施后代码审查覆盖边界问题、漂移问题、数据一致性、依赖一致性、CI 闭环和测试充分性；发现必须修复或记录。
19. PR 通过 GitHub CI、合并到 `main`、远程分支删除、本地 `main` 同步后，才能把 story 与 sprint status 标记为 `done` 并推送状态同步 commit。

## Tasks / Subtasks

- [x] T1: Add RED tests for the i18n single-source gate (AC: 3, 5-9, 12, 15)
  - [x] Test committed dictionaries validate and zh/en keys match.
  - [x] Test hard-coded RFC 7807 `title` / `detail` in production TS fails with rule name and dictionary path.
  - [x] Test valid `remediation_hint_key` passes only when key exists in zh-CN dictionary.
  - [x] Test missing/invalid remediation key fails.
  - [x] Test ignored files include tests, Storybook stories, i18n message JSON, OpenAPI JSON, and story markdown.
  - [x] Test CI path filter contains the new enforcement inputs.

- [x] T2: Create `packages/i18n` error dictionaries (AC: 1-3, 16)
  - [x] Add `errors.zh-CN.yaml` with canonical FG1.3 error keys and title/detail/remediation fields.
  - [x] Add `errors.en-US.yaml` with exact key parity.
  - [x] Add a short README documenting key naming and where developers add new error text.

- [x] T3: Implement `error-message-i18n-single-source` gate (AC: 4-9, 14, 16)
  - [x] Implement zero-dependency parser/validator for the flat YAML dictionaries.
  - [x] Implement TS/TSX scanner for RFC 7807/problem-detail object literals.
  - [x] Reject hard-coded `title` / `detail` strings in production problem objects.
  - [x] Validate `remediation_hint_key` shape and dictionary membership.
  - [x] Emit deterministic, actionable failure output with rule ID and dictionary path.

- [x] T4: Wire lint and CI closure (AC: 10-13, 17)
  - [x] Add root `lint:error-i18n` script and make root `lint` run it.
  - [x] Add `.pre-commit-config.yaml` local hook.
  - [x] Update CI path filters and add/extend validation job for the gate.
  - [x] Ensure packages without lint scripts do not make root lint brittle.

- [x] T5: Run local validation gates (AC: 15, 17)
  - [x] `uv run pytest tests/test_error_i18n_single_source.py -v`
  - [x] `python scripts/error_message_i18n_single_source.py`
  - [x] `uv run pre-commit run error-message-i18n-single-source --all-files`
  - [x] `pnpm -r typecheck`
  - [x] `git diff --check`

- [ ] T6: Review and GitHub sync (AC: 18-19)
  - [x] Complete post-implementation code review and fix findings.
  - [ ] Commit, push, create PR, wait CI, merge, delete remote branch, sync local `main`.
  - [ ] Only after merge/sync, mark story and sprint status `done` and push status-sync commit.

## Dev Notes

### Existing Files And Current State

- `.github/workflows/ci.yml`
  - Current state: path filter has `web`, `ui`, `shared_ts`, `ci_or_root`; TypeScript job runs `pnpm -r typecheck`; lint job only runs pre-commit.
  - This story changes: add path filter coverage for `packages/i18n/**`, lint gate script/tests, and package/pre-commit config; add focused job or ensure pre-commit hook closes CI.
  - Preserve: existing service path filters and continue-on-error behavior for unrelated typecheck/openapi jobs.

- `.pre-commit-config.yaml`
  - Current state: Python/pre-commit hooks plus local license check; no TS/i18n error-string hook.
  - This story changes: add local hook `error-message-i18n-single-source`.
  - Preserve: current hook exclusions and no dependency on `pnpm install`.

- `package.json`
  - Current state: `lint` is `pnpm -r lint`; only `apps/web` has `lint`, and `next lint` is not currently reliable without ESLint config.
  - This story changes: expose `lint:error-i18n` and make root `lint` run the gate before/with recursive package lint in a non-brittle way.
  - Preserve: `typecheck` and `test` scripts.

- `apps/web/src/lib/api.ts`
  - Current state: client normalizes RFC 7807 errors and has fallback hard-coded title/detail strings (`Request failed`, `Network Error`, Chinese response parse fallback).
  - This story changes: align fallback problem strings with the new dictionary boundary or ensure they are not scanned as naked RFC 7807 hardcoded problem text.
  - Preserve: `Accept-Language` header behavior, `OptiCloudClientError` shape, `errors[]` and `next_action_url` preservation.

- `packages/ui/src/components/RFC7807ErrorPanel/index.tsx`
  - Current state: presentation-only component renders payload title/detail/errors/remediation/CTA.
  - This story changes: no direct component rewrite expected. The gate may scan this file but should not fail on component labels that are not constructing RFC 7807 problem objects.
  - Preserve: Story 8.B.4 behavior and tests.

### Enforcement Design Guardrails

- Prefer a standard-library Python gate because CI lint currently has Python/uv/pre-commit but not `pnpm install`; do not introduce an ESLint dependency merely to satisfy naming if it makes CI non-closed.
- The rule ID, script output, npm script, and pre-commit hook must use `error-message-i18n-single-source` so the product requirement remains traceable.
- Scan production TS/TSX under `apps/web/src`, `packages/ui/src`, and `packages/shared-ts/src`.
- Exclude `*.test.ts`, `*.test.tsx`, `*.stories.tsx`, `*.a11y.test.tsx`, generated OpenAPI JSON, i18n message JSON, story docs, and `packages/i18n/**`.
- Detect RFC 7807/problem-detail object literals conservatively: object with status/errors/next_action_url/request_id/trace_id, or nested error detail object with `field_path`/`constraint`/`remediation_hint_key`.
- Reject direct literal values for `title` / `detail` only in those problem-detail contexts; do not ban every UI label named `title`.
- Allow `remediation_hint_key` literal only as a dictionary key; this preserves the field-path contract while still preventing drift.
- Keep output deterministic so tests can assert exact snippets.

### Previous Story Intelligence

- Story 8.B.3 made `next_action_url` canonical and removed legacy `next_action`; this gate must not encourage or permit `next_action` drift.
- Story 8.B.4 preserved old `RFC7807Panel` alias and renders `remediation_hint_key`; 8.B.5 must not break that component surface.
- Story 8.B.4 final local gates included UI test/typecheck/storybook; for this story, the primary risk is CI/lint closure rather than UI rendering.
- Story 8.B.6 is the next SDK contract story; do not pull SDK changes into 8.B.5.

### Suggested Commands

```powershell
uv run pytest tests/test_error_i18n_single_source.py -v
python scripts/error_message_i18n_single_source.py
uv run pre-commit run error-message-i18n-single-source --all-files
pnpm -r typecheck
git diff --check
```

## Definition Of Done

- Story has passed 3 pre-implementation adversarial review rounds with revisions recorded.
- `packages/i18n/errors.zh-CN.yaml` and `errors.en-US.yaml` exist with key parity and canonical FG1.3 keys.
- `error-message-i18n-single-source` gate rejects hard-coded RFC 7807 title/detail strings and missing/invalid remediation keys.
- Root lint/pre-commit/CI path filters close the loop so related PRs fail in CI.
- Focused tests, lint gate scan, pre-commit hook, TypeScript typecheck, and diff-check pass locally.
- Post-implementation code review is complete and findings are fixed or explicitly documented.
- PR merge, remote branch deletion, and local `main` sync complete before story/sprint status becomes `done`.

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Debug Log References

- Baseline branch: `codex/8-b-5-error-i18n-eslint`.
- Customization resolver script absent at `_bmad/scripts/resolve_customization.py`; fallback loaded base `bmad-create-story/customize.toml`, found no project/user overrides, and no `project-context.md`.
- Story creation analyzed Epic 8.B / Story 8.B.5, PRD FG1.3, Architecture RFC7807/i18n/tooling sections, UX P73/ARIA i18n lint notes, Story 8.B.3, Story 8.B.4, CI/pre-commit/package setup, current web API client, and current RFC7807 UI component.
- Latest web research was not needed because the implementation is constrained by local pinned tooling and CI shape.
- 2026-06-03 - RED confirmed: `uv run pytest tests/test_error_i18n_single_source.py -v` failed because the lint gate script, dictionaries, and CI path filter did not exist.
- 2026-06-03 - Implemented zero-dependency `error-message-i18n-single-source` gate, zh/en error dictionaries, README, root `lint:error-i18n`, pre-commit hook, CI path filter and focused validation job.
- 2026-06-03 - Gate found existing production drift in chat CSV remediation keys; migrated `chat.csv.*` to `errors.chat_csv.*` and added dictionary entries.
- 2026-06-03 - Root `pnpm -r typecheck` exposed missing `packages/shared-ts/tsconfig.json` and an e2e capture-variable narrowing issue; both were fixed to close the local/CI typecheck gate.
- 2026-06-03 - Post-implementation review found scanner blind spots for single-quoted strings and outer nested problem objects, plus fallback RFC7807 strings in web pages; fixed scanner/tests and aligned fallbacks to dictionary keys.
- 2026-06-03 - Local gates passed: focused pytest, script scan, pre-commit hook, root lint, focused web recovery test, root typecheck, and diff-check.

### Completion Notes List

- Added `packages/i18n/errors.zh-CN.yaml` and `errors.en-US.yaml` with key parity, required FG1.3 keys, fallback keys, and chat CSV recovery keys.
- Added `scripts/error_message_i18n_single_source.py`, a zero-dependency lint gate with rule ID `error-message-i18n-single-source`.
- Added tests covering dictionary validation, hard-coded RFC7807 title/detail rejection, i18n-key title/detail allowance, remediation key membership, ignored-file boundaries, and CI path filter coverage.
- Wired root `pnpm lint`, `lint:error-i18n`, pre-commit hook, CI path filter, and `error-i18n-validation` job.
- Migrated production `chat.csv.*` remediation keys to `errors.chat_csv.*`.
- Aligned web fallback RFC7807 payloads to dictionary keys and added remediation details for client-side/network fallback paths.
- Added `packages/shared-ts/tsconfig.json` so root `pnpm -r typecheck` can run cleanly.
- Fixed e2e TypeScript capture typing in Lina CSV recovery spec without changing runtime behavior.
- Story status moved to `code-review`; final `done` remains gated on GitHub PR/CI/merge, remote branch deletion, local `main` sync, and status-sync commit.

### File List

- `.github/workflows/ci.yml`
- `.pre-commit-config.yaml`
- `_bmad-output/stories/8-b-5-error-i18n-eslint.md`
- `_bmad-output/stories/sprint-status.yaml`
- `apps/web/src/app/console/predictions/page.tsx`
- `apps/web/src/app/welcome/page.tsx`
- `apps/web/src/lib/api.ts`
- `apps/web/src/lib/chat-file-context-recovery.ts`
- `apps/web/src/lib/chat-file-context-recovery.test.ts`
- `e2e/tests/lina-csv-error-recovery.spec.ts`
- `package.json`
- `packages/i18n/README.md`
- `packages/i18n/errors.en-US.yaml`
- `packages/i18n/errors.zh-CN.yaml`
- `packages/shared-ts/tsconfig.json`
- `scripts/error_message_i18n_single_source.py`
- `tests/test_error_i18n_single_source.py`

## Change Log

- 2026-06-03 - Story created for i18n error dictionary, `error-message-i18n-single-source` lint gate, CI/pre-commit/root lint wiring, tests, review, and GitHub closure.
- 2026-06-03 - Implementation started; baseline commit recorded and status moved to `in-progress`.
- 2026-06-03 - Implemented i18n dictionaries, lint gate, tests, pre-commit/root lint/CI wiring, drift fixes, and post-review patches; story moved to `code-review` pending GitHub sync.

## Post-Implementation Code Review

### Findings

- [x] [Review][Patch] The initial scanner could miss single-quoted string literals and RFC7807 object literals where an inner `{...}` appeared before `title`/`detail`. Fixed by parsing single/double quoted literals separately and walking outward through enclosing braces; added regression coverage.
- [x] [Review][Patch] Two web fallback RFC7807 payloads still used hard-coded `title` strings after scanner hardening. Fixed by using dictionary keys in `console/predictions` and `welcome` fallback payloads and adding `errors.fallback.prediction_request_failed`.
- [x] [Review][Patch] `apps/web/src/lib/api.ts` fallback path was only implicitly covered. Fixed by centralizing fallback key constants and adding `errors[]` remediation for unparseable network/error responses.

### Outcome

Changes requested internally; all findings fixed and focused/full local gates rerun. No remaining high/medium findings found in boundary handling, drift control, dictionary data consistency, dependency consistency, CI closure, or regression coverage.

## Pre-Implementation Adversarial Reviews

### Round 1 - Boundary And Reinvention Review

Findings:

1. The PRD says ESLint, but the repository has no ESLint config and CI lint does not install Node dependencies. Introducing a real ESLint plugin first would expand scope into lint infrastructure migration.
2. Scanning every Python service and every historical `HTTPException(detail="...")` would turn this into a large backend i18n migration, overlapping Story 9.6 and likely breaking current services.
3. Many UI components use `title` props for normal labels; a naive string ban would create false positives and block unrelated UI work.
4. `remediation_hint_key` values are string keys by design; banning all string literals there would make valid RFC 7807 detail construction impossible.

Revision after Round 1:

- Scoped this story to a zero-dependency repo lint gate with the mandated rule ID, production TS/TSX RFC7807/problem-detail contexts, and dictionary membership validation. Backend full migration and future true ESLint plugin migration are explicitly out of scope.

### Round 2 - Drift, Data Consistency, And Dependency Review

Findings:

1. A zh-CN-only dictionary would satisfy the literal path requirement but drift from PRD/architecture `zh-CN / en-US` error-code fallback expectations.
2. A dictionary without schema validation could silently accept missing `detail` or empty `remediation`, making the gate look green while runtime content is incomplete.
3. Root `lint: pnpm -r lint` is brittle because workspace packages lack lint scripts and `apps/web` `next lint` is not configured.
4. If the gate only runs in a focused CI job and not pre-commit/root lint, local and CI behavior can diverge.

Revision after Round 2:

- Added en-US key parity, dictionary field validation, root `lint:error-i18n`, pre-commit hook, and CI path filter/focused job requirements. Root lint must run the i18n gate without relying on nonexistent package lint scripts.

### Round 3 - Closed-Loop, Regression, And Test Review

Findings:

1. A scanner that only searches raw text could miss object literal contexts or report normal labels; tests need both positive and negative fixtures.
2. The failure output must be actionable; otherwise developers will know CI failed but not where to add the message.
3. Existing `apps/web/src/lib/api.ts` fallback strings are a real drift vector and must either be aligned or explicitly handled.
4. Marking story done before GitHub PR/CI/merge/delete/sync would violate the user workflow and repeat prior status-sync risks.

Revision after Round 3:

- Added fixture tests for hardcoded title/detail, valid/missing remediation keys, ignored files, dictionary drift, CI path filters, and failure-output guidance. Added AC for `api.ts` fallback alignment and final GitHub closure before `done`.
