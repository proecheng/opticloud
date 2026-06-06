---
story_key: 6-c-3-capability-vocab-design
baseline_commit: 17d958e50eda522b51188f7fcb029e757838ce75
epic_num: 6
story_num: C.3
epic_name: Auto-migration + Provider Exit v2
status: code-review
priority: High
type: capability vocabulary governance
created_by: bmad-create-story
created_at: 2026-06-06
sources:
  - _bmad-output/planning/epics.md (Epic 6.C / Story 6.C.3 / R4 capability vocab)
  - _bmad-output/planning/prd.md (FR R4 auto-migrate to equivalent Provider using capability vocabulary)
  - _bmad-output/planning/architecture.md (Capability Registry backbone, Provider routing, Repro 5y SLA)
  - _bmad-output/stories/7-a-1-capability-registry-v1-schema.md
  - _bmad-output/stories/6-c-1-auto-migrate-provider.md
  - _bmad-output/stories/6-c-2-30d-exit-notification.md
  - apps/capability-registry/src/capability_registry/models.py
  - apps/capability-registry/src/capability_registry/schemas.py
  - apps/capability-registry/src/capability_registry/routes.py
  - apps/capability-registry/tests/test_api.py
  - infra/local-init/14-capability-registry.sql
---

# Story 6.C.3 - Capability Vocabulary Design

Status: code-review

## Story

**作为** 平台 Provider 与 Repro 能力治理团队，
**我希望** capability-registry 维护一套可审计的 canonical capability vocab，并在 Provider capability 注册时把别名解析成 active canonical tags，
**从而** 后续 voucher rerun auto-migration 和 Story 6.C.4 equivalent matching 能基于稳定、高精度、可治理的能力标签，而不是自由文本或各 Provider 自定义词。

## Context

Epic 6.C 的 R4 需要系统基于 capability 词表自动迁移到 equivalent Provider。Story 6.C.1 已在 `solver-orchestrator` 内完成本地、纯函数的 rerun migration preflight，并明确排除完整词表治理。Story 6.C.2 已完成 Provider exit >=30d 通知控制面，也明确排除 capability vocab 和 broader matching。本 story 是 6.C.4 的直接前置条件：在 capability-registry 内建立 canonical vocab contract，并让 Provider 注册 capability 时只能落库 active canonical tags。

现状：

- `apps/capability-registry` 已有 `capability_providers`、`capabilities`、`capability_tags`，以及 provider/capability CRUD、Redis cache、OpenAPI drift gate。
- `CapabilityUpsertRequest.tags` 当前只做 `normalize_tag()`，允许任意自由文本，例如 `"linear programming"` 自动变成 `linear_programming` 后写入 `capability_tags`。
- `upsert_capability()` 当前删除该 capability 的所有 `CapabilityTag` 后重新插入请求 tags；没有 canonical term 表、alias 表、状态机、别名解析或 active-only enforcement。
- 6.C.4 需要“2 Provider 同 vocab”后的匹配排序；本 story 只保证 vocab 进入 registry 且 tags canonical，不实现 matching score。

## Scope

1. 在 capability-registry 增加 canonical vocab term 和 alias 持久化合同。
2. 增加 read-only public API 读取 active/deprecated/draft vocab terms 与 aliases。
3. 增加 internal-secret 保护的 vocab term upsert API，用于创建/更新 canonical tags、状态、双语标签/描述、task_type、parent/replacement 关系和 aliases。
4. 修改 capability upsert：请求 tags 可包含 canonical tag 或 alias，但落库到 `capability_tags` 的必须是 active canonical tags。
5. 保持 capability response 里的 `tags` 为去重、排序后的 canonical tags；不把别名、draft/deprecated term 或 raw provider text 写入 `capability_tags`。
6. 覆盖多租户/global fallback、cache invalidation、OpenAPI drift、schema idempotence、数据一致性和边界隐私。

## Out Of Scope

