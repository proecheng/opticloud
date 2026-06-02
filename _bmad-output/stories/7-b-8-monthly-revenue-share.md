---
story_key: 7-b-8-monthly-revenue-share
baseline_commit: c4b61f1005f8eeee97a5b5fb59d41f4884ec49ab
epic_num: 7
story_num: B.8
epic_name: Provider Marketplace v2
status: done
priority: High
type: provider monthly revenue-share calculation batch contract
created_by: bmad-create-story
created_at: 2026-06-02
sources:
  - _bmad-output/planning/epics.md (Epic 7.B / Provider Marketplace v2)
  - _bmad-output/planning/prd.md (FR P8 / monthly revenue share)
  - _bmad-output/planning/architecture.md (C4 Revenue-Share Service v2 reservation)
  - _bmad-output/stories/7-a-2-revenue-share-hook-v2-reservation.md
  - _bmad-output/stories/7-b-6-revenue-payout.md
  - _bmad-output/stories/7-b-7-version-management.md
  - apps/capability-registry/src/capability_registry/models.py
  - apps/capability-registry/src/capability_registry/schemas.py
  - apps/capability-registry/src/capability_registry/routes.py
  - apps/capability-registry/tests/test_api.py
  - infra/local-init/14-capability-registry.sql
  - packages/shared-ts/openapi/capability-registry.json
---

# Story 7.B.8 - Monthly Revenue Share

Status: done

## Story

**作为** OptiCloud 财务/运营系统，
**我希望** 能按月对 Provider payout entries 生成分润计算批次、Provider 汇总和可审计快照，
**从而** 在真正的 Revenue-Share Service、银行打款、税务、发票和 Provider Console 自助月结上线前，先拥有一个确定性、只读可复核、不会改写结算事实的月度分润合同。

## Context

Epic 7.B 已完成 Provider application/evaluation intake、shadow validation、gradient rollout、route-share dashboard、KPI dashboard、revenue/pending payout projection 和 version update request contract。PRD FR P8 要求系统 can compute monthly revenue share，比例为自研 100/0、合作 60/40、商业 50/50。Architecture C4 将 Revenue-Share Service 作为 v2 启用项，但当前 deployable service catalog 尚未引入独立 service。

7.A.2 已预留 `revenue_share_policies` / `revenue_share_hooks`，7.B.6 已在 `apps/capability-registry` 中实现 `provider_revenue_payout_entries` 和 provider revenue/pending payout dashboard。7.B.8 的最小闭环应复用这些 payout entries，增加月度分润计算批次合同：内部服务可对指定 `period_month` 和 scope 计算 provider/currency 汇总，冻结本次计算引用的 payout entry ID 与金额快照，提供批次读取/列表。它不执行银行付款，不改写 payout entry 状态，不读取 billing-service ledger，不创建真正的 `apps/revenue-share-service`，也不实现税务、发票、支付审批或 Provider Console 页面。

## Scope

1. 在 `apps/capability-registry` 中新增 monthly revenue share calculation batch 存储、model、schemas。
2. 新增内部写入/读取 API：
   - `PUT /v1/revenue-share/monthly-batches/{batch_id}`
   - `GET /v1/revenue-share/monthly-batches/{batch_id}?tenant_id=`
   - `GET /v1/revenue-share/monthly-batches?tenant_id=&period_month=&status=&currency=`
   - `PATCH /v1/revenue-share/monthly-batches/{batch_id}/status`
3. Batch 从既有 `provider_revenue_payout_entries` 派生 provider/currency/month 汇总，不创建或修改 payout entries。
4. Batch snapshot 只存稳定引用和计算结果：entry IDs、provider summaries、currency totals、policy ratio summaries、excluded entry refs、checksum 和 metadata reference fields。
5. 对可变 batch status 实施 P39 ETag/If-Match：
   - response header `ETag: "<batch_id>:<record_version>"`
   - `PATCH .../status` 必须带 `If-Match`
   - 缺失返回 428，版本不匹配返回 412
