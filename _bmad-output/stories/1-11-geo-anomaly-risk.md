---
story_key: 1-11-geo-anomaly-risk
epic_num: 1
story_num: 1.11
epic_name: Account & Identity
status: done
priority: High (NFR-S4 API Key 异常地理风险评分；承接 Story 1.3 / 1.5 / 1.10)
sizing: M (~6-8 hours; solver 鉴权信号 + auth 列表风险摘要 + Web modal + tests)
type: implementation + security + ui + test
created_by: bmad-create-story
created_at: 2026-05-25
sources:
  - [Source: D:/优化预测网站/_bmad-output/planning/epics.md:1339-1341]
  - [Source: D:/优化预测网站/_bmad-output/planning/prd.md:748]
  - [Source: D:/优化预测网站/_bmad-output/planning/prd.md:1081]
  - [Source: D:/优化预测网站/_bmad-output/planning/prd.md:1628]
  - [Source: D:/优化预测网站/_bmad-output/planning/epics.md:148]
  - [Source: D:/优化预测网站/_bmad-output/planning/epics.md:299]
  - [Source: D:/优化预测网站/_bmad-output/stories/1-5-risk-control-freeze.md]
  - [Source: D:/优化预测网站/_bmad-output/stories/1-10-language-switch-zh.md]
  - [Source: D:/优化预测网站/apps/solver-orchestrator/src/solver_orchestrator/auth.py]
  - [Source: D:/优化预测网站/apps/auth-service/src/auth_service/routes.py]
  - [Source: D:/优化预测网站/apps/auth-service/src/auth_service/models.py]
  - [Source: D:/优化预测网站/apps/web/src/app/auth/api-keys/page.tsx]
dependencies:
  upstream:
    - 1-3-api-keys-crud-complete (done) - API Key CRUD、`last_used_at`、Web `/auth/api-keys`
    - 1-5-risk-control-freeze (done) - `risk_rules` / `risk_flags` / `users.risk_score` 风控底座
    - 1-10-language-switch-zh (done) - `Accept-Language` 与 locale helper
  downstream:
    - 1-12-j7-fraud-freeze-vertical-slice - 需要复用风险证据与用户可恢复路径
    - 3-7-rfc7807-errors-detail - 风险/错误提示继续接入统一错误面板
---

# Story 1.11 - 异常地理风险评分

Status: done

## User Story

**As** an API Key owner,
**I want** OptiCloud to detect when a continuously used API Key suddenly moves between clearly different geographies,
**so that** my account risk score rises, I see a focused warning, and I can revoke the suspicious key immediately.

## Why

PRD 的 NFR-S4 明确要求 API Key 仅 hash 入库、前缀可见、可一键吊销，并且“异常地理跨越触发风险评分”。Story 1.3 已经提供 API Key CRUD 与 `last_used_at` 更新，Story 1.5 已经提供 `risk_flags` 与 `users.risk_score` 风控底座，Story 1.10 已经统一 Web API 的 `Accept-Language`。本 story 的正确实现不是新建一套风控系统，而是把 solver 鉴权路径产生的 IP 使用信号接到现有风控与 API Key 管理页。

## Out Of Scope

- 外部 GeoIP 供应商、网络调用、MaxMind 数据库、计费型地理定位服务
- 自动冻结账号；本 story 只提高 `risk_score`、写风险证据、提示并支持吊销 key
- 管理员审核台、J7 冻结申诉 UI；Story 1.12 负责闭环
- 代理链 / `X-Forwarded-For` 信任模型；v1 只使用 `request.client.host`
- 细粒度城市级精确定位；v1 使用内置可测试的 coarse geo 区域映射
- 设备指纹、支付复用、24h 调用次数风控规则的启用

## Acceptance Criteria

