# Story 3.12: J3 SRE Incident Tier 3 brief

Status: done

owner: SRE / Observability owner

## Story

作为 OptiCloud SRE 王哲，
我希望 P0 provider incident 能生成可校验的 Tier 3 应急合同、Status Page 公告载荷和 24h Postmortem 骨架，
以便 on-call 在半夜收到告警时能按同一套数据、状态词和边界执行，并为后续 Epic 8.A 的真实公开状态页与 Postmortem 服务打下不漂移的基础。

## Acceptance Criteria

1. J3 P0 incident Tier 3 合同是明确的静态 source of truth。
   - 新增 `tools/incidents/j3_sre_incident_contract.json`。
   - 合同必须使用 `contract_version=j3_sre_incident_tier3_v1` 和 `source_story=3.12`。
   - 合同必须固定 `journey=J3`、`persona=wang-zhe-sre`、`severity=P0`、`incident_type=provider_outage`。
   - 合同必须定义 `primary_provider=deepseek-v3.5`、`fallback_provider=qwen-max`、`trigger=provider_health_deepseek_failure`。
   - 合同必须把 Provider Health 探活失败告警 SLA 设为 `alert_seconds_max=30`。
   - 合同必须把 P0 后 Status Page 初始公告 SLA 设为 `status_page_publish_seconds_max=60`。
   - 合同必须把 24h Postmortem 发布 SLA 设为 `postmortem_publish_hours_max=24`。
   - 合同必须引用 M3.6c 已有 incident fallback drill 计划 `tools/chat_load/incident_fallback_plan.json`，并记录其 canonical SHA-256，用于证明 fallback drill 合同被绑定而不是重写。
   - 合同不得包含真实生产 URL、DingTalk webhook、API key、bearer token、cookie、租户 ID、客户 prompt、provider request/response payload 或内部主机名。

2. Incident manifest schema/example 覆盖 Status Page 公告与 Postmortem 骨架，且可被静态验证。
   - 新增 `tools/incidents/j3_sre_incident.schema.json`。
   - 新增 `tools/incidents/j3_sre_incident.example.json`，作为 deterministic 非生产示例。
   - manifest 必须要求 `source_story`、`contract_version`、`incident_id`、`example_only`、`generated_by`、`commit_sha`、`environment`、`severity`、`trigger`、`providers`、`timeline`、`provider_health_snapshot`、`fallback_reference`、`status_page_announcement`、`postmortem_skeleton`。
   - `environment` 的示例值必须是 `tier3-static-example`；未来真实演练 evidence 才可使用 `staging-incident-drill` 或更具体的 operator evidence 环境。
   - `incident_id` 必须是稳定 slug，且未来真实 evidence 路径必须位于 `reports/j3-sre-incident/<incident_id>/incident_manifest.json`。
   - `status_page_announcement` 必须包含 `status=investigating`、`component=llm-provider-deepseek`、`started_at_utc`、`published_at_utc`、`public_summary`、`affected_scope`、`customer_visible=true|false`、`next_update_due_utc`。
   - `postmortem_skeleton` 必须包含 `public_url_path=/status/incidents/<incident_id>`、`publish_due_utc`、`sections.what_happened`、`sections.timeline`、`sections.impact`、`sections.detection`、`sections.mitigation`、`sections.root_cause_placeholder`、`sections.follow_ups`、`sections.compensation_placeholder`。
   - 示例 manifest 必须设置 `example_only=true`，并且不得被 validator 接受为真实 incident evidence。
   - 示例 manifest 可以声明 Status Page 公告载荷已生成，但不得声称真实公网 status page、RSS/Webhook 订阅、DingTalk 发送、Credits 退款或公开 Postmortem 已完成。

