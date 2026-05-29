# Story 4.A.3: Formulator 提取 Variables / Objective / Constraints

Status: done

owner: Chat Platform / Backend

## Story

作为 Chat Platform 工程师，
我希望在 4.A.2 Router LLM intent 后接入 Formulator LLM 结构化提取，
以便 internal beta 用户的自然语言输入可以得到可审计的 OptiCloud task schema preview，同时继续保持 AIGC 未备案前的 internal-only 边界，并且不提前触发 Coder、Solver、Sandbox、Billing、DB/Redis 或真实 provider 副作用。

## Acceptance Criteria

1. 继续复用 4.A.1/4.A.2 internal beta endpoint 和访问边界。
   - 仍只暴露 `POST /v1/chat/internal-beta/messages`；不得新增公开 `/v1/chat`、SSE、conversation persistence、Formulator public API、Coder、Solver、Sandbox runtime 或 Console Chat UI。
   - disabled、未签发 signoff、tenant/user/token 无效、allowlist 超过 5 人时，仍先于 body/schema 解析返回稀疏 404，不泄露 AIGC、router、formulator、allowlist 或 provider 细节。
   - `GET /health` 保持不变。

2. Formulator 使用 Story M3.8 LLM abstraction，而不是直接实现 provider client。
   - 通过 `opticloud_shared.llm_router.complete(prompt, model=...)` 或等价可注入 wrapper 调用 M3.8 router。
   - 构造 `Prompt(task="formulator_extraction", locale=<detected/request locale>, messages=[system,user], response_schema=<formulator JSON schema>)`。
   - 默认 model alias 为 `deepseek-v3.5`；只允许 M3.8 canonical aliases，未知 alias fail closed。
   - 测试和 CI 必须使用 M3.8 离线 deterministic provider 或注入 completion；不得读取或要求 API key，不得发外部网络请求。
   - 必须复用 4.A.2 已加入的 `opticloud-shared` workspace dependency；不得新增 DeepSeek/Qwen SDK、HTTP client、LangChain、OpenAI SDK 或 provider-specific package。
   - Formulator module 可以从 `chat_service.llm_intent` 复用 `CompletionFunc`、canonical alias 校验模式和安全 reasoning/secret guardrail 思路，但不得把 Router parser 与 Formulator parser 混成一个多任务函数。

3. 成功响应新增 `formulator_preview`，并保持 4.A.2 response contract 兼容。
   - 响应继续包含 `router_preview`、`aigc_gate`、`llm_invoked`、`provider_request_sent=false`、`solver_invoked=false`、`sandbox_invoked=false`。
   - 新增 `formulator_preview`，字段为 `status`、`source`、`task_type`、`confidence`、`variables`、`objective`、`constraints`、`validation_errors`、`supported_task_types`。
   - `status` 允许 `extracted`、`needs_clarification`、`skipped`；`source` 允许 `llm_formulator_internal_beta` 或 `heuristic_formulator_internal_beta`。
   - `task_type` 必须等于 `router_preview.task_type`，除非 router 为 `unknown` 时 Formulator 必须 `status="skipped"`、`task_type="unknown"`。
   - `confidence` 必须在 0.0 到 1.0；`variables`、`objective`、`constraints` 必须是结构化 JSON，不得是整段自然语言回显。
   - `validation_errors` 必须是 list，元素字段固定为 `field_path`、`message`，可选 `remediation_hint_key`；不得返回 exception repr、stack trace、prompt、raw completion 或 provider details。
   - `supported_task_types` 顺序必须与 `router_preview.supported_task_types` 一致：`lp`、`vrptw`、`prediction`、`schedule`、`inventory`、`unknown`。