1. `infra/local-init/08-geo-anomaly-risk.sql` idempotently seeds `risk_rules.code='geo_anomaly'` with `enabled=false`, documenting that it is a score/evidence signal and must not count toward Story 1.5 auto-freeze threshold in v1.
2. Solver API Key verification accepts the request client IP, updates `api_keys.last_used_at` and `api_keys.last_used_ip`, and compares the previous stored IP with the current request IP after successful HMAC verification.
3. A built-in deterministic coarse geo resolver maps only explicitly supported public IPv4 ranges such as Beijing and Singapore testable ranges; private, loopback, reserved, malformed, IPv6, and unknown ranges return `None` and never trigger risk.
4. When a key moves between two known different geo regions, solver writes one `risk_flags` row with `rule_code='geo_anomaly'`, `source='auto'`, `metadata.api_key_id`, previous/current IP, previous/current geo, reason, and score, then raises `users.risk_score` to at least `0.70` without lowering an already higher score.
5. Repeated calls from the same region, first use with no previous IP, unknown/private IPs, and revoked/expired/invalid keys do not create geo risk flags.
6. Auth `GET /v1/auth/api_keys` returns each key with optional `risk_warning` summary when that key has a recent `geo_anomaly` flag; the summary includes `risk_score`, `detected_at`, previous/current geo labels, previous/current IPs, and reason. Existing list fields remain backward compatible.
7. Web `/auth/api-keys` shows a warning modal for active keys with `risk_warning`, using the current locale preference for zh-CN/en-US copy and existing `Accept-Language` behavior for backend calls.
8. The modal provides one-click revoke for the warned key. Confirming revokes via existing `DELETE /v1/auth/api_keys/{id}` and refreshes the list so the row becomes revoked.
9. Tests cover solver geo detection, no-trigger boundaries, auth risk summary serialization, Web modal behavior, one-click revoke, locale copy, and existing regression suites pass.

## Tasks / Subtasks

- [x] Task 1: Add geo-anomaly risk rule migration and CI wiring (AC: 1)
  - [x] Add `infra/local-init/08-geo-anomaly-risk.sql`
  - [x] Apply it in auth-service and solver-orchestrator CI schema setup
  - [x] Add infra path filters so changing the migration triggers both jobs

- [x] Task 2: Implement solver-side geo anomaly detection (AC: 2, 3, 4, 5)
  - [x] Add a small pure helper module for coarse geo resolution and anomaly assessment
  - [x] Extend `verify_api_key` with optional `caller_ip`
  - [x] Update all solver routes to pass `request.client.host`
  - [x] Update `last_used_ip` and write `risk_flags` / `users.risk_score` only after successful HMAC verification

- [x] Task 3: Expose risk warning through auth API key list (AC: 6)
  - [x] Add Pydantic schema for optional API Key risk warning
  - [x] Query latest `geo_anomaly` flags for the authenticated user
  - [x] Attach per-key warning summaries without changing create/revoke response contracts

- [x] Task 4: Add Web warning modal and one-click revoke (AC: 7, 8)
  - [x] Extend TypeScript API key type with `risk_warning`
  - [x] Add zh-CN/en-US message keys for the modal
  - [x] Show the modal for active warned keys on `/auth/api-keys`
  - [x] Confirming the modal revokes the key and refreshes the table

- [x] Task 5: Tests and validation (AC: 9)
  - [x] Add solver tests for Beijing -> Singapore trigger, same-region no-trigger, and unknown/private no-trigger
  - [x] Add auth-service test for `risk_warning` serialization
  - [x] Add Web page tests for warning modal, revoke, and en-US copy
  - [x] Run backend, web, UI, and diff quality gates

- [x] Task 6: Story tracking and release hygiene
  - [x] Fill Dev Agent Record with validation outputs
  - [x] Update File List and Change Log
  - [x] Move story and sprint status through `in-progress`, `review`, and final review result

### Review Findings

