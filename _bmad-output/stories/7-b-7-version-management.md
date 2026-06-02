---
story_key: 7-b-7-version-management
baseline_commit: 598f36906a51e88f4aeee2eb01f2f2e60a0942a8
epic_num: 7
story_num: B.7
epic_name: Provider Marketplace v2
status: in-progress
priority: High
type: provider version update request contract
created_by: bmad-create-story
created_at: 2026-06-02
sources:
  - _bmad-output/planning/epics.md (Epic 7.B / Provider Marketplace v2)
  - _bmad-output/planning/prd.md (FR P7 / Provider version updates patch/minor/major)
  - _bmad-output/planning/architecture.md (P39 Optimistic Locking, P63 Event Versioning)
  - _bmad-output/stories/7-b-1-provider-apply-v2.md
  - _bmad-output/stories/7-b-2-shadow-validation.md
  - _bmad-output/stories/7-b-3-gradient-rollout.md
  - _bmad-output/stories/7-b-5-provider-kpi-dashboard.md
  - _bmad-output/stories/7-b-6-revenue-payout.md
  - apps/capability-registry/src/capability_registry/models.py
  - apps/capability-registry/src/capability_registry/schemas.py
  - apps/capability-registry/src/capability_registry/routes.py
  - apps/capability-registry/tests/test_api.py
  - infra/local-init/14-capability-registry.sql
  - packages/shared-ts/openapi/capability-registry.json
---

# Story 7.B.7 - Provider Version Management

Status: in-progress

## Story

**作为** 外部 Provider，
**我希望** 能提交 patch/minor/major 版本更新申请，并看到审查状态和版本证据，
**从而** 在真实发布、路由切换和 Provider Console 完整自助上线前，先拥有一个可审计、可并发保护、不会改写 live catalog 的版本更新合同。

## Context

Epic 7.B 已完成 Provider application/evaluation intake、shadow validation、gradient rollout、route-share dashboard、KPI dashboard、revenue/pending payout projection。PRD FR P7 要求 Provider can submit version updates (patch/minor/major)。Architecture P39 要求 UI 可编辑资源使用 ETag + If-Match 乐观锁；P63 要求版本演进兼容时新增字段 only 走 minor，重命名/移除字段需要兼容窗口。

本 story 的最小闭环是在 `apps/capability-registry` 增加 Provider version update request 合同。它记录 Provider 对既有申请/Provider ID 的版本更新证据、semver 变更类型、审查状态和内部审查引用。它不执行发布，不改写 `capability_providers` 或 `capabilities`，不触发 solver routing / feature flag / rollout / payout / voucher migration，也不实现 public Provider Console auth。

## Scope

1. 在 `apps/capability-registry` 中新增 provider version update request 存储、model、schemas。
2. 新增内部写入/读取 API：
   - `PUT /v1/provider-applications/{application_id}/version-updates/{version_update_id}`
   - `GET /v1/provider-applications/{application_id}/version-updates/{version_update_id}`
   - `GET /v1/provider-applications/{application_id}/version-updates?tenant_id=&requested_provider_id=&status=&change_kind=`
   - `PATCH /v1/provider-applications/{application_id}/version-updates/{version_update_id}/status`
3. 对可编辑 version update resource 实施 P39 ETag/If-Match：
   - response header `ETag: "<version_update_id>:<record_version>"`
   - 更新既有 version update 和 PATCH status 必须带 `If-Match`
   - 缺失返回 428，版本不匹配返回 412
4. 校验 semver 与 `change_kind` 一致：patch/minor/major 只能对应对应层级的递增更新，不允许 downgrade 或相同版本。
5. 添加 capability-registry tests，覆盖 schema idempotency、semver/change_kind、ETag/If-Match、tenant exact scope、status lifecycle、unsafe fields、no side effects、OpenAPI drift。
6. Regenerate `packages/shared-ts/openapi/capability-registry.json`。

## Out Of Scope