3. 时间线、状态词和 SLA 计算必须闭环。
   - `timeline` 必须包含 `incident_started_utc`、`provider_health_failed_utc`、`p0_declared_utc`、`sre_paged_utc`、`fallback_decision_utc`、`fallback_confirmed_utc`、`status_page_published_utc`、`postmortem_due_utc`。
   - 所有时间戳必须是 UTC `YYYY-MM-DDTHH:MM:SSZ`。
   - `provider_health_failed_utc` 不得早于 `incident_started_utc`。
   - `sre_paged_utc` 不得早于 `provider_health_failed_utc`。
   - `status_page_published_utc - p0_declared_utc <= 60s`。
   - `postmortem_due_utc - p0_declared_utc = 24h`。
   - `fallback_confirmed_utc` 必须晚于 `fallback_decision_utc`；switch duration 参考 M3.6c，不在 3.12 重写阈值。
   - Status Page 状态词 vocabulary 必须固定为 `investigating`、`identified`、`monitoring`、`resolved`；3.12 初始公告必须是 `investigating`。
   - `postmortem_skeleton.sections.timeline` 必须引用同一组 canonical timeline 字段，不能复制一套不一致字段名。

4. Validator 和测试防止数据/函数漂移与假完成。
   - 新增 `scripts/validate_j3_incident_contract.py`，默认校验 committed contract、schema、example manifest。
   - Validator 必须提供可选参数 `--evidence reports/j3-sre-incident/<incident_id>/incident_manifest.json`，用于未来 operator evidence PR。
   - Validator 必须校验 contract metadata、provider IDs、SLA 阈值、M3.6c plan hash、schema required fields、example-vs-real 边界、timeline ordering、SLA 计算、status vocabulary、postmortem section set、artifact path 归属、forbidden secret-like keys/values。
   - Validator 必须拒绝示例 manifest 以真实 evidence 模式提交。
   - Validator 必须拒绝 `status_page_publicly_available=true`、`subscriber_webhook_sent=true`、`dingtalk_webhook_called=true`、`credits_refunded=true`、`postmortem_publicly_published=true` 出现在 `example_only=true` manifest 中。
   - Validator 必须拒绝绝对路径、Windows drive path、URL scheme、`..` traversal、credentialed URL、bearer token、API key、cookie、tenant/customer identifiers。
   - 新增 `tests/test_j3_incident_contract.py` 覆盖成功校验和负例：provider drift、SLA drift、M3.6c hash drift、status vocabulary drift、60s 公告超时、24h due 计算错误、timeline 顺序错误、示例假装真实 evidence、路径越界、secret-like 字段、假公网发布/订阅/退款/Postmortem 完成声明。

5. Runbook 给 on-call 可执行流程，但不接入真实 webhook 或公网发布。
   - 新增 `docs/runbooks/j3-sre-incident-tier3.md`。
   - Runbook 必须按 UX Tier 3 flow 描述：告警 -> DingTalk page -> Console Provider Health -> 手动 Qwen-Max fallback -> Status Page `Investigating` -> 修复 -> 24h Postmortem。
   - Runbook 必须说明本 story 的 Status Page 与 Postmortem 是 payload/模板/校验合同，不是 Epic 8.A 的生产状态页、订阅系统或管理员发布后台。
   - Runbook 必须引用 `docs/runbooks/chat-incident-fallback.md` 和 M3.6c evidence 模式，说明 fallback drill evidence 与 J3 public-safe incident record 的关系。
   - Runbook 必须列出可提交的 redacted evidence 清单，不得要求或示例真实 API keys、webhook token、customer prompt、provider payload、tenant ID、内部 hostname。
   - Runbook 必须包含 rollback、Postmortem 审稿、后续 action item、补偿占位说明；补偿只能记录 placeholder，不得声称自动退款已经执行。

6. CI 静态执行，不依赖真实 provider、Status Page 服务或 DingTalk。
   - 扩展 `.github/workflows/ci.yml` path filter，新增 `j3_incident_contract`，覆盖 `tools/incidents/**`、`scripts/validate_j3_incident_contract.py`、`tests/test_j3_incident_contract.py`、`docs/runbooks/j3-sre-incident-tier3.md`、`reports/j3-sre-incident/**`。
   - 新增 focused CI job 运行 `uv run python scripts/validate_j3_incident_contract.py` 和 `uv run pytest tests/test_j3_incident_contract.py -v`。
   - CI 必须在存在 `reports/j3-sre-incident/**/incident_manifest.json` 时逐个运行 `uv run python scripts/validate_j3_incident_contract.py --evidence "$manifest"`。
   - CI 不得需要 Kubernetes、Grafana、Locust live run、DeepSeek API key、Qwen-Max API key、DingTalk secret、公网 status domain、数据库或外部网络。

