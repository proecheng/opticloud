---
story_key: 8-c-3-legal-inquiry-sla
epic_num: 8
story_num: C.3
epic_name: Teaching + Provider Routing + Legal + Algorithm Library
status: code-review
baseline_commit: 6125eaacc55a6a62db35b559ac22ed7648be8bc1
priority: High
type: FR O10 legal inquiry SLA
created_by: bmad-create-story
created_at: 2026-06-04
sources:
  - _bmad-output/planning/epics.md (Epic 8.C / Story 8.C.3)
  - _bmad-output/planning/prd.md (FR O10 / Journey 5 legal side path)
  - _bmad-output/planning/architecture.md (J5 / docs/customer-faqs / Appendix C)
  - _bmad-output/planning/implementation-readiness-report-2026-05-17-v2.md (O10 stage and service mapping)
  - docs/legal-templates.md (FR O10 legal ownership and FAQ linkage)
  - docs/customer-faqs/commercial-buyer-faq.md
  - docs/enterprise-gtm-toolkit.md
  - apps/billing-service/src/billing_service/routes.py
  - apps/billing-service/src/billing_service/models.py
  - apps/billing-service/src/billing_service/schemas.py
  - apps/billing-service/src/billing_service/auth_dep.py
  - apps/web/src/lib/api.ts
  - apps/web/src/app/console/data-exports/page.tsx
  - apps/web/src/app/console/providers/page.tsx
---

# Story 8.C.3 - Team+ 法务问询 <=24h SLA

Status: code-review

## Story

**作为** Team 或 Enterprise 计划用户，
**我希望** 在 Console 中提交法务问询，并收到一个带 24 小时响应截止时间的受理凭证，
**从而** 能把 PIPL、GDPR、等保 2.0、数据出境、DPA、许可合规等采购/合规问题交给 Customer Success/法务团队处理，而产品不会向非 Team+ 用户承诺法务 SLA，也不会伪造真实 Linear 集成结果。

## Context

Epic 8.C.3 的原始 AC 是：Given Team+ user / When `POST /v1/legal/inquiry` / Then 24h SLA 响应 + Linear ticket。PRD Journey 5 还要求法务问答库、数据流图模板、数据出境承诺函和 Team+ 24h 法务问询 SLA。现有仓库已经有 `docs/legal-templates.md`、`docs/customer-faqs/` 和 Team/Enterprise plan catalog，但没有真实 Linear API client、Linear token 配置、外部 ticket worker 或 legal inbox integration。

因此本 story 的最小闭环是：在 billing-service 内按 Team+ entitlement 接收法务问询，持久化一条受理记录，生成 Linear-ready 内部 ticket reference 和安全 outbox event，返回 24h SLA due timestamp，并提供 Console 表单入口和 FAQ 文档。不要声称已经创建了外部 Linear issue；真实 Linear API 投递属于后续集成故事。

## Scope

1. Backend public route。
   - 在 billing-service 进程内新增 `POST /v1/legal/inquiry`，保持 epics 指定的 public path，不放到 `/v1/billing/...` 下。
   - 使用现有 `require_user`，接受 auth-service JWT 或 internal-service bridge；Console 使用 JWT。
   - 要求 `Idempotency-Key` header，沿用 billing-service UUID idempotency format 和 `billing_idempotency_keys`。
2. Team+ entitlement。
   - Team+ 定义为当前用户存在 active `billing_subscriptions`，`plan_code in {"team", "enterprise"}`，且 `current_period_end > now()`。
   - implicit Free、Free、Starter、Pro、canceled、expired、period 已过期的 active row 全部拒绝，返回 RFC 7807 403，不创建 inquiry/outbox/idempotency cached success。
3. Durable legal inquiry record。
   - 新增 `legal_inquiries` table、SQLAlchemy model 和 schemas。
   - 记录用户提交的法务内容以便人工处理，但 response 和 outbox 不回显 raw `subject` / `message` / `contact_email`。
   - 字段必须有长度、枚举和状态约束；不得把请求 raw body 放进 idempotency row、outbox、logs 或 response。
