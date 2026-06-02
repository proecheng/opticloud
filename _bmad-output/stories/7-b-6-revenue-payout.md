---
story_key: 7-b-6-revenue-payout
baseline_commit: 629a24b961fa76f6de51694a31e83fa8e88fd403
epic_num: 7
story_num: B.6
epic_name: Provider Marketplace v2
status: in-progress
priority: High
type: provider revenue and pending-payout read projection
created_by: bmad-create-story
created_at: 2026-06-02
sources:
  - _bmad-output/planning/epics.md (Epic 7.B / Provider Marketplace v2)
  - _bmad-output/planning/prd.md (FR P6 / Provider revenue + pending payout)
  - _bmad-output/planning/architecture.md (C4 Revenue-Share Service v2 reservation)
  - _bmad-output/stories/7-a-2-revenue-share-hook-v2-reservation.md
  - _bmad-output/stories/7-b-1-provider-apply-v2.md
  - _bmad-output/stories/7-b-2-shadow-validation.md
  - _bmad-output/stories/7-b-3-gradient-rollout.md
  - _bmad-output/stories/7-b-4-route-share-dashboard.md
  - _bmad-output/stories/7-b-5-provider-kpi-dashboard.md
  - apps/capability-registry/src/capability_registry/models.py
  - apps/capability-registry/src/capability_registry/schemas.py
  - apps/capability-registry/src/capability_registry/routes.py
  - apps/capability-registry/tests/test_api.py
  - infra/local-init/14-capability-registry.sql
  - packages/shared-ts/openapi/capability-registry.json
---

# Story 7.B.6 - Provider Revenue + Pending Payout

Status: in-progress

## Story

**作为** 外部 Provider，
**我希望** 能查看自己已捕获 revenue-share hook 对应的收入、待结算金额和历史状态，
**从而** 在真正的月度分润批处理和 Provider Console 接入前，先拥有一个可审计、只读、不会暴露账本原文或支付凭证的数据契约。

## Context

Epic 7.B 已完成 Provider 申请、shadow validation、gradient rollout、route-share dashboard 和 KPI dashboard。PRD FR P6 要求 Provider can view own revenue + pending payout。7.A.2 已在 `apps/capability-registry` 中预留 `revenue_share_policies` 和 `revenue_share_hooks`，但 hook 当前只保存 provider/capability/policy/billing references，不保存金额，不计算 payout。

本 story 的最小闭环是在 capability-registry 内增加 Provider revenue/pending-payout projection。实现应增加一个金额化但仍 reference-only 的 payout entry 合同：内部服务可基于已存在的 `revenue_share_hooks` 写入 gross amount，服务端根据 hook 对应 policy 的 ratio snapshot 计算 provider/platform 金额；Provider 只读 projection 再汇总 revenue 和 pending payout。它不读取 billing-service 原始 `credit_transactions`，不创建独立 `revenue-share-service`，不生成月度分润批次，不触发银行/税务/支付结算，也不实现 public Provider Console auth。

## Scope

1. 在 `apps/capability-registry` 中新增 provider revenue payout entry 存储、model 和 schemas。
2. 新增内部写入/读取 API：
   - `PUT /v1/revenue-share/payout-entries/{entry_id}`
   - `GET /v1/revenue-share/payout-entries/{entry_id}`
   - `GET /v1/revenue-share/payout-entries?tenant_id=&provider_id=&period_month=&status=&currency=`
3. 新增服务侧只读 dashboard API：
   - `GET /v1/providers/{provider_id}/revenue-payout-dashboard?tenant_id=&from=&to=&period_month=&status=&k_algo=&currency=`
4. Dashboard 从 payout entries 派生 provider revenue、pending payout、status counts、currency totals、period summaries 和 entry rows。
5. 添加 capability-registry tests，覆盖金额计算、tenant exact scope、hook/policy consistency、stored drift 409、无副作用和 OpenAPI unsafe-field 检查。
6. Regenerate `packages/shared-ts/openapi/capability-registry.json`。