7. 工作流状态和边界必须显式。
   - 本 story 文档必须记录三轮 pre-implementation story review，并在每轮审查后把修正落回 AC、tasks、Dev Notes 或边界规则。
   - `_bmad-output/stories/sprint-status.yaml` 只能在三轮 story review 完成后把 `3-12-j3-sre-incident-tier3` 从 `backlog` 改为 `ready-for-dev`。
   - 实施阶段开始后再把 story 改为 `in-progress`；实现完成后进入 `code-review`；代码审查修复和回归通过后才进入 `done`。
   - 本 story 不实现公开 status page 前端、RSS/Webhook 订阅、管理员 Postmortem CRUD、真实 DingTalk webhook、真实 Status Page 发布、真实 Credits 退款、`/v1/system/health` 后端、Provider Health Console、生产 provider router 或数据库表。
   - Epic 8.A.1 / 8.A.2 / 8.A.3 仍分别拥有公开状态页、incident 订阅和 24h Postmortem 生产功能。

## Tasks / Subtasks

- [x] Task 1: 建立 J3 incident 静态合同资产。 (AC: 1, 2, 3)
  - [x] 新增 `tools/incidents/j3_sre_incident_contract.json`。
  - [x] 新增 `tools/incidents/j3_sre_incident.schema.json`。
  - [x] 新增 `tools/incidents/j3_sre_incident.example.json`。
  - [x] 绑定 M3.6c `tools/chat_load/incident_fallback_plan.json` canonical hash，避免重新定义 fallback drill。
- [x] Task 2: 新增 validator 与回归测试。 (AC: 4)
  - [x] 新增 `scripts/validate_j3_incident_contract.py`。
  - [x] 新增 `tests/test_j3_incident_contract.py`。
  - [x] 覆盖 metadata、SLA、timeline、status vocabulary、Postmortem section、redaction、path 和 fake completion 负例。
- [x] Task 3: 新增 J3 on-call runbook。 (AC: 5)
  - [x] 新增 `docs/runbooks/j3-sre-incident-tier3.md`。
  - [x] 明确 internal Tier 3 contract 与未来 Epic 8.A 生产发布系统的边界。
  - [x] 列出 operator evidence、redaction、rollback、Postmortem 审稿和补偿占位流程。
- [x] Task 4: CI 接入。 (AC: 6)
  - [x] 扩展 `.github/workflows/ci.yml` path filter。
  - [x] 新增 `j3-incident-contract-validation` job。
  - [x] 添加未来真实 evidence optional validation loop。
- [x] Task 5: 验证、代码审查和 BMAD bookkeeping。 (AC: 7)
  - [x] 运行 `uv run python scripts/validate_j3_incident_contract.py`。
  - [x] 运行 `uv run pytest tests/test_j3_incident_contract.py -q`。
  - [x] 运行 `uv run ruff check scripts/validate_j3_incident_contract.py tests/test_j3_incident_contract.py`。
  - [x] 运行 `uv run ruff format --check scripts/validate_j3_incident_contract.py tests/test_j3_incident_contract.py`。
  - [x] 运行 `uv run pre-commit run --all-files --show-diff-on-failure`。
  - [x] 运行 `git diff --check`。
  - [x] 实施完成后进行代码审查，按审查意见修改，再同步 GitHub。

## Dev Notes

### Source Context

- `_bmad-output/planning/epics.md` Story 3.12 定义 J3 SRE Incident Tier 3 brief：P0 incident 后 status page 自动公告 + 24h Postmortem。
- `_bmad-output/planning/prd.md` Journey 3 描述王哲 SRE 的午夜 incident：DeepSeek Provider Health 探活失败、手动 Qwen-Max fallback、Status Page `Investigating`、24h Postmortem。
- `_bmad-output/planning/prd.md` Journey 3 的 incident automation SLA：Provider health failure alert <=30s，P0 触发 Postmortem 模板骨架，Status Page 公告 <=1min。
- `_bmad-output/planning/prd.md` FR O1/O2 把公开 status page、incident subscription、24h Postmortem 放在 v1 末。
- `_bmad-output/planning/ux-design-specification.md` Tier 3 brief 明确 J3 是内部应急 SOP：告警 -> DingTalk page -> Provider Health -> 手动 Qwen-Max fallback -> Status Page -> 24h Postmortem。
- `_bmad-output/planning/architecture.md` P46 定义 `/healthz`、`/readyz`、`/v1/system/health`，其中 `/v1/system/health` 是未来 Status Page / oncall deep health 输入。
- `_bmad-output/planning/epics.md` Epic 8.A.1/8.A.2/8.A.3 分别拥有生产公开 status page、incident 订阅和 24h Postmortem。

