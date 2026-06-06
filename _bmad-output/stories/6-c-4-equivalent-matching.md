---
story_key: 6-c-4-equivalent-matching
baseline_commit: adc459b99bed42e3671f180cabf8ade379b2a9f2
epic_num: 6
story_num: C.4
epic_name: Auto-migration + Provider Exit v2
status: code-review
priority: High
type: equivalent provider matching
created_by: bmad-create-story
created_at: 2026-06-06
sources:
  - _bmad-output/planning/epics.md (Epic 6.C / Story 6.C.4 / R4 equivalent matching)
  - _bmad-output/planning/prd.md (FR R4 auto-migrate to equivalent Provider using capability vocabulary)
  - _bmad-output/planning/architecture.md (Capability Registry, Provider routing, Repro 5y SLA)
  - _bmad-output/stories/6-c-1-auto-migrate-provider.md
  - _bmad-output/stories/6-c-2-30d-exit-notification.md
  - _bmad-output/stories/6-c-3-capability-vocab-design.md
  - apps/capability-registry/src/capability_registry/models.py
  - apps/capability-registry/src/capability_registry/schemas.py
  - apps/capability-registry/src/capability_registry/routes.py
  - apps/capability-registry/tests/test_api.py
  - infra/local-init/14-capability-registry.sql
---

# Story 6.C.4 - Equivalent Matching Algorithm

Status: code-review

## Story

**作为** Repro 自动迁移与 Provider 路由团队，
**我希望** capability-registry 能基于 active canonical vocab tags、task type、solver support、provider/capability 状态、precision 指标和版本相似度给出确定性的 equivalent Provider 候选排序，
**从而** voucher rerun auto-migration 和后续路由逻辑可以在“同 vocab Provider”之间选择高精度、版本接近且可审计的替代 Provider，而不是依赖自由文本或非确定性规则。

## Context

Epic 6.C 的 R4 要求系统能 auto-migrate to equivalent Provider。Story 6.C.1 已在 `solver-orchestrator` 内实现本地 rerun migration preflight，但明确排除了 broader equivalent matching service；Story 6.C.3 已让 capability-registry 维护 canonical vocab，并强制 capability tags 只落 active canonical tags。本 story 是 R4 的补全：在 capability-registry 内增加只读 equivalent matching/ranking 合同，为“两个 Provider 同 vocab 时 prefer 高 precision / similar version”提供可测试、可审计、确定性的排序结果。

现状：

- `capability_providers.status` 目前支持 `active`、`inactive`、`deprecated`。
- `capabilities.status` 目前支持 `v1`、`v1_late`、`v2`、`audited`、`shadow`。
- `capability_tags` 已被 6.C.3 约束为 active canonical tags。
- `Capability.capability_metadata` 可存非敏感结构化指标，但没有 dedicated precision 字段。
- capability-registry 已有 public read routes、internal-secret write routes、Redis cache 和 OpenAPI drift gate。
- solver-orchestrator 的 `provider_migration.py` 仍是本地 fallback/preflight 逻辑；本 story 不让 solver runtime 调 capability-registry。

## Scope

1. 在 capability-registry 增加只读 equivalent matching endpoint 和纯 ranking helper。
2. 匹配只从已注册的 provider/capability/vocab/tag 数据读取，不新增 worker、scheduler、DB 表或跨服务调用。
3. 等价候选必须满足同 `task_type`、同 canonical tag 集合、支持 requested solver、active provider、eligible capability status。
4. 排序必须优先 precision 分数，再版本相似度，再 provider/capability lexical tie-break，保证同输入同数据输出稳定。
5. 输出必须是审计友好的非敏感 fields：ranking version、filters、source、candidates、score breakdown、rejection counts。
6. 保持现有 provider/capability/vocab write/read 合同兼容；不修改 rerun、Provider exit notification、UI、billing 或 revenue share。

## Out Of Scope