- [x] [Review][Patch] Make `geo_anomaly` migration re-run enforce disabled state [`infra/local-init/08-geo-anomaly-risk.sql`] — fixed by using `ON CONFLICT DO UPDATE ... enabled = false`.
- [x] [Review][Patch] Keep API Key warning score tied to the geo risk event [`apps/auth-service/src/auth_service/routes.py`] — fixed by reading `metadata.score` instead of the user's aggregate `risk_score`.
- [x] [Review][Patch] Propagate revoke failures from the Web API client [`apps/web/src/lib/api.ts`] — fixed by sharing RFC 7807 error parsing with `revokeAPIKey` and adding a regression test.

## Dev Notes

- Reuse Story 1.5 objects. Do not create `geo_risk_flags`, `api_key_risk_events`, or a separate risk score table. `risk_flags` is the event log and `users.risk_score` is the score field.
- Keep `geo_anomaly.enabled=false` in `risk_rules`; this prevents geo score evidence from unexpectedly contributing to the Story 1.5 “任 2 项触发” freeze threshold. The flag is still queryable for audit and J7.
- Solver already owns API Key verification and `last_used_at`; it is the only reliable hot path for API Key use. Do not duplicate HMAC validation in auth-service.
- `verify_api_key` must keep its return shape `(user_id, api_key_id, scopes)` to avoid touching unrelated solver routes.
- Use `request.client.host` only. Do not trust `X-Forwarded-For` in this story.
- Coarse geo mapping must be deterministic and testable. Suggested v1 mappings:
  - `101.6.0.0/16` -> `CN-BJ`, label `中国北京`
  - `13.250.0.0/15` -> `SG`, label `新加坡`
  - `8.8.8.0/24` -> `US`, label `美国`
- Unknown/private IPs must still update `last_used_ip` when valid, but must not produce a risk flag.
- Risk score update should be monotonic: set `users.risk_score = GREATEST(users.risk_score, 0.70)`.
- `risk_flags.metadata.api_key_id` should be a string UUID so auth-service can map warnings back to individual keys without fragile JSON coercion.
- Auth API list remains JWT-gated and must keep cross-tenant isolation: only the owner sees their key warning.
- Web modal should use `ConfirmationModal` from `@opticloud/ui`; do not use browser `confirm()` for the risk warning path.
- Existing `revokeAPIKey` already sends `Accept-Language`; keep that path and do not regress Story 1.10.

### Project Structure Notes

- Migration: `infra/local-init/08-geo-anomaly-risk.sql`
- Solver risk helper: `apps/solver-orchestrator/src/solver_orchestrator/geo_risk.py`
- Solver auth path: `apps/solver-orchestrator/src/solver_orchestrator/auth.py`
- Solver request IP wiring: `apps/solver-orchestrator/src/solver_orchestrator/routes.py`
- Auth schema/list endpoint: `apps/auth-service/src/auth_service/schemas.py`, `apps/auth-service/src/auth_service/routes.py`
- Web API and page: `apps/web/src/lib/api.ts`, `apps/web/src/app/auth/api-keys/page.tsx`
- Locale copy: `apps/web/messages/zh-CN.json`, `apps/web/messages/en-US.json`
- Tests: `apps/solver-orchestrator/tests/test_geo_anomaly_risk.py`, `apps/auth-service/tests/test_api_keys_routes.py`, `apps/web/src/app/auth/api-keys/page.test.tsx`

### References

- [Source: D:/优化预测网站/_bmad-output/planning/epics.md:1339-1341]
- [Source: D:/优化预测网站/_bmad-output/planning/prd.md:748]
- [Source: D:/优化预测网站/_bmad-output/planning/prd.md:1081]
- [Source: D:/优化预测网站/_bmad-output/planning/prd.md:1628]
- [Source: D:/优化预测网站/_bmad-output/stories/1-5-risk-control-freeze.md]
- [Source: D:/优化预测网站/_bmad-output/stories/1-10-language-switch-zh.md]
- [Source: D:/优化预测网站/apps/solver-orchestrator/src/solver_orchestrator/auth.py]
- [Source: D:/优化预测网站/apps/auth-service/src/auth_service/routes.py]
- [Source: D:/优化预测网站/apps/web/src/app/auth/api-keys/page.tsx]