- 不实现 Story 6.C.4 equivalent matching score、precision/version ranking、ML scoring、manual review queue 或 solver rerun reranking。
- 不修改 Story 6.C.1 的 `solver-orchestrator.provider_migration`，不让 solver-orchestrator runtime 调 capability-registry。
- 不修改 Story 6.C.2 Provider exit notification、email、站内信、status page announcement。
- 不修改 provider application、shadow validation、gradient rollout、provider KPI、revenue-share、monthly payout 或 provider console。
- 不新增 worker、scheduler、独立 vocab service、UI、外部网络调用或实时同步到 solver-orchestrator。
- 不存储 raw provider payload、benchmark data、secret、OAuth token、email、phone、billing id、API key id、JWT 或 provider request/response body。

## Acceptance Criteria

1. `infra/local-init/14-capability-registry.sql` idempotently creates `capability_vocab_terms` and `capability_vocab_aliases`.
2. SQL schema remains self-contained for capability-registry tests and can be applied twice without failure.
3. `capability_vocab_terms` includes at minimum `tenant_id`, `tag`, `status`, `task_type`, `label_zh`, `label_en`, `description_zh`, `description_en`, `parent_tag`, `replaces_tag`, `metadata`, `created_at`, and `updated_at`.
4. `capability_vocab_aliases` includes at minimum `tenant_id`, `alias`, `canonical_tag`, `status`, `metadata`, `created_at`, and `updated_at`.
5. Status values are constrained: terms support `draft`, `active`, `deprecated`, and aliases support `active`, `deprecated`.
6. `tag`, `alias`, `parent_tag`, and `replaces_tag` use the same normalized slug contract as existing `normalize_tag()` (`[a-z0-9][a-z0-9_-]{0,63}`).
7. Global and tenant vocabulary scopes use partial unique indexes so duplicate global terms/aliases are impossible even with `tenant_id IS NULL`.
8. Tenant-scoped term/alias rows may override same-named global rows without mutating global rows.
9. ORM models in `models.py` match the SQL schema, including JSONB metadata and partial unique indexes.
10. Pydantic schemas define request/response contracts for term upsert, term response, alias response, and term list filters without allowing unsafe fields.
11. Internal vocab writes are protected by existing `X-Internal-Service-Auth` / `CAPABILITY_REGISTRY_INTERNAL_SECRET` semantics.
12. Empty internal secret keeps local/dev writes usable exactly as current provider/capability writes do; configured secret rejects missing/wrong headers with 401.
13. `PUT /v1/capability-vocab/terms/{tag}` creates or updates a term; path tag is authoritative and body tag may be omitted or must match.
14. Term upsert accepts an alias list and upserts aliases atomically with the term.
15. Alias upsert rejects alias values that normalize to the same value as `canonical_tag`.
16. Alias upsert rejects alias collisions where the same alias points to a different canonical tag in the same scope.
17. A term cannot set `parent_tag` or `replaces_tag` to itself.
18. `parent_tag` and `replaces_tag`, when provided, must resolve to an existing term in the same tenant scope or global fallback.
19. A term cannot be set `active` unless `task_type`, `label_zh`, `label_en`, `description_zh`, and `description_en` are non-empty after trimming.
20. `GET /v1/capability-vocab/terms` lists terms in deterministic order and supports optional `tenant_id`, `status`, `task_type`, and `include_aliases` filters.
21. `GET /v1/capability-vocab/terms/{tag}` resolves tenant row first and global fallback second when `tenant_id` is supplied, mirroring existing capability read semantics.
22. Vocab responses include `scope_source` (`global`, `tenant`, or `global_fallback`) and aliases only when requested or on detail response.
23. Capability upsert resolves every requested tag through the vocab table: canonical term tag first, then active alias, using tenant scope before global fallback.
24. Capability upsert stores only active canonical term tags in `capability_tags`, sorted and de-duplicated.
25. Capability upsert rejects unknown tags/aliases with 422 and does not create or modify capability rows or `capability_tags`.
26. Capability upsert rejects draft/deprecated canonical terms and deprecated aliases with 422.
27. Capability upsert accepts alias input such as `"linear programming"` when an active alias maps to active canonical `lp`, but response and DB store only `lp`.
28. Existing provider/capability APIs keep their public response shape except that capability tags are now canonical-only.
29. Existing cache behavior remains correct: provider/capability/vocab writes invalidate stale `capability_cache:*` entries that could contain changed vocab or tag results.
30. Redis-unavailable fallback still returns DB-backed provider, capability, and vocab responses.
31. Tests cover schema idempotence, term upsert/read/list, alias resolution, tenant override/global fallback, active-only enforcement, collision/self-reference validation, capability upsert canonicalization, no-mutation on invalid tags, cache invalidation, and write auth.
32. OpenAPI generation includes the new vocab endpoints and `scripts/check_openapi_drift.py` passes.
33. Focused capability-registry tests, ruff check/format, mypy, OpenAPI generation/drift, and `git diff --check` pass locally.
34. Post-implementation code review is run after implementation; findings are fixed or explicitly documented in this story.
35. GitHub PR CI must pass, PR must be merged, remote feature branch deleted, and local `main` synced before this story or sprint status is marked `done`.
36. The final `done` status update must be a separate status-sync commit after GitHub merge/sync.