## Out Of Scope

- 创建 `apps/revenue-share-service`、月度分润批处理、结算文件、支付任务、银行打款、税务表单、发票或 payout processor。
- 读取 billing-service 原始 `credit_transactions`、Saga payload、支付平台回调、用户账单明细或用户 PII。
- 改造 billing-service、solver-orchestrator、API gateway、真实 routing telemetry、Provider Console v2 页面、Grafana dashboard JSON 或 public provider auth/ownership enforcement。
- 提前实现 7.B.8 monthly revenue share batch、合同扣税、争议处理、自动付款重试、财务审批工作流。
- 在 request body 中接受 caller-computed `provider_amount`, `platform_amount`, `provider_revenue_amount`, `platform_revenue_amount`, `pending_payout_amount`, `paid_at`, `settlement_id`, bank/tax/payment credential fields, raw billing payloads, API keys, OAuth tokens, customer routing payloads, or PII。
- 暴露 raw hook metadata、raw payout metadata、raw billing refs beyond stable identifiers, bank/tax/payment credentials, or raw ledger payloads in dashboard schemas。

## Acceptance Criteria

1. `infra/local-init/14-capability-registry.sql` idempotently creates `provider_revenue_payout_entries` without requiring billing-service migrations。
2. `provider_revenue_payout_entries` has columns: `id UUID PRIMARY KEY DEFAULT gen_random_uuid()`, `tenant_id UUID NULL`, `entry_id VARCHAR(64) NOT NULL`, `hook_row_id UUID NOT NULL REFERENCES revenue_share_hooks(id) ON DELETE CASCADE`, `provider_id VARCHAR(64) NOT NULL`, `k_algo VARCHAR(64) NOT NULL`, `policy_id VARCHAR(64) NOT NULL`, `source_service VARCHAR(64) NOT NULL`, `source_event_id UUID NOT NULL`, `period_month CHAR(7) NOT NULL`, `currency CHAR(3) NOT NULL DEFAULT 'CNY'`, `gross_amount NUMERIC(12,4) NOT NULL`, `platform_share_ratio NUMERIC(7,6) NOT NULL`, `provider_share_ratio NUMERIC(7,6) NOT NULL`, `status VARCHAR(32) NOT NULL DEFAULT 'pending'`, `recognized_at TIMESTAMPTZ NOT NULL`, `metadata JSONB NOT NULL DEFAULT '{}'::jsonb`, `created_at`, and `updated_at`。
3. `entry_id`, `provider_id`, `k_algo`, and `policy_id` use `^[a-z0-9][a-z0-9-]{0,63}$`; `source_service` uses `^[a-z0-9][a-z0-9-]{0,63}$`; `period_month` is strict `YYYY-MM` with month `01`-`12`; `currency` is uppercase ISO-like `^[A-Z]{3}$`。
4. Nullable tenant uniqueness is correct: one global payout entry per `entry_id`, one tenant payout entry per `(tenant_id, entry_id)`, and at most one payout entry per `hook_row_id`。
5. `gross_amount` must be non-negative and quantized to four decimals. Negative revenue/refund adjustments are out of scope for this story and return 422。
6. Allowed payout entry statuses are exactly `pending`, `held`, `paid`, and `voided`。
7. `PUT /v1/revenue-share/payout-entries/{entry_id}` is write-protected by `X-Internal-Service-Auth` when `CAPABILITY_REGISTRY_INTERNAL_SECRET` is configured。
8. Payout entry upsert body accepts `tenant_id`, `entry_id`, `hook_id`, `gross_amount`, `currency`, `recognized_at`, `status`, and `metadata` only. It must not accept caller-computed amount fields, settlement/payment fields, bank/tax fields, raw billing payloads, credentials, or PII。
9. Path `entry_id` is authoritative; body `entry_id` may be omitted or must match the path. Mismatch returns 422。
10. `hook_id` must resolve to an existing `revenue_share_hooks.id` in the exact requested tenant scope. With no `tenant_id`, only global hooks are valid. With `tenant_id`, only hooks for that tenant are valid; no global hook fallback is allowed for payout entries。
11. On create, the service copies `provider_id`, `k_algo`, `policy_id`, `source_service`, `source_event_id`, and `period_month` from the resolved hook, not from the request body。
12. On create, the service loads the hook's policy in the hook scope, allowing the same global-policy fallback behavior that hook creation allowed, snapshots `platform_share_ratio` and `provider_share_ratio`, and fails closed with 409 if the policy is missing or malformed。
13. Request bodies cannot provide or override `platform_share_ratio`, `provider_share_ratio`, `provider_revenue_amount`, or `platform_revenue_amount`; these are service-owned calculations。
14. Provider revenue amount is computed as `gross_amount * provider_share_ratio`, quantized to four decimals using Decimal half-up rounding. Platform amount is `gross_amount - provider_revenue_amount`, quantized to four decimals so currency totals close exactly。
15. Existing entries are idempotent when source fields match. Material fields `hook_id`, `gross_amount`, `currency`, and `recognized_at` are immutable after creation; attempts to change them return 422。
16. Status may transition `pending -> held|paid|voided`, `held -> pending|paid|voided`; `paid` and `voided` are terminal except idempotent replays. Invalid transitions return 422。
17. `GET /v1/revenue-share/payout-entries/{entry_id}` resolves exact tenant scope by query `tenant_id`; missing rows return 404。
18. `GET /v1/revenue-share/payout-entries` supports filters by `tenant_id`, `provider_id`, `period_month`, `status`, and `currency`, uses exact tenant scope, and sorts deterministically by `recognized_at DESC`, `entry_id`。
19. `GET /v1/providers/{provider_id}/revenue-payout-dashboard` does not require a live `capability_providers` row. A provider with no payout entries returns the empty dashboard shape rather than 404。
20. Dashboard tenant filtering is exact. With no `tenant_id`, only global payout entries are returned. With `tenant_id`, only rows for that tenant are returned; no global fallback is mixed into tenant dashboards。
21. Dashboard filters:
    - `tenant_id` optional UUID。
    - `from` and `to` optional timezone-aware datetimes; if both present, `from <= to` or 422。
    - `period_month` optional strict `YYYY-MM`。
    - `status` optional entry status enum。
    - `k_algo` optional provider ID pattern。
    - `currency` optional uppercase 3-letter code。
