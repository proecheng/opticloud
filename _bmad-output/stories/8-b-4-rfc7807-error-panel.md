---
story_key: 8-b-4-rfc7807-error-panel
epic_num: 8
story_num: B.4
epic_name: AIGC Filter + Rate Limit + Error Codes RFC 7807
status: done
baseline_commit: db49ba8e3215da4146b7e72a75fb45c59b11fff7
priority: High
type: RFC7807 Tier 2 UI component
created_by: bmad-create-story
created_at: 2026-06-03
sources:
  - _bmad-output/planning/epics.md (Epic 8.B / Story 8.B.4)
  - _bmad-output/planning/prd.md (Error Codes RFC 7807 / FR O7 / FG1.3)
  - _bmad-output/planning/architecture.md (packages/ui / RFC7807 / P72 / P75 / P77 / P78)
  - _bmad-output/planning/ux-design-specification.md (UX-DR1 / UX-DR2 Error Recovery / a11y patterns)
  - _bmad-output/stories/8-b-3-errors-next-action-url.md
  - packages/ui/src/components/ErrorBoundary/index.tsx
  - packages/ui/src/components/ErrorBoundary/index.stories.tsx
  - packages/ui/src/components/Tier1.a11y.test.tsx
  - packages/ui/src/index.ts
  - apps/web/src/app/console/predictions/page.tsx
  - apps/web/src/app/auth/login/page.tsx
  - apps/web/src/app/auth/signup/page.tsx
  - apps/web/src/app/auth/frozen-appeal/page.tsx
  - apps/web/src/app/welcome/page.tsx
---

# Story 8.B.4 - RFC7807ErrorPanel Component

Status: done

## Story

**作为** Console 用户、业务 Epic 页面和集成支持人员，
**我希望** `packages/ui` 提供可复用的 `RFC7807ErrorPanel`，
**从而** 402/422/429 等可恢复错误能稳定展示 `detail`、字段级 `field_path`、remediation 信息和 `next_action_url` 操作按钮，并通过 `aria-live` 帮助用户在错误后闭环恢复。

## Context

Story 8.B.3 已将后端错误合同闭合到 canonical `next_action_url`，并保留 `errors[]` detail object。当前 UI 侧存在一个简化实现：`packages/ui/src/components/ErrorBoundary/index.tsx` 内部导出 `RFC7807Panel`，且多个业务页面已经从 `@opticloud/ui` 使用该旧名称。

这个简化面板能显示 `status/title/detail/errors/next_action_url`，但仍不满足 8.B.4：

- 它不是独立 Tier 2 `RFC7807ErrorPanel` 组件。
- 字段级 remediation 只隐含在 `remediation_hint_key`，没有可读的 remediation 展示/映射能力。
- `next_action_url` 没有安全 URL 边界，可能误渲染 `javascript:` 等危险 scheme。
- request/trace/type/instance 展示、长文本换行、敏感值防泄漏和 dedicated tests 不足。
- Storybook 仍挂在 Tier 1 ErrorBoundary；缺少 402/422/429、危险 URL、长字段、无 CTA 等独立组件状态。

本 story 的正确方向是扩展并迁移现有面板能力，而不是重写 ErrorBoundary 或触碰后端/SDK。

## Scope

1. 在 `packages/ui/src/components/RFC7807ErrorPanel/` 新增独立 Tier 2 component。
2. 保留现有 `RFC7807Panel` public export 作为兼容别名，保证 `apps/web` 现有 import 不需要立即迁移也能获得新行为。
3. 让 `ErrorBoundary` 复用新的 `RFC7807ErrorPanel`，不要在 ErrorBoundary 内保留第二套面板实现。
4. 渲染 RFC 7807 payload 的核心字段：`title`、`status`、`detail`、`type`、`instance`、`request_id`、`trace_id`、`errors[]`、`next_action_url`。
5. 对 `errors[]` 中的 `field_path`、`constraint`、`remediation_hint_key` 和安全化后的 `value` 做字段级展示。
6. 支持通过 prop 传入 remediation 文案映射；无映射时显示 `remediation_hint_key`，避免信息丢失。
7. 将 `next_action_url` 渲染为 keyboard-accessible link/button，并拒绝危险 URL scheme。
8. 增加 dedicated unit tests、axe a11y tests、Storybook stories，并更新 `test:a11y` 覆盖。
9. 运行本地验证、实施后代码审查、GitHub PR/CI/merge/branch cleanup/local main sync 后，才允许标记 `done`。

## Out Of Scope