## Tasks / Subtasks

- [x] T1: Add capability vocab persistence contract. (AC: 1-9)
  - [x] Add idempotent SQL for terms and aliases in `infra/local-init/14-capability-registry.sql`.
  - [x] Add ORM models and indexes in `apps/capability-registry/src/capability_registry/models.py`.
  - [x] Update capability-registry test cleanup to truncate vocab tables in FK-safe order.

- [x] T2: Add vocab schema and protected APIs. (AC: 10-22)
  - [x] Add Pydantic request/response schemas and validators.
  - [x] Add term list/detail/upsert routes under `/v1/capability-vocab/terms`.
  - [x] Implement parent/replacement resolution, alias atomics, collision checks, and active-state validation.
  - [x] Reuse existing internal secret write-protection and cache invalidation.

- [x] T3: Enforce canonical vocab on capability registration. (AC: 23-30)
  - [x] Resolve requested tags through tenant/global term and alias scope before capability mutation.
  - [x] Reject unknown, draft, deprecated, or conflicting tags without partial DB writes.
  - [x] Store only sorted/de-duped active canonical tags in `capability_tags`.
  - [x] Preserve provider/capability response contracts and Redis fallback behavior.

- [x] T4: Add tests and generated contracts. (AC: 31-33)
  - [x] Add focused API/schema tests for vocab governance and capability tag canonicalization.
  - [x] Update existing capability tests to seed active vocab terms before capability registration.
  - [x] Regenerate checked-in capability-registry OpenAPI and verify drift.
  - [x] Run focused tests, ruff check/format, mypy, OpenAPI gates, and `git diff --check`.

- [ ] T5: Post-implementation review and GitHub closure. (AC: 34-36)
  - [x] Run adversarial code review after implementation.
  - [x] Fix or document all findings.
  - [ ] Commit implementation, push branch, create PR, wait for CI.
  - [ ] Merge PR, delete remote branch, sync local `main`.
  - [ ] Only after sync, make a separate status commit marking story/sprint done.

## Dev Notes

### Existing Implementation Anchors

- `CapabilityTag` currently stores arbitrary normalized tags in `apps/capability-registry/src/capability_registry/models.py`.
- `normalize_tag()` in `schemas.py` is the existing normalization contract and must remain the single behavior for term/alias/capability tag input.
- `CapabilityUpsertRequest.tags` currently normalizes and dedupes input before route code runs.
- `upsert_capability()` currently validates provider existence, mutates/creates the capability row, then deletes/reinserts all `CapabilityTag` rows.
- Existing tests use `capability_payload(tags=["LP", "linear programming"])` and expect response tags `["linear_programming", "lp"]`; this story must change tests to seed vocab and expect canonical-only tags when an alias maps to `lp`.
- `CapabilityCache` and `_invalidate_cache()` already use coarse `capability_cache:*` invalidation; reuse it for vocab writes.