- Provider Console 页面、public provider auth/ownership enforcement、API gateway policy、OAuth flow 实现。
- 实际发布 Provider 新版本、Docker pull、cosign/SBOM 验证、OpenAPI diff 执行、shadow worker、traffic rollout、feature flag、solver-orchestrator routing mutation。
- 创建、更新或删除 live `capability_providers`, `capabilities`, `provider_oauth_flows`, `revenue_share_policies`, `revenue_share_hooks`, payout rows, shadow samples, rollout rows, voucher migration rows。
- 自动批准、自动上线、自动回滚、蓝绿发布、等价 Provider 匹配、Provider 退出通知、repro voucher 迁移。
- 月度分润、结算、银行/税务/支付、账本读取或 payout processor。
- 在 request body 中接受 raw credentials, raw provider/customer payloads, raw benchmark datasets, raw OpenAPI bodies, raw release notes bodies, registry auth, OAuth tokens, API keys, bank/tax/payment fields, PII。

## Acceptance Criteria

1. `infra/local-init/14-capability-registry.sql` idempotently creates `provider_version_update_requests` without requiring other service migrations。
2. `provider_version_update_requests` has columns: `id UUID PRIMARY KEY DEFAULT gen_random_uuid()`, `tenant_id UUID NULL`, `application_row_id UUID NOT NULL REFERENCES provider_applications(id) ON DELETE CASCADE`, `application_id VARCHAR(64) NOT NULL`, `version_update_id VARCHAR(64) NOT NULL`, `requested_provider_id VARCHAR(64) NOT NULL`, `current_version VARCHAR(64) NOT NULL`, `proposed_version VARCHAR(64) NOT NULL`, `change_kind VARCHAR(16) NOT NULL`, `openapi_url TEXT NOT NULL`, `openapi_sha256 VARCHAR(64) NOT NULL`, `image_digest TEXT NOT NULL`, `cosign_bundle JSONB NOT NULL DEFAULT '{}'::jsonb`, `sbom_ref TEXT NULL`, `release_notes_ref TEXT NULL`, `status VARCHAR(32) NOT NULL DEFAULT 'draft'`, `review_notes_ref TEXT NULL`, `submitted_at TIMESTAMPTZ NULL`, `reviewed_at TIMESTAMPTZ NULL`, `record_version INTEGER NOT NULL DEFAULT 1`, `metadata JSONB NOT NULL DEFAULT '{}'::jsonb`, `created_at`, and `updated_at`。
3. `application_id`, `version_update_id`, and `requested_provider_id` use `^[a-z0-9][a-z0-9-]{0,63}$`。
4. `current_version` and `proposed_version` must be strict semver `MAJOR.MINOR.PATCH` with non-negative integer components and no prerelease/build suffix in this story。
5. `change_kind` accepts exactly `patch`, `minor`, and `major`。
6. `patch` requires same major/minor and proposed patch greater than current patch。
7. `minor` requires same major, proposed minor greater than current minor, and proposed patch equal to `0`。
8. `major` requires proposed major greater than current major and proposed minor/patch equal to `0`。
9. Downgrades, equal versions, non-strict semver, or mismatch between semver delta and `change_kind` return 422。
10. Nullable tenant uniqueness is correct: one global version update per `(application_row_id, version_update_id)` and one tenant version update per `(tenant_id, application_row_id, version_update_id)`。
11. Version update creation requires an existing submitted provider application in exact requested tenant scope. With no `tenant_id`, only global applications are valid. With `tenant_id`, only applications for that tenant are valid; no global fallback is allowed。
12. Version update creation stores `application_row_id`, `application_id`, and `requested_provider_id` from the resolved application row, not from request body overrides。
13. The body may include `application_id` or `version_update_id`; if present they must match the path. Mismatch returns 422。
14. `requested_provider_id` is derived and caller-supplied `requested_provider_id` is rejected。
15. `openapi_url` must start with `http://` or `https://`; `openapi_sha256` must be 64 hex chars; `image_digest` must contain `sha256:<64 hex>`。
16. `cosign_bundle` and `metadata` must be JSON objects and reject nested sensitive/raw-payload keys recursively。
17. `sbom_ref`, `release_notes_ref`, and `review_notes_ref` must be reference strings with allowed prefixes `s3://`, `oss://`, `fixture://`, `benchmark://`, or `repro://`; raw release notes text is not accepted。
18. Allowed version update statuses are exactly `draft`, `submitted`, `under_review`, `approved`, `rejected`, and `cancelled`。
19. Upsert creates a new request in `draft` unless body status is `submitted`; submitted creation sets `submitted_at` when missing。
20. Draft version updates may update artifact fields and metadata with valid `If-Match`。
21. Once status is `submitted`, material fields are immutable: `current_version`, `proposed_version`, `change_kind`, `openapi_url`, `openapi_sha256`, `image_digest`, `cosign_bundle`, `sbom_ref`, and `release_notes_ref`。
22. Valid status transitions are: `draft -> submitted|cancelled`, `submitted -> under_review|cancelled`, `under_review -> approved|rejected|cancelled`。`approved`, `rejected`, and `cancelled` are terminal except idempotent replay。
23. `PATCH .../status` accepts only `status`, optional `review_notes_ref`, and optional `metadata`。It must reject artifact fields and caller-controlled timestamps/record_version。
24. `review_notes_ref` is required when transitioning to `approved` or `rejected`。
25. `submitted_at` is set once on transition to `submitted` and preserved on idempotent replays。`reviewed_at` is set once on transition to `approved` or `rejected` and preserved on idempotent replays。
26. Every successful mutation increments `record_version` by exactly 1. Idempotent no-op replay may return the existing response without incrementing。
27. All version update responses include `ETag: "<version_update_id>:<record_version>"`。
28. Updating an existing version update through `PUT` requires `If-Match`; missing returns 428 and mismatch returns 412。
29. `PATCH .../status` requires `If-Match`; missing returns 428 and mismatch returns 412。
30. Creating a new version update does not require `If-Match`。
31. `GET version-updates/{version_update_id}` resolves exact tenant scope by query `tenant_id`; missing rows return 404。
32. `GET version-updates` supports filters by `tenant_id`, `requested_provider_id`, `status`, and `change_kind`, uses exact tenant scope, and sorts deterministically by `created_at DESC`, `version_update_id`。
33. Stored row drift fails closed with 409 if status, change_kind, semver fields, artifact refs, tenant scope, derived requested_provider_id, record_version, or timezone fields are malformed or inconsistent with the referenced application。
34. Version update reads and writes do not create, update, or delete provider/capability/OAuth/revenue-share/payout/shadow/rollout rows as side effects。
35. Write routes use existing `X-Internal-Service-Auth` when `CAPABILITY_REGISTRY_INTERNAL_SECRET` is configured。
36. Existing provider/capability/OAuth/revenue-share/application/evaluation/shadow/rollout/route-share/KPI/payout tests continue to pass。
37. The new schemas/routes are included in `packages/shared-ts/openapi/capability-registry.json`; `scripts/check_openapi_drift.py` detects drift。
38. OpenAPI schemas for version updates do not expose unsafe fields such as credentials, raw request/response, raw dataset, customer routing payloads, bank/tax/payment fields, payout fields, caller-controlled `record_version`, or caller-controlled timestamps。
39. `.github/workflows/ci.yml` keeps the existing `capability-registry-test` job; no new CI service job is added。
40. Local gates pass: `uv run pytest apps/capability-registry/tests/ -v`, `uv run mypy apps packages`, `uv run ruff check apps/capability-registry`, `uv run ruff format --check apps/capability-registry`, `uv run python scripts/generate_openapi.py`, `uv run python scripts/check_openapi_drift.py`, and `git diff --check`。
41. Implementation record includes post-implementation code review findings and fixes。
42. GitHub CI passes, PR is merged, remote branch is deleted, local `main` is synced, and only then this story and sprint status are marked `done`。

