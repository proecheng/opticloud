---
story_key: 9-1-axe-core-quarterly-audit
epic_num: 9
story_num: 1
epic_name: NFR Governance
status: code-review
baseline_commit: 26a90ae40eceef79f5d3dfaae9a925633222d866
priority: High
type: NFR-A quarterly axe-core audit governance
created_by: bmad-create-story
created_at: 2026-06-04
sources:
  - _bmad-output/planning/epics.md (Epic 9 / Story 9.1 / NFR-A)
  - _bmad-output/planning/architecture.md (P78 / NFR-A WCAG 2.1 AA -> 2.2 path)
  - _bmad-output/planning/ux-design-specification.md (UX-DR5 / 6 a11y profiles)
  - packages/ui/package.json
  - packages/ui/README.md
  - packages/ui/vitest.config.ts
  - packages/ui/src/components/Tier1.a11y.test.tsx
  - packages/ui/src/components/RFC7807ErrorPanel/index.a11y.test.tsx
  - packages/ui/src/components/VoucherCard/index.a11y.test.tsx
  - packages/ui/src/components/ChatInterface/index.a11y.test.tsx
  - packages/ui/src/components/InvoiceCard/index.a11y.test.tsx
  - packages/ui/src/components/BudgetAlertCard/index.a11y.test.tsx
  - packages/ui/src/components/AuditLogTable/index.a11y.test.tsx
  - packages/ui/src/components/CapabilityCard/index.a11y.test.tsx
  - .github/workflows/ci.yml
---

# Story 9.1 - Quarterly axe-core CI Audit

Status: code-review

## Story

**作为** NFR-A accessibility owner，
**我希望** 已有 `packages/ui` axe-core / jest-axe 覆盖被纳入季度审计契约、证据 schema、runbook 和 CI gate，
**从而** 每次 UI 变更都会自动执行 `test:a11y`，季度人工抽样也能留下可复核、无 PII、可追踪的审计证据，而不是靠口头声明 WCAG / axe 合规。

## Context

Story 0.12 已交付 `useA11y`、`jest-axe`、`axe-core` 和 `packages/ui` `test:a11y` 基线。后续 UI stories 又把 `RFC7807ErrorPanel`、`VoucherCard`、`ChatInterface`、`InvoiceCard`、`BudgetAlertCard`、`AuditLogTable`、`CapabilityCard` 的 dedicated axe tests 加进 `test:a11y`。当前缺口不是新建 UI 组件，而是 NFR-A governance：审计范围、证据格式、季度手工抽样、CI 触发和 drift detection 没有单一闭环。

Epic 9.1 原始 AC 要求季度 axe-core CI 审计、axe-core CI violation 0、人工抽样、violation 工单和 sub-persona panel SOP。Architecture 同时说明 v1 是 WCAG 2.1 AA + axe-core/jest-axe CI + 季度 4 sub-persona panel；v1.5+ WCAG 2.2 升级属于 Story 9.5，不属于本 story。

本 story 只建立 NFR-A 审计闭环：

- CI 在 UI/a11y governance 相关变更时运行 `pnpm --filter @opticloud/ui test:a11y`。
- 静态 contract/validator 证明 `test:a11y` 没有漏掉 committed `*.a11y.test.tsx` 文件。
- 证据 schema 支持 6 a11y profile 和 4 sub-persona quarterly sampling，但 committed example 不得假装已经完成真实 panel。
- Runbook 明确季度执行、招募、红线、票据、redaction 和 rollback。

## Scope

1. Add a static quarterly accessibility audit contract under `tools/a11y_audit/`.
   - Contract pins source story `9.1`, NFR-A, WCAG 2.1 AA v1 scope, automated axe command, required package, required zero-violation gate, six a11y profiles, four sub-personas, panel SOP, and evidence report directory.
   - Contract must explicitly state WCAG 2.2 upgrade is out of scope and belongs to Story 9.5.
   - Contract must not claim a real quarterly audit, real panel, third-party audit, production status, or external ticket creation.