- 不修改后端 RFC7807 builder、billing/solver 错误响应、OpenAPI、Python/Node/Go SDK；这些属于 8.B.3/8.B.6。
- 不实现 `error-message-i18n-single-source` ESLint 规则或 `packages/i18n/errors.<lang>.yaml` 单源字典；这是 Story 8.B.5。
- 不新增 app route、营销页、ErrorBoundary crash 捕获逻辑、Toast/NotifyWrapper、RetryInline 重提交流程或真实模板下载 API。
- 不向 `packages/ui` 引入 `next/*`、app router、billing/auth/solver service、fetch、sessionStorage、localStorage 或新 runtime dependency。
- 不要求一次性把所有 `apps/web` 旧 import 改名为 `RFC7807ErrorPanel`；兼容别名是本 story 的回归保护。

## Acceptance Criteria

1. `packages/ui/src/components/RFC7807ErrorPanel/index.tsx` 存在，并导出 `RFC7807ErrorPanel`、`RFC7807ErrorPayload`、`RFC7807ErrorDetail` 和 props 类型。
2. `packages/ui/src/index.ts` 导出 `RFC7807ErrorPanel` 和公共类型，同时继续导出旧名 `RFC7807Panel`。
3. `packages/ui/src/components/ErrorBoundary/index.tsx` 复用新组件，并保留 `RFC7807Panel` 作为 `RFC7807ErrorPanel` 的兼容别名。
4. 现有业务页面使用 `RFC7807Panel` 的 import 不需要修改即可通过 typecheck。
5. 面板展示 `status/title/detail`，并在可用时展示 `type`、`instance`、`request_id`、`trace_id`。
6. `errors[]` 每一项展示 `field_path`、`constraint`、`remediation_hint_key` 或映射后的 remediation 文案。
7. `errors[]` 的 `value` 只以安全、截断、可换行的形式展示；疑似 token、authorization、password、cookie、secret、provider payload、traceback、文件路径等敏感文本不得原样渲染。
8. `errors[]` 为空、缺失、null-like optional 字段、`value=false`、`value=0`、长字段路径和长 constraint 时，面板不崩溃、不出现 `undefined` 文本、不横向溢出。
9. `next_action_url` 是唯一 CTA 输入；不得读取或渲染 legacy `next_action`。
10. `next_action_url` 仅允许 `https://...`、安全本地开发 `http://localhost...` / `http://127.0.0.1...`、或 root-relative `/...` URL；危险 scheme 不渲染 CTA。
11. CTA 是键盘可访问的 link/button 样式，使用可配置 label；默认文案为中文优先的操作文案。
12. 402 示例能展示充值 CTA，422 示例能展示字段级 remediation，429 示例能展示升级/重试引导。
13. 面板使用 `useA11y` 或等价模式提供 stable accessible name、`aria-live`、`aria-atomic` 和 error/status role 语义。
14. dedicated axe tests 覆盖 402、422 多字段、429 和危险 URL/无 CTA 状态，结果 0 violations。
15. Storybook stories 覆盖 402 Insufficient Credits、422 Schema Invalid、多字段长文本、429 Rate Limit、missing next action、unsafe URL rejected。
16. 组件使用现有 `cn`、Tailwind v3 token、lucide icon；不新增 dependency，不使用 Tailwind v4 `@theme` 或 OKLCH literal。
17. 组件是 presentation-only：不 fetch、不路由、不持久化、不读写浏览器 storage。
18. 组件避免卡片套卡片；外层可为一个 bordered panel，内部字段列表用 section/divider/list/table 等非 decorative nested-card 结构。
19. 组件在 mobile/desktop 下长 URL、长字段名、长 i18n key、长 request/trace id 都能换行或截断，不压缩按钮文本到不可读。
20. `packages/ui/src/components/Tier1.a11y.test.tsx` 继续通过，并用新组件/兼容别名覆盖 ErrorBoundary RFC7807 surface。
21. `packages/ui/package.json` 的 `test:a11y` 包含新的 `RFC7807ErrorPanel/index.a11y.test.tsx`。
22. Focused tests、UI package tests、typecheck、a11y gate、Storybook build 和 `git diff --check` 通过。
23. 实施后代码审查覆盖边界问题、漂移问题、数据一致性、依赖一致性、闭环行为和测试充分性；发现必须修复或记录。
24. PR 通过 GitHub CI、合并到 `main`、远程分支删除、本地 `main` 同步后，才能把 story 与 sprint status 标记为 `done` 并推送状态同步 commit。

## Tasks / Subtasks