22. Query aliases are exactly `from` and `to`; implementation may use `from_at` and `to_at`, but OpenAPI must expose aliases。
23. Time filters are inclusive and apply to entry `recognized_at` after provider/scope/status/k_algo/period/currency filters are applied。
24. Dashboard response includes at least `provider_id`, `tenant_id`, `from_at`, `to_at`, `period_month`, `status`, `k_algo`, `currency`, `status_counts`, `total_entries`, `currency_totals`, `period_summaries`, and `entries`。
25. `status_counts` includes all statuses `pending`, `held`, `paid`, and `voided`, even when zero。
26. Currency totals include `currency`, `entry_count`, `gross_amount`, `provider_revenue_amount`, `platform_revenue_amount`, `pending_payout_amount`, `held_payout_amount`, `paid_amount`, and `voided_gross_amount`。
27. `pending_payout_amount` sums provider revenue only for `pending` entries. `held_payout_amount` sums provider revenue only for `held` entries. `paid_amount` sums provider revenue only for `paid` entries. `voided` entries do not contribute to provider revenue or pending payout totals except `voided_gross_amount`。
28. Period summaries group by `period_month` and `currency`, use the same amount semantics as currency totals, and sort by `period_month`, `currency`。
29. Dashboard entry rows include stable derived fields only: `entry_id`, `hook_id`, `provider_id`, `k_algo`, `policy_id`, `source_service`, `source_event_id`, `period_month`, `currency`, `gross_amount`, `provider_share_ratio`, `platform_share_ratio`, `provider_revenue_amount`, `platform_revenue_amount`, `status`, `recognized_at`, and `scope_source`。
30. Dashboard schemas must not expose raw hook metadata, payout metadata, raw billing payloads, bank/tax/payment fields, settlement IDs, paid-at timestamps, credentials, OAuth tokens, API keys, customer routing payloads, or user PII。
31. Stored payout entry drift fails closed with 409 if status, ratios, amounts, tenant scope, denormalized hook fields, period month, currency, or timezone awareness are malformed or inconsistent with the referenced hook/policy contract。
32. Payout dashboard reads are read-only and must not insert, update, delete, lock, or mutate payout entries, hooks, policies, provider/capability rows, application/evaluation/shadow/rollout rows, OAuth rows, or billing rows。
33. Existing provider/capability/OAuth/revenue-share/application/evaluation/shadow/rollout/route-share/KPI tests continue to pass。
34. The new schemas/routes are included in `packages/shared-ts/openapi/capability-registry.json`; `scripts/check_openapi_drift.py` detects drift。
35. `.github/workflows/ci.yml` keeps the existing `capability-registry-test` job; no new CI service job is added。
36. Local gates pass: `uv run pytest apps/capability-registry/tests/ -v`, `uv run mypy apps packages`, `uv run ruff check apps/capability-registry`, `uv run ruff format --check apps/capability-registry`, `uv run python scripts/generate_openapi.py`, `uv run python scripts/check_openapi_drift.py`, and `git diff --check`。
37. Implementation record includes post-implementation code review findings and fixes。
38. GitHub CI passes, PR is merged, remote branch is deleted, local `main` is synced, and only then this story and sprint status are marked `done`。

