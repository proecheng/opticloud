---
story_key: 9-6-error-i18n-audit
epic_num: 9
story_num: 6
epic_name: NFR Governance
status: done
baseline_commit: a698b7e9e518b6a39368b65af3a68fcae7090b92
priority: High
type: FG1.3 error i18n quarterly audit governance
created_by: bmad-create-story
created_at: 2026-06-05
owner: Platform / Frontend / API Governance
sources:
  - _bmad-output/planning/epics.md (Epic 9 / Story 9.6)
  - _bmad-output/planning/prd.md (Error Codes RFC 7807 / FG1.3)
  - _bmad-output/planning/architecture.md (P29 Error Handling)
  - _bmad-output/stories/8-b-5-error-i18n-eslint.md
  - _bmad-output/stories/8-b-6-sdk-errors-preservation.md
  - _bmad-output/stories/9-5-wcag-2-2-upgrade-path.md
  - scripts/error_message_i18n_single_source.py
  - tests/test_error_i18n_single_source.py
  - packages/i18n/errors.zh-CN.yaml
  - packages/i18n/errors.en-US.yaml
  - apps/solver-orchestrator/src/solver_orchestrator/error_catalog.py
  - apps/solver-orchestrator/src/solver_orchestrator/error_responses.py
  - apps/billing-service/src/billing_service/problem_details.py
  - .github/workflows/ci.yml
---

# Story 9.6 - 错误码 i18n 单源 ESLint Enforcement Audit

Status: done

## Story

**作为** FG1.3 错误合同维护者和季度治理 owner，
**我希望** 8.B.5 的 `error-message-i18n-single-source` gate 升级为全仓季度审计闭环，覆盖前端 RFC 7807 problem-detail 构造、共享 i18n 字典、Python RFC 7807 目录/响应 builder、SDK preservation fixture、审计证据 manifest、runbook 和 CI hard gate，
**从而** 每次季度审计能证明“被纳入 FG1.3 公共错误合同的硬编码 user-visible error string 数 = 0”，并把历史/新发现 drift 以 ticket-backed findings 闭环，而不是让裸 `title` / `detail` / `remediation_hint_key` 再次散落。

## Context

Epic 9.6 原始 AC：Given Story 8.B.5 ESLint / When quarterly / Then 全 codebase scan + 硬编码 error string 数 = 0。

Story 8.B.5 已交付：

- `packages/i18n/errors.zh-CN.yaml` 和 `errors.en-US.yaml`
- `scripts/error_message_i18n_single_source.py`
- `tests/test_error_i18n_single_source.py`
- root lint / pre-commit / CI `error-i18n-validation`

但 8.B.5 明确把“全仓季度审计”和 Python 服务历史错误面留给 Story 9.6。当前仓库中还有多个需要被审计治理的公共错误 surface：

- `apps/solver-orchestrator/src/solver_orchestrator/error_catalog.py` 是 solver RFC 7807 title/detail/remediation 的真实目录，但 key 集合比 `packages/i18n` 字典更大。
- `apps/solver-orchestrator/src/solver_orchestrator/error_responses.py` 已按 `Accept-Language` 从目录选取错误文案。
- `apps/billing-service/src/billing_service/problem_details.py` 通过共享 `rfc7807_error` 输出 billing RFC 7807 响应，但还需要被季度审计纳入。
- Auth/capability/chat 等历史 `HTTPException(detail="...")` 仍存在；本 story 不一次性迁移所有业务 endpoint，但必须让审计 contract 明确它们是否在 FG1.3 公共错误合同内、是否有 finding/ticket、是否阻断 release approval。

## Scope