4. Formulator 输出必须映射到 OptiCloud task schema preview，且不伪造无法从输入中提取的数据。
   - `lp` 输出对齐 `solver_orchestrator.schemas.OptimizationRequest` 的 LP 结构：`task_type="lp"`、`objective.sense in {"minimize","maximize"}`、`objective.coefficients`、`constraints.linear`、可选 `bounds`。
   - `vrptw` 输出对齐现有 Excel VRPTW payload：`customers`、`vehicles`、可选 `time_windows`、`objective.kind="minimize_total_distance"`。
   - `schedule` 输出对齐现有 Excel Schedule payload：`tasks`、`resources`、`precedences`、`objective.kind="minimize_makespan"` 或 `satisfy_constraints`。
   - `inventory`/`prediction` 输出对齐现有 inventory/prediction preview：`series`、`horizon`、可选 `skus`、`history`、`seasonality`；`prediction` 归一到 `task_type="prediction"`，不调用 `/v1/predictions`。
   - 缺少关键字段时返回 `status="needs_clarification"` 和 field-level `validation_errors`，不得填充假客户、假车辆、假 SKU、假系数或假约束。
   - Chat-service 不得 import `solver_orchestrator` 或 `apps/web` 代码；LP、VRPTW、Schedule、Inventory schema 在 chat-service 内以 preview models 表达，来源只在 story 和 tests 中对齐。
   - `unknown`、空信息、纯闲聊、prompt injection 或模型输出只包含泛化词时，必须 `skipped` 或 `needs_clarification`；不得升级为具体 task schema。
   - 所有 list 型结构必须有合理上限：variables ≤ 50，constraints 顶层键 ≤ 20，validation_errors ≤ 10，单个错误 message ≤ 160 chars，防止 LLM 输出撑爆 response。

5. Completion 解析必须结构化、可审计、可降级。
   - 优先解析 JSON object：`task_type`、`confidence`、`variables`、`objective`、`constraints`、可选 `validation_errors`。
   - 兼容 M3.8 deterministic text envelope 中的 `formulator extraction variables constraints objective ...`，但仅允许形成低信息量的 `needs_clarification` preview，不得伪造完整模型。
   - 如果 completion 缺字段、非法 task_type、confidence 越界、被 content filter、router error、prompt validation error、secret-like 输出或与 Router task_type 冲突，则 fail closed 到 heuristic/clarification preview，而不是返回 500 或错误模型。
   - `llm_invoked` 表示本请求是否至少实际调用过一次 M3.8 `complete(...)`；如果 Router 或 Formulator 任一阶段调用到 `complete(...)` 即为 `true`，若两个阶段都在 pre-call 校验前 fail closed 则为 `false`。
   - Formulator 阶段需要单独返回内部 `formulator_invoked` 给 endpoint 聚合，但该字段不暴露到 response body；外部只看聚合后的 `llm_invoked`。
   - `provider_request_sent` 在本 story 所有成功响应中固定为 `false`；不得新增 provider/model/raw_response/raw_prompt 字段到 response body。
   - 对 `finish_reason in {"length","content_filter","error"}` 必须返回 fallback preview；不得部分采信截断输出。
   - 对 prompt injection markers（如 `ignore previous`、`system:`、`DAN`、`</s>`、`# system`）不需要阻断请求，但 Formulator prompt 必须保持 user role 隔离，输出不得采信任何要求泄露系统提示或改写 schema 的内容。

6. 无业务副作用边界清晰。
   - 成功响应只生成 preview，不提交 Optimization/Prediction，不创建 conversation，不触发 Coder，不运行 Solver/Sandbox，不计费。
   - 不创建 DB table、migration、Redis stream、outbox event、billing charge、optimization task、prediction task、sandbox execution、provider request、audit payload 或 cost telemetry event。
   - 不调用 Critic、AIGC filter/watermark module；用户可见 NL 输出过滤留给 4.B/8.B，当前仅返回结构化 JSON preview。
   - 不新增 frontend changes。