- 不修改 `solver-orchestrator` rerun endpoint、`provider_migration.py` 运行时、voucher 数据模型、idempotency、billing 或 solver execution。
- 不实现 cross-service live lookup、repro-service、worker、scheduler、manual review queue、ML scorer 或 online traffic rerouting。
- 不新增 matching DB 表、precision telemetry ingestion pipeline、shadow validation computation、provider KPI dashboard 聚合或 revenue-share 逻辑。
- 不新增 UI、status page、email、站内信或 Provider exit notification 行为。
- 不放宽 6.C.3 canonical vocab active-only enforcement，也不允许 free-form tags 回流。
- 不暴露 raw benchmark payload、provider request/response、solution、API key、JWT、email、phone、billing id、provider secret 或 raw dataset。

## Acceptance Criteria

1. Add a pure matching/ranking helper in capability-registry, preferably `apps/capability-registry/src/capability_registry/equivalent_matching.py`, with no database/session dependency and no network dependency.
2. The helper accepts a source capability snapshot, candidate snapshots, requested solver, and optional max results, then returns deterministic ranking plus rejection counts.
3. Snapshots include only safe fields needed for matching: tenant scope, `k_algo`, `task_type`, `provider_id`, provider kind/status/url, model version, capability status, supported solvers, canonical tags, precision score, and updated timestamp.
4. Source resolution is by `k_algo` plus optional `tenant_id`, using existing tenant-first/global-fallback semantics from capability detail reads.
5. `GET /v1/capabilities/{k_algo}/equivalents` returns equivalent candidates for the source capability.
6. Query params include optional `tenant_id`, required `solver`, optional `max_results` defaulting to 10 with safe upper bound 50, and optional `include_source` defaulting false.
7. The endpoint returns 404 when the source capability cannot be resolved.
8. The endpoint returns 422 when `solver` is blank or not supported by the source capability.
9. The endpoint never mutates provider, capability, vocab, tag, cache, or audit tables.
10. Matching requires candidate `task_type` equal to source `task_type`.
11. Matching requires candidate canonical tag set equal to the source canonical tag set; strict subset, superset, or unrelated tags are rejected.
12. Matching requires candidate `supported_solvers` contains the requested solver.
13. Matching requires candidate provider status `active`.
14. Matching requires candidate capability status in the eligible set `v1`, `v1_late`, `v2`, or `audited`; `shadow` is rejected.
15. Matching excludes the source capability by default; when `include_source=true`, source can appear only if it passes the same eligibility rules.
16. Tenant-scoped candidate rows override global rows with the same `k_algo`, mirroring existing capability list behavior.
17. A tenant request can include global fallback candidates unless a tenant row overrides that `k_algo`.
18. Candidate provider resolution uses candidate tenant scope first and global fallback second; provider mismatch or missing provider rejects the candidate.
19. Precision score is read from safe metadata fields only: prefer `metadata.matching.precision`, fallback `metadata.precision`, and treat missing precision as `0`.
20. Precision score must be numeric in `[0, 1]`; invalid precision metadata rejects the candidate rather than crashing.
21. Version similarity compares source and candidate `model_version` as semantic versions when both parse as `MAJOR.MINOR.PATCH`; smaller semantic distance ranks higher.
22. Non-semver versions are allowed but rank behind parseable semantic-version candidates for the version-similarity component.
23. Ranking order is deterministic: higher precision, then smaller version distance, then same provider kind as source, then lexicographic `provider_id`, `model_version`, and `k_algo`.
24. Response includes `ranking_version`, `source`, `solver`, `required_tags`, `total_candidates_considered`, `rejection_counts`, and `candidates`.
25. Each candidate includes `rank`, `k_algo`, `provider_id`, `model_version`, `provider_kind`, `provider_url`, `task_type`, `supported_solvers`, `tags`, `precision`, `version_distance`, `score`, `score_breakdown`, and `scope_source`.
26. `score` is deterministic and JSON-safe, expressed as a string with fixed precision; it must not be used as the only ranking authority when tie-breakers differ.
27. Response and logs do not include raw capability metadata except the allowed numeric precision-derived fields.
28. Empty candidate result returns 200 with `candidates=[]` and populated rejection counts, not 404.
29. Redis cache may be used for the new read endpoint, but Redis unavailable must fall back to DB-backed responses.
30. Existing provider/capability/vocab writes must invalidate any cached equivalent results through the existing `capability_cache:*` invalidation.
31. Existing provider, capability, and vocab response shapes remain unchanged.
32. OpenAPI generation includes the new endpoint and response schemas.
33. Tests cover pure ranking: precision priority, version similarity, solver mismatch rejection, tag mismatch rejection, inactive provider rejection, shadow capability rejection, invalid precision rejection, include_source behavior, and lexical deterministic tie-breaks.
34. API tests cover source not found, unsupported solver 422, empty candidates 200, tenant override/global fallback, Redis fallback, cache invalidation after candidate precision update, and privacy of metadata.
35. Focused capability-registry tests, ruff check/format, mypy, OpenAPI generation/drift, `uv run python scripts/validate_error_i18n_audit.py` if HTTPException counts drift, and `git diff --check` pass locally.
36. Post-implementation adversarial code review is run after implementation; findings are fixed or explicitly documented in this story.
37. GitHub PR CI must pass, PR must be merged, remote feature branch deleted, and local `main` synced before this story or sprint status is marked `done`.
38. The final `done` status update must be a separate status-sync commit after GitHub merge/sync.