6. 添加 capability-registry tests，覆盖 month/scope filtering、比例金额、status lifecycle、ETag、idempotency、stored drift 409、no side effects、OpenAPI unsafe-field absence。
7. Regenerate `packages/shared-ts/openapi/capability-registry.json`。

## Out Of Scope

- 创建 `apps/revenue-share-service`、scheduled worker、Dramatiq/Cron monthly job、真实财务审批、结算文件生成、银行/支付宝/微信/Stripe/对公打款、税务代扣、发票、付款失败重试、对账单下载、Provider Console 页面或 public provider auth。
- 读取 billing-service 原始 `credit_transactions`、Saga payload、支付平台回调、用户账单明细、用户 PII、税号、银行账号、邮件正文或 raw billing payload。
- 改写 `provider_revenue_payout_entries.status` 为 paid/held/voided，或创建、更新、删除 hooks、policies、provider/capability/application/evaluation/shadow/rollout/version rows。
- 支持负数退款/冲正、跨月重算自动差额、税务扣减、平台服务费之外的新费用项、币种换汇、发票拆分、合同模板、争议处理，或把 `exported` 解释为已支付/已结税。
- 在 request body 或 response schema 中接受/暴露 raw payout metadata、raw hook metadata、settlement IDs、paid_at、bank/tax/payment credentials、API keys、OAuth tokens、customer routing payloads、raw datasets、raw request/response payloads 或用户 PII。

## Acceptance Criteria

