---
story_key: 8-c-9-teaching-grading-api
epic_num: 8
story_num: C.9
epic_name: Teaching + Provider Routing + Legal + Algorithm Library
status: done
baseline_commit: 2ff7e83fe3cd26615acca1514c397ae982256712
priority: High
type: Teaching Mode Grading API
created_by: bmad-create-story
created_at: 2026-06-04
sources:
  - _bmad-output/planning/epics.md (Expert Panel E12 / Story 8.C.9 brief)
  - _bmad-output/planning/prd.md (Classroom Plan / teaching mode growth boundary)
  - _bmad-output/planning/ux-design-specification.md (J4 classroom dashboard / student privacy notes)
  - _bmad-output/stories/8-c-1-mode-teaching-explain.md
  - _bmad-output/stories/8-c-7-classroom-plan-v1-stub.md
  - apps/solver-orchestrator/src/solver_orchestrator/routes.py
  - apps/solver-orchestrator/src/solver_orchestrator/schemas.py
  - apps/solver-orchestrator/src/solver_orchestrator/models.py
  - apps/solver-orchestrator/tests/test_teaching_mode.py
  - apps/web/src/lib/api.ts
---

# Story 8.C.9 - Teaching Mode Grading API

Status: done

## Story

**作为** 高校教师或 Academic Relations / Customer Success 人员，
**我希望** 能对当前账号下的 Teaching Mode 学生任务进行批量评分，
**从而** 在不伪造教师 master account、学生账号、Roster、LMS 或共享 Credits 的前提下，把课堂作业的提交摘要、评分和复核记录形成一个可查询的 v1 API 闭环。

## Context

Expert Panel E12 只给出 brief："Teaching Mode Grading API (教师 master account batch review 学生 task + grade) — v1 末"。PRD 与 UX 把完整 Classroom Plan、教师 dashboard、学生账号、共享 Credits、LMS gradebook 和课程管理放在 Growth/v2+，但 v1 末需要有一个可执行的 grading API surface。

Story 8.C.1 已实现 `POST /v1/optimizations?mode=teaching`，将 teaching metadata 持久化在 `optimizations.input_payload._system.teaching`，并在 POST/GET/idempotency replay 返回相同 teaching 信息。Story 8.C.7 已明确 Classroom Plan v1 是本地 planning stub，不创建 teacher master account、学生账号、Roster、共享 Credits、LMS/LTI 或 grading API。

因此 8.C.9 的最小闭环不是完整 classroom 产品，而是一个真实后端 API：当前 API key 所属账号作为 v1 teacher owner，提交一组 opaque `student_ref + optimization_id`，服务端只读取同 owner 的 completed teaching optimization，按固定 v1 rubric 生成并持久化 batch grading result。Academic Relations / Customer Success 在本 story 中不是管理员代评分角色；他们只能使用自己账号/API key 做 demo 或人工 cohort 支持，不能跨租户批改。API 不接收或返回学生姓名、邮箱、学号、Roster 原文、原始作业数据、solution payload、billing charge id、LMS token 或 Provider training data。

## Scope

1. 新增 solver-orchestrator Teaching Grading persistence。
   - 在 `infra/local-init/02-solver-schema.sql` 增加 idempotent local schema DDL。
   - 在 `apps/solver-orchestrator/src/solver_orchestrator/models.py` 增加 ORM models。
   - 新增 `teaching_grading_batches`、`teaching_grading_items` 和 `teaching_grading_idempotency_keys`。
   - 表按 `user_id` owner scope，不引入 teacher/student account FK。
   - DB rows persist only opaque refs, grading criteria JSON, score, status, bounded feedback, timestamps and FK references; no raw optimization payload snapshots.
   - `teaching_grading_items` enforces stable uniqueness for `(grading_batch_id, item_index)`, `(grading_batch_id, student_ref)`, and `(grading_batch_id, optimization_id)`.
   - `teaching_grading_idempotency_keys` primary key is `(user_id, key)` and stores the normalized request hash plus `grading_batch_id`.