## Tasks / Subtasks

- [x] T1: Add pure equivalent matching helper and schemas. (AC: 1-3, 10-28, 33)
  - [x] Add snapshot/result dataclasses or Pydantic-safe structures in a local module.
  - [x] Implement precision extraction, semantic-version distance, eligibility filtering, rejection counts, and deterministic sorting.
  - [x] Add response schemas in `schemas.py` without exposing raw metadata.
  - [x] Add pure helper tests for score/ranking boundaries.

- [x] T2: Add read-only equivalent matching endpoint. (AC: 4-9, 16-18, 24-32, 34)
  - [x] Add `GET /v1/capabilities/{k_algo}/equivalents`.
  - [x] Resolve source and candidates using existing tenant/global fallback semantics.
  - [x] Resolve providers with candidate tenant scope then global fallback.
  - [x] Preserve Redis-unavailable DB fallback and cache invalidation behavior.
  - [x] Keep the endpoint read-only and public like existing capability reads.

- [x] T3: Add focused API tests and generated OpenAPI. (AC: 32-35)
  - [x] Extend `apps/capability-registry/tests/test_api.py` or add a focused test file.
  - [x] Seed active vocab terms before capability creation.
  - [x] Cover equivalent matching API edge cases, cache, tenant scope, and metadata privacy.
  - [x] Regenerate `packages/shared-ts/openapi/capability-registry.json`.

- [x] T4: Validate implementation and update story records. (AC: 35)
  - [x] Run focused capability-registry equivalent matching tests.
  - [x] Run full capability-registry tests as feasible.
  - [x] Run ruff check/format, mypy, OpenAPI generation/drift, error-i18n audit if needed, and `git diff --check`.
  - [x] Update Dev Agent Record, File List, Completion Notes, and Change Log.

- [ ] T5: Post-implementation review and GitHub closure. (AC: 36-38)
  - [x] Run adversarial code review after implementation.
  - [x] Fix or document all findings.
  - [ ] Commit implementation, push branch, create PR, wait for CI.
  - [ ] Merge PR, delete remote branch, sync local `main`.
  - [ ] Only after sync, make a separate status commit marking story/sprint done.

### Review Findings

- [x] [Review][Patch] Source capabilities without canonical tags could still be matched — Fixed by rejecting equivalent matching requests for a source capability with no canonical tags and adding an API regression.
- [x] [Review][Patch] `include_source=true` lacked direct regression coverage — Added API coverage proving the source is included only when requested and eligible.