7. Regression 与 M3.8 合同闭环。
   - 4.A.1/4.A.2 focused tests 继续通过，并新增 4.A.3 tests 覆盖 Formulator prompt、JSON parser、deterministic text fallback、router unknown skip、task_type conflict fallback、prompt validation failure、router/formulator combined invocation semantics、unauthorized-before-body-validation。
   - Adjacent M3.8 validation 继续通过：`uv run python scripts/validate_llm_router_contract.py` 和 `uv run pytest tests/llm_router/test_implementations_parity.py -q`。
   - Static closure：`uv run pytest apps/chat-service/tests -q`、`uv run mypy apps packages`、`uv tool run pre-commit run --all-files --show-diff-on-failure`、`git diff --check`。
   - CI `chat-service-test` must continue to trigger when `packages/shared-py/opticloud_shared/llm_router/**`, `packages/shared-py/opticloud_shared/__init__.py`, or `packages/shared-py/pyproject.toml` changes.

## Tasks / Subtasks

- [x] Task 1: Add Formulator schema and pure extraction module. (AC: 2-5, 7)
  - [x] Add `FormulatorPreview`, `FormulatorObjective`, `FormulatorValidationError` and related typed models to `apps/chat-service/src/chat_service/schemas.py`.
  - [x] Add `apps/chat-service/src/chat_service/formulator.py` with `build_formulator_prompt(...)`, `parse_formulator_completion(...)`, and `extract_formulation_with_llm(...)`.
  - [x] Keep completion wrapper injectable so tests can simulate JSON, deterministic text, malformed output, content-filter finish reason and router errors without network.
  - [x] Reuse `SUPPORTED_TASK_TYPES` and 4.A.2 `RouterPreview`; do not duplicate task type lists.
  - [x] Do not add new dependencies; use stdlib + Pydantic + existing `opticloud-shared`.
- [x] Task 2: Wire Formulator into internal beta endpoint after Router. (AC: 1, 3, 5, 6)
  - [x] Preserve internal beta access gate before body parsing.
  - [x] Call Formulator only after request validation and Router result exist.
  - [x] Skip extraction when `router_preview.task_type == "unknown"` and return `formulator_preview.status="skipped"`.
  - [x] Aggregate LLM invocation semantics across Router and Formulator while keeping `provider_request_sent=false`.
- [x] Task 3: Implement schema validation and safe fallback behavior. (AC: 4-6)
  - [x] Reject Formulator task_type that conflicts with Router task_type.
  - [x] Return `needs_clarification` with field-level validation errors for missing critical fields.
  - [x] Strip or reject raw message echo, secret-like text, provider raw payloads and deterministic digests from preview fields.
  - [x] Ensure preview is JSON-serializable and uses `extra="forbid"` Pydantic models.
- [x] Task 4: Add RED tests and validation evidence. (AC: 1-7)
  - [x] Add failing tests before implementation for LP JSON extraction and endpoint `formulator_preview`.
  - [x] Add parser/fallback/conflict/unknown/prompt-safety/unauthorized regression tests.
  - [x] Run focused, adjacent, static, pre-commit and diff-check validation commands.
  - [x] Update Dev Agent Record, File List and Change Log.

### Review Follow-ups (AI)

- [x] [Review][Patch] Reject nested oversized Formulator payloads and validation-error original-message echoes instead of accepting them into preview.

## Dev Notes

### Source Context

- `_bmad-output/planning/epics.md:398` defines Epic 4.A goal: NL Chat Router & Formulator for Router LLM classification, Formulator extraction and Coder generation.
- `_bmad-output/planning/epics.md:1520` defines Story 4.A.3: Formulator 提取 variables/objective/constraints (N3).
- `_bmad-output/planning/epics.md:1522` requires: Given Router output / When Formulator LLM extracts / Then output structured OptiCloud task schema.
- `_bmad-output/planning/prd.md:1488` defines FR N3 as v1 required: Formulator can extract variables/objective/constraints.
- `_bmad-output/planning/prd.md:1012` defines the pipeline order: Router LLM -> Formulator -> Planner/Coder -> sandbox -> Critic.
- `_bmad-output/planning/architecture.md:120` requires test environment LLM mock abstraction; CI must not call paid APIs.
- `_bmad-output/planning/architecture.md:2940` through `2942` keeps M3 prompts inside `apps/chat-service/prompts/` or code constants until later prompt-store.
- `_bmad-output/planning/architecture.md:2990` through `2999` requires prompt injection defense: user input stays out of system role, role tagging, pre-LLM filtering and no secret leakage.
- Story 4.A.2 established M3.8 `opticloud_shared.llm_router` consumption, prompt validation fallback, guarded parser, source semantics, response side-effect fields and CI path filter.

