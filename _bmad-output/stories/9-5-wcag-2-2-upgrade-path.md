---
story_key: 9-5-wcag-2-2-upgrade-path
epic_num: 9
story_num: 5
epic_name: NFR Governance
status: done
baseline_commit: 1e9d3468dc5c48c9aee068f461466c88a5a4619a
priority: High
type: NFR-A WCAG 2.2 v1.5+ upgrade path governance
created_by: bmad-create-story
created_at: 2026-06-05
owner: Frontend / NFR-A
sources:
  - _bmad-output/planning/epics.md (Epic 9 / Story 9.5 / FR7)
  - _bmad-output/planning/prd.md (§7 Accessibility / FR7)
  - _bmad-output/planning/architecture.md (P78 / NFR-A5)
  - _bmad-output/planning/ux-design-specification.md (Step 13 / UX-DR5 / AA6)
  - _bmad-output/stories/9-1-axe-core-quarterly-audit.md
  - tools/a11y_audit/quarterly_a11y_contract.json
  - scripts/validate_a11y_quarterly_audit.py
  - packages/ui/src/hooks/useA11y.ts
  - packages/ui/src/components/ConfirmationModal/index.tsx
  - packages/ui/src/components/ExcelDropZone/index.tsx
  - packages/ui/src/components/FilePicker/index.tsx
  - packages/ui/package.json
  - packages/ui/README.md
  - .github/workflows/ci.yml
  - W3C WAI What's New in WCAG 2.2 (official reference)
---

# Story 9.5 - WCAG 2.2 Upgrade Path v1.5+

Status: done

## Story

**作为** Frontend / NFR-A owner，
**我希望** WCAG 2.1 AA v1 到 WCAG 2.2 v1.5+ 的升级路径被固化为项目合同、证据 schema、Standard a11y Hook v2 readiness、组件重构清单、runbook 和 CI gate，
**从而** Story 9.5 不再停留在 FR7 forward reference 里，也不会把“4 项工程化 criteria 的升级路径准备”伪造成完整 WCAG 2.2 AA 合规声明。

## Context

Epic 9.5 原始 AC：Given v1.5+ / When WCAG 2.2 release / Then Standard a11y Hook upgrade + Component refactor (4 new criteria)。

Architecture P78 / NFR-A5 已把项目 v1.5+ 的工程化范围收敛为 4 项 criteria：

- 2.4.11 Focus Not Obscured (Minimum)
- 2.4.12 Focus Not Obscured (Enhanced)
- 2.5.7 Dragging Movements
- 3.2.6 Consistent Help

W3C 官方 WCAG 2.2 是 2023-10-05 发布的 Recommendation，并且从 WCAG 2.1 增加了 9 项 success criteria。项目 P78 的 4 项不是完整 WCAG 2.2 新增项集合，也不是完整 WCAG 2.2 AA 合规所需集合：例如 2.5.8 Target Size (Minimum) 和 3.3.8 Accessible Authentication (Minimum) 是 WCAG 2.2 AA 新项，但未列入当前 P78 4 项工程化范围。因此本 story 必须做两件事：

- 交付项目 v1.5+ P78/NFR-A5 的 4 项升级路径闭环。
- 明确禁止把该闭环描述为完整 WCAG 2.2 AA conformance。

Story 9.1 已建立 WCAG 2.1 AA v1 的季度 a11y audit governance、6 a11y profile、`pnpm --filter @opticloud/ui test:a11y` 和 handoff to Story 9.5。本 story 接续 9.1，不替代 9.1，也不声称真实第三方审计、真实残障用户 panel 或所有页面/组件已完成 WCAG 2.2 重构。

## Scope

1. Add static WCAG 2.2 v1.5+ upgrade-path governance assets under `tools/wcag_2_2_upgrade/`.
   - Contract pins `source_story=9.5`, `upgrade_version=wcag_2_2_upgrade_path_v1`, `nfr=NFR-A`, baseline `WCAG 2.1 AA v1`, and target `WCAG 2.2 v1.5+ project engineering gate`.
   - Contract records W3C WCAG 2.2 publication metadata and `w3c_total_new_success_criteria=9`.
   - Contract defines exactly four project P78 criteria in order: 2.4.11, 2.4.12, 2.5.7, 3.2.6.
   - Contract records deferred WCAG 2.2 criteria outside P78, including 2.5.8 and 3.3.8 as explicit no-full-AA-claim blockers.