## Dev Notes

### Existing Implementation Anchors

- `CapabilityProvider`, `Capability`, `CapabilityTag`, `CapabilityVocabTerm`, and `CapabilityVocabAlias` live in `apps/capability-registry/src/capability_registry/models.py`.
- `CapabilityResponse`, vocab response schemas, `normalize_tag()`, metadata forbidden-field checks, and current Literal status definitions live in `apps/capability-registry/src/capability_registry/schemas.py`.
- Existing route helpers in `routes.py` already implement tenant/global fallback, provider resolution, cache get/set/fallback, cache invalidation, and capability tag lookup.
- 6.C.3 changed capability upsert to resolve and persist only active canonical vocab tags. Matching can trust `capability_tags` as canonical, but tests should still seed vocab explicitly.
- `Capability.capability_metadata` is exposed today as `metadata`; this story must not expose raw metadata in equivalent matching responses.
- Existing `provider_migration.py` in solver-orchestrator contains similar ranking concepts, but it is not a shared library and must not be imported into capability-registry.

### Matching Contract

- Treat equality of canonical tag sets as the equivalence boundary for this story. Do not use fuzzy tag overlap, parent/replacement expansion, ML embeddings, or cross-task substitution.
- Precision source is optional metadata:
  - `{"matching": {"precision": 0.98}}` is preferred.
  - `{"precision": 0.98}` is fallback.
  - missing precision = `0`.
  - invalid precision rejects the candidate and increments `invalid_precision`.
- Suggested score string can be derived from precision plus small deterministic version component, but sorting must follow the explicit rank tuple, not opaque score math.
- Suggested ranking version: `capability-equivalent-matching-v1`.
- Suggested rejection count keys: `task_type_mismatch`, `tag_mismatch`, `solver_mismatch`, `provider_not_active`, `capability_not_eligible`, `provider_missing`, `invalid_precision`, `source_excluded`.

### API Guidance

- Suggested route:
  - `GET /v1/capabilities/{k_algo}/equivalents?solver=highs&tenant_id=...&max_results=10&include_source=false`
- `solver` should be stripped and non-empty.
- `max_results` should be bounded to avoid large response/cache keys.
- Cache key must include source `k_algo`, tenant id/global, solver, max_results, and include_source.
- Provider/capability/vocab writes already call `_invalidate_cache()`; keep equivalent matching cache under `capability_cache:*`.
- If this story adds new HTTPException(detail=literal) entries, update `tools/error_i18n_audit/error_i18n_audit_contract.json` and `tests/test_error_i18n_audit.py` pins as needed.

### Boundary Guidance

- Do not change `solver-orchestrator` runtime migration in this story. Future integration can consume this API or export snapshots, but that is not part of 6.C.4.
- Do not add SQL migrations unless implementation proves a stored field is unavoidable. Metadata-derived precision is enough for this story and avoids schema churn.
- Do not mutate existing capability/provider response models. Equivalent matching gets new response schemas only.
- Do not rely on provider application/shadow validation tables for precision calculation. Those flows are separate and may later write safe precision metadata.

### Suggested Commands

```powershell
$env:PYTHONPATH='apps/capability-registry/src'; uv run pytest apps/capability-registry/tests/test_api.py -q
uv run ruff check apps/capability-registry/src/capability_registry apps/capability-registry/tests/test_api.py
uv run ruff format --check apps/capability-registry/src/capability_registry apps/capability-registry/tests/test_api.py
uv run mypy apps/capability-registry/src/capability_registry
uv run python scripts/generate_openapi.py
uv run python scripts/check_openapi_drift.py
uv run python scripts/validate_error_i18n_audit.py
git diff --check
```

## Definition Of Done