- [x] T1: Add RED tests for `RFC7807ErrorPanel` contract (AC: 1-15, 20-21)
  - [x] Unit test 402 renders title/detail/field/remediation and safe CTA from `next_action_url`.
  - [x] Unit test 422 renders multiple field errors with `field_path`, `constraint`, mapped remediation text, and preserves `0` / `false` values.
  - [x] Unit test rejects `javascript:` / unsafe URL and never renders legacy `next_action`.
  - [x] Unit test redacts/truncates sensitive and long `value` / metadata text.
  - [x] A11y tests cover 402/422/429/unsafe URL states with axe.

- [x] T2: Implement independent `RFC7807ErrorPanel` (AC: 1, 5-19)
  - [x] Define public payload/detail/props types without importing app or backend modules.
  - [x] Render RFC7807 summary, diagnostic metadata, field error list, remediation, safe value preview, and CTA.
  - [x] Add safe URL guard and value preview guard.
  - [x] Use existing design tokens, `cn`, `useA11y`, and lucide icons.

- [x] T3: Refactor compatibility surface (AC: 2-4, 20)
  - [x] Update `ErrorBoundary` to call `RFC7807ErrorPanel`.
  - [x] Preserve `RFC7807Panel` alias and `RFC7807ErrorPayload` type export.
  - [x] Update package root exports.
  - [x] Update Tier 1 a11y fixture if needed without weakening existing coverage.

- [x] T4: Add Storybook and docs touchpoints (AC: 15, 17-19)
  - [x] Add `RFC7807ErrorPanel/index.stories.tsx` under Tier 2.
  - [x] Keep old ErrorBoundary story working through alias or update it to reference the new component.
  - [x] Update `packages/ui/README.md` component catalog if needed.

- [x] T5: Run local validation gates (AC: 22)
  - [x] `pnpm --filter @opticloud/ui test -- src/components/RFC7807ErrorPanel/index.test.tsx`
  - [x] `pnpm --filter @opticloud/ui test:a11y`
  - [x] `pnpm --filter @opticloud/ui test`
  - [x] `pnpm --filter @opticloud/ui typecheck`
  - [x] `pnpm --filter @opticloud/ui build-storybook`
  - [x] `git diff --check`

- [ ] T6: Review and GitHub sync (AC: 23-24)
  - [x] Complete post-implementation code review and fix findings.
  - [x] Commit, push, create PR, wait CI, merge, delete remote branch, sync local `main`.
  - [x] Only after merge/sync, mark story and sprint status `done` and push status-sync commit.

## Dev Notes

### Existing Files And Current State

- `packages/ui/src/components/ErrorBoundary/index.tsx`
  - Current state: class-based React error boundary plus an inline `RFC7807Panel` function.
  - This story changes: move panel behavior into `components/RFC7807ErrorPanel` and re-export old name as alias.
  - Preserve: crash fallback behavior, `onError`, `fallback`, `rfc7807` prop, and existing `RFC7807Panel` import compatibility.

- `packages/ui/src/index.ts`
  - Current state: package root exports Tier 1/Tier 2 components; `RFC7807Panel` is exported from ErrorBoundary.
  - This story changes: add explicit `RFC7807ErrorPanel` export and keep `RFC7807Panel`.
  - Preserve: all existing named exports and `UI_VERSION`.

- `packages/ui/src/components/Tier1.a11y.test.tsx`
  - Current state: uses `RFC7807Panel` as part of Tier 1 ErrorBoundary coverage.
  - This story changes: keep coverage green, preferably still exercising the compatibility alias.
  - Preserve: no weakening of existing Tier 1 axe tests.

- `apps/web` usage
  - Current state: `welcome`, `auth/signup`, `auth/login`, `auth/frozen-appeal`, and `console/predictions` use `RFC7807Panel`.
  - This story changes: no app page rewrite is required if the alias works.
  - Preserve: existing pages should typecheck without import changes.

### Frontend Implementation Guardrails

- Follow local Tier component shape: `index.tsx`, `index.test.tsx`, `index.a11y.test.tsx`, `index.stories.tsx`.
- Use `useA11y` for region/live semantics where practical; if direct ARIA props are clearer, keep them explicit and tested.
- Use lucide icons for severity/field/action cues; never rely on color alone.
- Keep cards at `rounded-md` or smaller and avoid nested card-inside-card composition.
- Use `break-words`, `min-w-0`, bounded monospace blocks, and flex wrapping to prevent long RFC7807 metadata from overflowing.
- Do not show raw object JSON for arbitrary `value`; provide a safe primitive preview or redacted/truncated summary.
- Do not add `target="_blank"` unless also adding safe `rel` semantics; same-tab links are acceptable for recovery CTAs.
- Do not introduce broad i18n dictionary enforcement. Expose label/remediation props so 8.B.5 can later wire single-source i18n.