2. Add evidence schema and static example manifest.
   - Example manifest is static and `example_only=true`.
   - Real evidence, when supplied via validator flag, must live under `reports/wcag-2-2-upgrade/<run_id>/upgrade_manifest.json`.
   - Real evidence requires all four project criteria, Standard a11y Hook v2 readiness checks, component-refactor checks, source snapshots, findings, redaction review, and ticket-backed closure for failures.
   - Evidence must be public-safe: no tenant/user/customer ids, emails, phone numbers, API keys, bearer tokens, cookies, passwords, prompt/provider payloads, raw browser logs, absolute local paths, participant identifiers, production hostnames, or credentialed URLs.
3. Add `scripts/validate_wcag_2_2_upgrade_path.py` using stdlib only.
   - Validate contract/schema/example and optional real evidence path mode.
   - Discover current committed UI substrates: `useA11y`, `ConfirmationModal`, `ExcelDropZone`, `FilePicker`, `packages/ui` exports/scripts, 9.1 a11y contract, and CI wiring.
   - Fail on P78 criteria drift, W3C 9-vs-project-4 confusion, fake completion, stale observed UI state, unsafe evidence, missing tickets, unresolved stop-ship findings, or missing CI closure.
4. Add `tests/test_wcag_2_2_upgrade_path.py`.
   - Cover validator happy path, criteria drift, W3C/project-scope confusion, deferred AA blocker loss, observed UI drift, static fake completion, unsafe evidence path, leak rejection, missing criteria/component/hook evidence, missing-ticket enforcement, release blocking, and CI wiring.
5. Add `docs/runbooks/wcag-2-2-upgrade-path.md`.
   - Document local/CI commands, W3C 9-vs-project-4 boundary, P78 criteria audit, Standard a11y Hook v2 readiness, component-refactor workflow, evidence path, redaction rules, ticket policy, stop-ship policy, release gate, and Story 9.1 handoff.
6. Upgrade `packages/ui/src/hooks/useA11y.ts` non-destructively for v2 readiness.
   - Add typed WCAG 2.2 options for focus-not-obscured mode, consistent help id, and dragging alternative marker.
   - Preserve all existing call sites and return shape.
   - Add minimal focus-not-obscured behavior without introducing dependencies.
7. Add minimal component refactor evidence for P78.
   - `ConfirmationModal` uses the new focus-not-obscured readiness path.
   - `ExcelDropZone` exposes a non-drag `FilePicker` alternative as explicit 2.5.7 evidence and links visible instructions via `aria-describedby`.
   - Static contract/runbook records that full Console consistent-help placement remains an evidence-gated v1.5+ rollout, not a claimed completed redesign.
8. Update `.github/workflows/ci.yml`.
   - Add `wcag_2_2_upgrade_path` path filter and `wcag-2-2-upgrade-path-validation` job.
   - Job hard-gates static validator, optional committed real evidence validation, focused Python tests, UI hook WCAG 2.2 tests, `test:a11y`, and `typecheck`.
9. Do not add new npm or Python dependencies.
10. Do not modify backend services, database migrations, OpenAPI contracts, billing, auth, provider routing, solver behavior, external audit integrations, or WCAG 2.2 third-party tooling.

## Out Of Scope

- Claiming complete WCAG 2.2 AA conformance, third-party audit completion, annual audit completion, real disabled-user panel completion, production release approval, or all pages/components refactored.
- Adding browser E2E, Playwright axe, Cypress axe, pa11y, jsonschema, pydantic, ESLint plugin changes, Storybook addon changes, third-party SaaS audit tooling, external ticket creation, or production telemetry.
- Rewriting the full design system, all Console help placements, all modal/dropdown stacks, all touch target behavior, all authentication flows, or all future WCAG 2.2 AA criteria.
- Changing Story 9.1 WCAG 2.1 AA quarterly audit scope except for explicit handoff references.
- Creating real GitHub/Linear/DingTalk tickets from CI.

## Acceptance Criteria