1. `infra/local-init/14-capability-registry.sql` idempotently creates `provider_monthly_revenue_share_batches` without requiring billing-service migrations or a new service migration.
2. `provider_monthly_revenue_share_batches` has columns: `id UUID PRIMARY KEY DEFAULT gen_random_uuid()`, `tenant_id UUID NULL`, `batch_id VARCHAR(64) NOT NULL`, `period_month CHAR(7) NOT NULL`, `status VARCHAR(32) NOT NULL DEFAULT 'draft'`, `calculated_at TIMESTAMPTZ NOT NULL`, `entry_count INTEGER NOT NULL DEFAULT 0`, `provider_count INTEGER NOT NULL DEFAULT 0`, `currency_totals JSONB NOT NULL DEFAULT '[]'::jsonb`, `provider_summaries JSONB NOT NULL DEFAULT '[]'::jsonb`, `policy_ratio_summaries JSONB NOT NULL DEFAULT '[]'::jsonb`, `excluded_entries JSONB NOT NULL DEFAULT '[]'::jsonb`, `source_entry_ids JSONB NOT NULL DEFAULT '[]'::jsonb`, `calculation_checksum VARCHAR(64) NOT NULL`, `notes_ref TEXT NULL`, `approved_by_ref TEXT NULL`, `metadata JSONB NOT NULL DEFAULT '{}'::jsonb`, `record_version INTEGER NOT NULL DEFAULT 1`, `created_at`, and `updated_at`.
3. `batch_id` uses `^[a-z0-9][a-z0-9-]{0,63}$`; `period_month` is strict `YYYY-MM` with month `01`-`12`; `calculation_checksum` is 64 lowercase hex.
4. Nullable tenant uniqueness is correct and unambiguous for path reads: one global batch per `batch_id` and one tenant batch per `(tenant_id, batch_id)`. `period_month` is part of the batch payload but not part of the path identity.
5. Batch creation reads only payout entries in exact requested tenant scope. With no `tenant_id`, only global payout entries are included. With `tenant_id`, only rows for that tenant are included; no global fallback is allowed.
6. Batch creation includes only payout entries whose `period_month` matches the batch period and whose status is `pending` or `held`. `paid` and `voided` entries must be excluded and listed in `excluded_entries` with stable reason codes.
7. Excluded entry reason codes are exactly `paid`, `voided`, `stored_drift`, and `unsupported_status`. `stored_drift` rows are never included in totals.
8. Stored payout entry drift encountered during batch calculation fails closed with 409 by default. If request `allow_drift_exclusions=true`, drifted rows are excluded with reason `stored_drift`, but the response must not expose raw drift payloads.
9. Batch creation does not require a live `capability_providers` row. Provider identity is derived from payout entries already validated against hooks.
10. Batch body accepts only `tenant_id`, optional `batch_id`, `period_month`, optional `notes_ref`, optional `metadata`, and optional `allow_drift_exclusions`. It must reject caller-provided amount totals, provider summaries, source entry IDs, status, calculated timestamps, checksum, record_version, settlement/payment fields, bank/tax fields, raw billing payloads, credentials, or PII.
11. `notes_ref` and `approved_by_ref` are reference strings with allowed prefixes `s3://`, `oss://`, `fixture://`, `benchmark://`, or `repro://`; inline notes, reviewer names, emails, employee IDs, signatures, approval comments, or payment refs are not accepted.
12. Batch creation defaults to status `draft`, sets `calculated_at`, `created_at`, and `updated_at` server-side, and returns all amount fields serialized as four-decimal strings and ratios as six-decimal strings.
13. Provider summaries group by `provider_id` and `currency`, include `entry_count`, `pending_entry_count`, `held_entry_count`, `gross_amount`, `provider_revenue_amount`, `platform_revenue_amount`, `pending_payout_amount`, `held_payout_amount`, `entry_ids`, and `scope_source`.
14. Currency totals group by `currency`, include `entry_count`, `provider_count`, `gross_amount`, `provider_revenue_amount`, `platform_revenue_amount`, `pending_payout_amount`, and `held_payout_amount`.
15. Policy ratio summaries group by `policy_id`, `provider_share_ratio`, `platform_share_ratio`, and `currency`, include `entry_count`, `gross_amount`, `provider_revenue_amount`, and `platform_revenue_amount`.
16. Amount semantics match 7.B.6: `pending_payout_amount` sums provider revenue only for pending entries; `held_payout_amount` sums provider revenue only for held entries; voided and paid rows do not contribute to included totals.
17. Provider summaries sort deterministically by `provider_id`, `currency`; currency totals sort by `currency`; policy ratio summaries sort by `policy_id`, `currency`, ratios; source entry IDs sort by `entry_id`; excluded entries sort by `entry_id`, reason.
18. Calculation checksum is deterministic SHA-256 over a canonical JSON payload containing `tenant_id`, `period_month`, `source_entry_ids`, provider summaries, currency totals, policy summaries, and excluded entries. Recomputing the same batch over unchanged source rows returns the same checksum.
19. Upserting an existing draft batch with unchanged source payout rows is idempotent and returns the existing response without incrementing `record_version`.
20. Upserting an existing draft batch after source payout rows changed recalculates the snapshot, updates totals/checksum, updates `updated_at`, and increments `record_version` by exactly 1.
21. Once status leaves `draft`, source snapshot fields are immutable. Re-running `PUT` for a non-draft batch returns 422 unless the recalculated checksum is identical to the stored snapshot, in which case it returns the existing response without incrementing.
22. Allowed batch statuses are exactly `draft`, `reviewed`, `approved`, `exported`, `cancelled`.
23. Valid transitions are `draft -> reviewed|cancelled`, `reviewed -> approved|cancelled`, `approved -> exported|cancelled`. `exported` and `cancelled` are terminal except idempotent replay.
24. `PATCH .../status` accepts only `status`, optional `approved_by_ref`, optional `notes_ref`, and optional `metadata`. It rejects amount fields, source entry IDs, timestamps, checksum, record_version, settlement/payment fields, bank/tax fields, raw billing payloads, credentials, or PII.
25. `approved_by_ref` is required when transitioning to `approved` or `exported`; it is preserved on idempotent replay.
26. Every successful status mutation increments `record_version` by exactly 1. Idempotent no-op replay may return the existing response without incrementing.
27. All single-batch GET/PUT/PATCH responses include `ETag: "<batch_id>:<record_version>"`.
28. `PATCH .../status` requires `If-Match`; missing returns 428 and mismatch returns 412. New batch creation does not require `If-Match`.
29. `GET /v1/revenue-share/monthly-batches/{batch_id}` resolves exact tenant scope by query `tenant_id`; missing rows return 404.
30. `GET /v1/revenue-share/monthly-batches` supports filters by `tenant_id`, `period_month`, `status`, and `currency`, uses exact tenant scope, and sorts deterministically by `period_month DESC`, `calculated_at DESC`, `batch_id`.
31. List filtering by `currency` includes batches whose `currency_totals` contain that currency, without exposing raw JSON metadata.
32. Stored batch drift fails closed with 409 if status, period month, checksum, record_version, JSON array shapes, amount strings, ratios, source entry IDs, excluded reasons, tenant scope, timestamps, notes refs, approved refs, or referenced payout immutable fields are malformed or inconsistent with the payout-entry contract. Later payout-entry status changes after the batch snapshot are not drift for non-draft batch reads; the stored snapshot remains the audit record.
33. Batch reads are read-only and must not insert, update, delete, lock, or mutate payout entries, hooks, policies, provider/capability rows, application/evaluation/shadow/rollout/version rows, OAuth rows, or billing rows.
34. Batch creation and status patch use existing `X-Internal-Service-Auth` when `CAPABILITY_REGISTRY_INTERNAL_SECRET` is configured.
35. Batch creation must handle concurrent duplicate create/recalculate attempts deterministically. Unique-index races resolve to idempotent same-checksum response or 409/422 conflict, never raw database errors.
36. Existing provider/capability/OAuth/revenue-share/application/evaluation/shadow/rollout/route-share/KPI/payout/version tests continue to pass.
37. The new schemas/routes are included in `packages/shared-ts/openapi/capability-registry.json`; `scripts/check_openapi_drift.py` detects drift.
38. OpenAPI schemas for monthly revenue share do not expose unsafe fields such as metadata in responses, raw billing payloads, settlement IDs, paid_at timestamps, payment refs, bank/tax fields, credentials, raw request/response, raw dataset, customer routing payloads, caller-controlled calculated timestamps, caller-controlled checksum, or caller-controlled record_version.
39. `.github/workflows/ci.yml` keeps the existing `capability-registry-test` job; no new CI service job is added.
40. Local gates pass: `uv run pytest apps/capability-registry/tests/ -v`, `uv run mypy apps packages`, `uv run ruff check apps/capability-registry`, `uv run ruff format --check apps/capability-registry`, `uv run python scripts/generate_openapi.py`, `uv run python scripts/check_openapi_drift.py`, and `git diff --check`.
41. Implementation record includes post-implementation code review findings and fixes.
42. GitHub CI passes, PR is merged, remote branch is deleted, local `main` is synced, and only then this story and sprint status are marked `done`.