### Current Repository Reality

- 现有 repo 已有 M3.6c static incident fallback drill：`tools/chat_load/incident_fallback_plan.json`、`tools/chat_load/incident_fallback_evidence_manifest.schema.json`、`tools/chat_load/incident_fallback_evidence_manifest.example.json`、`scripts/validate_chat_load_plan.py`、`tests/test_chat_load_plan.py`、`docs/runbooks/chat-incident-fallback.md`。
- M3.6c 已明确：CI 验证结构，真实 operator evidence 未来单独提交；它不证明生产 router、Status Page 或 Postmortem 已上线。
- `docs/runbooks/llm-provider-abstraction.md` 说明 fallback 是 explicit incident behavior，不改变正常 v1 SLO，也不实现普通 multi-LLM routing。
- 当前 `apps/web/src/app` 没有公开 status page、incident history、subscription 或 Postmortem UI。
- 当前服务已有 `/healthz`/`/readyz` 模式，但没有统一实现 `/v1/system/health`；本 story 不应新增该后端端点。
- `docs/runbooks/README.md` 已把 P0 incident 24h Postmortem 模板列为 M5 商用前重要 SOP，但仓库尚未有 `postmortem-template.md`。

### Implementation Guidance

- 使用 `tools/incidents/` 作为 J3 incident 合同资产目录，避免把非 Chat-only 的 Status/Postmortem 合同继续塞进 `tools/chat_load/`。
- 使用 JSON Schema 2020-12，与 M3.6c 的 schema 风格保持一致。
- Validator 可复用 M3.6c 的思想：canonical JSON hash、UTC timestamp parse、secret-like key/value 检查、repository-relative path 检查、example-vs-real evidence 区分；不要从 `scripts/validate_chat_load_plan.py` 直接耦合导入大量 Chat-only 全局常量。
- M3.6c fallback plan hash 只用于绑定已有 fallback drill 合同；3.12 不重新定义 `fallback_first_token_p95_ms`、prompt fixture、Locust artifacts 或 schema parity。
- `status_page_announcement.public_summary` 必须是 public-safe 文案，不能包含内部主机、上游错误响应、客户名、租户量、provider 原始返回或告警 token。
- `compensation_placeholder` 只能描述需要交给 billing/customer-success 处理的占位，不应写入真实 refund transaction、charge id 或自动补偿已执行声明。

### Boundary Rules

- 不实现 `status.opticloud.cn`、`/status/incidents/{id}` 页面、RSS/Webhook 订阅、email 推送、DingTalk webhook、Postmortem 管理后台、数据库表、真实公网发布或真实退款。
- 不把 J3 示例 evidence 当成生产事故证明；`example_only=true` 永远不能通过 `--evidence` 模式。
- 不修改 M3.6c existing Chat load plan/schema/example，除非只是读取其 canonical hash。
- 不新增 provider API 调用、网络请求、DingTalk SDK、StatusPage SaaS SDK、云凭证或外部服务依赖。
- 不记录真实客户 prompt、tenant id、API key、Authorization header、cookie、内部 URL 或 provider payload。

### Testing Standards

Expected local validation after implementation:

```bash
uv run python scripts/validate_j3_incident_contract.py
uv run pytest tests/test_j3_incident_contract.py -q
uv run ruff check scripts/validate_j3_incident_contract.py tests/test_j3_incident_contract.py
uv run ruff format --check scripts/validate_j3_incident_contract.py tests/test_j3_incident_contract.py
uv run pre-commit run --all-files --show-diff-on-failure
git diff --check
```

Focused red/green loop while implementing:

```bash
uv run python scripts/validate_j3_incident_contract.py
uv run pytest tests/test_j3_incident_contract.py -q
```

### Risks / Decisions