1. 新增静态治理资产 `tools/error_i18n_audit/`。
   - Contract pin `source_story=9.6`、`audit_version=error_i18n_quarterly_audit_v1`、`nfr=NFR-COMPLIANCE`、`fg=FG1.3`。
   - Contract 明确复用 8.B.5 的 rule id `error-message-i18n-single-source`，不创建第二套规则名。
   - Contract 定义 quarterly audit scan classes：TypeScript problem-detail 构造、`packages/i18n` 字典、solver error catalog、billing RFC 7807 helper、shared RFC 7807 helper、SDK fixture/preservation sample、legacy FastAPI `HTTPException` public backlog register。
   - Contract 记录 observed repo state，validator 必须在相关文件漂移时失败。
2. 新增 manifest schema 和 static example manifest。
   - Static example 必须 `example_only=true`，不能声称真实季度审计、真实全仓迁移、真实 production release approval 或真实外部 ticket 创建。
   - Real evidence path 仅允许 `reports/error-i18n-audit/<run_id>/audit_manifest.json`，目录名必须等于 `run_id`。
   - Real evidence 必须包含 scan summary、scan class results、dictionary parity result、hardcoded-error count、findings、ticket refs、redaction review、release gate。
3. 新增 `scripts/validate_error_i18n_audit.py`，只用 Python stdlib。
   - 默认模式校验 contract/schema/example/CI，并执行 committed static audit。
   - Optional `--evidence` 模式校验真实季度审计 manifest。
   - 复用或调用 8.B.5 gate 的语义，确保 TypeScript production problem-detail hard-coded title/detail 仍为 0。
   - 对 Python RFC 7807 catalog/helper 做 AST/文本审计：所有 production `remediation_hint_key` 必须是 `errors.*` 且存在于 zh/en 字典；solver catalog 的每个 entry 必须与字典 key parity 对齐；共享/billing helper 必须被登记。
   - 区分内部 exception/debug/assertion 文本和公共 RFC 7807/user-visible 错误文案，避免把非公共开发者错误误算为 FG1.3 drift。
4. 新增 `tests/test_error_i18n_audit.py`。
   - 覆盖 contract/schema/example、real evidence happy path、path mismatch、fake completion、dictionary drift、solver catalog drift、bad remediation key、hard-coded TS problem string、legacy HTTPException register drift、ticket-backed findings、release blocking、敏感信息泄漏、CI wiring。
5. 新增 `docs/runbooks/error-i18n-audit.md`。
   - 说明季度执行命令、scan class、硬编码 error string 计数口径、legacy backlog 处理、字典补齐流程、finding/ticket policy、redaction policy、release gate、rollback。
6. 补齐 `packages/i18n/errors.zh-CN.yaml` / `errors.en-US.yaml`。
   - 至少覆盖当前 solver `ERROR_CATALOG` 的所有 `remediation_hint_key`。
   - 覆盖 billing/shared helper 使用的 generic keys。
   - 保持 zh/en key 完全一致，字段仍是 `title/detail/remediation`。
7. 更新 `.github/workflows/ci.yml`。
   - 增加 `error_i18n_audit` path filter output 和 filter。
   - 新增 `error-i18n-audit-validation` job，无 `continue-on-error`。
   - Job 运行 static validator、optional committed real evidence validation、focused pytest，并继续运行 8.B.5 gate/test 以防规则漂移。
8. 不新增 npm/pip 依赖。
9. 不一次性重写所有 backend route、数据库 migration、OpenAPI、SDK runtime、业务错误语义或真实外部 ticket 集成。

## Out Of Scope

- 将仓库所有历史 `HTTPException(detail="...")`、Pydantic `ValueError(...)`、internal `RuntimeError(...)` 一次性迁移为 i18n runtime。
- 声称真实季度审计已经执行、真实生产 release 已批准、真实外部 ticket 已创建、所有 legacy public HTTPException 已迁移完成。
- 新增 ESLint flat config、npm ESLint plugin、jsonschema/pydantic、OpenAPI schema 重写、Accept-Language middleware 重构、SDK 运行时代码变更或后端业务逻辑迁移。
- 扫描测试、storybook、story docs、fixtures 中的示例错误文案并把它们计为 production drift。