## Tasks / Subtasks

- [x] T1: Add monthly batch data model (AC: 1-4, 22, 32)
  - [x] Extend `infra/local-init/14-capability-registry.sql` idempotently.
  - [x] Add SQLAlchemy model for `ProviderMonthlyRevenueShareBatch`.
  - [x] Preserve existing revenue-share policy/hook and payout-entry behavior.

- [x] T2: Add monthly batch schemas and validation (AC: 3, 7, 10-18, 22-28, 38)
  - [x] Add Pydantic create/status/response schemas.
  - [x] Reject caller-owned totals, timestamps, checksum, settlement/payment/tax/bank/PII fields recursively.
  - [x] Serialize monetary values and ratios deterministically as strings.

- [x] T3: Add batch calculation and lifecycle routes (AC: 5-31, 34-35)
  - [x] Add upsert/read/list/status routes under `/v1/revenue-share/monthly-batches`.
  - [x] Reuse payout-entry validation and amount helpers; batch related references, avoid N+1 lookups.
  - [x] Implement exact tenant scope, deterministic grouping, canonical checksum, idempotent recalculation, ETag/If-Match status locking, and lifecycle transitions.

- [x] T4: Add tests and OpenAPI coverage (AC: 32-40)
  - [x] Cover exact scope, pending/held inclusion, paid/voided exclusion, drift handling, checksum determinism, idempotency/recalculation, ETag/status transitions, no side effects, and auth.
  - [x] Cover OpenAPI unsafe-field absence and monthly batch route parameters.
  - [x] Regenerate checked-in OpenAPI and run drift check.