### Previous Story Intelligence

- Story 8.B.3 established canonical `next_action_url`; UI must not revive legacy `next_action`.
- Story 8.B.3 found service-layer drift between helpers and schemas; this story must guard UI drift by testing the canonical field and alias behavior.
- 402 topup URL is `https://console.opticloud.cn/topup?suggested_amount=10`.
- 429 plan upgrade URL is `https://console.opticloud.cn/billing/plans`.
- Python SDK already preserves `errors[]` and `next_action_url`; this story only renders the preserved shape.

### Suggested Commands

```powershell
pnpm --filter @opticloud/ui test -- src/components/RFC7807ErrorPanel/index.test.tsx
pnpm --filter @opticloud/ui test:a11y
pnpm --filter @opticloud/ui test
pnpm --filter @opticloud/ui typecheck
pnpm --filter @opticloud/ui build-storybook
git diff --check
```

## Definition Of Done

- Story has passed 3 pre-implementation adversarial review rounds with revisions recorded.
- `RFC7807ErrorPanel` exists as a dedicated `packages/ui` Tier 2 component and old `RFC7807Panel` import compatibility is preserved.
- Component renders RFC7807 detail, field path, remediation, safe value preview, request/trace metadata, and safe `next_action_url` CTA.
- Unit, a11y, Storybook, typecheck, Storybook build, and diff-check gates pass locally.
- Post-implementation code review is complete and findings are fixed or explicitly documented.
- PR merge, remote branch deletion, and local `main` sync complete before story/sprint status becomes `done`.

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Debug Log References

- Baseline branch: `codex/8-b-4-rfc7807-error-panel`.
- Story creation baseline commit: `db49ba8e3215da4146b7e72a75fb45c59b11fff7`.
- 2026-06-03 - Implementation started; story and sprint status moved to `in-progress`.
- 2026-06-03 - RED confirmed: focused `RFC7807ErrorPanel` test failed because `components/RFC7807ErrorPanel/index.tsx` did not exist.
- 2026-06-03 - Implemented dedicated `RFC7807ErrorPanel`, old `RFC7807Panel` compatibility alias, ErrorBoundary reuse, safe `next_action_url`, remediation mapping, safe value/metadata preview, tests, a11y tests, Storybook stories, and README catalog entry.
- 2026-06-03 - Post-implementation review found empty CTA label and metadata redaction gaps; fixed both and reran focused gates.
- 2026-06-03 - Local gates passed and story/sprint status moved to `code-review`; final `done` remains gated on GitHub PR merge, remote branch deletion, local `main` sync, and status-sync commit.
- 2026-06-03 - PR #155 passed GitHub CI, squash-merged to `main`, remote branch `codex/8-b-4-rfc7807-error-panel` was removed, and local `main` is synced to `origin/main`.
- Customization resolver script absent at `_bmad/scripts/resolve_customization.py`; fallback loaded base `bmad-create-story/customize.toml`, found no project/user overrides, and no `project-context.md`.
- Story creation analyzed Epic 8.B / Story 8.B.4, PRD Error Codes RFC7807, Architecture P72/P75/P77/P78, UX Error Recovery/a11y patterns, Story 8.B.3, current ErrorBoundary/RFC7807Panel, package exports, UI package test/storybook setup, and current app usages.
- Latest web research was not needed because the story uses pinned local package versions and existing project patterns: React 18.3, TypeScript 5.4.5, Storybook 8.4, Vitest 2.1, Tailwind v3.4.

### Completion Notes List

- Added independent `packages/ui/src/components/RFC7807ErrorPanel` Tier 2 component with typed RFC7807 payload/detail props.
- Preserved existing `RFC7807Panel` public import by aliasing it to `RFC7807ErrorPanel`, and refactored `ErrorBoundary` to reuse the new component.
- Rendered status/title/detail, type/instance/request/trace metadata, field-level `errors[]`, remediation key/message, safe value previews, and safe `next_action_url` CTA.
- Added URL allowlist for CTA, redaction/truncation for `errors[].value` and metadata, empty CTA label fallback, and no legacy `next_action` rendering.
- Added unit tests, axe a11y tests, Storybook states for 402/422/429/long/missing/unsafe URL, README catalog entry, and `test:a11y` inclusion.
- Local gates passed: focused RFC7807 tests, package a11y tests, full UI test suite, UI typecheck, web typecheck, Storybook build, and `git diff --check`.
- Storybook build emits existing bundler warnings about `"use client"` module directives and large Storybook chunks, but exits successfully.
- GitHub closure passed: PR #155 CI green, merged to `main` at `40f7deab36cd526af83d9eecff088d053c66ec9d`, remote story branch deleted, and local `main` clean and synced before marking this story done.