### Current Repository Reality

- `apps/chat-service/src/chat_service/main.py` owns the only Chat endpoint: `POST /v1/chat/internal-beta/messages`.
- `main.py` currently validates internal beta access before `ChatInternalBetaMessageRequest.model_validate(...)`; this must not regress.
- `apps/chat-service/src/chat_service/llm_intent.py` already wraps M3.8 `complete(...)` for `router_intent`, with canonical alias validation, prompt-construction fallback and conflict guardrails.
- `apps/chat-service/src/chat_service/router_preview.py` owns `SUPPORTED_TASK_TYPES`, locale detection, message excerpts and fallback classifier.
- `apps/chat-service/src/chat_service/schemas.py` currently defines `ChatInternalBetaMessageResponse` without `formulator_preview`; extend it minimally.
- `packages/shared-py/opticloud_shared/llm_router/providers.py` deterministic `formulator_extraction` text is not JSON and contains digest/provider fixture terms. 4.A.3 must parse it only as evidence of invocation and fallback to `needs_clarification`.
- `apps/solver-orchestrator/src/solver_orchestrator/schemas.py` defines LP `OptimizationRequest` shape. Do not import solver-orchestrator runtime into chat-service; copy only the minimum preview contract in chat schemas to avoid cross-service dependency.
- `apps/web/src/lib/vrptw-template.ts`, `schedule-template.ts`, and `inventory-template.ts` define current JSON payload shapes for non-LP previews; use these as shape references.

### Implementation Guidance

- Add `formulator.py` with pure functions:
  - `build_formulator_prompt(message, locale, prompt_id, router_preview) -> Prompt`
  - `parse_formulator_completion(text, router_preview, original_message=None) -> FormulatorPreview | None`
  - `extract_formulation_with_llm(message, locale, prompt_id, router_preview, completion_func=complete, model_alias="deepseek-v3.5") -> FormulatorRouteResult`
- Use `Prompt.response_schema` with only safe generic JSON-schema keys (`type`, `properties`, `required`, `enum`, `items`, `minimum`, `maximum`). Avoid blocked keys such as token, api_key, raw payload keys or full prompt/customer prompt labels.
- Keep user NL input only in the M3.8 `PromptMessage(role="user")`. Do not place the full input in metadata, response fields, logs or reasoning.
- For deterministic text from M3.8 offline provider, return `needs_clarification` with safe validation errors such as `variables: structured variables missing from deterministic completion`.
- Suggested response preview:

```json
{
  "status": "needs_clarification",
  "source": "heuristic_formulator_internal_beta",
  "task_type": "vrptw",
  "confidence": 0.4,
  "variables": {},
  "objective": {"kind": "minimize_total_distance"},
  "constraints": {},
  "validation_errors": [
    {"field_path": "customers", "message": "customer locations are required"}
  ],
  "supported_task_types": ["lp", "vrptw", "prediction", "schedule", "inventory", "unknown"]
}
```

- For a well-formed LP JSON completion, accept output only when it includes non-empty variables and either objective or constraints. Missing LP coefficients should become `needs_clarification`, not fabricated zeros.
- Do not add model alias env config unless strictly needed; keep default deterministic/offline-safe.

### Boundary Rules

- No public Chat route.
- No SSE.
- No real provider request or API key use.
- No Coder generation.
- No Planner.
- No Critic validation.
- No Solver/Sandbox invocation.
- No DB/Redis/outbox/billing/cost telemetry writes.
- No AIGC filter/watermark runtime call.
- No frontend changes.

### Story Review Rounds

### Round 1 - Data Consistency (2026-05-29)

Findings applied:

- Pinned `validation_errors` as a stable list of `{field_path, message, remediation_hint_key?}` rather than arbitrary strings, preventing response drift and leaked exceptions.
- Pinned `supported_task_types` order to match `router_preview.supported_task_types`, preventing Router/Formulator schema mismatch in tests and clients.
- Clarified aggregate `llm_invoked` semantics across Router and Formulator, and required an internal-only `formulator_invoked` flag so endpoint aggregation is testable without exposing another public response field.

Result: response data shape, invocation state and preview consistency are explicit before implementation.

Pending rounds:

### Round 2 - Function / Dependency Consistency and Drift (2026-05-29)

Findings applied:

- Required reuse of the existing 4.A.2 `opticloud-shared` dependency and M3.8 abstraction; explicitly banned adding provider SDKs or a new HTTP client path in chat-service.
- Clarified function ownership: Router parser remains in `llm_intent.py`; Formulator parser lives in `formulator.py`; shared patterns are allowed, but a multi-purpose parser would create hidden task drift.
- Prohibited runtime imports from `solver_orchestrator` and `apps/web`; their schemas are source references only. Chat-service owns its preview Pydantic models to keep service dependency boundaries clean.
- Confirmed CI path-filter coverage from 4.A.2 is still required for shared LLM router drift.

Result: 4.A.3 remains a chat-service preview layer over M3.8, without cross-service runtime coupling or duplicate provider infrastructure.

### Round 3 - Boundary / Edge Cases / Closure (2026-05-29)

Findings applied:

- Added unknown/prompt-injection boundary: Formulator cannot promote unknown or generic text into a concrete schema, and prompt-injection markers must stay isolated in user role.
- Added response size limits for variables, constraints and validation errors so malformed LLM output cannot produce oversized previews.
- Required non-stop finish reasons (`length`, `content_filter`, `error`) to fallback instead of partially accepting truncated or filtered output.
- Reconfirmed no Coder/Solver/Sandbox/Billing/DB/Redis/AIGC runtime side effects, and closure requires focused chat tests, adjacent M3.8 validators, mypy, pre-commit and diff-check.

Result: edge cases, prompt-safety, response-size limits and validation closure are explicit before implementation.

### Test / Validation Notes

Expected commands:

```bash
uv run pytest apps/chat-service/tests -q
uv run python scripts/validate_llm_router_contract.py
uv run pytest tests/llm_router/test_implementations_parity.py -q
uv run mypy apps packages
uv tool run pre-commit run --all-files --show-diff-on-failure
git diff --check
```

RED expectation for implementation: add tests for 4.A.3 Formulator first, then confirm `uv run pytest apps/chat-service/tests -q` fails before wiring the implementation.

## Dev Agent Record

### Agent Model Used

GPT-5

### Debug Log References

- 2026-05-29 - Story 4.A.3 draft created after Story 4.A.2 merged in PR #94 and sprint status showed `4-a-3-formulator-extract: backlog`.
- 2026-05-29 - Story moved to in-progress after three story review rounds; starting RED tests for 4.A.3 Formulator extraction.
- 2026-05-29 - RED focused test failed before implementation: `uv run pytest apps/chat-service/tests -q` failed with `ModuleNotFoundError: No module named 'chat_service.formulator'`.
- 2026-05-29 - Implemented `formulator.py`, Formulator prompt construction, JSON/deterministic completion parsing, safe clarification fallback, schema extension and endpoint wiring.
- 2026-05-29 - Focused validation passed: `uv run pytest apps/chat-service/tests -q` -> 45 passed.
- 2026-05-29 - Adjacent M3.8 validation passed: `uv run python scripts/validate_llm_router_contract.py` -> `llm router contract OK`; `uv run pytest tests/llm_router/test_implementations_parity.py -q` -> 14 passed.
- 2026-05-29 - Static validation passed: `uv run mypy apps packages`, `uv tool run pre-commit run --all-files --show-diff-on-failure`, and `git diff --check`.
- 2026-05-29 - Post-implementation code review found and fixed one nested payload boundary issue: oversized nested Formulator JSON arrays and validation-error original-message echoes now fail closed.
- 2026-05-29 - Post-review full validation passed: `uv run pytest apps/chat-service/tests -q` -> 47 passed; M3.8 adjacent validators passed; mypy, pre-commit and diff-check passed.