- [x] T5: Review, gates, and GitHub sync (AC: 41-42)
  - [x] Run post-implementation code review and fix findings.
  - [x] Record code review findings and fixes in `Post-Implementation Code Review`.
  - [x] Run local gates after fixes.
  - [x] Commit, push, create PR, wait for CI, merge, delete remote branch, and sync local `main`.
  - [x] Mark story and sprint status `done` only after merge/sync.

## Dev Notes

### Service Boundary

- Implement in `apps/capability-registry`, `infra/local-init/14-capability-registry.sql`, checked-in capability-registry OpenAPI, tests, and story/status files.
- Do not add `apps/revenue-share-service` yet. Architecture C4 reserves that service for v2, but current repo flow has been landing Provider Marketplace contracts in capability-registry.
- Do not import billing-service models or query `credit_transactions`. Monthly batches derive only from validated `provider_revenue_payout_entries`.
- This story computes a monthly share snapshot. It is not a payout processor and must not mark entries paid, create payment refs, expose bank/tax fields, or generate settlement files.

### Data Semantics

- `provider_revenue_payout_entries` remains the monetary source of truth for this story.
- Batch included rows are `pending` and `held` payout entries for the exact `period_month` and exact tenant/global scope.
- `paid` and `voided` entries are excluded from included totals and listed with reasons for auditability.
- Batch totals are snapshots. If source payout entries change while a batch is still draft, PUT may recalculate. Once a batch is reviewed/approved/exported/cancelled, source snapshots become immutable.
- Reads validate the stored snapshot shape and referenced immutable payout fields, but do not reinterpret historical totals if a payout entry status later moves from pending/held to paid/voided outside this story.
- `approved` means the calculation has been approved for downstream export, not that any bank transfer or tax settlement happened. `exported` means an external process may safely consume the reference snapshot; it does not mean paid, settled, invoiced, taxed, or transferred.

### Existing Patterns To Reuse

- Reuse `_PATH_ID_PATTERN`, `_PERIOD_MONTH_PATTERN`, `_require_write_auth(...)`, `_scope_source(...)`, `_payout_entry_references`, `_validated_payout_entry_response(...)`, `_payout_amounts(...)`, `_payout_currency_totals(...)`, `provider_revenue_amount(...)`, `platform_revenue_amount(...)`, and Decimal helpers.
- Use `begin_nested()` around insert/update paths that can hit unique constraints, mirroring prior hook/payout race handling.
- Reuse 7.B.4/7.B.5/7.B.6 exact tenant-scope dashboard behavior: no global fallback in provider-owned/monthly batch calculations.
- Use partial unique indexes for nullable tenant uniqueness.
- Use JSONB arrays for snapshot payloads, but validate them strictly on every read. Fail closed with 409 on malformed stored JSON.
- Existing tests apply `infra/local-init/14-capability-registry.sql` twice. Extend that harness and clean-table list.
- OpenAPI generation and drift scripts already include capability-registry.

### Previous Story Intelligence