### Data Model Guidance

- Use two new tables rather than overloading `capability_tags`. `capability_tags` remains a per-capability join table containing canonical tags only.
- Keep global/tenant uniqueness consistent with existing provider/capability tables:
  - global term unique: `tag WHERE tenant_id IS NULL`
  - tenant term unique: `(tenant_id, tag) WHERE tenant_id IS NOT NULL`
  - global alias unique: `alias WHERE tenant_id IS NULL`
  - tenant alias unique: `(tenant_id, alias) WHERE tenant_id IS NOT NULL`
- Consider indexes for `status`, `task_type`, and `canonical_tag` to support later 6.C.4 reads without adding matching logic now.
- Do not add foreign keys from alias canonical tag to term tag unless they correctly handle tenant/global fallback. Service-layer validation is acceptable and matches existing provider/capability provider-reference handling.
- Metadata fields must reject credential/raw-payload keys using the existing `_reject_forbidden_reference_fields()` helper.

### API Guidance

- Suggested routes:
  - `GET /v1/capability-vocab/terms`
  - `GET /v1/capability-vocab/terms/{tag}`
  - `PUT /v1/capability-vocab/terms/{tag}`
- Suggested response shape:
  - term fields plus `scope_source`, `aliases`, `created_at`, `updated_at`
  - alias fields include `alias`, `canonical_tag`, `status`, `metadata`, timestamps
- Keep errors simple `HTTPException` responses, consistent with current capability-registry v1.
- When resolving a tag for capability upsert, prefer tenant term over global term, and tenant alias over global alias. If both an active canonical term and active alias exist with the same input in the same effective scope but point differently, fail closed with 409/422 rather than guessing.

### Boundary Guidance

- This story creates the vocabulary substrate for 6.C.4; it must not add equivalent-provider ranking or modify rerun.
- `solver-orchestrator` can continue using its local resolver from 6.C.1. No runtime dependency on capability-registry is introduced here.
- Do not add UI. Public/read-only vocab APIs are enough for future docs/admin surfaces.

### Suggested Commands

```powershell
$env:PYTHONPATH='apps/capability-registry/src'; uv run pytest apps/capability-registry/tests/test_api.py -q
uv run ruff check apps/capability-registry/src/capability_registry apps/capability-registry/tests/test_api.py
uv run ruff format --check apps/capability-registry/src/capability_registry apps/capability-registry/tests/test_api.py
uv run mypy apps/capability-registry/src/capability_registry
uv run python scripts/generate_openapi.py
uv run python scripts/check_openapi_drift.py
git diff --check
```

## Definition Of Done

- Story file has passed exactly three pre-implementation adversarial review rounds and has been revised after each round.
- capability-registry has canonical vocab term/alias persistence, read APIs, protected upsert API, and active canonical tag enforcement during capability registration.
- Existing provider/capability public shapes remain compatible except for canonical-only tag normalization.
- Story 6.C.4 matching and solver-orchestrator runtime integration remain out of scope.
- Post-implementation code review is completed and findings are fixed or explicitly documented.
- Local gates and GitHub CI pass.
- PR is merged, remote branch is deleted, and local `main` is synced before story/sprint status is marked `done`.
- Final done status is recorded in a separate post-merge status-sync commit.

## Pre-Implementation Adversarial Review

### Round 1 - Boundary, Scope, And Fake-Completion Review

Findings:

1. The raw Epic AC could be faked by continuing to store free-form normalized tags in `capability_tags` without any canonical vocabulary governance.
2. A story titled "vocab design" could drift into 6.C.4 equivalent matching or solver rerun integration instead of building the registry contract.
3. Existing `capability_tags` has no status or alias semantics; overloading it would make per-capability tags indistinguishable from governed vocabulary terms.
4. Without explicit active-only enforcement at capability upsert, draft/deprecated vocabulary rows could still enter Provider registration and corrupt future matching.

Revision after Round 1:

- Added dedicated `capability_vocab_terms` and `capability_vocab_aliases` scope.
- Added explicit out-of-scope boundaries for 6.C.4 matching and solver-orchestrator runtime integration.
- Required capability upsert to resolve tags through vocab before mutation and store only active canonical tags.
- Required unknown/draft/deprecated tags to fail before DB mutation.

Status: PASS after revision.

### Round 2 - Drift, Data Consistency, Tenant Scope, And Alias Review

Findings:

1. Tenant/global fallback semantics could drift from existing provider/capability behavior unless the story repeats the expected resolution order.
2. Postgres `NULL` uniqueness would allow duplicate global terms/aliases if ordinary composite unique indexes were used.
3. Alias collisions could silently point the same provider input to different canonical tags across updates.
4. Parent/replacement links can create self-references or point to missing terms unless explicitly checked.
5. Capability upsert currently mutates the capability before deleting/reinserting tags; invalid tags after that point would cause partial writes.

Revision after Round 2:

- Added tenant-first/global-fallback vocab resolution with `scope_source`.
- Required partial unique indexes for global and tenant term/alias uniqueness.
- Added alias same-value/collision checks and parent/replacement validation.
- Required resolving all tags before capability mutation, preserving atomic no-mutation behavior.

Status: PASS after revision.

### Round 3 - Dependency, Cache, OpenAPI, Closure, And Privacy Review

Findings:

1. Vocab writes can stale existing capability list/detail cache because capability responses include tags.
2. New schemas could expose metadata with secrets/raw provider payload unless they reuse existing forbidden-field validation.
3. Tests need to update existing capability fixtures; otherwise canonical enforcement will make current tests fail without proving the new behavior.
4. OpenAPI drift is likely because new routes/schemas are public.
5. The user's workflow requires GitHub merge/delete/sync before marking story or sprint `done`.

Revision after Round 3:

- Required vocab writes to invalidate `capability_cache:*` and Redis-unavailable fallback tests to remain green.
- Required metadata forbidden-field validation on vocab term and alias schemas.
- Added explicit fixture/test updates for active vocab seeding and alias-to-canonical capability registration.
- Added OpenAPI generation/drift gates and GitHub closure with separate final status-sync commit.

Status: PASS after revision. Story is ready for development.

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Debug Log References

- 2026-06-06 - Created Story 6.C.3 from Epic 6.C / PRD R4 / architecture Capability Registry backbone / Story 7.A.1 service foundation / Story 6.C.1 and 6.C.2 boundaries.
- 2026-06-06 - Completed exactly three pre-implementation adversarial review rounds and revised story after each round.
- 2026-06-06 - Implementation started; story and sprint status moved to in-progress. Baseline commit: `17d958e50eda522b51188f7fcb029e757838ce75`.
- 2026-06-06 - Red phase confirmed: new vocab endpoint test failed with `404 Not Found`.
- 2026-06-06 - Implemented vocab term/alias SQL, ORM, schemas, APIs, capability tag canonicalization, tests, and generated OpenAPI.
- 2026-06-06 - Local validation passed: focused vocab tests `5 passed`; full capability-registry tests `60 passed`; ruff check/format passed; mypy passed; OpenAPI drift passed; `git diff --check` passed.
- 2026-06-06 - Post-implementation adversarial code review found two patch findings: alias response lacked audit timestamps and blank `task_type` list filter shared the same cache key as no filter. Both were fixed, with tenant alias override regression added.
- 2026-06-06 - Final local validation after review fixes passed: focused vocab tests `6 passed`; full capability-registry tests `61 passed`; ruff check/format passed; mypy passed; OpenAPI drift passed; `git diff --check` passed.
- 2026-06-06 - CI remediation completed: fixed story trailing whitespace and synchronized the error-i18n audit legacy HTTPException register baseline for the new capability-registry routes. Validation passed: `uv run python scripts/validate_error_i18n_audit.py`; `uv tool run pre-commit run --all-files --show-diff-on-failure`; `git diff --check`.