2. 新增 API schema。
   - `TeachingGradingBatchCreateRequest`
   - `TeachingGradingSubmission`
   - `TeachingGradingBatchResponse`
   - `TeachingGradingItemResponse`
   - Fixed v1 rubric result fields.
   - Pydantic validators should raise standard request validation errors where possible so existing FastAPI RFC 7807 validation handling remains single-source.
3. 新增 authenticated endpoints。
   - `POST /v1/teaching/grading-batches`
   - `GET /v1/teaching/grading-batches/{grading_batch_id}`
   - Auth uses existing `Authorization: Bearer sk-...` API key verification.
   - Scope uses existing `optimize:write` because v1 API creates a grading record derived from optimization tasks.
   - Do not change CORS settings: required request headers are existing `Authorization`, `Content-Type`, and optional `Idempotency-Key`.
4. Implement deterministic fixed rubric v1.
   - Input items contain only `student_ref` and `optimization_id`.
   - `assignment_ref` is an opaque classroom assignment reference controlled by the caller.
   - API validates `student_ref` and `assignment_ref` as non-PII opaque refs using a restricted character set.
   - Opaque refs must use prefix-style identifiers such as `assign-001` or `stu-001`; tests must reject email-like, whitespace, slash-separated and Chinese/raw free-text examples.
   - API loads only optimizations owned by the current `user_id`.
   - Only completed optimization rows with `_system.teaching.mode == "teaching"` are gradable.
   - Each item stores criterion results and a final numeric score without storing raw input/solution payloads. The code may inspect booleans such as whether `solution is not None`, but must not copy solution content into grading rows or responses.
   - `rubric_version` defaults to `teaching-grading-v1`; any other value is rejected before writes.
5. Implement per-user idempotency.
   - `Idempotency-Key` replay with identical request body returns the existing batch response.
   - Same user + same key + different request body returns 409 RFC 7807.
   - Idempotency keys are scoped by `user_id`; different users may reuse the same key without cross-tenant collision.
   - The idempotency hash is computed from the normalized Pydantic request body after default `rubric_version` is applied, so omitted default and explicit `teaching-grading-v1` are replay-compatible.
   - Batch row, item rows and idempotency key row are written in one transaction; partial item writes are not allowed.
6. Add web API helper types only.
   - Add TS types and helpers in `apps/web/src/lib/api.ts`.
   - No UI page, no Console nav, no Classroom page fetch.
7. Add focused tests.
   - Backend API tests for happy path, non-teaching/non-completed/missing/cross-owner rows, validation, idempotency, persistence and no sensitive data exposure.
   - Web API helper tests for request path, headers and response typing.
8. Sprint lifecycle.
   - After exactly three pre-implementation review rounds and revisions, update this story and sprint status to `ready-for-dev`.
   - During implementation, update status to `in-progress`, then `code-review`, and only after CI/merge/branch cleanup/local main sync use a separate status-sync commit to mark `done`.

## Out Of Scope

- Teacher master account backend model, teacher role management, student account creation/invite, course code, Roster CSV upload, classroom membership table or student email verification.
- LMS/LTI 1.3 launch, OAuth/SSO, Canvas/Moodle/雨课堂/学堂在线 API integration, LMS gradebook callback or assignment deep link.
- Shared Credits, student quota allocation, billing ledger changes, payment/subscription logic or teaching discount changes.
- Provider training data, model fine-tuning, student raw data collection, raw optimization input/solution export or plagiarism detection.
- UI page, Console classroom integration, teacher dashboard, grading table component, file upload, CSV import/export or notification/email.
- Manual grade override, teacher comments, rubric authoring UI/API, per-course settings, multiple graders, admin impersonation or audit approval workflow.
- OpenAPI generated client, new service, new package dependency, infra/CI workflow changes or auth-service schema changes.
- CORS changes, error catalog/i18n catalog changes, generated SDK/OpenAPI artifacts or browser-visible UI behavior.