## Acceptance Criteria

1. `tools/error_i18n_audit/error_i18n_audit_contract.json` 存在并作为 Story 9.6 canonical contract。
2. Contract pins `source_story=9.6`、`audit_version=error_i18n_quarterly_audit_v1`、`fg=FG1.3`、`standard_cadence=quarterly`。
3. Contract 复用 rule id `error-message-i18n-single-source`，禁止产生第二套同类 rule id。
4. Contract 定义 scan classes：`typescript_problem_detail`、`i18n_dictionary_parity`、`solver_error_catalog`、`billing_problem_details`、`shared_rfc7807_helper`、`sdk_preservation_fixture`、`legacy_http_exception_register`。
5. Contract observed repo state 与当前提交中文件/目录状态一致；相关文件或 catalog key 漂移时 validator 失败。
6. Contract 明确“hardcoded error string count = 0”的口径只覆盖 FG1.3 公共错误合同 surface，不把内部 exception/assertion/debug 文本计入。
7. Contract 明确 legacy public `HTTPException(detail=...)` 若未纳入 i18n runtime，必须作为 backlog register/finding 进入真实 evidence，不能被当作 completed migration。
8. Evidence schema 和 static example manifest 存在于 `tools/error_i18n_audit/`。
9. Static example `example_only=true`，`real_quarterly_audit_completed=false`，`real_full_codebase_migration_completed=false`，`release_approved=false`。
10. Static example 不能声称真实外部 ticket 创建、真实生产审批、真实 legacy migration 完成或硬编码历史问题全部修复。
11. Optional real evidence path 仅接受 `reports/error-i18n-audit/<run_id>/audit_manifest.json`。
12. Real evidence 必须 `example_only=false`、`redaction_reviewed=true`、`real_quarterly_audit_completed=true`。
13. Real evidence 的每个 scan class 必须有结果，且 `typescript_problem_detail` / `i18n_dictionary_parity` / `solver_error_catalog` 的 `hardcoded_error_string_count` 必须为 0。
14. Real evidence 中任何 failed/missing/stale scan class 或 nonzero legacy backlog 必须引用 finding；finding 必须有 ticket refs。
15. Real evidence 不能在 unresolved P0/P1/P2 finding 存在时标记 `release_approved=true`。
16. Validator 拒绝 tenant/user/customer ids、emails、phone、API keys、bearer tokens、cookies、passwords、secrets、credentialed URLs、production hostnames、absolute paths、directory traversal、raw logs、prompt/provider payloads。
17. 8.B.5 gate 仍能在 production TS/TSX RFC 7807 problem object 写 hard-coded `title/detail` 时失败。
18. 所有 production `remediation_hint_key` 必须形如 `errors.<scope>.<name>`，并存在于 zh/en 字典。
19. Solver `ERROR_CATALOG` 每个 entry 的 `remediation_hint_key` 都存在于 zh/en 字典。
20. Solver `ERROR_CATALOG` 每个 entry 的英文/中文 title/detail 与 i18n 字典 key 集合不漂移；若运行时模板保留 `{detail}`，字典至少必须提供该 key 的 title/detail/remediation。
21. Billing/shared RFC 7807 helper 使用到的 generic keys 存在于 zh/en 字典。
22. SDK preservation fixture 中出现的 `remediation_hint_key` 必须存在于 zh/en 字典。
23. Legacy public `HTTPException(detail=...)` register 由 validator 从 committed source 发现并与 contract observed state 对齐，防止静默新增。
24. `.github/workflows/ci.yml` exposes `error_i18n_audit` from `changes` outputs。
25. CI path filter 覆盖 `tools/error_i18n_audit/**`、`scripts/validate_error_i18n_audit.py`、`tests/test_error_i18n_audit.py`、`docs/runbooks/error-i18n-audit.md`、`reports/error-i18n-audit/**`、`packages/i18n/**`、8.B.5 gate/test、relevant RFC 7807 Python/TS surfaces 和 `.github/workflows/ci.yml`。
26. CI job `error-i18n-audit-validation` 无 `continue-on-error`。
27. CI job 运行 static audit validator、optional real evidence validation、focused tests、8.B.5 single-source gate 和 8.B.5 tests。
28. No new npm/Python dependency is added and lockfiles remain unchanged unless justified in Dev Agent Record。
29. Local gates pass: `uv run python scripts/validate_error_i18n_audit.py`、`uv run pytest tests/test_error_i18n_audit.py -q`、`uv run python scripts/error_message_i18n_single_source.py`、`uv run pytest tests/test_error_i18n_single_source.py -q`、`git diff --check`。
30. Post-implementation code review covers boundary issues、drift issues、data consistency、dependency consistency、closure completeness、fake-completion risk、CI hard gate、evidence redaction、test adequacy；findings fixed or documented。
31. Story status flow is `ready-for-dev -> in-progress -> code-review -> done`。
32. `done` is forbidden before GitHub CI passes, PR merges, remote branch is deleted, and local `main` is synced。
33. After merge/sync, story and sprint status are marked `done` only through a separate status-sync commit。

