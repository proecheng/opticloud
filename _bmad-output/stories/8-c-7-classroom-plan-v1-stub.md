---
story_key: 8-c-7-classroom-plan-v1-stub
epic_num: 8
story_num: C.7
epic_name: Teaching + Provider Routing + Legal + Algorithm Library
status: done
baseline_commit: 6c9d03bd6dcb97878ab2a58841a0fb1db386b03f
priority: High
type: Classroom Plan v1 stub
created_by: bmad-create-story
created_at: 2026-06-04
sources:
  - _bmad-output/planning/epics.md (Expert Panel E6 / Story 8.C.7 brief)
  - _bmad-output/planning/prd.md (Classroom Plan 5-200 students / shared Credits)
  - _bmad-output/planning/architecture.md (Appendix F.5 PR4/PR5/PR8/PR9)
  - _bmad-output/planning/ux-design-specification.md (J4 / FG15 / LMS references)
  - docs/academic-provider-handbook.md (Classroom Plan and LMS route-map boundaries)
  - docs/customer-faqs/academic-onboarding-faq.md (Classroom FAQ wording)
  - _bmad-output/stories/8-c-1-mode-teaching-explain.md
  - _bmad-output/stories/8-c-6-provider-console-tier3.md
  - apps/web/src/app/console/legal-inquiry/page.tsx
  - apps/web/src/app/console/legal-inquiry/page.test.tsx
  - apps/web/src/lib/api.ts
---

# Story 8.C.7 - Classroom Plan v1 stub

Status: done

## Story

**作为** 高校教师或 Academic Relations / Customer Success 人员，
**我希望** Console 中有一个明确标注为 v1 stub 的 Classroom Plan 规划面，
**从而** 能在不伪造教师 master account、学生账号、共享 Credits、LMS/LTI 或 grading API 已上线的前提下，校验教师联系人/规划 email、学生人数上限、共享 Credits 申请口径和 LMS 集成路线图，并把人工 cohort 的下一步边界讲清楚。

## Context

Expert Panel E6 只给出 brief："Classroom Plan v1 stub (教师 master + 学生 <=200 + 共享 Credits + LMS Integration foundation)"。PRD 和 UX 把 Classroom Plan 定位为 Growth/v2 完整能力，但也要求 v1 末有占位。`docs/academic-provider-handbook.md` 已明确：完整 Classroom Plan、LMS gradebook、课程码和自动课程管理是 v2+ 路线图；v1 处理方式是人工 cohort：教师/Academic Relations 建课程名单，学生教育邮箱注册，手动发放 credits 或使用教育版额度。

Story 8.C.1 已交付 `mode=teaching` API 教学折扣和 Notebook 链接，但明确排除了 Classroom Plan、grading API、LMS/LTI、教师 master account 和学生名单管理。Story 8.C.7 必须承接这个边界：提供一个可执行的 v1 planning stub，而不是提前实现账户、计费、课程或 LMS 后端。

## Scope

1. 新增 `/console/classroom` client route。
   - 读取现有 `sessionStorage.jwt_access` 作为 Console 访问门槛；缺失时重定向 `/auth/login`。
   - 使用本地 React state 和纯 helper 生成 Classroom Plan draft summary。
   - 不调用后端，不 fetch，不新增 API client，不创建教师 master account，不创建学生账号，不分配真实 Credits，不连接 LMS，不提交 grading。
2. 新增 classroom plan helper。
   - 放在 `apps/web/src/lib/classroom-plan.ts`，集中定义 v1 contract、seat limit、shared Credits request normalization、LMS foundation status 和 validation。
   - helper 必须 deterministic，不依赖 `Date.now()`、random、browser storage 或 network。
   - 数字输入必须按 trimmed base-10 digit string 解析，拒绝空字符串、符号、逗号、小数、指数、`NaN`、`Infinity` 和单位后缀。
3. 页面支持教师联系人/teacher master planning email + 课程草案输入。
   - Teacher contact / master planning email。
   - Course name。
   - Student seats，范围 5-200，超过 200 必须阻止生成。
   - Shared Credits monthly request，作为申请口径/人工处理信息，不是账本 proof。
   - LMS provider selector：Manual cohort、Canvas、Moodle、雨课堂、学堂在线。