4. Linear-ready ticket reference。
   - 每个 accepted inquiry 生成 `ticket_key`，格式 `OPTI-LEGAL-YYYYMMDD-XXXXXX`。
   - Response 返回 `linear_ticket.provider="linear"`、`linear_ticket.status="pending"`、`linear_ticket.reference=ticket_key`。
   - Outbox event `legal.inquiry.submitted` 只包含 pointer-safe fields，供后续真实 Linear relayer 使用。
5. Console submit flow。
   - 新增 `/console/legal-inquiry` 页面。
   - 使用 `sessionStorage.jwt_access` 作为 billing-service JWT；缺失时跳转 `/auth/login`。
   - 表单包含 category、contact_email、subject、message；前端做基本必填和长度校验。
   - 成功态显示 inquiry id、ticket reference、submitted_at、sla_due_at 和 status；不得显示 message raw body。
6. Docs and discoverability。
   - 新增或更新 `docs/customer-faqs/` 中的 O10 FAQ，解释 Team+ 法务问询范围、24h 响应含义和不构成法律意见边界。
   - 在现有 Console nav 至少一个已上线入口中加入 Legal Inquiry 链接；优先更新 `/console/providers` 和 `/console/routing-history` 以覆盖 Epic 8.C 相邻页面。

## Out Of Scope

- 不调用真实 Linear API，不新增 Linear SDK、webhook secret、OAuth、background worker、cron 或外部网络依赖。
- 不承诺人工已经回复、法务意见已经给出、合同审查已经完成、SOW/DPA 已签署、SOC 2/ISO 27001/AIGC 备案已通过或生产可用性 SLA。
- 不向 Free/Starter/Pro 暴露 Team+ 法务 SLA。
- 不实现 legal inquiry list/detail/admin review queue、邮件发送、Zoom scheduling、附件上传、数据流图模板生成、数据出境承诺函生成或法务知识库搜索。
- 不修改 subscription plan semantics、pricing copy、billing charge/refund behavior、auth-service JWT format 或 notification preferences。
- 不在 Console、outbox、response、logs 或 docs 示例中放真实客户 PII、合同文本、法律意见、Linear token、API key、JWT、phone、email 以外的用户提交原文。

## Acceptance Criteria