## Acceptance Criteria

1. `infra/local-init/02-solver-schema.sql` creates `teaching_grading_batches`, `teaching_grading_items`, and `teaching_grading_idempotency_keys` idempotently.
2. Schema includes FK from items to batches with cascade delete, FK from items to optimizations with no cascade requirement, owner indexes, `(user_id, created_at DESC)` batch index, and unique constraints/indexes for `(grading_batch_id, item_index)`, `(grading_batch_id, student_ref)`, `(grading_batch_id, optimization_id)`, and `(user_id, key)`.
3. `models.py` defines ORM models matching the local schema, including owner indexes and idempotency key table.
4. `POST /v1/teaching/grading-batches` requires a valid API key and `optimize:write` scope.
5. `GET /v1/teaching/grading-batches/{grading_batch_id}` requires a valid API key and returns only batches owned by the current user.
6. A valid request accepts `assignment_ref`, optional `rubric_version`, and `submissions`.
7. `rubric_version` defaults to `teaching-grading-v1`; any unsupported rubric version returns 422 and writes no grading or idempotency rows.
8. Omitting `rubric_version` and explicitly passing `teaching-grading-v1` produce the same normalized idempotency hash for otherwise identical requests.
9. `submissions` length is 1-100.
10. Each submission contains only `student_ref` and `optimization_id`.
11. `assignment_ref` and `student_ref` reject emails, whitespace, slashes, Chinese/raw free text and arbitrary prose by allowing only `[A-Za-z0-9._:-]` with bounded lengths and requiring at least one separator character from `._:-`.
12. Duplicate `student_ref` values in one batch return 422 and do not write rows.
13. Duplicate `optimization_id` values in one batch return 422 and do not write rows.
14. Reusing the same `assignment_ref` in a later non-idempotent request is allowed and creates a new batch; assignment refs are labels, not uniqueness keys.
15. A completed owner-scoped optimization created through `mode=teaching` grades as `graded`.
16. A completed owner-scoped optimization without teaching metadata grades as `not_gradable` with score 0 and a bounded reason.
17. A queued, in-progress, failed, timeout, cancelled or otherwise non-completed teaching optimization grades as `not_gradable` with score 0 and a bounded reason.
18. A missing or cross-owner `optimization_id` grades as `not_gradable` with score 0 without revealing whether the row exists for another tenant.
19. A batch with mixed gradable and not-gradable submissions still returns 201 with per-item statuses rather than failing the whole batch after validation has passed.
20. The response contains `grading_batch_id`, `assignment_ref`, `rubric_version`, `item_count`, `graded_count`, `not_gradable_count`, `created_at`, and ordered `items`.
21. `created_at` values are the persisted DB timestamps and are identical across POST response, GET response and idempotency replay.
22. Response item order matches request submission order.
23. Each response item contains `index`, `student_ref`, `optimization_id`, `grading_status`, `score`, `max_score`, `criteria`, and `feedback_zh`.
24. `max_score` is fixed at 100 for `teaching-grading-v1`.
25. `score` is numeric, non-negative, <= `max_score`, and rounded deterministically to 2 decimal places.
26. The fixed v1 rubric has exactly four criteria: `teaching_mode` 25 points, `completed_status` 25 points, `solution_available` 25 points, and `explanation_ready` 25 points.
27. `explanation_ready` is true only when persisted teaching metadata contains `principle_explanation` with non-empty `summary_zh`.
28. `solution_available` may only inspect whether a solution exists; it must not persist or return solution content.
29. Criteria results are stored and replayed exactly by GET and idempotency replay.
30. Public response and DB grade rows do not contain `_system`, raw `input_payload`, `solution`, `objective`, billing charge ids, JWT/API key material, email, phone, LMS token, Roster content or Provider training payloads.
31. `POST` persists exactly one batch row, one item row per submission, and one idempotency row when `Idempotency-Key` is present on success.
32. Batch, item and idempotency writes are atomic: an `IntegrityError` or later write failure leaves no partial grading batch/items/idempotency row.
33. `GET` on a missing or cross-owner grading batch returns 404 RFC 7807 without leaking ownership.
34. `Idempotency-Key` identical replay returns the existing batch response and does not insert duplicate batch or item rows.
35. `Idempotency-Key` same user + same key + different request body returns 409 RFC 7807.
36. Same `Idempotency-Key` may be reused by a different user without collision or data leakage.
37. Concurrent identical creates with the same user/key either return one created response and one replay response for the same batch, or one created response and one 409 idempotency conflict; they must not create duplicate batches.
38. Request validation failures do not create grading rows or idempotency rows.
39. The API does not call billing-service, auth-service write endpoints, Provider services, LMS endpoints or solver execution.
40. Existing `POST /v1/optimizations?mode=teaching` behavior, teaching discount behavior, GET replay and idempotency semantics remain unchanged.
41. Request validation errors use the existing FastAPI/RFC 7807 validation path and include bounded `errors[]`; no custom ad hoc 422 response shape is introduced for Pydantic validation.
42. No CORS changes are required or made; web helper only uses currently allowed headers.
43. `apps/web/src/lib/api.ts` exposes typed request/response contracts and helpers for create/get grading batch.
44. Web helper sends `POST /v1/teaching/grading-batches` with `Authorization` and optional `Idempotency-Key`.
45. Web helper sends `GET /v1/teaching/grading-batches/{grading_batch_id}` with `Authorization`.
46. No UI route, Console page, nav link, package dependency, lockfile, OpenAPI generated artifact, infra workflow, CORS setting, error catalog/i18n catalog, auth-service file or billing-service file is changed.
47. Backend tests cover happy path, item ordering, GET replay, non-teaching, non-completed, missing/cross-owner masking, validation, idempotency replay/conflict, cross-user idempotency isolation, normalized hash default compatibility, allowed assignment-ref reuse, atomic write failure behavior, concurrent same-key behavior and sensitive-data exclusion.
48. Web tests cover helper URL/header/body behavior and response passthrough.
49. Local gates pass: focused teaching grading backend tests, existing teaching mode regression tests, focused web API tests, solver ruff/format, solver mypy, web typecheck, and `git diff --check`.
50. Post-implementation code review is completed and findings are fixed or explicitly documented.
51. GitHub CI passes, PR is merged, remote branch is deleted, local `main` is synced, and only then this story and sprint status are marked `done` through a separate status-sync commit.