1. `tools/wcag_2_2_upgrade/wcag_2_2_upgrade_contract.json` exists and validates as the canonical Story 9.5 NFR-A WCAG 2.2 upgrade-path contract.
2. Contract pins `source_story=9.5`, `upgrade_version=wcag_2_2_upgrade_path_v1`, `nfr=NFR-A`, `baseline_standard=WCAG 2.1 AA v1`, and `target_gate=WCAG 2.2 v1.5+ project engineering gate`.
3. Contract records W3C WCAG 2.2 Recommendation date `2023-10-05`, W3C total new success criteria `9`, and official reference URLs.
4. Contract defines exactly four project P78 criteria in order: `2.4.11`, `2.4.12`, `2.5.7`, `3.2.6`.
5. Contract records the W3C levels for the four criteria: AA, AAA, AA, A; validator rejects any story/evidence language that treats all four as AA-only.
6. Contract defines deferred criteria exactly as `2.4.13`, `2.5.8`, `3.3.7`, `3.3.8`, and `3.3.9`, and marks `2.5.8` and `3.3.8` as full-WCAG-2.2-AA blockers.
7. Contract explicitly states the P78 4-criteria engineering gate does not prove full WCAG 2.2 AA conformance.
8. Contract links Story 9.1 as the WCAG 2.1 AA quarterly audit upstream and does not mutate Story 9.1 scope.
9. Contract defines Standard a11y Hook v2 readiness fields: `focus_not_obscured`, `consistent_help_id`, and `dragging_alternative`.
10. Contract defines component refactor targets for `useA11y`, `ConfirmationModal`, `ExcelDropZone`, `FilePicker`, and `Console consistent help placement`.
11. Contract observed UI state matches committed `packages/ui` sources and fails when any required readiness marker drifts.
12. Evidence schema and static example manifest exist under `tools/wcag_2_2_upgrade/`.
13. Static example manifest has `example_only=true`, `real_wcag_2_2_conformance_claimed=false`, `real_third_party_audit_completed=false`, `real_component_refactor_completed=false`, and `release_approved=false`.
14. Static example cannot claim full WCAG 2.2 conformance, real third-party audit, real production approval, real complete component refactor, external ticket creation, or annual audit completion.
15. Optional real evidence path mode accepts only `reports/wcag-2-2-upgrade/<run_id>/upgrade_manifest.json` where directory name equals `run_id`.
16. Optional real evidence requires `example_only=false`, `redaction_reviewed=true`, all four project criteria evaluations, all Standard a11y Hook v2 checks, all component-refactor checks, source snapshots, and findings.
17. Real evidence cannot claim `real_wcag_2_2_conformance_claimed=true` while the contract scope remains P78 4 criteria instead of all WCAG 2.2 AA requirements.
18. Every failed criterion, failed hook check, failed component check, or stale source snapshot must reference at least one finding with ticket refs.
19. Real evidence cannot mark `release_approved=true` while unresolved P0/P1/P2 NFR-A findings remain open, in progress, or deferred.
20. Validator rejects tenant/user/customer ids, emails, phone numbers, API keys, bearer tokens, cookies, passwords, secrets, credentialed URLs, production hostnames, absolute paths, directory traversal, participant identifiers, raw browser logs, prompt/provider payloads, and full WCAG conformance claims outside the contract boundary.
21. `useA11y` exposes typed WCAG 2.2 readiness options without breaking existing callers.
22. `useA11y` returns/sets stable WCAG 2.2 data attributes and applies focus-not-obscured scroll behavior when enabled.
23. `ConfirmationModal` opts into focus-not-obscured readiness without changing existing props.
24. `ExcelDropZone` declares a non-drag `FilePicker` alternative and links visible instructions through `aria-describedby`.
25. `packages/ui` focused tests cover `useA11y` WCAG 2.2 readiness behavior.
26. `.github/workflows/ci.yml` exposes `wcag_2_2_upgrade_path` from `changes` outputs.
27. CI path filter `wcag_2_2_upgrade_path` covers `packages/ui/**`, `tools/wcag_2_2_upgrade/**`, `scripts/validate_wcag_2_2_upgrade_path.py`, `tests/test_wcag_2_2_upgrade_path.py`, `docs/runbooks/wcag-2-2-upgrade-path.md`, `reports/wcag-2-2-upgrade/**`, `tools/a11y_audit/**`, `scripts/validate_a11y_quarterly_audit.py`, and `.github/workflows/ci.yml`.
28. CI job `wcag-2-2-upgrade-path-validation` runs without `continue-on-error`.
29. CI job runs static validator, optional committed real evidence validation, focused Python tests, UI WCAG 2.2 hook tests, `pnpm --filter @opticloud/ui test:a11y`, and `pnpm --filter @opticloud/ui typecheck`.
30. No new package dependency is added to root, `packages/ui`, or Python workspace.
31. No backend service, database migration, OpenAPI, billing, auth, provider, solver, external audit SaaS, or ticket-integration file is modified.
32. Local gates pass: `uv run python scripts/validate_wcag_2_2_upgrade_path.py`, `uv run pytest tests/test_wcag_2_2_upgrade_path.py -q`, `pnpm --filter @opticloud/ui test -- src/hooks/useA11y.wcag22.test.tsx`, `pnpm --filter @opticloud/ui test:a11y`, `pnpm --filter @opticloud/ui typecheck`, and `git diff --check`.
33. Post-implementation code review covers boundary issues, drift issues, data consistency, dependency consistency, fake-completion risk, CI closure, no-leak guarantees, criteria-level correctness, and test adequacy; findings are fixed or explicitly documented.
34. Story status flow is `ready-for-dev -> in-progress -> code-review -> done`; `done` is forbidden before GitHub CI passes, PR merges, remote branch is deleted, and local `main` is synced.
35. After merge/sync, story and sprint status are marked `done` only through a separate status-sync commit.