1. `POST /v1/legal/inquiry` exists exactly at that path in billing-service and requires authenticated user identity through existing billing auth dependency.
2. The endpoint requires `Idempotency-Key` and validates it with the existing billing UUID format.
3. Request body accepts only controlled fields: `category`, `contact_email`, `subject`, `message`, optional `company_name`, optional `urgency`; extra fields are rejected.
4. `category` is constrained to `pipl`, `gdpr`, `graded_protection`, `data_export`, `dpa`, `license`, `security`, or `other`.
5. `urgency` is constrained to `normal` or `urgent`; urgent does not change the 24h SLA in this story.
6. `subject`, `message`, `company_name`, and `contact_email` have explicit length limits; blank/whitespace-only values are rejected where required.
7. Contact email uses a local no-new-dependency validator; do not add `email-validator` or any new runtime dependency.
8. Team+ entitlement allows only active Team or Enterprise subscription rows whose `current_period_end` is in the future.
9. implicit Free, Free, Starter, Pro, canceled, expired, and period-expired active subscriptions return RFC 7807 403.
10. Rejected entitlement attempts do not create `legal_inquiries`, outbox events, or cached successful idempotency responses.
11. Accepted inquiries create one durable `legal_inquiries` row with user id, subscription id, plan code, category, contact email, subject, message, urgency, status, ticket key, submitted timestamp, and SLA due timestamp.
12. `sla_due_at` is exactly `submitted_at + 24 hours` in UTC.
13. The response includes `inquiry_id`, `status`, `submitted_at`, `sla_due_at`, `sla_hours=24`, and `linear_ticket`.
14. The response does not echo `subject`, `message`, `contact_email`, `company_name`, user id, subscription id, JWT, API key, or request body hash.
15. `linear_ticket.provider` is `"linear"`, `linear_ticket.status` is `"pending"`, and `linear_ticket.reference` equals the stored ticket key.
16. The implementation does not claim a real external Linear issue was created; pending means Linear-ready handoff only.
17. Accepted inquiries write exactly one pointer-safe outbox event `legal.inquiry.submitted`.
18. Outbox payload includes only `inquiry_id`, `ticket_key`, `plan_code`, `category`, `urgency`, `status`, `submitted_at`, `sla_due_at`, and `sla_hours`.
19. Outbox payload and headers do not include raw message, subject, contact email, company name, user id, subscription id, JWT, API key, phone, or request body.
20. Replaying the same idempotency key with the same normalized body returns the same response and does not duplicate inquiry rows or outbox events.
21. Replaying the same idempotency key with a different body returns RFC 7807 409 and does not mutate the original inquiry.
22. Cross-tenant idempotency key reuse returns RFC 7807 403 and never returns the owner tenant response.
23. Expired idempotency rows are ignored for replay and can be replaced by a new valid inquiry.
24. The SQL migration is idempotent and included under `infra/local-init/` after the existing numbered init files.
25. SQLAlchemy model definitions and migration constraints stay aligned.
26. Billing-service tests cover allowed Team, allowed Enterprise, rejected non-Team+ plans, expired/canceled subscriptions, idempotency replay, idempotency conflict, cross-tenant reuse, SLA calculation, response non-echo, outbox redaction, and exact public path.
27. `apps/web/src/lib/api.ts` exposes `submitLegalInquiry(jwtAccess, body, idempotencyKey?)` using `POST /v1/legal/inquiry` against `BILLING_SERVICE_URL`.
28. The web client sends `Authorization`, `Idempotency-Key`, `Content-Type`, and existing `Accept-Language`; it sends no solver API key, no billing charge id, and no internal service auth.
29. The web client response type matches backend snake_case fields including `linear_ticket`.
30. `/console/legal-inquiry` redirects to `/auth/login` when `sessionStorage.jwt_access` is missing.
31. `/console/legal-inquiry` validates required fields before submit and does not call the API on invalid input.
32. The page renders success with inquiry id, status, SLA due time, and Linear-ready ticket reference.
33. The page does not render the raw message after submit and does not write legal inquiry data to `localStorage` or `sessionStorage`.
34. The page renders safe backend errors for 403 and 409 without exposing raw backend payload internals.
35. Console navigation exposes the Legal Inquiry page from at least `/console/providers` and `/console/routing-history`.
36. `docs/customer-faqs/legal-inquiry-faq.md` exists and states Team+ scope, 24h response boundary, Linear-ready handoff boundary, and no-final-legal-advice caveat.
37. `docs/enterprise-gtm-toolkit.md` references the Legal Inquiry FAQ without changing GTM controlled status semantics.
38. Implementation introduces no new Python dependency, npm dependency, DB service, queue, worker, or external API call.
39. Local gates pass: targeted billing tests, targeted web tests, web typecheck, billing ruff/format, billing mypy if touched, GTM docs validation if docs touched, and `git diff --check`.
40. Post-implementation code review is completed and findings are fixed or explicitly documented.
41. GitHub CI passes, PR is merged, remote feature branch is deleted, local `main` is synced, and only then this story and sprint status are marked `done` through a separate status-sync commit.

## Tasks / Subtasks

- [x] T1: Backend persistence contract (AC: 11-12, 17-19, 24-26, 38)
  - [x] Add `infra/local-init/15-legal-inquiries.sql`.
  - [x] Add `LegalInquiry` SQLAlchemy model in `apps/billing-service/src/billing_service/models.py`.
  - [x] Add request/response schemas in `apps/billing-service/src/billing_service/schemas.py`.
  - [x] Ensure billing test setup can create the table on local DBs that predate the migration.

- [x] T2: Backend route, entitlement and idempotency (AC: 1-23, 26, 38)
  - [x] Add a `legal_router` with prefix `/v1/legal` and include it in `main.py`.
  - [x] Implement exact `POST /v1/legal/inquiry` with Team+ entitlement check.
  - [x] Implement normalized request hashing and replay/conflict/cross-tenant behavior using `billing_idempotency_keys`.
  - [x] Generate `OPTI-LEGAL-YYYYMMDD-XXXXXX` ticket key and pointer-safe outbox event.
  - [x] Add backend tests for Team/Enterprise allow, lower plans reject, expired/canceled reject, idempotency, SLA, response non-echo, outbox redaction and path.

- [x] T3: Web API client (AC: 27-29, 38)
  - [x] Add TypeScript request/response types and `submitLegalInquiry()`.
  - [x] Generate or accept a UUID idempotency key without adding dependencies.
  - [x] Add Vitest coverage for URL/path, headers, body, idempotency and error normalization.