2. Add a quarterly evidence schema and example manifest.
   - Example manifest is static and `example_only=true`.
   - Real evidence, when supplied via validator flag, must live under `reports/a11y-quarterly/<run_id>/audit_manifest.json`.
   - Evidence supports automated axe results, manual 6-profile x 4-sub-persona sampling results, findings, ticket references, and redaction review.
   - Evidence must be public-safe: no participant names, email, phone, tenant/user ids, prompt text, provider payloads, credentials, URLs with credentials, absolute local paths, or raw browser logs.
3. Add `scripts/validate_a11y_quarterly_audit.py`.
   - Validator checks contract, schema, example manifest, optional real evidence manifests, `packages/ui/package.json` `test:a11y` coverage, and CI workflow wiring.
   - Validator discovers all committed `packages/ui/src/components/**/*.a11y.test.tsx` files and fails if any are absent from `test:a11y`.
   - Validator fails if `test:a11y` drops `Tier1.a11y.test.tsx` or stops using `vitest run`.
   - Validator fails on fake completion claims in static examples.
4. Add `tests/test_a11y_quarterly_audit.py`.
   - Tests cover happy-path CLI validation, package-script drift, missing a11y test inclusion, fake completion, unsafe evidence paths, PII/secret leakage, six-profile/four-persona completeness, failure findings requiring ticket refs, and CI wiring.
5. Add `docs/runbooks/quarterly-a11y-audit.md`.
   - Documents quarterly operator flow, CI/local commands, manual sampling matrix, panel SOP, no-PII evidence rules, violation ticket policy, rollback/stop-ship rules, and handoff to Story 9.5 for WCAG 2.2.
6. Update `.github/workflows/ci.yml`.
   - Add a dedicated `ui_a11y_audit` path filter and job.
   - Job hard-gates the static validator, optional committed real evidence manifests, Python tests, and `pnpm --filter @opticloud/ui test:a11y`.
   - UI package changes must trigger this job; a11y governance files must trigger it; no `continue-on-error`.
7. Do not add new npm or Python dependencies.
8. Do not modify UI component implementation, backend services, database migrations, OpenAPI contracts, billing, auth, provider, or WCAG 2.2 rules.

## Out Of Scope

- Implementing new UI components or refactoring existing UI surfaces.
- Completing a real quarterly manual panel or claiming real participant feedback in committed static examples.
- Recruiting participants, collecting personal data, paying panel compensation, issuing invoices, or integrating with HR/vendor systems.
- Upgrading to WCAG 2.2, adding WCAG 2.2 criteria, or changing `useA11y` behavior. That is Story 9.5.
- Running browser E2E, Lighthouse, Storybook Chromatic, external axe SaaS, third-party accessibility audits, screen reader recordings, or production telemetry.
- Creating real GitHub/Linear tickets automatically from CI.
- Adding dependencies such as playwright-axe, axe-playwright, pa11y, cypress-axe, jsonschema, pydantic, or pytest plugins.

## Acceptance Criteria