- Data consistency risk: incident ID、timeline、Status Page status、Postmortem URL path、evidence path 可能各自拼一套。Schema/validator 必须把这些字段绑定到同一个 `incident_id` 和 canonical timeline。
- Function consistency risk: 3.12 可能重写 M3.6c fallback drill。只引用 M3.6c plan hash，不复制 prompt/evidence/latency schema。
- Drift risk: initial status page vocabulary 可能随 Epic 8.A 变化。3.12 先固定最小 vocabulary，并让未来 Epic 8.A 如需扩展必须有显式迁移。
- Boundary risk: "自动公告 + 24h Postmortem" 容易被实现成真实公网系统。3.12 只创建 payload/template/validator/runbook；生产发布系统仍归 Epic 8.A。
- Closure risk: 示例 manifest 可能伪造真实公告、订阅、退款或公开 Postmortem。Validator 必须显式拒绝这些 fake completion flags。

## Story Review Rounds

### Round 1 - Data Consistency (2026-05-28)

Findings applied:

- 统一 `incident_id` 为 schema、example manifest、Status Page `public_url_path`、future evidence path 的唯一绑定键，避免公告、Postmortem 和 reports 目录各自命名。
- 把 `status_page_published_utc - p0_declared_utc <= 60s`、`postmortem_due_utc - p0_declared_utc = 24h` 写入 AC，避免 PRD SLA 只停留在叙述。
- 固定 Status Page 初始状态为 `investigating`，并列出最小状态词 vocabulary，避免 runbook、schema、测试使用不同词。
- 要求 Postmortem skeleton timeline 引用 canonical timeline 字段，而不是复制另一套时间线。

Result: incident ID、时间线、Status Page 公告和 Postmortem skeleton 数据一致。

### Round 2 - Function / Dependency Consistency and Drift (2026-05-28)

Findings applied:

- 明确 3.12 只绑定 M3.6c fallback plan hash，不重新定义 Chat fallback drill 的 Locust、prompt、latency、schema parity 合同。
- 新增 `tools/incidents/` 目录作为 cross-domain incident contract 位置，避免污染 `tools/chat_load/`。
- 明确不实现 `/v1/system/health`、Provider Health Console、生产 router 或公开 Status Page；这些仍属于架构 P46 / Epic 8.A / future runtime stories。
- 要求 validator 单独实现 J3 incident contract 校验，不从 `validate_chat_load_plan.py` 继承 Chat-only evidence 模式。

Result: Story 3.12 与 M3.6c、P46、Epic 8.A 的职责边界一致，避免依赖漂移和重复实现。

### Round 3 - Boundary / Edge Cases / Closure (2026-05-28)

Findings applied:

- `example_only=true` manifest 被禁止通过真实 `--evidence` 模式，防止静态示例被当成真实事故证明。
- 示例 manifest 被禁止声明真实公网 status page、subscriber webhook、DingTalk webhook、Credits refund 或公开 Postmortem 完成。
- Redaction 边界覆盖 secret-like keys/values、credentialed URL、tenant/customer identifiers、provider payload、内部 hostname、Windows absolute path 和 traversal。
- Runbook 必须包含 rollback、Postmortem 审稿、action item 和补偿占位，保证 on-call 流程闭环但不伪造实际补偿。

Result: fake completion、隐私泄漏、路径越界、生产能力越界和 operator 流程闭环风险已写入 story。

## Dev Agent Record

### Agent Model Used

GPT-5

### Debug Log References

- 2026-05-28 - Story 3.12 draft created from sprint status, Epics/PRD/Architecture/UX, M3.6c incident fallback assets, J3 runbook context, CI patterns, and Story 3.11 workflow lessons.
- 2026-05-28 - Story review Round 1 completed and applied: data consistency for incident ID, timeline, Status Page status vocabulary, and 24h Postmortem due calculation.
- 2026-05-28 - Story review Round 2 completed and applied: function/dependency consistency for M3.6c hash binding, `tools/incidents/` ownership, and Epic 8.A/P46 boundaries.
- 2026-05-28 - Story review Round 3 completed and applied: boundary closure for fake completion flags, redaction, path safety, rollback, compensation placeholder, and public-production scope.
- 2026-05-28 - Dev implementation started; sprint/story status moved to in-progress.
- 2026-05-28 - RED phase confirmed: J3 incident contract tests failed because validator, assets, runbook, and CI wiring did not exist.
- 2026-05-28 - Implemented J3 static incident contract, schema/example manifest, validator, runbook, CI path filter/job, and 14 regression tests.
- 2026-05-28 - Focused validation passed: validator, pytest, ruff check, ruff format check, and git diff check.
- 2026-05-28 - Full pre-commit validation passed.
- 2026-05-28 - Post-implementation code review completed; patched fake completion claims for real evidence and added nested-field/timeline robustness checks.
- 2026-05-28 - Final validation passed after review fixes: validator, 16 focused tests, ruff, pre-commit, and diff-check.