- [x] T4: Console Legal Inquiry page (AC: 30-35, 38)
  - [x] Add `/console/legal-inquiry/page.tsx`.
  - [x] Implement dense Console form, loading, success and safe error states.
  - [x] Keep JWT in existing sessionStorage only; do not persist inquiry form content or response content.
  - [x] Add page tests for redirect, validation, success, 403/409 error, no raw message echo and no storage writes.
  - [x] Add nav links from `/console/providers` and `/console/routing-history`.

- [x] T5: Documentation (AC: 36-38)
  - [x] Add `docs/customer-faqs/legal-inquiry-faq.md`.
  - [x] Update `docs/enterprise-gtm-toolkit.md` asset index/boundary wording narrowly.
  - [x] Run GTM/docs validator because `docs/customer-faqs/**` and enterprise toolkit are CI-filtered.

- [ ] T6: Review, gates and GitHub sync (AC: 39-41)
  - [x] Run local quality gates and fix failures.
  - [x] Run post-implementation code review and fix/document findings.
  - [ ] Commit, push, create PR, wait for CI, merge, delete remote branch, sync local `main`.
  - [ ] Mark story/sprint status `done` only after merge/sync via separate status-sync commit.

## Dev Notes

### Existing Backend Facts

- `apps/billing-service/src/billing_service/main.py` currently includes only `billing_router`; this story should add a second router rather than changing the existing `/v1/billing` prefix.
- `apps/billing-service/src/billing_service/routes.py` has `billing_router = APIRouter(prefix="/v1/billing", tags=["billing"])`. Keep existing billing endpoints unchanged.
- `require_user` in `auth_dep.py` already supports JWT and internal bridge; no new auth mechanism is needed.
- `_active_subscription_for(session, user_id, for_update=False)` returns active subscription by status only. For O10, add a stricter helper requiring `current_period_end > now`.
- Plan codes already include `free`, `starter`, `pro`, `team`, `enterprise`; `team` and `enterprise` are the Team+ entitlement set.
- Existing idempotency pattern stores SHA-256 request hash and cached response in `billing_idempotency_keys`; raw body must never be stored there.
- Existing outbox model is `OutboxEvent`; sidecar exists, but no legal/Linear relayer exists. This story only writes a safe event.
- Existing `billing_problem_response()` supplies O7 `next_action_url` defaults for 4xx; use `_problem_response()` in routes for consistent RFC 7807.

### Existing Web Facts

- `apps/web/src/lib/api.ts` already has `BILLING_SERVICE_URL`, generic `request()`, `OptiCloudClientError`, and billing functions.
- Console pages that use billing/auth JWT read `sessionStorage.jwt_access` and redirect to `/auth/login`.
- Dense Console layout patterns exist in `/console/providers`, `/console/routing-history`, and `/console/data-exports`.
- `@opticloud/ui` provides `StatusCard`, `EmptyState`, and `LoadingShimmer`; no new UI dependency is needed.

### Data And Security Semantics

- Legal inquiry content is user-submitted sensitive support content. It may be stored in `legal_inquiries` for manual handling, but must not be copied to outbox, idempotency payload, response, logs, docs examples or frontend success panels.
- `sla_due_at` means "first human/legal response due by this timestamp", not "legal answer is complete by this timestamp".
- `linear_ticket.status="pending"` means internal Linear-ready handoff. It does not prove external Linear API mutation.
- Use UTC timestamps throughout.
- Use field sizes and enum checks in both Pydantic and SQL to prevent drift.

### Testing Guidance

- Backend tests should mirror subscription route fixtures: ASGITransport + dependency override + generated JWT.
- Tests should query DB directly to prove row counts, outbox payload redaction and idempotency behavior.
- Web tests should mock `submitLegalInquiry()` and `next/navigation` router like existing Console tests.
- Since docs under `docs/customer-faqs/**` are CI-filtered by GTM toolkit validation, run `uv run python scripts/validate_gtm_toolkit.py` and `uv run pytest tests/test_gtm_toolkit.py -q`.

### Review Constraints

- This story has passed exactly 3 pre-implementation adversarial review rounds before implementation.
- Do not move implementation status to `in-progress` until after these rounds are recorded.
- Do not mark story/sprint `done` before PR CI, merge, remote branch deletion, local main sync, and separate status-sync commit.