- 7.A.2 reserved revenue-share hooks and policies, but deliberately did not compute payout amounts.
- 7.B.6 introduced payout entries and fixed N+1 validation by batching hook/policy references; monthly batch reads/calculation should reuse batched validation.
- 7.B.6 established exact tenant scope, reference-only schemas, Decimal half-up four-decimal money rounding, six-decimal ratio serialization, and fail-closed stored drift.
- 7.B.7 showed P39 ETag/If-Match is expected for UI-editable/reviewable resources; apply it to monthly batch status changes.
- Prior post-review fixes repeatedly found sensitive-key matching must catch snake/camel/compact variants recursively.

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

- Story file has passed 3 pre-implementation adversarial review rounds and revisions.
- Monthly revenue-share API satisfies FR P8 as a safe calculation-batch contract without implementing real payout settlement, Revenue-Share Service, scheduled jobs, Provider Console UX, tax/bank/payment flows, or billing-ledger reads early.
- Existing provider marketplace, revenue-share hook, payout, and version behavior remains compatible.
- Post-implementation code review is completed and findings are fixed or explicitly documented.
- Local quality gates and GitHub CI pass.
- Story and sprint status are updated to `done` only after review, gates, CI, merge, branch cleanup, and local `main` sync.

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Debug Log References

- Story creation used local context from PRD P8, Architecture C4, 7.A.2 revenue-share hook reservation, 7.B.6 payout projection, 7.B.7 version management, and current capability-registry implementation files.
- Baseline branch: `codex/7-b-8-monthly-revenue-share`.
- Baseline commit: `c4b61f1005f8eeee97a5b5fb59d41f4884ec49ab`.
- Implementation started; story and sprint status moved to in-progress.
- Implementation clarification: batch path identity must be unique per scope because GET/PATCH routes address batches by `batch_id` without `period_month`.
- Focused monthly tests before post-review fixes: `uv run pytest apps/capability-registry/tests/test_api.py -k "monthly_revenue_share" -v` -> 4 passed.
- Full capability-registry tests before post-review fixes: `uv run pytest apps/capability-registry/tests/ -v` -> 54 passed.
- Type gate: `uv run mypy apps packages` -> passed.
- Lint/format gates: `uv run ruff check apps/capability-registry` and `uv run ruff format --check apps/capability-registry` -> passed.
- OpenAPI gates: `uv run python scripts/generate_openapi.py` and `uv run python scripts/check_openapi_drift.py` -> passed.
- Whitespace gate: `git diff --check` -> passed.
- Post-implementation code review found 3 patch findings: create-race mismatch handling, PATCH metadata/terminal immutability, and source-entry immutable-field drift validation.
- Post-review focused monthly tests: `uv run pytest apps/capability-registry/tests/test_api.py -k "monthly_revenue_share" -v` -> 6 passed.
- Post-review full capability-registry tests: `uv run pytest apps/capability-registry/tests/ -v` -> 56 passed.
- Post-review type gate: `uv run mypy apps packages` -> passed.
- Post-review lint/format gates: `uv run ruff check apps/capability-registry` and `uv run ruff format --check apps/capability-registry` -> passed.
- Post-review OpenAPI gates: `uv run python scripts/generate_openapi.py` and `uv run python scripts/check_openapi_drift.py` -> passed.
- Post-review whitespace gate: `git diff --check` -> passed.
- GitHub PR #143 created for `codex/7-b-8-monthly-revenue-share`; GitHub checks passed including capability-registry-test, mypy, lint, openapi-drift, ts-typecheck, and e2e.
- PR #143 squash-merged to `main` at merge commit `e2b28241d44da1366ee0b5bd84292aef5cf0823c`; remote feature branch deleted; local `main` synced to `origin/main`.

### Completion Notes List