## Tasks / Subtasks

- [x] T1: Add payout entry data model (AC: 1-6, 31)
  - [x] Extend `infra/local-init/14-capability-registry.sql` idempotently。
  - [x] Add SQLAlchemy model for `ProviderRevenuePayoutEntry`。
  - [x] Preserve existing revenue-share hook/policy behavior。

- [x] T2: Add payout entry schemas and validation (AC: 3, 5-16, 24-30)
  - [x] Add Pydantic request/response/dashboard schemas。
  - [x] Reject caller-computed amount/payment/credential/PII fields recursively。
  - [x] Serialize monetary values and ratios deterministically as strings。

- [x] T3: Add internal payout entry routes (AC: 7-18, 31-32)
  - [x] Add upsert/read/list routes under `/v1/revenue-share/payout-entries`。
  - [x] Resolve hooks with exact tenant scope and snapshot policy ratios。
  - [x] Enforce material immutability, status transitions, and drift checks。

- [x] T4: Add provider revenue/payout dashboard route (AC: 19-32)
  - [x] Add `GET /v1/providers/{provider_id}/revenue-payout-dashboard`。
  - [x] Implement exact tenant scope, filters, status counts, currency totals, period summaries, and stable entry rows。
  - [x] Keep dashboard schemas reference-only and free of unsafe fields。

- [x] T5: Add tests and OpenAPI coverage (AC: 33-36)
  - [x] Cover schema idempotency, amount calculation, status transitions, tenant exact scope, hook/policy consistency, empty dashboard, no side effects, and drift 409。
  - [x] Cover OpenAPI unsafe-field absence and `from`/`to` aliases。
  - [x] Regenerate checked-in OpenAPI and run drift check。

- [ ] T6: Review, gates, and GitHub sync (AC: 37-38)
  - [x] Run post-implementation code review and fix findings。
  - [x] Record code review findings and fixes in `Post-Implementation Code Review`。
  - [x] Run local gates after fixes。
  - [ ] Commit, push, create PR, wait for CI, merge, delete remote branch, and sync local `main`。
  - [ ] Mark story and sprint status `done` only after merge/sync。