1. `tools/a11y_audit/quarterly_a11y_contract.json` exists and validates as the canonical Story 9.1 NFR-A contract.
2. Contract pins `source_story=9.1`, `audit_version=quarterly_a11y_audit_v1`, `nfr=NFR-A`, `wcag_scope=WCAG 2.1 AA`, and `wcag_2_2_upgrade_story=9.5`.
3. Contract pins automated command `pnpm --filter @opticloud/ui test:a11y` and package `@opticloud/ui`.
4. Contract defines exactly six a11y profiles: screen reader, keyboard-only, high contrast, low vision, motor, and cognitive.
5. Contract defines exactly four sub-personas for quarterly sampling: Li Gong cURL, Lina CSV, Lao Zhang Excel, and Chen Architect SDK.
6. Contract documents panel SOP fields: quarterly cadence, 6-week recruitment lead time, at least 5 participants per sub-persona target, backup pool target, channel per persona, compensation policy placeholder, and finance/legal approval requirement.
7. Contract explicitly states the panel is sub-persona workflow sampling, not a claim of disabled-user panel completion.
8. Evidence schema and static example manifest exist under `tools/a11y_audit/`.
9. Static example manifest has `example_only=true`, `real_panel_completed=false`, and cannot claim real audit pass, real recruitment, production release approval, external ticket creation, or third-party audit.
10. Optional real evidence path mode accepts only `reports/a11y-quarterly/<run_id>/audit_manifest.json` where directory name equals `run_id`.
11. Optional real evidence requires `example_only=false`, `redaction_reviewed=true`, full six-profile x four-sub-persona sampling matrix, and automated axe result fields.
12. Optional real evidence may record failures, but every failed automated or manual check must have at least one ticket reference with owner, severity, due date, and status.
13. Real evidence cannot mark `release_approved=true` while open P0/P1/P2 accessibility findings remain unresolved.
14. Validator rejects participant names, email addresses, phone numbers, tenant/user/customer ids, API keys, bearer tokens, cookies, prompt/provider payload fields, credentialed URLs, absolute paths, and directory traversal in contract/evidence.
15. Validator discovers all committed `packages/ui/src/components/**/*.a11y.test.tsx` files and fails when any discovered test file is absent from `packages/ui/package.json` `scripts.test:a11y`.
16. Validator fails if `packages/ui/package.json` `scripts.test:a11y` does not include `vitest run` or drops `src/components/Tier1.a11y.test.tsx`.
17. Validator does not require exact wall-clock, browser, OS, runner, or CI log parity.
18. Tests cover validator happy path, package `test:a11y` drift, missing a11y file inclusion, fake completion claims, unsafe evidence paths, leak rejection, finding ticket requirements, release approval blocking, matrix completeness, and CI workflow wiring.
19. Runbook documents local commands, quarterly calendar flow, panel SOP, evidence path, redaction rules, ticket policy, stop-ship policy, rollback, and WCAG 2.2 handoff to Story 9.5.
20. `.github/workflows/ci.yml` exposes `ui_a11y_audit` from `changes` outputs.
21. CI path filter `ui_a11y_audit` covers `packages/ui/**`, `tools/a11y_audit/**`, `scripts/validate_a11y_quarterly_audit.py`, `tests/test_a11y_quarterly_audit.py`, `docs/runbooks/quarterly-a11y-audit.md`, and `reports/a11y-quarterly/**`.
22. CI job `ui-a11y-audit-validation` runs without `continue-on-error`.
23. CI job runs static validator, optional committed real evidence validation for every `reports/a11y-quarterly/**/audit_manifest.json`, Python tests, `pnpm install --frozen-lockfile`, and `pnpm --filter @opticloud/ui test:a11y`.
24. No new package dependency is added to root, `packages/ui`, or Python workspace.
25. No UI component, backend service, database migration, OpenAPI, billing, auth, provider, or WCAG 2.2 implementation file is modified.
26. Local gates pass: `uv run python scripts/validate_a11y_quarterly_audit.py`, `uv run pytest tests/test_a11y_quarterly_audit.py -q`, `pnpm --filter @opticloud/ui test:a11y`, `pnpm --filter @opticloud/ui typecheck`, and `git diff --check`.
27. Post-implementation code review covers boundary issues, drift issues, data consistency, dependency consistency, fake-completion risk, CI closure, no-leak guarantees, and test adequacy; findings are fixed or explicitly documented.
28. Story status flow is `ready-for-dev -> in-progress -> code-review -> done`; `done` is forbidden before GitHub CI passes, PR merges, remote branch is deleted, and local `main` is synced.
29. After merge/sync, story and sprint status are marked `done` only through a separate status-sync commit.

## Tasks / Subtasks

- [x] T1: Add static audit contract and evidence schema (AC: 1-14)
  - [x] Create `tools/a11y_audit/quarterly_a11y_contract.json`.
  - [x] Create `tools/a11y_audit/quarterly_a11y_manifest.schema.json`.
  - [x] Create `tools/a11y_audit/quarterly_a11y_manifest.example.json`.
  - [x] Encode six-profile/four-sub-persona sampling and panel SOP without real-completion claims.
  - [x] Encode public-safe evidence and failed-finding ticket requirements.