## Tasks / Subtasks

- [x] T1: Add Teaching Grading persistence and schema contract (AC: 1-3, 30-32, 38-39, 41-42, 46)
  - [x] Add idempotent local schema DDL.
  - [x] Add ORM models and imports.
  - [x] Add Pydantic request/response schemas with `extra="forbid"` where applicable.

- [x] T2: Add grading API behavior (AC: 4-42)
  - [x] Implement owner-scoped POST endpoint.
  - [x] Implement owner-scoped GET endpoint.
  - [x] Implement deterministic fixed v1 rubric and no-sensitive-data response shape.
  - [x] Implement per-user idempotency replay and conflict handling.

- [x] T3: Add web API helper types (AC: 43-46, 48)
  - [x] Add TS request/response types.
  - [x] Add `createTeachingGradingBatch` and `getTeachingGradingBatch` helpers.
  - [x] Add focused helper tests.

- [ ] T4: Tests, review, gates, and GitHub sync (AC: 47, 49-51)
  - [x] Add focused backend tests.
  - [x] Run required local gates and fix failures.
  - [x] Run post-implementation code review and fix/document findings.
  - [ ] Commit, push, create PR, wait for CI, merge, delete remote branch, and sync local `main`.
  - [ ] Mark story and sprint status `done` only after merge/sync through a separate status-sync commit.