4. 页面展示 v1/v2 边界。
   - Manual cohort 显示 v1 可人工处理。
   - Canvas/Moodle/雨课堂/学堂在线均显示 foundation/planned，不显示已连接、已授权、已同步、已回传成绩。
   - 明确说明学生数据不进入 Provider 训练集、教师可见的是进度和提交摘要而非默认下载原始数据、真实人类/敏感教育数据需要 IRB 或校内伦理审批路径。
5. 更新 Console discoverability。
   - 新页面 header 必须包含现有 Console nav 入口。
   - 在 `/console/providers` 和 `/console/legal-inquiry` header nav 中增加 Classroom 链接，作为本 story 的最小可发现入口。
   - 不做全局 nav abstraction，不批量改所有 Console 页面。
6. 更新学术 handbook/FAQ 中 Classroom Plan 文案，加入 `/console/classroom` v1 stub 入口和边界。
7. 新增 focused tests 覆盖 helper、page 和被触达 nav 页面。
8. 运行 post-implementation code review、local gates、GitHub sync，并且只在 CI/merge/branch cleanup/local main sync 后用单独状态同步提交标记 `done`。

## Out Of Scope

- 后端 endpoint、OpenAPI generated artifacts、数据库 migration、auth-service/billing-service/solver-orchestrator/capability-registry 改动。
- 教师 master account 后端模型或真实创建、学生账号创建/邀请、课程码、Roster CSV 上传、学生名单存储、学生邮箱批量校验。
- 真实 shared Credits 账本、bucket 创建、转账/扣减/冻结、budget alert、invoice、payment、tax 或 settlement。
- LMS/LTI 1.3 launch、OAuth/SSO、Canvas/Moodle/雨课堂/学堂在线 API 调用、gradebook 回传、assignment deep link。
- Teaching Mode Grading API、作业批改、rubric、学生 task batch review；这些留给 Story 8.C.9。
- 把 teacher email、course name、student count、LMS selection、draft summary 或任何课堂数据写入 localStorage/sessionStorage/cookies/query string。
- 收集或展示学生个人邮箱、学号、姓名、成绩、原始提交、真实课堂数据或 Provider training data。
- 新 npm dependency、shared UI dependency、charting/table library、TanStack Query/Zustand/RHF/Zod。

## Acceptance Criteria