- Story file has passed exactly three pre-implementation adversarial review rounds and has been revised after each round.
- capability-registry exposes deterministic equivalent matching over active canonical vocab tags with precision/version ranking.
- Existing provider, capability, vocab, rerun, Provider exit, billing, UI, and revenue-share behavior remain compatible.
- Post-implementation code review is completed and findings are fixed or explicitly documented.
- Local gates and GitHub CI pass.
- PR is merged, remote branch is deleted, and local `main` is synced before story/sprint status is marked `done`.
- Final done status is recorded in a separate post-merge status-sync commit.

## Pre-Implementation Adversarial Review

### Round 1 - Boundary, Scope, And Fake-Completion Review

Findings:

1. The raw Epic AC could be faked by returning all same-task providers without proving canonical vocab equality.
2. A broad "matching algorithm" title could drift into solver-orchestrator rerun integration, ML scoring, manual review queues, or routing infrastructure.
3. Adding dedicated precision columns/tables would increase schema churn even though capability metadata can already hold safe numeric metrics.
4. Without an explicit no-mutation rule, a read endpoint could accidentally update cache/audit/provider state or create derived records.

Revision after Round 1:

- Required exact canonical tag-set equality and same task type as the equivalence boundary.
- Scoped implementation to capability-registry read-only helper/API; solver runtime integration and ML/manual queues are out of scope.
- Chose metadata-derived precision with strict allowlisted extraction instead of a new DB table.
- Added no-mutation AC and cache-only behavior.

Status: PASS after revision.

### Round 2 - Drift, Data Consistency, Tenant Scope, And Ranking Review

Findings:

1. Tenant/global fallback could drift from existing capability reads unless source and candidate resolution rules are explicit.
2. "Prefer high precision / similar version" was underspecified and could produce non-deterministic ordering.
3. Provider rows are separate from capability rows; a candidate with missing/inactive provider must be rejected rather than returned with stale model_version data.
4. Invalid precision metadata could crash requests or silently rank unsafe data high.

Revision after Round 2:

- Added source/candidate/provider tenant-first/global-fallback rules and override semantics.
- Defined deterministic rank tuple: precision desc, semantic version distance, same provider kind, lexical provider/version/k_algo.
- Required active provider and eligible capability status checks.
- Required invalid precision rejection with rejection counts and no crash.

Status: PASS after revision.

### Round 3 - Dependency, Privacy, Cache, CI, And Closure Review

Findings:

1. Raw capability metadata may contain future sensitive references; equivalent matching must not echo it.
2. New endpoint responses and schemas will change OpenAPI and could drift CI if not regenerated.
3. Equivalent cache can stale after provider/capability/vocab writes if it does not share the existing cache invalidation prefix.
4. New HTTPException literals can break the Story 9.6 error-i18n audit pin.
5. The user's workflow requires GitHub merge/delete/sync before marking story or sprint `done`.

Revision after Round 3:

- Added response field allowlist and explicit raw metadata privacy AC.
- Added OpenAPI generation/drift and focused API test requirements.
- Required equivalent cache to use `capability_cache:*` invalidation.
- Added error-i18n audit validation/update guidance.
- Added GitHub closure and separate final status-sync commit ACs/DoD.

Status: PASS after revision. Story is ready for development.

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Debug Log References

- 2026-06-06 - Created Story 6.C.4 from Epic 6.C / PRD R4 / architecture capability-registry ownership / Story 6.C.1, 6.C.2, and 6.C.3 boundaries.
- 2026-06-06 - Completed exactly three pre-implementation adversarial review rounds and revised story after each round.
- 2026-06-06 - Implementation started; story and sprint status moved to in-progress. Baseline commit: `adc459b99bed42e3671f180cabf8ade379b2a9f2`.
- 2026-06-06 - Red phase confirmed: equivalent matching API tests failed with `404 Not Found` because `/v1/capabilities/{k_algo}/equivalents` did not exist.
- 2026-06-06 - Implemented pure equivalent matching helper, response schemas, read-only API endpoint, API tests, pure helper tests, OpenAPI update, and error-i18n audit baseline/test pin sync.
- 2026-06-06 - Local validation passed: focused equivalent tests `6 passed`; full capability-registry tests `67 passed`; error-i18n audit tests `23 passed`; ruff check/format passed; mypy passed; OpenAPI generation/drift passed; error-i18n audit validation passed; `git diff --check` passed.
- 2026-06-06 - Post-implementation adversarial code review found two patch findings: source capabilities without canonical tags could be matched, and `include_source=true` needed direct regression coverage. Both were fixed.
- 2026-06-06 - Final local validation after review fixes passed: full capability-registry tests `67 passed`; error-i18n audit tests `23 passed`; mypy passed; OpenAPI generation/drift passed; error-i18n audit validation passed; full pre-commit passed; `git diff --check` passed.