## Tasks / Subtasks

- [x] T1: Add Story 9.6 audit contract/schema/example (AC: 1-16)
  - [x] Create `tools/error_i18n_audit/error_i18n_audit_contract.json`.
  - [x] Create `tools/error_i18n_audit/error_i18n_audit_manifest.schema.json`.
  - [x] Create `tools/error_i18n_audit/error_i18n_audit_manifest.example.json`.
  - [x] Encode scan classes, fake-completion flags, redaction rules, release gate, and legacy backlog boundary.

- [x] T2: Add validator and focused tests (AC: 11-27)
  - [x] Implement `scripts/validate_error_i18n_audit.py` using stdlib only.
  - [x] Validate static assets, current repo observed state, dictionary parity, solver catalog parity, TS gate reuse, SDK fixture keys, legacy register drift, evidence path mode, sensitive-value rejection, and CI wiring.
  - [x] Add `tests/test_error_i18n_audit.py`.

- [x] T3: Bring i18n dictionaries to audited parity (AC: 18-22, 28)
  - [x] Add missing solver catalog keys to zh/en dictionaries.
  - [x] Add billing/shared generic keys.
  - [x] Add SDK fixture keys as needed.
  - [x] Verify key parity and no empty title/detail/remediation fields.

- [x] T4: Add runbook and CI closure (AC: 24-29)
  - [x] Add `docs/runbooks/error-i18n-audit.md`.
  - [x] Add `error_i18n_audit` output/path filter and validation job to `.github/workflows/ci.yml`.
  - [x] Ensure 8.B.5 gate/test run inside the 9.6 audit job.

- [x] T5: Gates, review, and GitHub sync (AC: 29-33)
  - [x] Run local validation gates.
  - [x] Run post-implementation code review and fix/document findings.
  - [x] Commit, push, create PR, wait for CI, merge, delete remote branch, and sync local `main`.
  - [x] Mark story and sprint status `done` only after merge/sync through a separate status-sync commit.

## Dev Notes

### Existing Implementation To Reuse

- 8.B.5 `scripts/error_message_i18n_single_source.py` is authoritative for production TS/TSX problem-detail string checks. Do not replace it; call it or import its validation functions.
- `packages/i18n/errors.zh-CN.yaml` and `errors.en-US.yaml` are flat two-level dictionaries under `errors.<scope>.<name>`.
- `apps/solver-orchestrator/src/solver_orchestrator/error_catalog.py` is the most mature Python i18n runtime catalog. Use it as the key parity source for solver RFC 7807 responses.
- 9.1-9.5 governance stories established the local pattern: `tools/<topic>/` JSON contract/schema/example, stdlib validator, focused pytest, runbook, CI path filter/job, optional real evidence mode.