## Definition Of Done

- Story has passed exactly 3 pre-implementation adversarial review rounds with revisions recorded.
- Team/Enterprise users can submit legal inquiries through API and Console.
- Non-Team+ users receive safe RFC 7807 errors and no ticket is created.
- Response includes a 24h SLA due timestamp and Linear-ready ticket reference without claiming external Linear completion.
- Inquiry content is never echoed outside the durable DB row.
- Local gates and GitHub CI pass.
- Post-implementation code review completed and findings fixed or explicitly documented.
- Story and sprint status become `done` only after PR merge/sync/status-sync closure.

## Story Review Log

### Round 1: Boundary, Auth And Entitlement Review

Findings fixed:

- Initial implementation boundary drifted toward `/v1/billing/legal/inquiry`; revised to require exact public `POST /v1/legal/inquiry` while hosting it in billing-service through a separate router.
- Initial Team+ wording was ambiguous. Revised entitlement to active, future-period Team or Enterprise only; implicit Free, lower paid plans, canceled, expired and period-expired rows are explicitly rejected.
- Initial Console auth boundary could be confused with solver API key flows. Revised Console requirement to use billing-service JWT via existing `sessionStorage.jwt_access`, not solver API key.

Status: PASS after fixes.

### Round 2: SLA, Data Consistency And PII Review

Findings fixed:

- Initial SLA wording could be read as legal answer completion. Revised to "first human/legal response due within 24h" and made `sla_due_at = submitted_at + 24h UTC`.
- Initial response shape risked echoing user-submitted subject/message/contact email. Revised response and Console success panel to omit raw user content.
- Initial outbox payload risked copying support content into event infrastructure. Revised outbox contract to pointer-safe fields only and added explicit redaction tests.

Status: PASS after fixes.

### Round 3: Dependency, Linear And Closure Review

Findings fixed:

- Initial Linear wording overclaimed external integration. Revised to Linear-ready internal ticket reference with `status="pending"` and no external API call or dependency.
- Initial idempotency coverage missed cross-tenant and expired-row behavior. Revised AC/tests to cover replay, conflict, cross-tenant reuse and expired idempotency rows.
- Initial docs scope risked creating GTM/legal claims. Revised FAQ/toolkit changes to state Team+ scope, no-final-legal-advice caveat and no production SLA/certification claim.

Status: PASS after fixes. Story is ready for development.

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Debug Log References

- Customization resolver script absent at `_bmad/scripts/resolve_customization.py`; fallback loaded base skill instructions and project config.
- Story creation analyzed Epic 8.C.3, PRD O10/J5 legal side path, architecture J5/customer FAQ structure, legal-template ownership, billing subscription/idempotency/outbox patterns, and existing Console/API client patterns.
- 2026-06-04 - Completed pre-implementation adversarial review round 1 and revised path/auth/Team+ entitlement boundaries.
- 2026-06-04 - Completed pre-implementation adversarial review round 2 and revised 24h SLA semantics, response non-echo and outbox redaction requirements.
- 2026-06-04 - Completed pre-implementation adversarial review round 3 and revised Linear-ready dependency boundary, idempotency closure and docs claim controls.
- 2026-06-04 - Moved story to in-progress after exactly three pre-implementation adversarial review rounds.
- 2026-06-04 - Implemented backend persistence, exact `/v1/legal/inquiry` route, Team+ entitlement, pointer-safe outbox, idempotency replay/conflict/cross-tenant/expired-row handling, Console page, API client, nav links, and GTM FAQ docs.
- 2026-06-04 - Post-implementation code review fixed schema trim-before-length validation, local DB constraint backfill parity, frontend failure-state sensitive field clearing, frontend max-length validation, default UUID idempotency coverage, and concurrent same-key replay handling.
- 2026-06-04 - Local gates passed: billing targeted pytest 17 passed; web targeted Vitest 8 passed; billing ruff check/format check passed; billing mypy passed; web typecheck passed; GTM validator passed; GTM tests 7 passed; git diff --check passed.

### Completion Notes List