### Completion Notes List

- Story 3.12 is prepared as a Tier 3 static incident contract/runbook/validator vertical slice, not as production Status Page or Postmortem implementation.
- Three pre-implementation story review rounds were completed and reflected directly in ACs, tasks, Dev Notes, and boundary rules.
- Ready for `bmad-dev-story` implementation as the next workflow step.
- Implemented Story 3.12 as a static J3 incident contract package under `tools/incidents/`, with M3.6c fallback plan hash binding and public-safe Status Page/Postmortem manifest semantics.
- Added an independent validator that checks timeline ordering, 60s Status Page SLA, exact 24h Postmortem due time, status vocabulary, Postmortem sections, future evidence path mode, redaction, path safety, and fake completion flags.
- Added focused CI wiring and tests without requiring providers, DingTalk, status.opticloud.cn, database, external network, or live services.
- Post-implementation code review found and fixed two validator gaps: real evidence can no longer claim out-of-scope production completion, and malformed nested objects/timeline inputs now fail validation instead of crashing or passing silently.

### File List

- `_bmad-output/stories/3-12-j3-sre-incident-tier3.md`
- `_bmad-output/stories/sprint-status.yaml`
- `.github/workflows/ci.yml`
- `docs/runbooks/j3-sre-incident-tier3.md`
- `scripts/validate_j3_incident_contract.py`
- `tests/test_j3_incident_contract.py`
- `tools/incidents/j3_sre_incident.example.json`
- `tools/incidents/j3_sre_incident.schema.json`
- `tools/incidents/j3_sre_incident_contract.json`

### Change Log

- 2026-05-28 - Initial Story 3.12 created and reviewed through three pre-implementation rounds; sprint status moved from backlog to ready-for-dev.
- 2026-05-28 - Dev implementation started; story moved to in-progress.
- 2026-05-28 - Implemented J3 incident static contract package, validator/tests, runbook, and CI wiring; focused validation passed.
- 2026-05-28 - Full pre-commit validation passed.
- 2026-05-28 - Completed post-implementation code review; fixed out-of-scope real evidence completion claims and nested-field/timeline robustness; final validation passed.

## Senior Developer Review (AI) - Post-Implementation (2026-05-28)

### Review Scope

- Uncommitted branch diff for Story 3.12.
- Layers covered: Blind Hunter, Edge Case Hunter, Acceptance Auditor.

### Findings

- [x] [Review][Patch] Real operator evidence could include out-of-scope completion flags such as `status_page_publicly_available`, `subscriber_webhook_sent`, `dingtalk_webhook_called`, `credits_refunded`, or `postmortem_publicly_published` without rejection. Patched validator to reject these flags for all manifests, not only `example_only=true`, and added regression coverage.
- [x] [Review][Patch] Malformed nested structures could cause weak validation or a crash: non-object `timeline` was later accessed with `.get()`, and missing nested fields were not manually checked outside the static schema file. Patched validator to use safe timeline access, validate `incident_id`/`commit_sha`, and reject missing nested fields in fallback reference, provider health, status page, and Postmortem sections.

### Fixes Applied

- Added `test_real_manifest_rejects_out_of_scope_completion_claims`.
- Added `test_manifest_rejects_missing_nested_fields_and_non_object_timeline`.
- Hardened `scripts/validate_j3_incident_contract.py` for fake completion flags, nested required fields, timeline object safety, stable slug format, commit SHA format, and URL scheme redaction.

### Result

Approved after patch. `uv run python scripts/validate_j3_incident_contract.py`, `uv run pytest tests/test_j3_incident_contract.py -q`, `uv run ruff check`, `uv run ruff format --check`, `uv run pre-commit run --all-files --show-diff-on-failure`, and `git diff --check` all passed.