## Three-Round Story Review

### Round 1: Data Consistency Review

Scope: IP fields, geo metadata, risk score, user/key identity, status fields, and locale/error keys.

Findings and fixes:

- [x] API Key identity drift risk: solver knows `api_key_id`, while auth list displays user-owned keys. Fixed by requiring `metadata.api_key_id` string UUID in every `geo_anomaly` risk flag.
- [x] IP source mismatch risk: `api_keys.last_used_ip`, `audit_logs.ip_address`, and `request.client.host` could diverge. Fixed by making `api_keys.last_used_ip` the API Key baseline and `request.client.host` the only current signal in this story.
- [x] Score semantics ambiguity: Story 1.5 reserved `risk_score` but did not define geo scoring. Fixed by requiring monotonic `GREATEST(current, 0.70)` and forbidding automatic lowering.
- [x] Freeze-count contamination risk: enabling `geo_anomaly` would accidentally participate in Story 1.5 distinct enabled-rule freeze threshold. Fixed by seeding the rule as `enabled=false`.
- [x] Locale key drift risk: modal copy could hard-code Chinese after Story 1.10. Fixed by requiring zh-CN/en-US message keys and existing `Accept-Language` preserving revoke calls.

Round 1 result: PASS after story corrections.

### Round 2: Function Consistency / Drift Review

Scope: existing API Key CRUD, solver authentication, risk_rules/risk_flags, Web API key page, and UI components.

Findings and fixes:

- [x] Parallel風控系统 risk: implementing a separate geo-risk table would bypass Story 1.5 and J7. Fixed by requiring existing `risk_flags` and `users.risk_score`.
- [x] Solver/auth responsibility drift: auth-service list endpoint should not validate Bearer `sk-*` keys. Fixed by keeping HMAC verification and IP comparison in solver only.
- [x] Return-shape regression risk: changing `verify_api_key` tuple would touch every solver route. Fixed by requiring optional `caller_ip` while preserving the return tuple.
- [x] Web UI drift risk: inventing a bespoke modal would diverge from Tier 1 `ConfirmationModal`. Fixed by requiring the shared component for the risk warning.
- [x] Revoke behavior duplication risk: modal could call a new revoke endpoint. Fixed by requiring existing `DELETE /v1/auth/api_keys/{id}` and existing web `revokeAPIKey`.

Round 2 result: PASS after story corrections.

### Round 3: Boundary / Closure Review

Scope: private/unknown IPs, first use, repeated use, revoked/expired keys, false positives, and test closure.

Findings and fixes:

- [x] Private/proxy/local test IP false-positive risk: `127.0.0.1` and private ranges could trigger in local dev. Fixed by requiring resolver `None` for private, loopback, reserved, malformed, IPv6, and unknown ranges.
- [x] First-use false-positive risk: no baseline IP means no anomaly. Fixed by requiring no flag when `last_used_ip` is null.
- [x] Repeat-call spam risk: same-region calls should not create repeated flags. Fixed by requiring a known different-region transition only.
- [x] Revoked/expired invalid-key risk: failed auth should not update last-used IP or score. Fixed by placing updates after successful HMAC/expiry/revoke checks.
- [x] Closure gap: story initially had backend-only risk evidence but no user-facing loop. Fixed by requiring modal warning, one-click revoke, list refresh, and tests.

Round 3 result: PASS after story corrections; story is ready for dev implementation.

## Dev Agent Record

### Agent Model Used

GPT-5

### Debug Log References