### File List

- `_bmad-output/stories/8-b-4-rfc7807-error-panel.md`
- `_bmad-output/stories/sprint-status.yaml`
- `packages/ui/README.md`
- `packages/ui/package.json`
- `packages/ui/src/index.ts`
- `packages/ui/src/components/ErrorBoundary/index.tsx`
- `packages/ui/src/components/RFC7807ErrorPanel/index.tsx`
- `packages/ui/src/components/RFC7807ErrorPanel/index.test.tsx`
- `packages/ui/src/components/RFC7807ErrorPanel/index.a11y.test.tsx`
- `packages/ui/src/components/RFC7807ErrorPanel/index.stories.tsx`

## Change Log

- 2026-06-03 - Story created for dedicated `RFC7807ErrorPanel` component, compatibility alias, tests, a11y, Storybook, and GitHub closure.
- 2026-06-03 - Implementation started; baseline commit recorded and status moved to `in-progress`.
- 2026-06-03 - Implemented dedicated RFC7807 error panel, compatibility alias, tests/a11y/storybook/docs, and post-review fixes; story moved to `code-review` pending GitHub sync.
- 2026-06-03 - PR #155 passed CI, merged, remote branch removed, local main synced; story status moved to `done`.

## Post-Implementation Code Review

### Findings

- [x] [Review][Patch] Empty `nextActionLabel` could render a CTA with no accessible name when callers pass whitespace. Fixed by falling back to the default Chinese label after trimming.
- [x] [Review][Patch] Metadata fields (`type`, `instance`, `request_id`, `trace_id`) were displayed directly while only `errors[].value` used sensitive-value protection. Fixed by applying safe text preview/redaction to metadata as well and adding regression coverage.

### Outcome

Changes requested internally; all findings fixed and focused gates rerun. No remaining high/medium findings found in boundary, drift, data consistency, dependency consistency, closed-loop behavior, or test coverage review.

## Pre-Implementation Adversarial Reviews

### Round 1 - Boundary And Reinvention Review

Findings:

1. There is already an inline `RFC7807Panel` inside `ErrorBoundary`; creating a second unrelated component would duplicate behavior and leave existing app pages on the old weaker implementation.
2. Existing app pages import `RFC7807Panel`; renaming everything immediately would widen the change and risk app regressions unrelated to the component contract.
3. Backend/SDK contracts were closed in Story 8.B.3 and 8.B.6 is still backlog; touching backend or SDK here would blur story ownership.
4. Epics text says `next_action` button, but the PRD and 8.B.3 canonical field is `next_action_url`; using `next_action` would reintroduce contract drift.

Revision after Round 1:

- Scoped implementation to `packages/ui`, required the new component to replace the inline ErrorBoundary panel, preserved `RFC7807Panel` as an alias, and explicitly forbade backend/SDK changes and legacy `next_action`.

### Round 2 - Drift, Data Consistency, And Security Review

Findings:

1. `value` inside `errors[]` can be arbitrary and may contain sensitive data if an upstream bug leaks raw payloads; rendering JSON wholesale would create a UI data leak.
2. `next_action_url` is externally supplied problem-detail data; blindly rendering it as `href` can create `javascript:` or unsafe scheme injection.
3. Remediation could be either an i18n key or a mapped readable message; the story must preserve the key while allowing future i18n wiring.
4. Long field paths, constraints, trace ids, and URLs can break compact Console layouts unless wrapping/truncation is part of the contract.

Revision after Round 2:

- Added safe value preview/redaction requirements, safe URL allowlist, remediation mapping fallback, no `undefined` rendering, and responsive long-text constraints.

### Round 3 - A11y, Dependency, And Closure Review

Findings:

1. Existing coverage only includes Tier 1 a11y for `RFC7807Panel`; a Tier 2 component needs dedicated unit/a11y stories for 402/422/429 and unsafe URL states.
2. Adding dependencies or Tailwind v4 syntax would violate local architecture constraints and create avoidable build risk.
3. `test:a11y` must explicitly include the new a11y test, otherwise the new component may pass focused tests but not the package a11y gate.
4. User workflow requires final `done` only after post-implementation review, GitHub CI, merge, remote branch deletion, and local `main` sync.

Revision after Round 3:

- Added dedicated tests/storybook/a11y gates, no-new-dependency and Tailwind v3 constraints, `test:a11y` inclusion, and final workflow closure AC.