## Tasks / Subtasks

- [x] T1: Add WCAG 2.2 upgrade-path contract and evidence schema (AC: 1-20)
  - [x] Create `tools/wcag_2_2_upgrade/wcag_2_2_upgrade_contract.json`.
  - [x] Create `tools/wcag_2_2_upgrade/wcag_2_2_upgrade_manifest.schema.json`.
  - [x] Create `tools/wcag_2_2_upgrade/wcag_2_2_upgrade_manifest.example.json`.
  - [x] Encode W3C 9-vs-project-4 boundary and deferred AA blockers.
  - [x] Encode public-safe evidence and ticket-backed closure rules.

- [x] T2: Add validator and unit tests (AC: 15-20, 26-29)
  - [x] Implement `scripts/validate_wcag_2_2_upgrade_path.py` using only stdlib.
  - [x] Validate contract/schema/example and optional real evidence path mode.
  - [x] Discover committed UI substrates and CI wiring.
  - [x] Add `tests/test_wcag_2_2_upgrade_path.py` with drift, leak, fake-completion, coverage, ticket, release-blocking, and CI tests.

- [x] T3: Upgrade Standard a11y Hook v2 readiness and minimal components (AC: 21-25, 30-31)
  - [x] Extend `useA11y` with WCAG 2.2 readiness options while preserving existing callers.
  - [x] Add focused hook tests.
  - [x] Opt `ConfirmationModal` into focus-not-obscured readiness.
  - [x] Mark `ExcelDropZone` / `FilePicker` dragging alternative and linked instructions.
  - [x] Confirm no new dependencies or out-of-scope files are modified.

- [x] T4: Add runbook and CI closure (AC: 26-29)
  - [x] Add `docs/runbooks/wcag-2-2-upgrade-path.md`.
  - [x] Add `wcag_2_2_upgrade_path` output and path filter to `.github/workflows/ci.yml`.
  - [x] Add `wcag-2-2-upgrade-path-validation` job.
  - [x] Ensure Story 9.1 a11y substrate changes trigger the validator.

- [x] T5: Gates, review, and GitHub sync (AC: 32-35)
  - [x] Run local validation gates.
  - [x] Run post-implementation code review and fix/document findings.
  - [x] Commit, push, create PR, wait for CI, merge, delete remote branch, and sync local `main`.
  - [x] Mark story and sprint status `done` only after merge/sync through a separate status-sync commit.

## Dev Notes

### Current A11y Infrastructure