## Dev Notes

### Existing Facts

- `POST /v1/optimizations?mode=teaching` is a teaching profile over existing sync execution mode. Public execution `mode` remains sync/async-only; teaching semantics live under `teaching.mode`.
- Teaching metadata is persisted under `optimizations.input_payload._system.teaching` and replayed through optimization GET.
- Existing auth path is `verify_api_key()` + `require_scope("optimize:write", scopes)`.
- Existing batch/idempotency patterns in `routes.py` scope idempotency by `(user_id, key)`.
- The repo uses append-only idempotent SQL in `infra/local-init/02-solver-schema.sql`, not an Alembic migration path.
- Existing tests seed `users` and `api_keys` directly, then override `get_session` with an `AsyncSession`.
- Existing response builders use ISO datetime strings; grading response should follow that style but source timestamps from persisted rows.
- `apps/solver-orchestrator/src/solver_orchestrator/main.py` already allows CORS headers `Authorization`, `Content-Type`, `Accept-Language`, `Idempotency-Key`, and `X-Billing-Charge-Id`; grading helpers do not need a new header.

### Implementation Guardrails

- Treat the current API key owner as the v1 teacher owner. Do not introduce a real teacher master account model, admin impersonation path or Customer Success cross-tenant grading.
- Treat `student_ref` as an opaque caller-defined reference. It must not accept email-like, slash-separated or free-text PII, and docs/copy in responses must call it an opaque reference rather than a name.
- Do not read or expose raw optimization `input_payload`, `solution`, `objective`, billing metadata or `_system`.
- Cross-owner optimization ids and missing optimization ids must collapse to the same `not_gradable` item result.
- Keep grading deterministic and synchronous; do not invoke solver execution.
- Do not update optimization rows when grading. Grading records are append-only derived records.
- Use fixed rubric version `teaching-grading-v1`; reject unsupported versions before DB writes instead of silently drifting.
- Keep `teaching-grading-v1` rubric weights exact: 25 points each for teaching metadata, completed status, solution availability and explanation readiness.
- Keep item order stable by storing `item_index`.
- Build response bodies from persisted batch/item rows after flush, not from transient request objects, so GET and replay have identical shape.
- Compute idempotency hashes from `request.model_dump(mode="json")` after Pydantic defaults, sorted and compact JSON.
- Do not make `(user_id, assignment_ref)` unique; the same assignment label may have multiple grading batches over time.
- Keep route naming under `/v1/teaching/grading-batches` so it does not collide with `/v1/optimizations/batch`.
- Prefer Pydantic field/model validators for request validation so the existing FastAPI validation exception handler produces the error envelope. Use explicit RFC 7807 helpers only for domain conflicts such as idempotency mismatch and not-found.
- Do not add error catalog entries unless a new shared catalog key is truly needed. This story can use existing validation handling and bounded domain error titles.
- Leave OpenAPI generated artifacts untouched; this repo has not been using generated client updates for these additive API-helper stories.
- Do not update `sprint-status.yaml` to `done` until PR merge, remote branch deletion and local `main` sync are complete.

### Suggested Commands

```powershell
uv run --directory apps/solver-orchestrator pytest tests/test_teaching_grading_api.py tests/test_teaching_mode.py -q
uv run --directory apps/solver-orchestrator ruff check src tests/test_teaching_grading_api.py tests/test_teaching_mode.py
uv run --directory apps/solver-orchestrator ruff format --check src tests/test_teaching_grading_api.py tests/test_teaching_mode.py
uv run --directory apps/solver-orchestrator mypy src
pnpm --filter @opticloud/web test -- src/lib/api-teaching-grading.test.ts
pnpm --filter @opticloud/web typecheck
git diff --check
```

## Definition Of Done