## Tasks / Subtasks

- [x] T1: Add version update data model (AC: 1-12, 18, 33)
  - [x] Extend `infra/local-init/14-capability-registry.sql` idempotently。
  - [x] Add SQLAlchemy model for `ProviderVersionUpdateRequest`。
  - [x] Preserve existing application/evaluation/shadow/rollout/dashboard/payout behavior。

- [x] T2: Add schemas and validation (AC: 3-9, 13-17, 21-25, 38)
  - [x] Add request/response/status patch schemas。
  - [x] Implement strict semver parsing and change-kind consistency without adding a dependency。
  - [x] Reject derived fields, caller-controlled timestamps/version, raw payloads, credentials, and unsafe metadata recursively。

- [x] T3: Add routes, lifecycle, and ETag locking (AC: 19-35)
  - [x] Add nested version update upsert/read/list routes under provider applications。
  - [x] Add status PATCH route。
  - [x] Implement exact tenant scope, material immutability, lifecycle transitions, ETag response headers, `If-Match` 428/412, and `record_version` increments。

- [x] T4: Add tests and OpenAPI coverage (AC: 36-40)
  - [x] Cover schema idempotency, semver/change-kind validation, exact tenant scope, status lifecycle, material immutability, ETag/If-Match, write auth, drift 409, and no side effects。
  - [x] Add OpenAPI unsafe-field absence and ETag-related behavior coverage。
  - [x] Regenerate checked-in OpenAPI and run drift check。