- Story created for Provider Monthly Revenue Share calculation batch contract.
- Completed 3 pre-implementation adversarial review rounds and revised the story after each round.
- Added `provider_monthly_revenue_share_batches` schema/model, monthly batch create/status/summary/response schemas, and checked-in OpenAPI updates.
- Added monthly batch upsert/read/list/status APIs with exact tenant scope, pending/held inclusion, paid/voided exclusions, canonical checksum, idempotent draft recalculation, non-draft immutability, ETag/If-Match status locking, and no payout-entry side effects.
- Added tests for calculation totals, provider/currency/policy summaries, exact tenant scope, auth, draft recalculation, status lifecycle, ETag handling, stored drift exclusions/fail-closed behavior, no side effects, and OpenAPI contract safety.
- Post-review fixes added conflict validation for duplicate-create races, optional metadata preservation plus terminal status immutability on PATCH, and source-entry immutable field drift validation while preserving historical reads after later payout status changes.
- GitHub sync completed: PR #143 passed CI, merged, remote branch deleted, local `main` synced, and story/sprint status marked done.

### File List

- `_bmad-output/stories/7-b-8-monthly-revenue-share.md`
- `_bmad-output/stories/sprint-status.yaml`
- `infra/local-init/14-capability-registry.sql`
- `apps/capability-registry/src/capability_registry/models.py`
- `apps/capability-registry/src/capability_registry/schemas.py`
- `apps/capability-registry/src/capability_registry/routes.py`
- `apps/capability-registry/tests/test_api.py`
- `packages/shared-ts/openapi/capability-registry.json`

## Change Log

- 2026-06-02 - Story created for Provider Monthly Revenue Share calculation batch contract.
- 2026-06-02 - Completed 3 pre-implementation adversarial review rounds; story marked ready for development.
- 2026-06-02 - Implementation started; story and sprint status moved to in-progress.
- 2026-06-02 - Clarified monthly batch `batch_id` uniqueness to avoid ambiguous GET/PATCH path reads.
- 2026-06-02 - Implemented Provider Monthly Revenue Share calculation batch contract, tests, OpenAPI update, and local gates; pending post-implementation review.
- 2026-06-02 - Completed post-implementation code review, fixed 3 patch findings, added regression coverage, and reran local gates; pending GitHub sync.
- 2026-06-02 - PR #143 passed GitHub CI, merged to main, remote branch deleted, local main synced; story marked done.

## Pre-Implementation Adversarial Reviews

### Round 1 - Boundary, Ownership, And Product Fit Review

Findings:

1. "Monthly revenue share" could be misread as real payment settlement, tax withholding, invoice generation, or payout processor work.
2. Architecture C4 names Revenue-Share Service, but current repo sequencing has not introduced that deployable; creating it here would break the Provider Marketplace incremental path.
3. `exported` could be interpreted as paid or bank-transfer complete rather than a reference-ready calculation state.
4. `approved_by_ref` could accidentally become a person name, email, employee ID, signature, or inline approval comment.
5. Batch creation could be mistaken as scheduled job work rather than service-side API contract.
6. The story needed to prevent mutation of payout entry status to `paid` during monthly close.
7. It needed to avoid pulling raw billing ledgers into capability-registry.
8. It needed to keep Provider Console/public auth explicitly out of scope.
9. Snapshot metadata could accidentally expose internal settlement/payment references.
10. The story needed to state that `approved` and `exported` are calculation lifecycle states only.

Revisions applied:

- Clarified `exported` is not paid/settled/invoiced/taxed/transferred.
- Tightened `approved_by_ref` to reference-only values and rejected names, emails, IDs, signatures, comments, and payment refs.
- Preserved scope as capability-registry API contract only, with no new service, scheduled worker, payment, tax, invoice, or Provider Console work.

### Round 2 - Data Consistency, Snapshot Drift, And Amount Semantics Review

Findings:

1. The original drift wording could make historical batch reads fail after legitimate downstream payout entry status changes.
2. Batch snapshots need a clear split between source-of-truth calculation time and later audit reads.
3. Recalculation should be allowed for draft batches only; reviewed/approved/exported/cancelled batches must stay immutable.
4. Provider/currency totals must close exactly using the same Decimal semantics as 7.B.6.
5. `paid`/`voided` entries need excluded reasons, but excluded rows must not leak raw payout metadata.
6. `allow_drift_exclusions=true` could hide true corruption if raw drift payloads leak into response.
7. `source_entry_ids` must be deterministic and must not include raw UUID/database IDs when stable entry IDs suffice.
8. Policy ratio summaries need ratios in the grouping key, not only policy ID, because policy IDs can be overridden per tenant/scope.
9. Draft idempotency and recalculation rules needed to distinguish unchanged source rows from changed source rows.
10. Stored JSON snapshots need strict read-time validation, not blind return.