1. `/console/classroom` route exists and is the only new route added by this story.
2. `/console/classroom` redirects to `/auth/login` when `sessionStorage.jwt_access` is missing.
3. The route does not call `fetch`, does not import `apps/web/src/lib/api.ts`, and does not send any request body or auth header to any service.
4. The route does not write teacher/course/classroom data to `localStorage`, `sessionStorage`, cookies, URL query string or clipboard.
5. Page form includes Teacher contact / master planning email, Course name, Student seats, Shared Credits monthly request, and LMS provider.
6. Teacher contact / master planning email is required, trimmed, max 254 chars, and must pass a basic email format check before draft generation.
7. Course name is required, trimmed, 3-120 chars.
8. Student seats must be an integer from 5 to 200 inclusive.
9. Student seats greater than 200 are blocked with explicit copy that Classroom Plan v1/v2 planning caps the cohort at 200 students.
10. Student seats below 5 are blocked with explicit copy that Classroom Plan starts at 5 students.
11. Shared Credits monthly request must be an integer from 0 to 2,000,000 inclusive.
12. Shared Credits copy labels the value as "manual request / planning estimate", not wallet balance, ledger proof, invoice, grant or actual allocation.
13. Generated draft summary includes teacher contact / master planning email, course name, student seats, shared Credits request, LMS provider, and v1 handling mode.
14. Generated draft summary visibly states it is a local v1 stub and does not create teacher master account, students, credits, LMS connection, assignment, gradebook row or billing entry.
15. Manual cohort LMS option is marked as v1 manual handling.
16. Canvas and Moodle options are marked as LTI 1.3 foundation/planned, not connected.
17. 雨课堂 and 学堂在线 options are marked as China LMS foundation/planned, not connected.
18. Page includes a closure checklist for v1 manual cohort: confirm teacher contact and future master-owner candidate, collect roster out-of-band, students register with education email, manually grant/use existing education quota, communicate no LMS gradebook.
19. Page includes privacy/ethics boundaries: student input belongs to students, not Provider training data; teacher sees progress/submission summary, not default raw data download; sensitive human/education data requires IRB or school ethics path.
20. Page includes handoff guidance to Academic Provider Handbook and FAQ, but does not treat docs as legal approval or contract completion.
21. The helper exposes a typed `ClassroomPlanDraftInput`, `ClassroomPlanDraft`, `ClassroomLmsProvider`, LMS metadata, validation result, and constants for seat/credits bounds.
22. Helper validation returns field-specific errors and does not throw for malformed user input.
23. Helper normalizes whitespace and numeric string inputs deterministically.
24. Helper accepts only these LMS provider keys: `manual_cohort`, `canvas`, `moodle`, `yuketang`, `xuetangx`; unknown values return a field-specific error.
25. Helper uses explicit LMS metadata: `manual_cohort` has `availability="manual_v1"` and `connected=false`; every other LMS has `availability="foundation_planned"` and `connected=false`.
26. Helper derives no fields from current wall-clock time, randomness, network, storage or hidden browser state.
27. Student seats and Shared Credits request validation accepts only trimmed ASCII digit strings; it rejects blank strings, signs, decimals, exponents, commas, whitespace-inside digits and unit suffixes.
28. Tests cover valid manual cohort draft generation and all LMS provider states.
29. Tests cover invalid teacher email, course name, student seats below 5, student seats above 200, non-integer seats, blank/decimal/exponent/comma numeric strings, unknown LMS provider, and shared Credits bounds.
30. Page tests cover unauthenticated redirect, successful draft rendering, >200 seat block, manual cohort checklist, LMS planned copy, privacy/ethics copy, no fetch, and no storage writes.
31. Tests confirm the page does not ask for or render student emails, grades, LMS tokens, API keys, JWT, raw roster, billing refs or Provider training payloads.
32. Existing Console navigation remains stable and adds a discoverable Classroom link exactly in `/console/classroom`, `/console/providers`, and `/console/legal-inquiry`; no broad unrelated Console nav rewrite is performed.
33. Layout remains dense Console UI with stable controls on desktop/mobile; long course names and provider labels wrap without horizontal overflow.
34. Implementation introduces no new npm dependency and no package/lockfile changes.
35. No files under `apps/auth-service/**`, `apps/billing-service/**`, `apps/solver-orchestrator/**`, `apps/capability-registry/**`, migrations, generated OpenAPI, infra manifests or CI workflows are modified.
36. Local gates pass: focused Classroom helper/page tests, `/console/providers` and `/console/legal-inquiry` page tests, web typecheck, and `git diff --check`.
37. Post-implementation code review is completed and findings are fixed or explicitly documented in this story.
38. GitHub CI passes, PR is merged, remote branch is deleted, local `main` is synced, and only then this story and sprint status are marked `done` through a separate status-sync commit.

## Tasks / Subtasks

- [x] T1: Add deterministic classroom plan helper (AC: 21-29, 34-35)
  - [x] Define typed draft input/output, LMS metadata and bounds constants.
  - [x] Validate teacher contact email, course name, student seats and shared Credits request.
  - [x] Normalize whitespace and parse numeric strings only through strict ASCII digit validation.
  - [x] Mark manual cohort as v1 manual and all LMS integrations as planned/not connected using fixed provider keys.
  - [x] Add focused helper unit tests.

- [x] T2: Add `/console/classroom` v1 stub page (AC: 1-20, 30-33)
  - [x] Add auth redirect using existing `sessionStorage.jwt_access` read-only pattern.
  - [x] Render dense Console form and generated local draft summary.
  - [x] Render v1 manual cohort checklist, LMS foundation statuses and privacy/ethics boundaries.
  - [x] Avoid all fetch/API/storage writes/query-string/clipboard behavior.
  - [x] Add page tests.

- [x] T3: Add discoverability and docs boundary updates (AC: 20, 32, 34-36)
  - [x] Add Classroom nav link to `/console/classroom`, `/console/providers`, and `/console/legal-inquiry` only.
  - [x] Update Academic Provider Handbook / FAQ to reference `/console/classroom` as v1 planning stub, not full product.
  - [x] Verify no package/lockfile/backend/migration/OpenAPI/infra diff exists.