- [ ] T5: Review, gates, and GitHub sync (AC: 41-42)
  - [x] Run post-implementation code review and fix findings。
  - [x] Record code review findings and fixes in `Post-Implementation Code Review`。
  - [x] Run local gates after fixes。
  - [ ] Commit, push, create PR, wait for CI, merge, delete remote branch, and sync local `main`。
  - [ ] Mark story and sprint status `done` only after merge/sync。

## Dev Notes

### Service Boundary

- Implement only in `apps/capability-registry`, `infra/local-init/14-capability-registry.sql`, checked-in capability-registry OpenAPI, tests, and story/status files。
- This is a review-ready version update contract. It does not promote Provider versions, mutate live catalog rows, call provider runtimes, run OpenAPI diff tools, or update routing。
- Treat public Provider ownership/auth as a later Provider Console/API gateway concern. These routes stay internal-service protected for writes and service-side for reads。

### Existing Patterns To Reuse

- Reuse `_PATH_ID_PATTERN`, `_assert_path_id(...)`, `_require_write_auth(...)`, `_validate_reference(...)`, `_reject_forbidden_reference_fields(...)`, `_validate_http_url(...)`, `_DIGEST_PATTERN`, `_SHA256_PATTERN`, and existing FastAPI/Pydantic style。
- Reuse 7.B.4/7.B.5/7.B.6 exact tenant-scope dashboard behavior for provider-owned resources: no global fallback in tenant-owned version update records。
- Use partial unique indexes for nullable tenant uniqueness. Do not use plain unique indexes containing nullable `tenant_id`。
- Existing tests apply `infra/local-init/14-capability-registry.sql` twice. Extend that harness。
- OpenAPI generation and drift scripts already include capability-registry。

### P39 ETag Guidance

- `record_version` is the mutable resource version, not the provider semantic version。
- ETag format must be exactly `"<version_update_id>:<record_version>"` including quotes in the header value。
- Existing `PUT` update and all status PATCH transitions require `If-Match`。New creates do not。
- Use FastAPI `Response` to set headers on typed response-model endpoints。
- Missing `If-Match` should raise `HTTPException(status_code=428, detail="If-Match header required")`。Mismatched ETag should raise 412。

### Data Semantics

- `current_version` is the version the provider claims is currently live or reviewed; this story does not verify it against `capability_providers.model_version`。
- `proposed_version` is the requested new version; approval here only means review approval, not deployment or routing activation。
- `openapi_url`/`openapi_sha256`, `image_digest`, `cosign_bundle`, `sbom_ref`, and `release_notes_ref` are artifact references. Do not store raw OpenAPI specs, release notes bodies, SBOM JSON bodies, Docker credentials, registry passwords, or provider request/response payloads。
- `approved` must not mutate `capability_providers`, `capabilities`, rollouts, route-share dashboard inputs, KPI inputs, or payout entries。

### Previous Story Intelligence