- Initial story created.
- Round 1 pre-implementation review completed and story revised.
- Round 2 pre-implementation review completed and story revised.
- Round 3 pre-implementation review completed and story revised.
- Story is ready for implementation.
- Story moved to in-progress for implementation.
- Backend route and persistence shipped in billing-service with exact public path `/v1/legal/inquiry`, JWT auth, active future-period Team/Enterprise entitlement, 24h UTC SLA calculation, Linear-ready pending reference, and pointer-safe outbox payload.
- Legal inquiry content is stored only in `legal_inquiries`; response, idempotency row, outbox payload/headers, and Console success state omit raw subject/message/contact email/company name.
- Console `/console/legal-inquiry` added with JWT redirect, client validation, safe 403/409 errors, sensitive field clearing after submit attempts, and nav links from providers/routing history.
- Post-implementation code review completed and all confirmed findings were fixed.
- Story is ready for GitHub sync; not marked done until PR CI/merge/branch cleanup/local main sync and separate status-sync commit complete.

### File List

- `_bmad-output/stories/8-c-3-legal-inquiry-sla.md`
- `_bmad-output/stories/sprint-status.yaml`
- `.github/workflows/ci.yml`
- `infra/local-init/15-legal-inquiries.sql`
- `apps/billing-service/src/billing_service/main.py`
- `apps/billing-service/src/billing_service/models.py`
- `apps/billing-service/src/billing_service/schemas.py`
- `apps/billing-service/src/billing_service/legal_routes.py`
- `apps/billing-service/tests/conftest.py`
- `apps/billing-service/tests/test_legal_inquiry_routes.py`
- `apps/web/src/lib/api.ts`
- `apps/web/src/lib/api-legal-inquiry.test.ts`
- `apps/web/src/app/console/legal-inquiry/page.tsx`
- `apps/web/src/app/console/legal-inquiry/page.test.tsx`
- `apps/web/src/app/console/providers/page.tsx`
- `apps/web/src/app/console/routing-history/page.tsx`
- `docs/customer-faqs/legal-inquiry-faq.md`
- `docs/enterprise-gtm-toolkit.md`

## Senior Developer Review (AI)

Reviewer: GPT-5 Codex on 2026-06-04

Outcome: Approved for GitHub sync after fixes. No critical issues remain.

Findings fixed:

- MEDIUM: Local billing test schema backfill created `legal_inquiries` without the migration/model CHECK constraints, weakening AC25 drift evidence. Fixed by adding idempotent `NOT VALID` CHECK constraints to the fixture and a constraint-presence regression.
- MEDIUM: Pydantic validators stripped `subject`/`message` after built-in length checks, allowing trim-short values to reach DB constraints instead of stable HTTP 422. Fixed by switching to before validators and adding trim-short tests.
- MEDIUM: Concurrent same-key submissions could race on `billing_idempotency_keys` unique key and return a DB error. Fixed with IntegrityError replay/conflict handling and a concurrent same-key regression.
- MEDIUM: Console validation covered required/minimum values but not maximum length limits before submit. Fixed frontend max-length validation and test coverage.
- LOW: Console failure state kept sensitive raw form content after a submit attempt. Fixed by clearing sensitive fields on backend error as well as success.
- LOW: API client default UUID idempotency generation was not explicitly tested. Added coverage for generated key propagation.

Review checklist:

- AC 1-41 cross-checked against implementation and tests.
- Changed file list reconciled against git status.
- No new Python/npm dependency, worker, DB service, external API call, Linear SDK, token, or webhook introduced.
- Response/outbox/idempotency/Console success redaction checked.
- Local gates passed as recorded in Dev Agent debug log.

## Change Log

- 2026-06-04 - Story created for 8.C.3 Team+ legal inquiry SLA.
- 2026-06-04 - Round 1 pre-implementation review revised route, auth and entitlement boundaries.
- 2026-06-04 - Round 2 pre-implementation review revised SLA, PII and outbox redaction semantics.
- 2026-06-04 - Round 3 pre-implementation review revised Linear-ready dependency boundary, idempotency closure and docs claim controls; story status set ready-for-dev.
- 2026-06-04 - Story status moved to in-progress after pre-implementation review closure.
- 2026-06-04 - Implemented Team+ legal inquiry SLA API, Console flow, docs, tests, CI schema hook, and post-implementation review fixes; story status set code-review pending GitHub sync.