### Boundary Rules

- This story proves an audit gate and dictionary/catalog parity for defined FG1.3 public error surfaces.
- This story does not prove every historical backend error response is already runtime-localized.
- This story must not hide legacy public `HTTPException(detail=...)` drift; it must record the discovered register and require real-evidence findings/tickets before release approval.
- Internal exceptions, validation assertions, CLI errors, tests, story docs, and fixture examples are not counted as production public FG1.3 hard-coded user-visible error strings.

### Suggested Commands

```powershell
uv run python scripts/validate_error_i18n_audit.py
uv run pytest tests/test_error_i18n_audit.py -q
uv run python scripts/error_message_i18n_single_source.py
uv run pytest tests/test_error_i18n_single_source.py -q
git diff --check
```

## Definition Of Done

- Story has passed exactly 3 pre-implementation adversarial review rounds with revisions recorded after each round.
- Error i18n audit contract/schema/example, validator, tests, runbook, dictionary parity, and CI hard gate exist.
- Validator catches fake completion, dictionary/catalog drift, hard-coded TS problem strings, invalid/missing remediation keys, legacy register drift, unsafe evidence, missing tickets, release approval with unresolved stop-ship findings, and CI soft-gate drift.
- Local gates and GitHub CI pass.
- Post-implementation code review is completed and findings are fixed or explicitly documented.
- Story and sprint status become `done` only after PR CI green, merge, remote branch deletion, local main sync, and a separate status-sync commit.

## Story Review Log

### Round 1: Boundary And Scope Review

Findings fixed:

- Initial reading could force a full backend runtime i18n migration across auth/capability/chat/billing/solver, which would exceed Story 9.6 and collide with business endpoint behavior. Revised scope to a quarterly audit governance gate plus dictionary/catalog parity for defined FG1.3 surfaces.
- Initial “全 codebase scan” could count tests, assertions, CLI errors, Pydantic validator internals, and debug strings as user-visible error strings. Revised count definition to public FG1.3 error-contract surfaces and added explicit exclusions.
- Initial “hard-coded count = 0” could hide legacy `HTTPException(detail=...)` by excluding it. Revised scope to discover and pin a legacy public HTTPException register and require findings/tickets in real evidence.

Status: PASS after fixes.

### Round 2: Drift, Data Consistency, And Dependency Review

Findings fixed:

- 8.B.5 dictionaries currently contain fewer keys than solver `ERROR_CATALOG`; without catalog parity, the audit could be green while Python runtime keys are absent from the i18n single source. Added solver catalog parity AC and dictionary completion task.
- Billing/shared RFC 7807 helper keys are not automatically covered by the TS gate. Added billing/shared helper scan class and generic-key dictionary coverage.
- SDK preservation fixtures can carry remediation keys that drift from dictionaries. Added SDK fixture key validation.
- Adding a real ESLint plugin or JSON schema dependency would violate established 9.x governance pattern. Added stdlib-only and no-new-dependency constraints.

Status: PASS after fixes.

### Round 3: Closure, Evidence, And CI Review

Findings fixed:

- Static example could falsely imply the quarterly audit already ran. Added fake-completion flags and example-only restrictions.
- Real evidence could mark release approved while P0/P1/P2 findings remain unresolved. Added release blocking and ticket requirements.
- CI could validate only new assets and miss 8.B.5 rule drift. Added explicit 8.B.5 gate/test execution inside `error-i18n-audit-validation`.
- Lifecycle could accidentally mark `done` before GitHub sync. Added strict status flow and separate post-merge status-sync requirement.

Status: PASS after fixes. Story is ready for development.

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Debug Log References