- [x] T2: Add validator and unit tests (AC: 10-18)
  - [x] Implement `scripts/validate_a11y_quarterly_audit.py` using only stdlib.
  - [x] Validate contract/schema/example and optional real evidence path mode.
  - [x] Validate `packages/ui/package.json` `test:a11y` covers committed component a11y tests.
  - [x] Add `tests/test_a11y_quarterly_audit.py` with drift, leak, fake-completion, matrix, ticket, and release-blocking coverage.

- [x] T3: Add quarterly audit runbook (AC: 19)
  - [x] Document local/CI commands.
  - [x] Document quarterly manual sampling and panel SOP.
  - [x] Document evidence redaction, ticket policy, stop-ship rules, rollback, and WCAG 2.2 handoff.

- [x] T4: Add CI closure (AC: 20-25)
  - [x] Add `ui_a11y_audit` output and path filter to `.github/workflows/ci.yml`.
  - [x] Add `ui-a11y-audit-validation` job.
  - [x] Ensure UI package changes trigger `pnpm --filter @opticloud/ui test:a11y`.
  - [x] Confirm no new dependencies or out-of-scope code files are modified.

- [x] T5: Gates, review, and GitHub sync (AC: 26-29)
  - [x] Run local validation gates.
  - [x] Run post-implementation code review and fix/document findings.
  - [ ] Commit, push, create PR, wait for CI, merge, delete remote branch, and sync local `main`.
  - [ ] Mark story and sprint status `done` only after merge/sync through a separate status-sync commit.

## Dev Notes

### Current A11y Infrastructure

- `packages/ui/package.json` already has `test:a11y` using `vitest run`.
- Current dedicated component axe tests are:
  - `src/components/Tier1.a11y.test.tsx`
  - `src/components/RFC7807ErrorPanel/index.a11y.test.tsx`
  - `src/components/VoucherCard/index.a11y.test.tsx`
  - `src/components/ChatInterface/index.a11y.test.tsx`
  - `src/components/InvoiceCard/index.a11y.test.tsx`
  - `src/components/BudgetAlertCard/index.a11y.test.tsx`
  - `src/components/AuditLogTable/index.a11y.test.tsx`
  - `src/components/CapabilityCard/index.a11y.test.tsx`
- `packages/ui/vitest.config.ts` already includes `src/**/*.{test,a11y.test}.{ts,tsx}` and happy-dom setup.
- `packages/ui/README.md` documents Story 0.12 and UX-DR5 baseline: `useA11y`, aria labels, focus visible, 44x44 touch target, disabled contrast >=3:1, axe-core 0 violations, and Storybook a11y addon.

### Implementation Pattern To Reuse

- Follow static governance patterns from:
  - `scripts/validate_j3_incident_contract.py`
  - `tests/test_j3_incident_contract.py`
  - `scripts/validate_sandbox_security_audit.py`
  - `tests/sandbox/security/test_sandbox_security_audit.py`
  - `docs/runbooks/j3-sre-incident-tier3.md`
  - `docs/runbooks/sandbox-security-audit.md`
- Use stdlib JSON/path/hash/re only. Do not introduce `jsonschema` or package deps.
- Prefer explicit semantic validators over accepting arbitrary schema content.
- Keep optional real evidence validation opt-in via `--evidence`.

### Boundary Rules

- This story does not prove a real quarterly manual audit has happened.
- This story does not prove WCAG 2.2 compliance.
- This story does not prove production user accessibility outcomes.
- This story does prove:
  - current committed `packages/ui` a11y tests are wired into `test:a11y`;
  - CI runs `test:a11y` for UI/a11y-relevant changes;
  - future quarterly evidence must use a complete, redacted, ticket-linked schema;
  - static examples cannot fake completion.

### Suggested Commands