- Story 0.12 delivered `useA11y`, `jest-axe`, `axe-core`, and `packages/ui` `test:a11y`.
- Story 9.1 delivered the WCAG 2.1 AA quarterly audit governance contract, evidence schema, validator, runbook, and CI `ui-a11y-audit-validation`.
- Current `useA11y` supports aria label/description, focus trap, ESC close, focus restore, live region, and role.
- `ConfirmationModal` already uses `trapFocus`, `escapeToClose`, and `restoreFocus`.
- `ExcelDropZone` already offers a `FilePicker` click alternative, but it is not yet encoded as a WCAG 2.2 2.5.7 artifact.

### Implementation Pattern To Reuse

- Follow Story 9.1/9.2/9.3/9.4 static governance pattern:
  - contract + schema + static example under `tools/...`
  - stdlib validator under `scripts/...`
  - focused pytest module under `tests/...`
  - runbook under `docs/runbooks/...`
  - dedicated CI path filter and hard gate
- Use semantic validation instead of adding `jsonschema`.
- Keep optional real evidence validation opt-in via `--evidence`.
- Avoid raw 64-character SHA-256 literals in committed JSON to prevent `detect-secrets` false positives; use grouped fingerprints only if source snapshots are needed.

### Boundary Rules

- This story does not prove full WCAG 2.2 AA conformance.
- This story does not prove a third-party audit or disabled-user panel happened.
- This story does not complete all future Console help placement or all component refactors.
- This story does prove:
  - P78/NFR-A5 has a static, reviewable, evidence-gated upgrade path;
  - Standard a11y Hook has a non-breaking v2 readiness surface;
  - project 4-criteria scope cannot be confused with W3C 9-new-criteria scope;
  - CI detects drift in upgrade-path governance, UI readiness markers, and evidence closure.

### Suggested Commands

```powershell
uv run python scripts/validate_wcag_2_2_upgrade_path.py
uv run pytest tests/test_wcag_2_2_upgrade_path.py -q
pnpm --filter @opticloud/ui test -- src/hooks/useA11y.wcag22.test.tsx
pnpm --filter @opticloud/ui test:a11y
pnpm --filter @opticloud/ui typecheck
git diff --check
```

## Definition Of Done

- Story has passed exactly 3 pre-implementation adversarial review rounds with revisions recorded after each round.
- WCAG 2.2 upgrade-path contract, schema, example, validator, tests, runbook, Standard a11y Hook v2 readiness, minimal P78 component evidence, and CI job exist.
- Validator catches fake completion, criteria drift, W3C/project-scope confusion, deferred AA blocker loss, stale UI substrate state, unsafe evidence paths, unresolved stop-ship findings, sensitive data leakage, missing tickets, and CI closure drift.
- Local gates and GitHub CI pass.
- Post-implementation code review is completed and findings are fixed or explicitly documented.
- Story and sprint status become `done` only after PR CI green, merge, remote branch deletion, local main sync, and a separate status-sync commit.

## Story Review Log

### Round 1: Boundary And Fake-Completion Review

Findings fixed:

- Initial Epic wording could be read as full WCAG 2.2 AA compliance. Revised scope so this story is a P78/NFR-A5 project engineering gate and explicitly forbids full-conformance claims.
- Initial “WCAG 2.2 release” wording was temporally stale because W3C WCAG 2.2 is already a Recommendation. Revised story to record official WCAG 2.2 metadata and treat the work as v1.5+ product upgrade-path governance.
- Initial “Component refactor” wording could imply all UI components are fully refactored. Revised scope to a non-breaking `useA11y` v2 readiness upgrade, minimal component evidence, and evidence-gated component-refactor plan.

Status: PASS after fixes.

### Round 2: Drift, Criteria, And Data Consistency Review

Findings fixed:

- Initial 4-criteria list risked hiding the W3C fact that WCAG 2.2 adds 9 success criteria. Added contract and validator requirements for W3C total 9 and project P78 exactly 4.
- Initial story did not identify that P78 includes 2.4.12 AAA and 3.2.6 A, so “4 AA criteria” would be false. Added criterion-level W3C level validation and anti-confusion AC.
- Initial deferred criteria were too vague. Added explicit deferred list, including 2.5.8 and 3.3.8 as full-WCAG-2.2-AA blockers.
- Initial evidence model could pass with missing component or hook checks. Added completeness requirements for all four criteria, all hook v2 checks, all component-refactor checks, and source snapshots.

Status: PASS after fixes.