### Completion Notes List

- Story context created and marked ready-for-dev.
- Added canonical capability vocab term and alias governance in capability-registry.
- Added protected `/v1/capability-vocab/terms` list/detail/upsert APIs with tenant/global fallback, alias management, parent/replacement validation, and metadata safety checks.
- Capability upsert now resolves submitted tags through active canonical terms or active aliases before mutating rows, stores only sorted/de-duped canonical tags, and rejects unknown/draft/deprecated tags without partial writes.
- Updated capability-registry API tests and OpenAPI spec; implementation is ready for post-implementation code review.
- Post-implementation review completed; fixed alias response audit fields and normalized blank task_type filtering/cache keys.
- PR CI remediation completed for lint trailing whitespace and error-i18n audit contract drift without marking the story done before merge/sync.

### File List

- `_bmad-output/stories/6-c-3-capability-vocab-design.md`
- `_bmad-output/stories/sprint-status.yaml`
- `apps/capability-registry/src/capability_registry/models.py`
- `apps/capability-registry/src/capability_registry/routes.py`
- `apps/capability-registry/src/capability_registry/schemas.py`
- `apps/capability-registry/tests/test_api.py`
- `infra/local-init/14-capability-registry.sql`
- `packages/shared-ts/openapi/capability-registry.json`
- `tools/error_i18n_audit/error_i18n_audit_contract.json`

## Change Log

- 2026-06-06 - Created Story 6.C.3 and completed three pre-implementation adversarial review rounds.
- 2026-06-06 - Implemented capability vocab governance and moved story to code-review after local validation.
- 2026-06-06 - Completed post-implementation code review and fixed two patch findings.
- 2026-06-06 - Fixed PR CI lint and error-i18n audit contract drift.

## Post-Implementation Code Review

### Scope

- Reviewed capability vocab SQL/ORM/schema/routes/tests/OpenAPI against AC 1-36.
- Checked boundary risks: free-form tag bypass, draft/deprecated tag leakage, tenant/global fallback drift, alias collision, partial writes on invalid tags, stale cache, unsafe metadata, 6.C.4 scope creep, and solver-orchestrator coupling.

### Findings

1. Finding: `CapabilityVocabAliasResponse` omitted `id`, `tenant_id`, `created_at`, and `updated_at`.
   - Risk: weaker audit/read contract for alias rows and drift from story guidance that alias responses include timestamps.
   - Resolution: added alias response id/scope/timestamps, regenerated OpenAPI, and updated vocab response assertions.

2. Finding: `GET /v1/capability-vocab/terms?task_type=` normalized blank task_type to no filtering at runtime but used the same cache key as no filter only by coincidence through `or "all"`.
   - Risk: ambiguous filter semantics and future cache-key drift if blank task_type handling changes.
   - Resolution: normalized blank task_type to `None` before cache-key construction and filtering.

3. Finding: tenant alias override behavior needed explicit regression coverage.
   - Risk: future changes could silently bypass a tenant alias by falling back to a global alias, undermining tenant override semantics.
   - Resolution: added `test_capability_vocab_tenant_alias_overrides_global_alias_fail_closed`, proving tenant alias wins and non-active canonical resolution fails closed.

### Review Result

- No remaining blocking findings after fixes.
- Validation evidence: focused vocab tests `6 passed`; full capability-registry suite `61 passed`; ruff check/format passed; `uv run mypy apps/capability-registry/src/capability_registry` passed; OpenAPI generation/drift passed; `git diff --check` passed.