```powershell
uv run python scripts/validate_a11y_quarterly_audit.py
uv run pytest tests/test_a11y_quarterly_audit.py -q
pnpm --filter @opticloud/ui test:a11y
pnpm --filter @opticloud/ui typecheck
git diff --check
```

## Definition Of Done

- Story has passed exactly 3 pre-implementation adversarial review rounds with revisions recorded after each round.
- Static NFR-A quarterly a11y contract, schema, example, validator, tests, runbook, and CI job exist.
- `packages/ui` `test:a11y` is hard-gated in CI for UI/a11y-relevant changes.
- Validator catches fake completion, package-script drift, missing committed a11y tests, incomplete manual matrix, unsafe evidence paths, unresolved stop-ship findings, and sensitive data leakage.
- Local gates and GitHub CI pass.
- Post-implementation code review is completed and findings are fixed or explicitly documented.
- Story and sprint status become `done` only after PR CI green, merge, remote branch deletion, local main sync, and a separate status-sync commit.

## Story Review Log

### Round 1: Boundary And Fake-Completion Review

Findings fixed:

- Initial scope could be interpreted as completing the quarterly manual audit itself. Revised the story so committed examples must set `example_only=true` and `real_panel_completed=false`, and validator rejects real audit/pass/recruitment/third-party/ticket completion claims in static examples.
- Initial scope did not explicitly separate WCAG 2.2 upgrade work. Added contract and AC requirements to pin WCAG 2.1 AA v1 scope and defer WCAG 2.2 to Story 9.5.
- Initial manual sampling language risked implying disabled-user panel completion. Revised ACs and contract requirements to say the panel is sub-persona workflow sampling, not a claim of disabled-user panel completion.

Status: PASS after fixes.

### Round 2: Drift And Data Consistency Review

Findings fixed:

- Initial story depended on a manually maintained list of a11y tests, which could drift as future components add `*.a11y.test.tsx`. Revised validator ACs to discover committed component a11y test files and fail when `test:a11y` misses any discovered file.
- Initial evidence requirements did not require a complete six-profile x four-sub-persona matrix for real evidence. Added a 24-cell completeness requirement and tests for missing combinations.
- Initial failure handling allowed accessibility failures without a closure mechanism. Added ticket reference requirements for every failed automated/manual check and release approval blocking for unresolved P0/P1/P2 findings.

Status: PASS after fixes.

### Round 3: Dependency, CI, And Closure Review

Findings fixed:

- Initial story did not explicitly ban external audit/axe/browser packages. Added no-new-dependency constraints and banned `jsonschema`, `playwright-axe`, `pa11y`, `cypress-axe`, and pytest plugins.
- Initial CI closure did not specify UI package changes must trigger the a11y job. Added `packages/ui/**` to the required `ui_a11y_audit` path filter.
- Initial closure rule mentioned GitHub sync but not a separate status-sync commit. Added explicit status flow and post-merge-only `done` update requirement.

Status: PASS after fixes. Story is ready for development.

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Debug Log References

- Baseline branch: `codex/9-1-axe-core-quarterly-audit`.
- Baseline commit: `26a90ae40eceef79f5d3dfaae9a925633222d866`.
- Customization resolver script absent at `_bmad/scripts/resolve_customization.py`; fallback loaded base skill instructions and project config.
- Story creation analyzed Epic 9.1, Architecture NFR-A/P78, UX-DR5, current `packages/ui` package script, UI README/vitest setup, committed component axe tests, and existing static governance validator/runbook patterns.
- 2026-06-04 - Completed pre-implementation adversarial review round 1 and revised fake-completion, WCAG 2.2 boundary, and sub-persona sampling language.
- 2026-06-04 - Completed pre-implementation adversarial review round 2 and revised package-script drift detection, full manual matrix, failed-finding ticket, and stop-ship requirements.
- 2026-06-04 - Completed pre-implementation adversarial review round 3 and revised dependency, CI trigger, and GitHub/status-sync closure requirements.
- 2026-06-04 - Implemented static quarterly a11y audit contract/schema/example, stdlib validator, runbook, Python tests, and CI `ui-a11y-audit-validation` hard gate.
- 2026-06-04 - Local gates passed: `uv run python scripts/validate_a11y_quarterly_audit.py`, `uv run pytest tests/test_a11y_quarterly_audit.py -q` (16 passed), `pnpm --filter @opticloud/ui test:a11y` (36 passed), `pnpm --filter @opticloud/ui typecheck`, and `git diff --check`.
- 2026-06-04 - Post-implementation code review completed; fixed POSIX absolute-path leak detection and CI filter-block drift validation, then reran all local gates successfully.