### Round 3: Dependency, CI, And Closure Review

Findings fixed:

- Initial story did not explicitly ban new a11y/browser/schema dependencies. Added no-new-dependency and no third-party audit tooling constraints.
- Initial CI closure did not include Story 9.1 substrate drift. Added path-filter coverage for `tools/a11y_audit/**` and `scripts/validate_a11y_quarterly_audit.py`.
- Initial lifecycle did not restate the user's strict GitHub/status-sync ordering. Added status flow and post-merge-only separate `done` status-sync requirement.

Status: PASS after fixes. Story is ready for development.

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Debug Log References

- Baseline branch: `codex/9-5-wcag-2-2-upgrade-path`.
- Baseline commit: `1e9d3468dc5c48c9aee068f461466c88a5a4619a`.
- Customization resolver script absent at `_bmad/scripts/resolve_customization.py`; fallback loaded base skill instructions and project config.
- Story creation analyzed Epic 9.5, PRD FR7, Architecture P78/NFR-A5, UX Spec Step 13/UX-DR5, Story 9.1 a11y audit governance, current `useA11y`, `ConfirmationModal`, `ExcelDropZone`, `FilePicker`, `packages/ui` scripts, and existing 9.x static governance validator/runbook patterns.
- 2026-06-05 - Completed pre-implementation adversarial review round 1 and revised full-conformance, temporal, and component-refactor boundaries.
- 2026-06-05 - Completed pre-implementation adversarial review round 2 and revised W3C 9-vs-project-4 criteria handling, criterion levels, deferred AA blockers, and evidence completeness.
- 2026-06-05 - Completed pre-implementation adversarial review round 3 and revised dependency, CI trigger, and GitHub/status-sync closure requirements.
- 2026-06-05 - Story moved to in-progress after exactly three pre-implementation review rounds.
- 2026-06-05 - Red phase: `uv run pytest tests/test_wcag_2_2_upgrade_path.py -q` produced 13 expected failures before validator/assets/runbook/CI existed; `pnpm --filter @opticloud/ui test -- src/hooks/useA11y.wcag22.test.tsx` produced 2 expected failures before hook readiness existed.
- 2026-06-05 - Implemented WCAG 2.2 upgrade contract/schema/example, stdlib validator, tests, runbook, CI path-filter/job, non-breaking `useA11y` v2 readiness options, and minimal `ConfirmationModal` / `ExcelDropZone` evidence.
- 2026-06-05 - Local gates passed: `uv run python scripts/validate_wcag_2_2_upgrade_path.py`, `uv run pytest tests/test_wcag_2_2_upgrade_path.py -q`, `pnpm --filter @opticloud/ui test -- src/hooks/useA11y.wcag22.test.tsx`, `pnpm --filter @opticloud/ui test:a11y`, `pnpm --filter @opticloud/ui typecheck`, and `git diff --check`.
- 2026-06-05 - Post-implementation code review found real-evidence status-enum and CI filter-block validation gaps; patched validator and added regression coverage.
- 2026-06-05 - Post-review gates passed: `uv run python scripts/validate_wcag_2_2_upgrade_path.py`, `uv run pytest tests/test_wcag_2_2_upgrade_path.py -q` (15 passed), `pnpm --filter @opticloud/ui test -- src/hooks/useA11y.wcag22.test.tsx`, `pnpm --filter @opticloud/ui test:a11y`, `pnpm --filter @opticloud/ui typecheck`, `uv run ruff check scripts/validate_wcag_2_2_upgrade_path.py tests/test_wcag_2_2_upgrade_path.py`, and `git diff --check`.
- 2026-06-05 - PR #174 passed GitHub CI, squash-merged to `main` at `6e2ba43`, remote branch `codex/9-5-wcag-2-2-upgrade-path` was deleted, and local `main` was synced.
- 2026-06-05 - Separate status-sync commit prepared after merge/sync to mark Story 9.5 and sprint status `done`.

### Completion Notes List