- 7.B.1 made application intake submitted-only for downstream work and froze submitted material fields. Version updates should follow the same auditability rule after submission。
- 7.B.2 and 7.B.3 showed state machines need row locks or optimistic concurrency before mutation. This story uses P39 `If-Match` plus `record_version`。
- 7.B.4/7.B.5/7.B.6 established exact tenant scope and fail-closed 409 behavior for provider-owned projections。
- 7.B.6 fixed N+1 reference validation by batching related refs; version update list/read should avoid avoidable per-row application lookups where practical。
- Prior post-review fixes repeatedly found sensitive-key matching must catch snake/camel/compact variants recursively。

### Suggested Commands

```powershell
uv sync --all-packages --extra dev
uv run pytest apps/capability-registry/tests/ -v
uv run mypy apps packages
uv run ruff check apps/capability-registry
uv run ruff format --check apps/capability-registry
uv run python scripts/generate_openapi.py
uv run python scripts/check_openapi_drift.py
git diff --check
```

## Definition Of Done

- Story file has passed 3 pre-implementation adversarial review rounds and revisions。
- Provider version update request API satisfies FR P7 as a safe, review-ready contract without implementing real release, routing, rollout, Console auth, voucher migration, or catalog mutation early。
- Existing provider marketplace behavior remains compatible。
- Post-implementation code review is completed and findings are fixed or explicitly documented。
- Local quality gates and GitHub CI pass。
- Story and sprint status are updated to `done` only after review, gates, CI, merge, branch cleanup, and local `main` sync。

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Debug Log References

- Story creation used local context from PRD P7, Architecture P39/P63, 7.B.1-7.B.6 provider marketplace stories, and current capability-registry implementation files。
- Baseline branch: `codex/7-b-7-version-management`。
- Baseline commit: `598f36906a51e88f4aeee2eb01f2f2e60a0942a8`。
- Implementation started; story and sprint status moved to in-progress。
- Focused version update tests: `uv run pytest apps/capability-registry/tests/test_api.py -k "provider_version_update" -v` -> 4 passed。
- Full capability-registry tests after implementation/review fix: `uv run pytest apps/capability-registry/tests/ -v` -> 50 passed。
- Type gate: `uv run mypy apps packages` -> passed。
- Lint/format gates: `uv run ruff check apps/capability-registry` and `uv run ruff format --check apps/capability-registry` -> passed。
- OpenAPI gates: `uv run python scripts/generate_openapi.py` and `uv run python scripts/check_openapi_drift.py` -> passed。
- Whitespace gate: `git diff --check` -> passed。

### Completion Notes List

- Story created for Provider Version Management request contract。
- Completed 3 pre-implementation adversarial review rounds and revised the story after each round。
- Added `provider_version_update_requests` schema/model, version update request/response/status-patch schemas, and checked-in OpenAPI updates。
- Added nested version update APIs under provider applications with exact tenant scope, submitted-application prerequisite, strict semver/change-kind validation, material immutability after submission, status lifecycle, ETag/If-Match locking, and no live catalog/routing side effects。
- Added tests for lifecycle, ETag/If-Match, tenant scope, write auth, semver validation, forbidden unsafe fields, no side effects, stored drift 409, and OpenAPI contract safety。
- Post-implementation review finding fixed: read paths now reject stored unsafe `cosign_bundle`/`metadata` drift with 409 rather than returning manually corrupted sensitive fields。

### File List

- `_bmad-output/stories/7-b-7-version-management.md`
- `_bmad-output/stories/sprint-status.yaml`
- `infra/local-init/14-capability-registry.sql`
- `apps/capability-registry/src/capability_registry/models.py`
- `apps/capability-registry/src/capability_registry/schemas.py`
- `apps/capability-registry/src/capability_registry/routes.py`
- `apps/capability-registry/tests/test_api.py`
- `packages/shared-ts/openapi/capability-registry.json`

## Change Log

- 2026-06-02 - Story created for Provider Version Management request contract。
- 2026-06-02 - Completed 3 pre-implementation adversarial review rounds; story marked ready for development。
- 2026-06-02 - Implementation started; story and sprint status moved to in-progress。
- 2026-06-02 - Implemented Provider Version Management request contract, tests, OpenAPI update, post-review fix, and local gates; pending GitHub sync。

## Pre-Implementation Adversarial Reviews