- Story authoring and three-round review completed on 2026-05-25.
- `uv run ruff check apps/solver-orchestrator/src/solver_orchestrator apps/solver-orchestrator/tests apps/auth-service/src/auth_service apps/auth-service/tests/test_api_keys_routes.py apps/auth-service/tests/test_risk_freeze.py` — passed.
- `uv run pytest apps/auth-service/tests -q` — 52 passed.
- `PYTHONPATH=packages/shared-py;apps/solver-orchestrator/src;packages/python-sdk/src uv run pytest apps/solver-orchestrator/tests/ -q` — 120 passed, 9 pre-existing FastAPI deprecation warnings.
- `pnpm --dir apps/web test` — 15 files / 74 tests passed.
- `pnpm --dir apps/web typecheck` — passed.
- `pnpm --dir packages/ui test` — 8 files / 50 tests passed.
- `pnpm --dir packages/ui typecheck` — passed.
- `git diff --check` — passed.

### Completion Notes List

- Created Story 1.11 with explicit reuse of Story 1.5 risk infrastructure and Story 1.3 API Key paths.
- Completed three story review rounds and applied corrections before implementation.
- Added disabled evidence-only `geo_anomaly` risk rule migration and wired it into auth-service and solver-orchestrator CI schema setup.
- Implemented deterministic solver-side coarse geo detection on successful API Key HMAC verification, including `last_used_ip`, `risk_flags`, and monotonic `users.risk_score` updates.
- Exposed per-key `risk_warning` summaries from `GET /v1/auth/api_keys` while preserving existing create/revoke contracts.
- Added localized Web warning modal on `/auth/api-keys` using `ConfirmationModal`; one-click revoke uses the existing DELETE endpoint and refreshes the list.
- Completed post-implementation code review and fixed migration idempotency, risk score summary drift, solver CI import path, and Web revoke error propagation.

### File List

- `.github/workflows/ci.yml`
- `_bmad-output/stories/1-11-geo-anomaly-risk.md`
- `_bmad-output/stories/sprint-status.yaml`
- `infra/local-init/08-geo-anomaly-risk.sql`
- `apps/solver-orchestrator/src/solver_orchestrator/geo_risk.py`
- `apps/solver-orchestrator/src/solver_orchestrator/auth.py`
- `apps/solver-orchestrator/src/solver_orchestrator/routes.py`
- `apps/solver-orchestrator/tests/test_geo_anomaly_risk.py`
- `apps/solver-orchestrator/tests/test_billing_integration.py`
- `apps/auth-service/src/auth_service/routes.py`
- `apps/auth-service/src/auth_service/schemas.py`
- `apps/auth-service/tests/test_api_keys_routes.py`
- `apps/auth-service/tests/test_risk_freeze.py`
- `apps/web/src/lib/api.ts`
- `apps/web/src/lib/api-locale.test.ts`
- `apps/web/src/app/auth/api-keys/page.tsx`
- `apps/web/src/app/auth/api-keys/page.test.tsx`
- `apps/web/messages/zh-CN.json`
- `apps/web/messages/en-US.json`

### Implementation Plan

- Add the `geo_anomaly` rule as disabled evidence-only risk metadata.
- Implement deterministic solver-side IP geo comparison on successful API Key auth.
- Surface per-key risk summaries through auth-service list endpoint.
- Add a localized risk modal on `/auth/api-keys` that revokes the suspicious key through the existing API.

### Change Log

- 2026-05-25: Created and three-round reviewed Story 1.11; status set to ready-for-dev.
- 2026-05-25: Started dev-story implementation; status set to in-progress.
- 2026-05-25: Implemented geo anomaly risk rule, solver scoring path, auth warning serialization, localized Web warning modal, one-click revoke, and regression tests.
- 2026-05-25: Completed post-implementation code review; fixed migration disabled-state idempotency, per-event warning score source, solver CI test path, and Web revoke failure propagation.
- 2026-05-25: Final validation passed; story and sprint status set to done.