- Initial story created.
- Exactly three pre-implementation adversarial review rounds completed; story is ready for implementation.
- Story moved to in-progress after exactly three pre-implementation review rounds.
- Added Story 9.5 WCAG 2.2 upgrade-path governance assets, validator, tests, runbook, and CI hard gate.
- Added non-breaking Standard a11y Hook v2 readiness options and minimal P78 component evidence.
- Story moved to code-review after local implementation gates passed; `done` remains blocked until post-review, PR CI, merge, remote branch deletion, local main sync, and separate status-sync commit.
- Post-implementation review patches completed; focused Python test count is now 15.
- PR #174 passed CI and merged. Story and sprint status now marked `done` in this separate post-merge status-sync.

### File List

- `_bmad-output/stories/9-5-wcag-2-2-upgrade-path.md`
- `_bmad-output/stories/sprint-status.yaml`
- `.github/workflows/ci.yml`
- `docs/runbooks/wcag-2-2-upgrade-path.md`
- `packages/ui/src/components/ConfirmationModal/index.tsx`
- `packages/ui/src/components/ExcelDropZone/index.tsx`
- `packages/ui/src/hooks/useA11y.ts`
- `packages/ui/src/hooks/useA11y.wcag22.test.tsx`
- `scripts/validate_wcag_2_2_upgrade_path.py`
- `tests/test_wcag_2_2_upgrade_path.py`
- `tools/wcag_2_2_upgrade/wcag_2_2_upgrade_contract.json`
- `tools/wcag_2_2_upgrade/wcag_2_2_upgrade_manifest.schema.json`
- `tools/wcag_2_2_upgrade/wcag_2_2_upgrade_manifest.example.json`

## Post-Implementation Code Review

### Blind Hunter - Boundary And Fake-Completion Review

Findings:

- No remaining issue found in full-conformance boundary: contract, manifest, validator, runbook, and story all state that P78 4-criteria evidence does not prove full WCAG 2.2 AA conformance.
- No remaining issue found in static example semantics: committed example remains `example_only=true`, `real_wcag_2_2_conformance_claimed=false`, `real_third_party_audit_completed=false`, `real_component_refactor_completed=false`, and `release_approved=false`.

### Edge Case Hunter - Data And Drift Review

Findings:

- [x] P2 fixed: real evidence initially accepted `current` / `stale` status values for criteria, hook, and component rows. Tightened status enums by row type and added regression coverage.
- [x] P2 fixed: CI filter validation needed an explicit block-scoped regression test so required path snippets cannot be satisfied by unrelated workflow text. Added block-scoped mutation coverage.

### Acceptance Auditor - AC Closure Review

Findings:

- No remaining issue found against AC 1-20: static assets, scope boundary, W3C 9-vs-project-4 handling, evidence schema, fake-completion rejection, no-leak checks, and ticket closure rules are present and locally validated.
- No remaining issue found against AC 21-25: `useA11y` exposes non-breaking WCAG 2.2 readiness options, focused hook tests pass, `ConfirmationModal` opts into focus-not-obscured readiness, and `ExcelDropZone` records a `FilePicker` non-drag alternative.
- No remaining issue found against AC 26-31: CI path filter/job are present, no new dependency was added, and no backend/database/OpenAPI/business-logic file was modified.
- AC 32-33 closed locally: validation gates pass and post-implementation review findings are fixed.
- AC 34-35 closed: PR #174 passed GitHub CI, was squash-merged to `main`, remote branch was deleted, local `main` was synced, and this separate status-sync marks the story `done`.

Outcome: PASS after fixes.

## Change Log

- 2026-06-05 - Initial Story 9.5 created.
- 2026-06-05 - Round 1 pre-implementation review revised full-conformance, temporal, and component-refactor boundaries.
- 2026-06-05 - Round 2 pre-implementation review revised criteria scope, levels, deferred blockers, and evidence completeness.
- 2026-06-05 - Round 3 pre-implementation review revised dependency, CI trigger, and status-sync closure.
- 2026-06-05 - Story status moved to in-progress after exactly three pre-implementation review rounds.
- 2026-06-05 - Implemented WCAG 2.2 upgrade-path governance assets, validator, tests, runbook, CI hard gate, and Standard a11y Hook v2 readiness.
- 2026-06-05 - Story status moved to code-review after local implementation gates passed.
- 2026-06-05 - Post-implementation review tightened real-evidence row status enums and CI filter-block drift coverage.
- 2026-06-05 - PR #174 passed CI, merged to main, remote branch deleted, local main synced; story moved to `done`.