- Baseline branch: `codex/9-6-error-i18n-audit`.
- Customization resolver script absent at `_bmad/scripts/resolve_customization.py`; fallback loaded base skill instructions and project config.
- Story creation analyzed Epic 9.6, PRD FG1.3, Architecture P29, Story 8.B.5, Story 8.B.6, Story 9.5, current i18n dictionaries, current TypeScript gate, solver error catalog, billing/shared RFC 7807 helpers, and CI path-filter patterns.
- 2026-06-05 - Completed pre-implementation adversarial review round 1 and revised scope/count boundaries plus legacy HTTPException register handling.
- 2026-06-05 - Completed pre-implementation adversarial review round 2 and revised dictionary/catalog/helper/SDK parity and dependency boundaries.
- 2026-06-05 - Completed pre-implementation adversarial review round 3 and revised evidence fake-completion, release gate, CI closure, and status-sync ordering.
- 2026-06-05 - Story moved to in-progress after exactly three pre-implementation review rounds.
- 2026-06-05 - RED confirmed: `uv run pytest tests/test_error_i18n_audit.py -q` failed with 17 expected failures before validator/assets/runbook/CI existed.
- 2026-06-05 - Implemented Story 9.6 error i18n audit contract/schema/example, stdlib validator, focused tests, runbook, CI hard gate, and zh/en dictionary parity for solver/billing/shared/SDK keys.
- 2026-06-05 - Local gates passed: `uv run python scripts/validate_error_i18n_audit.py`, `uv run pytest tests/test_error_i18n_audit.py -q` (17 passed), `uv run python scripts/error_message_i18n_single_source.py`, `uv run pytest tests/test_error_i18n_single_source.py -q` (9 passed), `uv run ruff check scripts/validate_error_i18n_audit.py tests/test_error_i18n_audit.py`, and `git diff --check`.
- 2026-06-05 - Post-implementation code review finding 1 fixed: `error_i18n_audit` CI filter missed broad legacy Python public error surfaces. Added `apps/*/src/**/*.py` to the path filter and validator test coverage.
- 2026-06-05 - Post-implementation code review finding 2 fixed: production `remediation_hint_key` scanning only covered solver/billing/shared/SDK subsets and missed auth/chat/billing keys plus helper-position arguments. Migrated production keys to `errors.*`, added chat schema namespace validation, added production source scanner with bounded dynamic template expansion, and expanded zh/en dictionaries to 90 keys.
- 2026-06-05 - Post-review gates passed: `uv run python scripts/validate_error_i18n_audit.py`; `uv run pytest tests/test_error_i18n_audit.py -q` (23 passed); `uv run python scripts/error_message_i18n_single_source.py`; `uv run pytest tests/test_error_i18n_single_source.py -q` (9 passed); `uv run ruff check ...`; `git diff --check`.
- 2026-06-05 - Targeted post-review tests passed: auth frozen appeals (10 passed), billing warning classification (6 passed with service PYTHONPATH), chat coder/internal-beta/model-preview/language-response (69 passed with service PYTHONPATH).
- 2026-06-05 - PR #175 passed GitHub CI, squash-merged to `main` at `a90cd59`, remote branch `codex/9-6-error-i18n-audit` was deleted, and local `main` was synced.
- 2026-06-05 - Separate status-sync commit prepared after merge/sync to mark Story 9.6 and sprint status `done`.

### Completion Notes List

- Initial story created.
- Exactly three pre-implementation adversarial review rounds completed; story is ready for implementation.
- Story moved to in-progress after exactly three pre-implementation review rounds.
- Added Story 9.6 error i18n audit governance assets, validator, tests, runbook, CI hard gate, and dictionary parity coverage.
- Story moved to code-review after local implementation gates passed; `done` remains blocked until post-review, PR CI, merge, remote branch deletion, local main sync, and separate status-sync commit.
- Post-implementation code review completed. Fixed CI path filter drift and production remediation key audit blind spots, including auth frozen appeal, billing warnings, chat coder/critic/formulator/sandbox/model-preview/language default keys, bounded dynamic templates, and schema-level `errors.*` enforcement for chat validation errors.
- PR #175 passed CI and merged. Story and sprint status now marked `done` in this separate post-merge status-sync.