- Story file has passed exactly 3 pre-implementation adversarial review rounds and revisions.
- Teaching Grading API creates and replays owner-scoped grading batches for existing teaching optimizations.
- The implementation does not create teacher/student accounts, roster storage, LMS integration, shared Credits, billing mutations or UI.
- Missing and cross-owner optimization ids are indistinguishable in grading output.
- API response and persisted grade rows contain no raw optimization payloads or student PII fields.
- Idempotency replay/conflict behavior is per-user and regression-tested.
- Post-implementation code review is completed and findings are fixed or explicitly documented.
- Local quality gates and GitHub CI pass.
- Story and sprint status are updated to `done` only after review, gates, CI, merge, branch cleanup, local `main` sync, and separate status-sync closure.

## Story Review Log

### Round 1: Boundary And False-Completion Review

Findings fixed:

1. The initial story mentioned Academic Relations / Customer Success but did not prevent cross-tenant admin-like grading. Revised context/out-of-scope/guardrails to make the current API key owner the only v1 teacher owner.
2. The initial rubric was named but not executable. Added exact `teaching-grading-v1` criteria, weights and `max_score=100`.
3. Unsupported `rubric_version` was only a guardrail, not an acceptance criterion. Added pre-write rejection AC.
4. `solution_available` could be implemented by storing solution payloads. Revised scope and ACs to allow boolean inspection only and prohibit persistence/response of solution content.
5. Opaque ref validation allowed plain alphanumeric names such as `zhangsan`. Tightened AC to require a separator and reject Chinese/raw free text examples.
6. The story did not define whether mixed gradable/not-gradable submissions should fail the whole batch. Added per-item closure: validation passes, batch returns 201 with per-item statuses.
7. Persistence scope did not explicitly say grade rows avoid raw optimization snapshots. Added DB row content boundary.
8. Manual grade override/rubric authoring was out of scope for UI but not clearly out of scope for API. Revised out-of-scope.
9. The term `student_ref` could be displayed as a real student identity. Added guardrail to label it as an opaque reference.
10. AC numbering and task references drifted after the new hardening requirements. Renumbered and realigned task AC references.

Status: PASS after fixes.

### Round 2: Data Consistency And Drift Review

Findings fixed:

1. The first revision did not require DB uniqueness for item order, student refs or optimization ids inside a batch. Added explicit unique constraints/indexes.
2. Idempotency hashing did not specify normalized defaults, so omitted `rubric_version` could conflict with explicit default. Added normalized Pydantic JSON hash requirement and AC.
3. The story did not require atomic batch/item/idempotency writes. Added transaction/rollback AC and tests.
4. `created_at` could drift if response builders regenerated timestamps. Added persisted timestamp replay requirement.
5. It was unclear whether `assignment_ref` was unique. Clarified it is a label and can be reused across separate batches.
6. `explanation_ready` was subjective. Defined it from persisted teaching metadata `principle_explanation.summary_zh`.
7. Idempotency success did not specify idempotency row creation count. Added one-row-on-success requirement.
8. Concurrent same-key creates could create duplicate batches without a database-backed contract. Added concurrency acceptance boundary.
9. GET/idempotency replay could be assembled from request objects instead of persisted rows. Added implementation guardrail.
10. Backend test list did not cover normalized default hash, assignment reuse, atomic write failure or concurrent same-key behavior. Expanded AC 45.

Status: PASS after fixes.

### Round 3: Dependency Consistency And Closure Review

Findings fixed:

1. The second revision did not explicitly say whether CORS needed changes for the new web helper. Added a dependency note and AC: existing headers are sufficient, no CORS change.
2. Validation could drift into custom ad hoc 422 responses. Added a requirement to use existing FastAPI/RFC 7807 validation handling for Pydantic request validation.
3. Error catalog/i18n changes could be introduced unnecessarily. Added guardrail to avoid catalog changes unless truly needed.
4. OpenAPI/generated artifacts were already broadly out of scope but not tied to the web helper decision. Added a closure note that this story follows local TS helper patterns, not generated client updates.
5. Sprint lifecycle was not explicit after pre-implementation review. Added lifecycle requirement: after exactly three review rounds, mark story and sprint `ready-for-dev`; implementation later moves to `in-progress`/`code-review`.
6. The out-of-scope list omitted CORS and error catalog/i18n files, which are dependency surfaces for an API story. Added them.
7. Task AC references drifted after dependency hardening. Realigned them.
8. Backend tests did not explicitly require validation-envelope consistency. Covered through AC 41 and validation tests.
9. Web helper dependency on `Content-Type` and `Idempotency-Key` was implicit. Added header guardrail.
10. Closure still depended on post-merge separate status sync; preserved and reasserted in scope and DoD.

Status: PASS after fixes. Story is ready for development.

## Post-Implementation Code Review (AI)

Date: 2026-06-04

Outcome: APPROVED FOR PR after fixes. Closure completed after GitHub CI, merge, remote branch deletion and local `main` sync.

Findings fixed:

1. HIGH - Rejected `assignment_ref` / `student_ref` values were echoed in RFC 7807 validation `errors[].value`, which could leak PII-like rejected input such as emails or names. Fixed by redacting validation values for those field names in `error_responses.py` and strengthened teaching grading validation tests to assert rejected values do not appear anywhere in the response body.
2. MEDIUM - The schema satisfied owner scoping through batch owner lookup and idempotency primary key, but `teaching_grading_items` lacked an explicit owner/batch/index lookup index despite AC wording requiring owner indexes. Added `idx_teaching_grading_items_user_batch_index` to local-init SQL, ORM metadata and test schema setup/assertions.

Review verification:

- File List matches git changes, including new story/test files.
- ACs rechecked against DDL, ORM, schemas, routes, tests and web helper.
- Sensitive data boundary rechecked: grading rows/responses do not persist or expose `_system`, raw `input_payload`, `solution`, billing charge IDs, API/JWT material, email/phone, LMS tokens, Roster content or provider training payloads.
- Local gates passed after review fixes.

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Debug Log References

- Baseline branch: `codex/8-c-9-teaching-grading-api`.
- Story creation analyzed Expert Panel E12, PRD/UX classroom boundaries, Story 8.C.1 teaching metadata and discount behavior, Story 8.C.7 classroom stub boundaries, solver routes/schema/models, teaching mode tests and web API helper patterns.
- 2026-06-04 - Completed pre-implementation adversarial review round 1 and revised teacher-owner, opaque-ref, fixed-rubric and no-raw-solution boundaries.
- 2026-06-04 - Completed pre-implementation adversarial review round 2 and revised idempotency normalization, DB uniqueness, atomicity and replay-stability requirements.
- 2026-06-04 - Completed pre-implementation adversarial review round 3 and revised dependency consistency, validation envelope, CORS/no-generated-artifact and sprint lifecycle requirements.
- 2026-06-04 - RED phase confirmed: backend grading API tests failed with route 404 and web helper tests failed because `createTeachingGradingBatch` / `getTeachingGradingBatch` did not exist.
- 2026-06-04 - Implemented teaching grading persistence models/schema and idempotent local-init SQL for batches, items and per-user idempotency keys.
- 2026-06-04 - Implemented owner-scoped `POST /v1/teaching/grading-batches` and `GET /v1/teaching/grading-batches/{grading_batch_id}`.
- 2026-06-04 - Implemented deterministic `teaching-grading-v1` rubric, opaque ref validation, missing/cross-owner masking, no raw payload/solution exposure, and persisted response replay.
- 2026-06-04 - Implemented web API helper types and functions for create/get teaching grading batches.
- 2026-06-04 - Added backend tests for happy path, GET replay, non-teaching/non-completed/missing/cross-owner masking, validation, normalized idempotency replay/conflict, cross-user idempotency isolation, assignment-ref reuse, concurrent same-key behavior, atomic rollback and sensitive-data exclusion.
- 2026-06-04 - Added web helper tests for POST/GET URL, headers, body and response passthrough.
- 2026-06-04 - Local validation passed: teaching grading + teaching mode tests (20 passed), web helper tests (2 passed), solver ruff check/format, solver mypy, web typecheck and `git diff --check`.
- 2026-06-04 - Story moved to code-review after implementation and local validation.
- 2026-06-04 - Post-implementation code review found and fixed validation-value redaction for opaque refs and added an explicit teaching grading item owner index.
- 2026-06-04 - Local validation re-run after review fixes: teaching grading + teaching mode tests (20 passed), web helper tests (2 passed), solver ruff check/format, solver mypy, web typecheck and `git diff --check`.
- 2026-06-04 - PR #169 initial CI found full-repo mypy redundant-cast failures in existing touched files; removed redundant casts and validated with CI-equivalent `uv run mypy apps packages`.
- 2026-06-04 - PR #169 passed GitHub CI, was squash-merged to `main` as `6779e34`, remote branch `codex/8-c-9-teaching-grading-api` was deleted, and local `main` was synced.