- [x] T4: Review, gates, and GitHub sync (AC: 36-38)
  - [x] Run local quality gates and fix failures.
  - [x] Run post-implementation code review and fix/document findings.
  - [x] Commit, push, create PR, wait for CI, merge, delete remote branch, and sync local `main`.
  - [x] Mark story and sprint status `done` only after merge/sync through a separate status-sync commit.

## Dev Notes

### Existing Facts

- Console pages are standalone client pages with duplicated header/nav, `sessionStorage.jwt_access` read for auth, and `router.push("/auth/login")` when missing.
- `/console/legal-inquiry` is the closest local form pattern: client-side validation, no raw message echo after success, no storage writes, and safe boundary copy.
- `/console/providers` is the closest dense Console layout pattern and already contains the latest nav shape including Providers, Routing History, Legal Inquiry, invoices and audit logs.
- There is no existing Classroom Plan backend, API client type or route.
- `docs/academic-provider-handbook.md` and `docs/customer-faqs/academic-onboarding-faq.md` already say complete Classroom Plan/LMS gradebook/course code/automatic assignment management is v2+.

### Implementation Guardrails

- Prefer `apps/web/src/lib/classroom-plan.ts` for pure helper logic and `apps/web/src/lib/classroom-plan.test.ts` for helper tests.
- Keep the page in `apps/web/src/app/console/classroom/page.tsx` and `page.test.tsx`.
- Do not modify `apps/web/src/lib/api.ts`; this story has no network API contract.
- Do not add server actions or route handlers.
- Use existing `StatusCard`/`EmptyState` style and plain semantic `section`, `dl`, `ul`, labels, inputs and selects.
- Use `Number.isInteger()` after numeric conversion and reject non-integer, negative, NaN or Infinity values.
- Before numeric conversion, require `/^[0-9]+$/` on the trimmed input. Do not allow `1e3`, `10.0`, `1,000`, `+10`, `-1`, internal spaces, Chinese units or empty strings.
- LMS provider keys are part of the contract: `manual_cohort`, `canvas`, `moodle`, `yuketang`, `xuetangx`. UI labels may be localized, but stored/helper values must use these keys.
- The draft output should expose numeric `studentSeats` and `sharedCreditsMonthlyRequest` values after validation; the page should not separately parse these numbers a second time.
- A generated draft is a local planning summary only. Copy must not say "created", "provisioned", "allocated", "connected", "synced", "graded", "paid", "approved" or "contracted".
- Use "teacher contact / master planning email" in implementation copy. Do not label the input as a real master account, because no account is created by this story.
- Do not ask for student emails or roster in this stub. The manual cohort checklist should say roster collection happens out-of-band.
- Keep nav changes limited to `apps/web/src/app/console/classroom/page.tsx`, `apps/web/src/app/console/providers/page.tsx`, and `apps/web/src/app/console/legal-inquiry/page.tsx`; do not perform broad nav refactors.

### Suggested Commands

```powershell
pnpm --filter @opticloud/web test -- src/lib/classroom-plan.test.ts src/app/console/classroom/page.test.tsx
pnpm --filter @opticloud/web test -- src/app/console/legal-inquiry/page.test.tsx src/app/console/providers/page.test.tsx
pnpm --filter @opticloud/web typecheck
git diff --check
```

## Definition Of Done

- Story file has passed exactly 3 pre-implementation adversarial review rounds and revisions.
- `/console/classroom` provides a safe v1 Classroom Plan planning stub with teacher contact / master planning email, 5-200 student cap, shared Credits request and LMS foundation status.
- Stub does not fake account, billing, LMS, roster, grading or legal-contract completion.
- Helper/page tests cover boundary, drift, data consistency, dependency consistency and closure requirements.
- No backend/API/dependency drift is introduced.
- Post-implementation code review is completed and findings are fixed or explicitly documented.
- Local quality gates and GitHub CI pass.
- Story and sprint status are updated to `done` only after review, gates, CI, merge, branch cleanup, local `main` sync, and separate status-sync closure.

## Story Review Log

### Round 1: Boundary And False-Completion Review

Findings fixed:

- Initial story used "teacher master" wording too broadly, which could be implemented as or read as a real teacher master account. Revised Story, Scope, Out of Scope, ACs, tasks, DoD and guardrails to use "teacher contact / master planning email" and explicitly prohibit teacher master account creation.
- Initial sprint-status update attempted to move the story to `ready-for-dev` before the three mandatory pre-implementation review rounds. Reverted sprint status to `backlog`; the story will move to `ready-for-dev` only after all three rounds pass.
- Initial draft summary prohibition mentioned students/credits/LMS but omitted teacher master account. Revised AC 14 and scope boundaries so the draft cannot imply teacher account creation.

Status: PASS after fixes.

### Round 2: Data Consistency And Drift Review

Findings fixed:

- Initial numeric parsing rules only said "numeric string inputs" and `Number.isInteger()`, allowing JavaScript coercion hazards such as blank strings, `1e3`, `10.0`, `1,000`, signed values, internal whitespace or unit suffixes. Added strict ASCII digit-string validation before numeric conversion and expanded tests.
- Initial LMS requirements named display providers but did not define stable helper keys or output states. Added fixed `ClassroomLmsProvider` keys and explicit `availability` / `connected` metadata for manual and planned LMS providers.
- Initial AC numbering and task mappings lagged after adding provider/numeric validation requirements. Updated AC numbering and task AC references so implementation and tests trace to the right obligations.

Status: PASS after fixes.

### Round 3: Dependency, Discoverability, And Closure Review

Findings fixed:

- Initial story added `/console/classroom` but did not define a concrete discoverability path from existing Console pages. Revised scope, AC 32, tasks and gates so Classroom is linked exactly from the new page, `/console/providers`, and `/console/legal-inquiry`.
- Initial "touched Console pages" wording could invite broad nav refactoring across unrelated pages. Replaced it with an explicit three-file nav boundary and added tests for the two existing touched pages.
- Initial local gate wording made relevant Console page tests conditional. Revised AC 36 and suggested commands so Providers and Legal Inquiry tests always run when nav is changed.

Status: PASS after fixes. Story is ready for development.

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Debug Log References

- Baseline branch: `codex/8-c-7-classroom-plan-v1-stub`.
- Baseline commit: `6c9d03bd6dcb97878ab2a58841a0fb1db386b03f`.
- Story creation analyzed Expert Panel E6, PRD Classroom 5-200/shared Credits references, Architecture Appendix F.5 PR4/PR5/PR8/PR9, UX J4/FG15/LMS references, Academic Provider Handbook, Classroom FAQ, Story 8.C.1 exclusion boundaries, and current Console form/nav patterns.
- 2026-06-04 - Completed pre-implementation adversarial review round 1 and revised teacher-master account boundary plus sprint lifecycle timing.
- 2026-06-04 - Completed pre-implementation adversarial review round 2 and revised numeric parsing, LMS provider metadata and traceability mappings.
- 2026-06-04 - Completed pre-implementation adversarial review round 3 and revised discoverability, nav dependency boundary and gate closure; story is ready for development.
- 2026-06-04 - Story moved to in-progress after exactly three pre-implementation adversarial review rounds.
- 2026-06-04 - RED phase confirmed: focused Classroom helper/page/nav tests failed because the helper/page did not exist and existing Console nav lacked Classroom.
- 2026-06-04 - Implemented deterministic Classroom Plan helper with strict numeric parsing, fixed LMS provider metadata, and no Date/random/storage/network behavior.
- 2026-06-04 - Implemented `/console/classroom` local v1 planning stub page with auth redirect, local draft summary, manual cohort checklist, LMS foundation status, docs handoff and privacy/ethics boundaries.
- 2026-06-04 - Added Classroom nav links only to `/console/classroom`, `/console/providers`, and `/console/legal-inquiry`.
- 2026-06-04 - Updated Academic Provider Handbook and Academic Onboarding FAQ to describe `/console/classroom` as v1 planning stub, not full Classroom Plan.
- 2026-06-04 - Focused local tests passed: `pnpm --filter @opticloud/web test -- src/lib/classroom-plan.test.ts src/app/console/classroom/page.test.tsx src/app/console/legal-inquiry/page.test.tsx src/app/console/providers/page.test.tsx` -> 25 passed.
- 2026-06-04 - Web typecheck passed: `pnpm --filter @opticloud/web typecheck`.
- 2026-06-04 - Whitespace gate passed: `git diff --check`.
- 2026-06-04 - Diff scope checked: no package/lockfile, backend, migration, OpenAPI generated artifact, infra or CI workflow changes.
- 2026-06-04 - Full web regression passed before review fixes: `pnpm --filter @opticloud/web test` -> 246 passed.
- 2026-06-04 - Post-implementation code review found one patch finding: helper contract said malformed input should not throw, but runtime non-string inputs could throw before validation.
- 2026-06-04 - Review fix applied: helper input accepts `unknown`, normalizes non-string values safely, and regression test covers non-string malformed input.
- 2026-06-04 - Post-review focused tests passed: 26 passed; web typecheck passed; `git diff --check` passed.
- 2026-06-04 - Story and sprint status moved to code-review pending GitHub sync.
- 2026-06-04 - PR #167 passed GitHub CI: changes, lint, ts-typecheck, e2e, matrix-detect, build-and-sbom (auth-service), error-i18n-validation, and gtm-toolkit-validation passed; unrelated service jobs were skipped by matrix.
- 2026-06-04 - PR #167 squash-merged to `main` at merge commit `98ff7b082732216ee853f156f23e95ff6add9726`; remote feature branch deleted; local `main` synced to `origin/main`.
- 2026-06-04 - Story and sprint status marked `done` via separate status-sync commit after merge/sync closure.