### Round 1 - Boundary, Ownership, And Product Fit Review

Findings:

1. "Provider can submit version updates" could be misread as actual deployment, live Provider catalog mutation, or solver routing update。
2. "Version management" could expand into Provider Console public self-service auth and ownership enforcement。
3. Patch/minor/major could be interpreted as API versioning across all OptiCloud endpoints rather than Provider artifact semver。
4. Approval could be mistaken for release activation。
5. The story needed to avoid implementing automatic shadow validation, rollout, voucher migration, provider exit, or monthly revenue share early。
6. Artifact evidence could accidentally store raw OpenAPI docs, release notes bodies, SBOM JSON, Docker credentials, or provider payloads。
7. Reads could be mistaken as public provider-authenticated endpoints。
8. It was unclear whether approved version updates should mutate `capability_providers` / `capabilities`。
9. Tenant behavior needed exact scoping to avoid a tenant request editing a global application。
10. The story needed a concrete empty/no-side-effect contract。

Revisions applied:

- Scoped implementation to capability-registry version update request records only。
- Explicitly excluded live catalog mutation, routing, rollout, Provider Console auth, voucher migration, and payout/monthly-share work。
- Defined approval as review approval only, not deployment。
- Added exact tenant application resolution, artifact reference-only boundaries, and no-side-effect ACs。

### Round 2 - Drift, Data Consistency, And Lifecycle Review

Findings:

1. Semver validation needed strict rules or callers could mark a major update as patch。
2. Minor/major reset behavior needed to be explicit to avoid ambiguous `1.2.3 -> 1.3.4` classification。
3. `requested_provider_id` must be derived from the application to avoid application/version request drift。
4. Submitted requests need material immutability; otherwise reviewed artifacts can change after submission。
5. Status transitions needed a closed state machine with terminal states。
6. `review_notes_ref` should be required for final approval/rejection to close auditability。
7. Timestamps must be service-owned and set once。
8. `record_version` could drift from semver unless documented as separate mutable resource version。
9. Stored row drift needed fail-closed behavior on reads/lists, not only write-time validation。
10. Exact tenant scope should disallow global fallback for version updates。

Revisions applied:

- Added strict semver/change-kind rules, downgrade/equal rejection, and reset requirements。
- Made `requested_provider_id` derived and request-supplied values rejected。
- Added submitted material immutability, status state machine, review notes requirement, service-owned timestamps, and drift 409 ACs。
- Clarified `record_version` is the P39 mutable resource version, not semantic version。

### Round 3 - Dependencies, Concurrency, Tests, And Closure Review

Findings:

1. Architecture P39 applies to UI-editable resources, so version update mutation needs ETag/If-Match rather than only row locking。
2. The story needed exact 428/412 behavior for missing/mismatched `If-Match`。
3. ETag response headers should be present on all version update responses, including GET and mutations。
4. New creates should not require If-Match, or clients cannot create first versions。
5. `PATCH .../status` must reject artifact fields, timestamps, and caller-controlled record version。
6. Tests need to prove no side effects on live catalog and existing provider marketplace rows。
7. OpenAPI unsafe-field assertions must include request schemas and prevent caller-controlled `record_version`/timestamps。
8. Local gates must include OpenAPI generation before drift check。
9. No new dependencies should be added for semver parsing。
10. Story `done` must remain gated on GitHub CI, merge, remote branch deletion, and local main sync。

Revisions applied:

- Added P39 ETag/If-Match ACs, exact ETag format, 428/412 handling, and create exception。
- Added status PATCH request boundary and OpenAPI unsafe-field requirements。
- Added no-new-dependency guidance for semver parsing, no-side-effect tests, and full local/GitHub closure gates。

## Post-Implementation Code Review

- [x] [Review][Patch] Version update read paths validated stored `cosign_bundle` and `metadata` were JSON objects, but did not re-run recursive sensitive-key rejection on manually drifted database rows. A direct DB write could therefore place `accessToken`/credential-like keys into stored metadata and have GET/list return them. Fixed by applying the same forbidden-reference-field check during stored-row validation and returning 409 on unsafe metadata drift, with regression coverage。