### Completion Notes List

- Initial story draft created.
- Round 1 pre-implementation review completed and story revised.
- Round 2 pre-implementation review completed and story revised.
- Round 3 pre-implementation review completed and story revised.
- Story is ready for development.
- Story moved to in-progress after exactly three pre-implementation adversarial review rounds.
- Teaching Grading API implementation completed.
- Focused backend and frontend tests pass.
- Solver ruff/format, solver mypy, web typecheck and diff check pass locally.
- Post-implementation code review completed locally; findings fixed and gates re-run.
- PR #169 initial CI mypy failure fixed locally; CI-equivalent mypy now passes.
- PR #169 passed CI, merged, remote branch deleted, and local `main` synced; story is now closed through separate status-sync commit.

### File List

- _bmad-output/stories/8-c-9-teaching-grading-api.md
- _bmad-output/stories/sprint-status.yaml
- infra/local-init/02-solver-schema.sql
- apps/solver-orchestrator/src/solver_orchestrator/models.py
- apps/solver-orchestrator/src/solver_orchestrator/schemas.py
- apps/solver-orchestrator/src/solver_orchestrator/routes.py
- apps/solver-orchestrator/src/solver_orchestrator/error_responses.py
- apps/solver-orchestrator/src/solver_orchestrator/main.py
- apps/solver-orchestrator/src/solver_orchestrator/repro.py
- apps/solver-orchestrator/tests/test_teaching_grading_api.py
- apps/web/src/lib/api.ts
- apps/web/src/lib/api-teaching-grading.test.ts

## Change Log

- 2026-06-04 - Initial story draft created for Teaching Mode Grading API.
- 2026-06-04 - Round 1 pre-implementation review revised teacher-owner, opaque-ref, fixed-rubric and no-raw-solution boundaries.
- 2026-06-04 - Round 2 pre-implementation review revised idempotency normalization, DB uniqueness, atomicity and replay-stability requirements.
- 2026-06-04 - Round 3 pre-implementation review revised dependency consistency, validation envelope, CORS/no-generated-artifact and sprint lifecycle requirements.
- 2026-06-04 - Story status moved to in-progress after pre-implementation review closure.
- 2026-06-04 - Implemented Teaching Mode Grading API backend persistence/routes/rubric/idempotency and web API helper types; local gates pass; status moved to code-review.
- 2026-06-04 - Post-implementation code review completed locally; fixed opaque-ref validation redaction and item owner index; gates pass.
- 2026-06-04 - Fixed PR #169 CI mypy redundant-cast failures; CI-equivalent mypy and local gates pass.
- 2026-06-04 - PR #169 passed CI, merged to main, remote branch deleted, local main synced; story marked done.