Revisions applied:

- Clarified that later payout-entry status changes are not drift for non-draft historical batch reads.
- Tightened source snapshot immutability and draft-only recalculation semantics.
- Kept stored snapshot validation focused on JSON shape, deterministic identifiers, amount/ratio serialization, and referenced immutable payout fields.

### Round 3 - Dependencies, Concurrency, Tests, And Closure Review

Findings:

1. Batch create/recalculate could hit unique-index races under concurrent requests unless handled like previous hook/payout insert paths.
2. P39 ETag behavior should apply to status transitions but not block first batch creation.
3. OpenAPI must prove request schemas cannot accept `calculation_checksum`, `record_version`, timestamps, or caller-owned totals.
4. Response schemas must avoid `metadata` and any settlement/payment/tax fields.
5. Tests need to prove monthly batch reads do not mutate payout entries.
6. Tests need to cover exact tenant scope and no global fallback because Provider Marketplace projections have repeatedly regressed there.
7. Tests need to cover `allow_drift_exclusions=true` without leaking raw drift details.
8. Stored batch JSON drift validation must cover malformed arrays and unsafe excluded reason values.
9. CI should reuse `capability-registry-test`; adding a new service job would be sequencing drift.
10. Story `done` must remain gated on PR merge, branch cleanup, local `main` sync, then status sync commit.

Revisions applied:

- Added deterministic unique-race handling AC and `begin_nested()` implementation guidance.
- Tightened OpenAPI/test requirements around caller-owned checksum/timestamps/record version and unsafe response fields.
- Preserved final done gate on GitHub CI, merge, remote branch deletion, and local main sync.

## Post-Implementation Code Review

Completed on 2026-06-02.

Review layers:

- Blind Hunter perspective: reviewed API lifecycle, idempotency, ETag, and unsafe response/request field boundaries from the implementation diff.
- Edge Case Hunter perspective: reviewed concurrency, terminal state mutation, source drift, exact tenant scope, and historical snapshot semantics against code paths.
- Acceptance Auditor perspective: reviewed implementation against AC 21, AC 23-26, AC 32, AC 35, AC 38, and AC 41.

Findings and fixes:

- [x] [Review][Patch] Duplicate-create race could return an existing mismatched batch as if idempotent. Fix: race recovery now verifies `period_month`, checksum, `notes_ref`, and metadata against the incoming request before returning the existing row; mismatches return 409. Regression: `test_provider_monthly_revenue_share_batch_create_race_rejects_mismatched_row`.
- [x] [Review][Patch] Status PATCH treated omitted `metadata` as `{}` and terminal batches could be changed by metadata-only patches. Fix: PATCH metadata is now optional and only mutates when provided; `exported`/`cancelled` allow only idempotent replay. Regression: lifecycle test asserts metadata preservation, terminal immutability, and idempotent terminal replay.
- [x] [Review][Patch] Stored batch reads validated JSON/checksum but did not revalidate referenced payout entry immutable fields. Fix: single/list/PUT/PATCH responses now validate `source_entry_ids` against exact-scope payout rows and recompute provider/currency/policy immutable totals while ignoring later payout status changes as non-drift. Regression: `test_provider_monthly_revenue_share_batch_validates_source_immutable_fields`.

Dismissed/noise:

- [x] `_MONTHLY_EXCLUDED_REASONS` and `_money_string` were unused implementation leftovers. They were removed as dead code cleanup.

Decision-needed: 0. Deferred: 0. Unresolved patch findings: 0.