### Completion Notes List

- Initial story draft created.
- Round 1 pre-implementation review completed and story revised.
- Round 2 pre-implementation review completed and story revised.
- Round 3 pre-implementation review completed and story revised.
- Story is ready for development.
- Story moved to in-progress after exactly three pre-implementation adversarial review rounds.
- Classroom Plan v1 helper and page implemented.
- Classroom nav discoverability added to the three story-scoped Console pages.
- Academic docs updated to point at `/console/classroom` as a v1 planning stub.
- Focused tests, web typecheck and diff check pass locally.
- Full web regression passed.
- Post-implementation code review completed; malformed non-string helper input finding fixed and verified.
- GitHub CI passed; PR #167 merged; remote branch deleted; local `main` synced.
- Story closed as `done` after merge/sync in this separate status-sync.

### File List

- _bmad-output/stories/8-c-7-classroom-plan-v1-stub.md
- _bmad-output/stories/sprint-status.yaml
- apps/web/src/lib/classroom-plan.ts
- apps/web/src/lib/classroom-plan.test.ts
- apps/web/src/app/console/classroom/page.tsx
- apps/web/src/app/console/classroom/page.test.tsx
- apps/web/src/app/console/providers/page.tsx
- apps/web/src/app/console/providers/page.test.tsx
- apps/web/src/app/console/legal-inquiry/page.tsx
- apps/web/src/app/console/legal-inquiry/page.test.tsx
- docs/academic-provider-handbook.md
- docs/customer-faqs/academic-onboarding-faq.md

## Change Log

- 2026-06-04 - Initial story draft created for Classroom Plan v1 stub.
- 2026-06-04 - Round 1 pre-implementation review revised teacher master account wording and sprint lifecycle boundary.
- 2026-06-04 - Round 2 pre-implementation review revised numeric validation, LMS provider states and AC/task traceability.
- 2026-06-04 - Round 3 pre-implementation review revised Console discoverability, nav boundary and local gate closure.
- 2026-06-04 - Story status moved to in-progress after pre-implementation review closure.
- 2026-06-04 - Implemented Classroom Plan v1 helper/page, scoped Console nav links, docs updates and focused tests.
- 2026-06-04 - Completed post-implementation code review, fixed non-string malformed input handling, and moved story to code-review pending GitHub sync.
- 2026-06-04 - PR #167 passed CI, merged to `main`, branch cleanup and local sync completed; story status moved to `done`.

## Post-Implementation Code Review

### Findings

- [x] [Review][Patch] `buildClassroomPlanDraft()` promised field-specific validation without throwing for malformed user input, but `ClassroomPlanDraftInput` and helper normalization assumed string values and would throw on runtime non-string input before returning validation errors. Fixed by accepting `unknown`, safely normalizing non-string values, and adding regression coverage.

### Outcome

Changes requested internally; finding fixed and focused gates rerun.