## Dev Notes

### Service Boundary

- Implement in `apps/capability-registry`, `infra/local-init/14-capability-registry.sql`, checked-in capability-registry OpenAPI, tests, and story/status files。
- Do not add `apps/revenue-share-service` yet. Architecture C4 reserves that service for v2 monthly share, but current monorepo service catalog deliberately excludes it from current deployables。
- Do not import billing-service models or query `credit_transactions` from capability-registry. Payout entries are fed through internal references and gross amount input。
- This story is a service-side projection contract, not Provider Console, public provider auth, actual payout settlement, tax withholding, or monthly batch close。

### Data Semantics

- `revenue_share_hooks` remains the source of provider/capability/policy/event identity。
- `provider_revenue_payout_entries` is the first monetary projection source for P6. It stores gross amount plus ratio snapshots, not raw billing ledger payloads。
- Provider revenue is a derived amount from gross amount and provider-share ratio. Caller-provided provider/platform amounts must be rejected。
- Pending payout is a read-model concept: status `pending` provider revenue is pending payout. `held`, `paid`, and `voided` remain distinct for dashboard clarity。
- `paid` means the entry is no longer pending in this projection. It does not prove bank settlement, transfer ID, invoice, tax withholding, or external payment success。

### Existing Patterns To Reuse

- Reuse `_PATH_ID_PATTERN`, `_SOURCE_SERVICE_PATTERN`, `_PERIOD_MONTH_PATTERN`, `_require_write_auth(...)`, `_scope_source(...)`, and existing FastAPI/Pydantic route style。
- Reuse 7.B.4/7.B.5 exact tenant-scope behavior for provider-owned dashboards: no global fallback mixing in tenant dashboard reads。
- Reuse 7.A.2 recursive sensitive-key rejection pattern, but keep hook/policy responses backwards compatible。
- Use Decimal, not float. Quantize ratios to six decimals and money to four decimals。
- Existing tests apply `infra/local-init/14-capability-registry.sql` twice. Extend that harness。

### Previous Story Intelligence

- 7.A.2 reserved hooks only and intentionally did not compute payout amounts。
- 7.A.2 post-review fixed recursive sensitive-key rejection and source-event idempotency race handling。
- 7.B.4 and 7.B.5 proved dashboard read projections should be exact-scope, fail closed on malformed stored drift, avoid `global_fallback` scope in provider-owned dashboards, and exclude raw metadata/evidence。
- 7.B.5 proved read projections should batch related rows rather than issue N+1 queries。

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
- Provider revenue/pending payout API satisfies FR P6 as a safe, dashboard-ready read projection without implementing real payout settlement, Provider Console UX, or 7.B.8 monthly revenue share early。
- Existing provider marketplace and revenue-share hook behavior remains compatible。
- Post-implementation code review is completed and findings are fixed or explicitly documented。
- Local quality gates and GitHub CI pass。
- Story and sprint status are updated to `done` only after review, gates, CI, merge, branch cleanup, and local `main` sync。

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Debug Log References

- Baseline branch: `codex/7-b-6-revenue-payout`。
- Baseline commit: `629a24b961fa76f6de51694a31e83fa8e88fd403`。
- Story creation used local context from PRD P6/P8, Architecture C4, 7.A.2 revenue-share hook reservation, and 7.B.1-7.B.5 provider marketplace stories。
- Implementation started; story and sprint status moved to in-progress。
- Focused revenue/payout tests: `uv run pytest apps/capability-registry/tests/test_api.py -k "provider_revenue_payout or revenue_share_openapi" -v` -> 6 passed。
- Full capability-registry tests: `uv run pytest apps/capability-registry/tests/ -v` -> 46 passed。
- Type gate: `uv run mypy apps packages` -> passed。
- Lint/format gates: `uv run ruff check apps/capability-registry` and `uv run ruff format --check apps/capability-registry` -> passed。
- OpenAPI gates: `uv run python scripts/generate_openapi.py` and `uv run python scripts/check_openapi_drift.py` -> passed。
- Whitespace gate: `git diff --check` -> passed。
- Post-review focused payout tests and type/lint/format gates passed after fixes。