### Completion Notes List

- Initial story created.
- Exactly three pre-implementation adversarial review rounds completed; story is ready for implementation.
- Static contract/schema/example, validator, tests, runbook, and CI hard gate implemented.
- Post-implementation code review completed; findings fixed and gates rerun.
- Story moved to `code-review` pending GitHub PR/CI/merge cleanup. Not marked done.
- Story moved to in-progress after exactly three pre-implementation review rounds.

### File List

- `_bmad-output/stories/9-1-axe-core-quarterly-audit.md`
- `_bmad-output/stories/sprint-status.yaml`
- `.github/workflows/ci.yml`
- `docs/runbooks/quarterly-a11y-audit.md`
- `scripts/validate_a11y_quarterly_audit.py`
- `tests/test_a11y_quarterly_audit.py`
- `tools/a11y_audit/quarterly_a11y_contract.json`
- `tools/a11y_audit/quarterly_a11y_manifest.schema.json`
- `tools/a11y_audit/quarterly_a11y_manifest.example.json`

## Post-Implementation Code Review

### Blind Hunter - Boundary And Fake-Completion Review

Findings:

- No remaining issue found in scope boundary: implementation does not modify UI components, backend services, package dependencies, OpenAPI, billing/auth/provider code, or WCAG 2.2 behavior.
- No remaining issue found in static example semantics: committed example remains `example_only=true`, `real_panel_completed=false`, `release_approved=false`, and validator rejects fake completion flags.

### Edge Case Hunter - Data And Drift Review

Findings:

- [x] P2 fixed: sensitive-value scanning rejected Windows absolute paths but not POSIX absolute paths such as `/tmp/raw-a11y-browser.log`. Added POSIX absolute-path detection and regression coverage.
- [x] P2 fixed: CI validation originally searched required path snippets globally, so `packages/ui/**` could be removed from the `ui_a11y_audit` filter while still appearing elsewhere. Added block-level filter validation and regression coverage.

### Acceptance Auditor - AC Closure Review

Findings:

- No remaining issue found against AC 1-23: static assets, validator, tests, runbook, and CI job are present and locally validated.
- No remaining issue found against AC 24-25: no dependencies or out-of-scope implementation files changed.
- AC 26-27 closed locally: validation gates pass and post-implementation review findings are fixed.
- AC 28-29 remain pending by design until GitHub PR CI passes, merge completes, remote branch is deleted, local `main` is synced, and the separate status-sync commit marks the story `done`.

Outcome: PASS after fixes; awaiting GitHub sync.

## Change Log

- 2026-06-04 - Initial Story 9.1 created.
- 2026-06-04 - Round 1 pre-implementation review revised fake-completion and WCAG 2.2 boundaries.
- 2026-06-04 - Round 2 pre-implementation review revised drift detection, matrix completeness, and ticket/stop-ship closure.
- 2026-06-04 - Round 3 pre-implementation review revised dependency, CI trigger, and status-sync closure.
- 2026-06-04 - Implemented quarterly a11y audit contract, evidence schema/example, validator, tests, runbook, and CI hard gate.
- 2026-06-04 - Post-implementation code review fixed POSIX path leakage detection and CI filter-block drift validation; story moved to `code-review` pending GitHub sync.
- 2026-06-04 - Story status moved to in-progress after exactly three pre-implementation review rounds.