### Implementation Plan

- Reuse 4.A.2 internal beta endpoint and guarded Router result.
- Add Formulator preview models in chat-service only; do not import solver/web runtime modules.
- Add M3.8 `formulator_extraction` prompt wrapper with injectable completion and strict parser.
- Return JSON-safe `formulator_preview` with `extracted`, `needs_clarification`, or `skipped` status.
- Preserve no-side-effect boundary and aggregate `llm_invoked` across Router/Formulator.

### Completion Notes List

- Story drafted from Epic 4.A, PRD N3, Architecture P68/P70, Story 4.A.2 completion learnings, current chat-service code, solver LP schema and Excel template payload contracts.
- Dev implementation started with RED tests and completed through focused, adjacent, static, pre-commit and diff-check validation.
- Added Formulator extraction preview after Router classification for internal beta messages.
- Well-formed LP JSON completions can produce `status="extracted"` preview; deterministic M3.8 fixture text and incomplete outputs safely produce `needs_clarification`.
- Unknown router task_type skips Formulator invocation and returns `status="skipped"`.
- Endpoint still does not create conversations, call Coder/Solver/Sandbox/Billing/DB/Redis/provider, or expose provider/raw fields.
- Post-review parser hardening rejects nested payloads over configured list/dict limits and rejects validation errors that echo the original message.

### File List

- `_bmad-output/stories/4-a-3-formulator-extract.md`
- `_bmad-output/stories/sprint-status.yaml`
- `apps/chat-service/src/chat_service/formulator.py`
- `apps/chat-service/src/chat_service/main.py`
- `apps/chat-service/src/chat_service/schemas.py`
- `apps/chat-service/tests/test_formulator.py`
- `apps/chat-service/tests/test_internal_beta.py`

### Change Log

- 2026-05-29 - Initial Story 4.A.3 created from Epic 4.A, M3.8 LLM router contract, Architecture prompt-safety constraints, Story 4.A.2 learnings and current OptiCloud task schema references.
- 2026-05-29 - Completed three story review rounds and moved story to in-progress for implementation.
- 2026-05-29 - Implemented Formulator extraction preview for internal beta endpoint; status moved to code-review after validation passed.
- 2026-05-29 - Addressed code review nested-payload and validation-error echo finding.
- 2026-05-29 - Post-review validation passed; story marked done.

### Senior Developer Review (AI)

Review date: 2026-05-29

Outcome: Approve after fixes.

Review layers executed locally: blind diff review, edge-case boundary review, acceptance audit against Story 4.A.3.

Findings:

- [x] Patch - Formulator parser capped only top-level `variables` and `constraints` keys. A completion with one top-level key containing a very large nested list could bypass the response-size guardrail, and validation error messages were not checked for original-message echo. Fixed by adding recursive nested dict/list limits, checking `remediation_hint_key` and validation error text for unsafe content/original-message echo, and adding regression tests.

Validation after review fix:

- `uv run pytest apps/chat-service/tests/test_formulator.py -q` -> 13 passed.
- `uv run ruff check apps/chat-service/src/chat_service/formulator.py apps/chat-service/tests/test_formulator.py` -> passed.
- `uv run mypy apps/chat-service apps/solver-orchestrator packages/shared-py` -> success.

Final validation:

- `uv run pytest apps/chat-service/tests -q` -> 47 passed.
- `uv run python scripts/validate_llm_router_contract.py` -> `llm router contract OK`.
- `uv run pytest tests/llm_router/test_implementations_parity.py -q` -> 14 passed.
- `uv run mypy apps packages` -> success, no issues found in 99 source files.
- `uv tool run pre-commit run --all-files --show-diff-on-failure` -> passed.
- `git diff --check` -> passed.