### Completion Notes List

- Story context created and marked ready-for-dev.
- Equivalent matching scope constrained to capability-registry read-only ranking over canonical tags, precision metadata, and version similarity.
- Explicitly excluded solver rerun integration, Provider exit notifications, UI, workers, ML scoring, manual review queues, and new DB tables.
- Added `capability_registry.equivalent_matching` with deterministic eligibility filtering, precision extraction, semantic-version distance, rejection counts, ranking, and JSON-safe response projection.
- Added `GET /v1/capabilities/{k_algo}/equivalents` with tenant/global fallback, solver validation, cache support, Redis-unavailable fallback, and metadata privacy.
- Added focused pure/API tests, regenerated capability-registry OpenAPI, and synchronized error-i18n audit legacy HTTPException pins for the new route literals.
- Post-implementation review completed; fixed no-canonical-tag source rejection and added `include_source=true` regression coverage.
- Implementation is ready for GitHub PR/CI closure; story remains `code-review` until merge/delete/sync completes.

### File List

- `_bmad-output/stories/6-c-4-equivalent-matching.md`
- `_bmad-output/stories/sprint-status.yaml`
- `apps/capability-registry/src/capability_registry/equivalent_matching.py`
- `apps/capability-registry/src/capability_registry/routes.py`
- `apps/capability-registry/src/capability_registry/schemas.py`
- `apps/capability-registry/tests/test_api.py`
- `apps/capability-registry/tests/test_equivalent_matching.py`
- `packages/shared-ts/openapi/capability-registry.json`
- `tools/error_i18n_audit/error_i18n_audit_contract.json`
- `tests/test_error_i18n_audit.py`

## Change Log

- 2026-06-06 - Created Story 6.C.4 and completed three pre-implementation adversarial review rounds.
- 2026-06-06 - Implementation started; story moved to in-progress.
- 2026-06-06 - Implemented equivalent matching helper/API/tests and moved story to code-review after local validation.
- 2026-06-06 - Completed post-implementation code review and fixed two patch findings.

## Post-Implementation Code Review

### Scope

- Reviewed equivalent matching helper, route integration, schemas, tests, OpenAPI, and error-i18n audit pin updates against AC 1-38.
- Checked boundary risks: tag-set equality, tenant/global fallback, solver support, active provider gating, shadow capability rejection, invalid precision handling, metadata privacy, cache invalidation, read-only behavior, and no solver-orchestrator coupling.

### Findings

1. Finding: source capabilities without canonical tags could still invoke matching and return candidates with empty tag sets.
   - Risk: violates the "同 vocab" boundary and could make untagged capabilities look equivalent.
   - Resolution: endpoint now rejects sources with no canonical tags using 422; API regression added.

2. Finding: `include_source=true` behavior lacked direct API regression coverage.
   - Risk: future route/helper changes could ignore or invert the flag without being caught.
   - Resolution: API regression now proves the source is excluded by default and included only with `include_source=true` when eligible.

### Review Result

- No remaining blocking findings after fixes.
- Validation evidence: full capability-registry tests `67 passed`; error-i18n audit tests `23 passed`; `uv run mypy apps/capability-registry/src/capability_registry` passed; OpenAPI generation/drift passed; `uv run python scripts/validate_error_i18n_audit.py` passed; full pre-commit passed; `git diff --check` passed.