### Completion Notes List

- Story created for Provider Revenue + Pending Payout read projection。
- Completed 3 pre-implementation adversarial review rounds and revised the story after each round。
- Added `provider_revenue_payout_entries` schema/model, payout entry request/response/dashboard schemas, and checked-in OpenAPI updates。
- Added internal payout entry upsert/read/list routes with exact tenant hook resolution, policy ratio snapshots, material immutability, status transitions, and fail-closed stored-drift checks。
- Added `GET /v1/providers/{provider_id}/revenue-payout-dashboard` with exact tenant scope, filters, status counts, currency totals, period summaries, stable entry rows, and read-only/no-metadata behavior。
- Added tests for amount calculation, status transitions, forbidden unsafe fields, tenant exact scope, write auth, dashboard totals/filters/empty state/no side effects, stored drift 409, and OpenAPI aliases/unsafe-field absence。
- Post-implementation review findings fixed: payout response scope now uses the provider dashboard scope type, list/dashboard validation batches hook/policy references instead of N+1 queries, and payout upsert handles unique-index races with deterministic conflict/idempotency recovery。
- Local implementation gates passed; story remains `in-progress` pending GitHub PR/CI/merge/branch cleanup/local main sync。

### File List

- `_bmad-output/stories/7-b-6-revenue-payout.md`
- `_bmad-output/stories/sprint-status.yaml`
- `infra/local-init/14-capability-registry.sql`
- `apps/capability-registry/src/capability_registry/models.py`
- `apps/capability-registry/src/capability_registry/schemas.py`
- `apps/capability-registry/src/capability_registry/routes.py`
- `apps/capability-registry/tests/test_api.py`
- `packages/shared-ts/openapi/capability-registry.json`

## Change Log

- 2026-06-02 - Story created for Provider Revenue + Pending Payout read projection。
- 2026-06-02 - Completed 3 pre-implementation adversarial review rounds; story marked ready for development。
- 2026-06-02 - Implementation started; story and sprint status moved to in-progress。
- 2026-06-02 - Implemented Provider Revenue + Pending Payout projection, post-review fixes, tests, OpenAPI update, and local gates; story remains in-progress pending GitHub sync。

## Pre-Implementation Adversarial Reviews

### Round 1 - Boundary, Ownership, And Product Fit Review

Findings:

1. "Provider can view own revenue + pending payout" could be misread as Provider Console UX, public provider auth, or provider ownership enforcement。
2. "Pending payout" could imply real bank settlement, tax forms, invoices, or payout processor work。
3. "Revenue" could imply reading billing-service raw ledger rows, Saga payloads, payment provider callbacks, or user PII。
4. Architecture C4 reserves revenue-share-service for v2, but current deployable service catalog still excludes it; creating a new service here would violate sequencing。
5. 7.A.2 hooks are reference-only and do not contain amounts, so P6 needs a monetary projection source without rewriting hook semantics。
6. Returning `payout_status`, `settlement_id`, `paid_at`, bank/tax/payment fields, or raw billing payloads would break the 7.A.2 safety boundary。
7. Dashboard reads could accidentally document themselves as public provider-authenticated endpoints。
8. The story needed to clarify that `paid` in this projection is not evidence of external bank transfer。
9. It was unclear whether provider must exist in live `capability_providers` to view revenue。
10. It was unclear whether global rows can fall back into tenant provider dashboards。

Revisions applied:

- Scoped implementation to capability-registry projection only, not Console/public auth。
- Added payout entry contract as the monetary projection source while preserving hook reference-only semantics。
- Explicitly excluded raw billing reads, payout processor, tax/bank/payment credentials, and revenue-share-service creation。
- Added exact tenant-scope dashboard behavior, no live provider-row requirement, and `paid` semantics disclaimer。

### Round 2 - Drift, Data Consistency, And Amount Semantics Review

Findings:

1. If callers can provide `provider_amount` or `platform_amount`, stored amounts can drift from policy ratios。
2. Policy ratios can change after hook creation; payout entries need historical ratio snapshots。
3. Rounding must be deterministic or totals will not close across gross/provider/platform amounts。
4. Tenant-scoped payout entries created from global hooks could mix evidence across scopes。
5. Existing hooks denormalize provider/k_algo/policy/source-event values; payout entries must fail closed if later DB drift makes those inconsistent。
6. `voided` entries need explicit total semantics so they do not inflate revenue or pending payout。
7. `held` needs to remain separate from `pending`; otherwise pending payout can be overstated。
8. Naive `recognized_at` timestamps could break `from`/`to` filtering。
9. Multi-currency totals need grouping rather than a single aggregate。
10. Material fields must be immutable after creation to avoid silently rewriting financial history。

Revisions applied:

- Made provider/platform amounts service-derived only and rejected caller-computed amount fields。
- Added policy ratio snapshots, Decimal half-up four-decimal money rounding, exact tenant hook resolution, drift 409 rules, and immutable material fields。
- Defined status-specific total semantics for pending/held/paid/voided and grouped totals by currency and period。

### Round 3 - Dependencies, Tests, And Closure Review

Findings:

1. The implementation could accidentally read billing-service tables or import billing-service models for convenience。
2. The dashboard could expose payout metadata or hook metadata that contains sensitive internal references。
3. Query aliases might drift to `from_at`/`to_at` in OpenAPI。
4. List and dashboard routes need deterministic sorting for stable clients and tests。
5. Payout entry upsert must be internal-write protected like revenue-share hooks and policies。
6. Tests must separately cover empty dashboards, no side effects, malformed stored drift, and tenant exact scope。
7. OpenAPI unsafe-field assertions must include new dashboard schemas and not rely on runtime validators only。
8. Existing 7.A/7.B tests must continue to pass; this story touches shared revenue-share code paths。
9. No new CI service job should be introduced。
10. Story `done` must remain gated on PR merge, branch cleanup, and local `main` sync。

Revisions applied:

- Added explicit no billing-service import/query boundary and unsafe dashboard schema exclusions。
- Added OpenAPI alias and unsafe-field ACs, deterministic sorting, write auth, no-side-effect tests, and full local/GitHub done gates。
- Kept sprint/story done transition gated on CI, merge, remote branch deletion, and local main sync。

## Post-Implementation Code Review

- [x] [Review][Patch] Payout response construction initially cast dashboard `scope_source` through the route-share scope alias, coupling the new payout projection to an unrelated dashboard contract. Fixed by using `ProviderDashboardScopeSource` through a payout-specific scope helper that rejects `global_fallback` on provider-owned projections。
- [x] [Review][Patch] Payout list/dashboard reads initially validated each row by re-querying hook and policy references, creating an N+1 pattern that would scale poorly for providers with many payout entries. Fixed by batching selected hooks and policies once per list/dashboard response and validating rows against the batched reference map。
- [x] [Review][Patch] Payout entry create initially pre-checked unique hook usage but could still surface a raw database conflict under concurrent duplicate writes. Fixed by wrapping insert in `begin_nested()`, then resolving same-entry idempotency or same-hook conflict deterministically after `IntegrityError`。
- [x] [Review][Patch] Stored drift validation covered status, ratios, money, period, currency, timezone, and denormalized hook fields, but not every stored path/source identifier format. Fixed by validating stored `entry_id`, `provider_id`, `k_algo`, `policy_id`, and `source_service` on read paths so malformed projection rows fail closed with 409。