### Post-Implementation Code Review

Outcome: Changes requested, then fixed.

Findings fixed:

- CI hard-gate coverage gap: the audit path filter covered named RFC 7807 files but missed broad Python service source drift. Fixed by adding `apps/*/src/**/*.py` to the `error_i18n_audit` path filter and CI wiring tests.
- AC18 enforcement gap: validator did not scan all production `remediation_hint_key` emitters and allowed old non-`errors.*` namespaces to persist in auth/chat/billing paths. Fixed by migrating production default keys, adding dictionary entries, adding chat schema namespace validation, and adding static/dynamic production key validation to `scripts/validate_error_i18n_audit.py`.
- Dynamic key boundary: retained only bounded templates for `errors.422.{result.status}`, `errors.chat_sandbox.{error_code.value}`, and `errors.{status_code}.billing_http_error`; validator expands them to concrete dictionary keys.

Residual risk:

- Legacy public `HTTPException(detail=...)` migration remains intentionally out of scope and pinned as the `legacy_http_exception_register` backlog for real quarterly evidence.

### File List

- `_bmad-output/stories/9-6-error-i18n-audit.md`
- `_bmad-output/stories/sprint-status.yaml`
- `.github/workflows/ci.yml`
- `docs/runbooks/error-i18n-audit.md`
- `packages/i18n/errors.en-US.yaml`
- `packages/i18n/errors.zh-CN.yaml`
- `scripts/validate_error_i18n_audit.py`
- `tests/test_error_i18n_audit.py`
- `tools/error_i18n_audit/error_i18n_audit_contract.json`
- `tools/error_i18n_audit/error_i18n_audit_manifest.schema.json`
- `tools/error_i18n_audit/error_i18n_audit_manifest.example.json`
- `apps/auth-service/src/auth_service/frozen_appeals.py`
- `apps/auth-service/tests/test_frozen_appeals.py`
- `apps/billing-service/src/billing_service/pricing.py`
- `apps/billing-service/tests/test_classify_warnings.py`
- `apps/chat-service/src/chat_service/coder.py`
- `apps/chat-service/src/chat_service/critic.py`
- `apps/chat-service/src/chat_service/formulator.py`
- `apps/chat-service/src/chat_service/language_response.py`
- `apps/chat-service/src/chat_service/model_preview.py`
- `apps/chat-service/src/chat_service/sandbox.py`
- `apps/chat-service/src/chat_service/schemas.py`
- `apps/chat-service/tests/test_coder.py`
- `apps/chat-service/tests/test_internal_beta.py`
- `apps/chat-service/tests/test_model_preview.py`
- `apps/web/src/app/auth/login/page.test.tsx`

## Change Log

- 2026-06-05 - Initial Story 9.6 created.
- 2026-06-05 - Round 1 pre-implementation review revised boundary/count and legacy register handling.
- 2026-06-05 - Round 2 pre-implementation review revised dictionary/catalog/helper/SDK parity and dependency constraints.
- 2026-06-05 - Round 3 pre-implementation review revised evidence, CI closure, and GitHub/status-sync ordering.
- 2026-06-05 - Story status moved to in-progress after exactly three pre-implementation review rounds.
- 2026-06-05 - Implemented error i18n quarterly audit governance assets, validator, tests, dictionary parity, runbook, and CI hard gate.
- 2026-06-05 - Story status moved to code-review after local implementation gates passed.
- 2026-06-05 - Addressed post-implementation code review findings for CI coverage and production `remediation_hint_key` namespace/dictionary enforcement.
- 2026-06-05 - PR #175 passed CI, merged to `main`, remote branch deleted, local `main` synced, and Story 9.6 marked `done` through a separate status-sync commit.
