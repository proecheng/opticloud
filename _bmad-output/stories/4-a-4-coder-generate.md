# Story 4.A.4: Coder 生成可执行代码 (N4)

Status: done

owner: Chat Platform / Backend

## Story

作为 Chat Platform 工程师，
我希望在 4.A.3 Formulator preview 后接入 Coder LLM 代码生成预览，
以便 internal beta 用户的自然语言建模链路可以产出可审计的 Python 代码 artifact，并通过 Pydantic/AST 验证其结构，同时继续保持 AIGC 未备案前的 internal-only 边界，并且不提前触发 Critic、Sandbox、Solver、Billing、DB/Redis 或真实 provider 副作用。

## Acceptance Criteria

1. 继续复用 4.A.1-4.A.3 internal beta endpoint 和访问边界。
   - 仍只暴露 `POST /v1/chat/internal-beta/messages`；不得新增公开 `/v1/chat`、SSE、conversation persistence、Coder public API、Critic、Sandbox runtime、Solver submission 或 Console Chat UI。
   - disabled、未签发 signoff、tenant/user/token 无效、allowlist 超过 5 人时，仍先于 body/schema 解析返回稀疏 404，不泄露 AIGC、router、formulator、coder、allowlist 或 provider 细节。
   - `GET /health` 保持不变。

2. Coder 使用 Story M3.8 LLM abstraction，而不是直接实现 provider client。
   - 通过 `opticloud_shared.llm_router.complete(prompt, model=...)` 或等价可注入 wrapper 调用 M3.8 router。
   - 构造 `Prompt(task="coder_generation", locale=<detected/request locale>, messages=[system,user], response_schema=<coder JSON schema>)`。
   - `Prompt.metadata` 只能包含不敏感的小字段，例如 `formulator_task_type`；不得放完整用户 message、完整 Formulator payload、prompt text、raw completion 或 provider payload。
   - 默认 model alias 为 `deepseek-v3.5`；只允许 M3.8 canonical aliases，未知 alias fail closed。
   - 测试和 CI 必须使用 M3.8 离线 deterministic provider 或注入 completion；不得读取或要求 API key，不得发外部网络请求。
   - 必须复用已有 `opticloud-shared` workspace dependency；不得新增 DeepSeek/Qwen SDK、HTTP client、LangChain、OpenAI SDK、代码执行库或 provider-specific package。
   - Coder module 可以复用 4.A.2/4.A.3 的 injectable completion、canonical alias 校验、safe fallback 思路，但不得把 Router/Formulator/Coder parser 混成一个多任务函数。

3. 成功响应新增 `coder_preview`，并保持 4.A.3 response contract 兼容。
   - 响应继续包含 `router_preview`、`formulator_preview`、`aigc_gate`、`llm_invoked`、`provider_request_sent=false`、`solver_invoked=false`、`sandbox_invoked=false`。
   - 新增 `coder_preview`，字段固定为 `status`、`source`、`task_type`、`artifact`、`validation_errors`、`supported_task_types`；不得暴露 Coder LLM 的 provider/model/raw/usage/confidence 字段，避免与 4.B Critic confidence 混淆。
   - `status` 允许 `generated`、`needs_clarification`、`skipped`。
   - `source` 允许 `llm_coder_internal_beta`、`template_coder_internal_beta` 或 `heuristic_coder_internal_beta`。
   - `task_type` 必须等于 `formulator_preview.task_type`；当 Formulator 为 `skipped` 或 task 为 `unknown` 时 Coder 必须 `status="skipped"`、`artifact=null`。
   - 当 `formulator_preview.status="needs_clarification"` 时 Coder 必须 `status="needs_clarification"`、`artifact=null`，并将至少一条 `validation_errors` 指向 `formulator_preview.<field>` 或对应缺失字段。
   - `artifact` 为 `null` 或固定 shape：`language="python"`、`code`、`entrypoint`、`input_model`、`output_model`、`imports`。
   - `status="generated"` 时 `artifact` 必须非空；`status in {"needs_clarification","skipped"}` 时 `artifact` 必须为 `null`。
   - `code` 必须是纯 Python 源码字符串，不得含 Markdown fences、prompt、raw completion、provider details、stack trace、API key 或原始用户全文回显。
   - `entrypoint`、`input_model`、`output_model` 必须是合法 Python identifier，并且必须在 `code` AST 中存在对应函数/类定义。
   - `imports` 必须与 AST import 节点一致，且只能包含允许模块：`pydantic`、`typing`、`math`、`statistics`、`datetime`、`json`、`decimal`。
   - `input_model` 和 `output_model` 类必须继承 `pydantic.BaseModel` 或 `BaseModel`；entrypoint 函数必须有参数和 return annotation，且不得是 async/generator。
   - `code` 长度上限为 8,000 chars；`imports` 最多 12 个 top-level module；`validation_errors` 最多 10 条；单个 `field_path` 最多 128 chars，单个 `message` 最多 160 chars，单个 `remediation_hint_key` 最多 128 chars。
   - `validation_errors` 必须是 list，元素字段固定为 `field_path`、`message`，可选 `remediation_hint_key`；不得返回 exception repr、stack trace、prompt、raw completion 或 provider details。
   - `supported_task_types` 顺序必须与 `router_preview.supported_task_types` 和 `formulator_preview.supported_task_types` 一致：`lp`、`vrptw`、`prediction`、`schedule`、`inventory`、`unknown`。

4. Coder 只基于 Formulator preview 生成可执行 Python artifact preview，不伪造模型输入。
   - 只有 `formulator_preview.status == "extracted"` 时才允许 `coder_preview.status="generated"`。
   - `needs_clarification` Formulator 输出必须让 Coder 返回 `needs_clarification`，并指向缺失字段；不得调用 Coder LLM，也不得用代码模板掩盖缺失 variables/objective/constraints。
   - `unknown`、空信息、纯闲聊、prompt injection 或模型输出只包含泛化词时，必须 `skipped` 或 `needs_clarification`；不得调用 Coder LLM，不得生成具体 Python 代码。
   - `lp` artifact 应生成一个包含 Pydantic input/output model 与 `entrypoint` 函数的 Python 源码，可表达 `objective`、`constraints` 与变量名，但不得调用求解器或提交 `/v1/optimizations`。
   - 当 extracted payload 缺少 Coder 生成必需字段，例如 LP 缺少 decision variables 或 objective/constraints 为空，Coder 必须返回 `needs_clarification`，不得生成空壳 artifact。
   - `vrptw`、`schedule`、`inventory`、`prediction` artifact 可以是 schema-normalization / payload-builder 代码 preview；不得调用 OR-Tools、HiGHS、Chronos、TimesFM、外部 API 或本地文件系统。
   - 生成代码可以 import `pydantic` 与 `typing` 等允许模块，但不得 import `requests`、`httpx`、`socket`、`subprocess`、`os`、`sys`、`pathlib`、`shutil`、`importlib`、`builtins` 或任何 solver/sandbox/provider module。
   - 禁止危险调用或动态执行节点：`eval`、`exec`、`compile`、`open`、`__import__`、`getattr`、`setattr`、`delattr`、`globals`、`locals`、`vars`、`input`，以及任何 dunder attribute 访问。
   - Coder 不执行生成代码；只用 Pydantic models 和 `ast.parse` 做结构验证。

5. Completion 解析必须结构化、可审计、可降级。
   - 优先解析 JSON object：`task_type`、`artifact`、可选 `validation_errors`。若 completion 额外包含 `confidence`，必须为 0.0 到 1.0 的 number 才能继续解析，但该字段不得暴露到 response。
   - `artifact` 必须通过 Pydantic schema 与 AST safety validator；任一失败则返回 `needs_clarification` 或 safe fallback preview，不得返回 500。
   - 兼容 M3.8 deterministic text envelope 中的 `coder generation python function validation ...`。当 Formulator 已 `extracted` 且 deterministic text 只证明 Coder 被调用时，允许生成 `template_coder_internal_beta` artifact；当 Formulator 未 `extracted` 时 Coder LLM 不应被调用，只能 `needs_clarification` 或 `skipped`。
   - 如果 completion 缺字段、非法 task_type、confidence 越界、被 content filter、router error、prompt validation error、secret-like 输出、代码 AST 不合法、危险 import/call、artifact task_type 与 Formulator 冲突，则 fail closed 到 safe preview，而不是返回 500 或错误代码。
   - `llm_invoked` 表示本请求是否至少实际调用过一次 M3.8 `complete(...)`；Router、Formulator 或 Coder 任一阶段调用到 `complete(...)` 即为 `true`，若三个阶段都在 pre-call 校验前 fail closed 则为 `false`。
   - Coder 阶段需要单独返回内部 `coder_invoked` 给 endpoint 聚合，但该字段不暴露到 response body；外部只看聚合后的 `llm_invoked`。
   - `provider_request_sent` 在本 story 所有成功响应中固定为 `false`；不得新增 provider/model/raw_response/raw_prompt 字段到 response body。
   - 对 `finish_reason in {"length","content_filter","error"}` 必须返回 fallback preview；不得部分采信截断输出。
   - 对 prompt injection markers（如 `ignore previous`、`system:`、`DAN`、`</s>`、`# system`）不需要阻断请求，但 Coder prompt 必须保持 user role 隔离，输出不得采信任何要求泄露系统提示、执行网络调用或改写 schema 的内容。

6. 无业务副作用边界清晰。
   - 成功响应只生成 preview，不提交 Optimization/Prediction，不创建 conversation，不运行 Coder artifact，不调用 Critic，不运行 Solver/Sandbox，不计费。
   - 不创建 DB table、migration、Redis stream、outbox event、billing charge、optimization task、prediction task、sandbox execution、provider request、audit payload 或 cost telemetry event。
   - 不调用 AIGC filter/watermark module；用户可见 NL 输出过滤留给 4.B/8.B，当前仅返回结构化 JSON preview。
   - 不新增 frontend changes。

7. Regression 与 M3.8 合同闭环。
   - 4.A.1-4.A.3 focused tests 继续通过，并新增 4.A.4 tests 覆盖 Coder prompt、JSON parser、deterministic text template fallback、Formulator skipped/needs-clarification gating、task_type conflict fallback、dangerous import/call rejection、prompt validation failure、Router/Formulator/Coder combined invocation semantics、unauthorized-before-body-validation。
   - Adjacent M3.8 validation 继续通过：`uv run python scripts/validate_llm_router_contract.py` 和 `uv run pytest tests/llm_router/test_implementations_parity.py -q`。
   - Static closure：`uv run pytest apps/chat-service/tests -q`、`uv run mypy apps packages`、`uv tool run pre-commit run --all-files --show-diff-on-failure`、`git diff --check`。
   - CI `chat-service-test` must continue to trigger when `packages/shared-py/opticloud_shared/llm_router/**`, `packages/shared-py/opticloud_shared/__init__.py`, or `packages/shared-py/pyproject.toml` changes.

## Tasks / Subtasks

- [x] Task 1: Add Coder schema and pure generation module. (AC: 2-5, 7)
  - [x] Add `CoderPreview`, `CoderCodeArtifact`, `CoderValidationError` and related literals to `apps/chat-service/src/chat_service/schemas.py`.
  - [x] Add `apps/chat-service/src/chat_service/coder.py` with `build_coder_prompt(...)`, `parse_coder_completion(...)`, `generate_code_with_llm(...)`, and pure AST/Pydantic validation helpers.
  - [x] Keep completion wrapper injectable so tests can simulate JSON, deterministic text, malformed output, content-filter finish reason, unsafe imports and router errors without network.
  - [x] Reuse `SUPPORTED_TASK_TYPES`, `TaskType`, `FormulatorPreview` and 4.A.3 patterns; do not duplicate task type lists.
  - [x] Do not add new dependencies; use stdlib `ast` + Pydantic + existing `opticloud-shared`.
- [x] Task 2: Wire Coder into internal beta endpoint after Formulator. (AC: 1, 3, 5, 6)
  - [x] Preserve internal beta access gate before body parsing.
  - [x] Call Coder only after request validation, Router result and Formulator preview exist.
  - [x] Skip or require clarification when `formulator_preview.status != "extracted"` or task is `unknown`.
  - [x] Aggregate LLM invocation semantics across Router, Formulator and Coder while keeping `provider_request_sent=false`.
- [x] Task 3: Implement code artifact validation and safe fallback behavior. (AC: 3-6)
  - [x] Reject Coder task_type that conflicts with Formulator task_type.
  - [x] Reject Markdown-fenced code, raw user message echo, secret-like text, provider raw payloads, deterministic digests and oversized artifacts.
  - [x] Validate code with `ast.parse`, required entrypoint function, required Pydantic input/output classes, allowed imports and dangerous call blacklist.
  - [x] Ensure preview is JSON-serializable and uses `extra="forbid"` Pydantic models.
- [x] Task 4: Add RED tests and validation evidence. (AC: 1-7)
  - [x] Add failing tests before implementation for well-formed LP JSON code artifact and endpoint `coder_preview`.
  - [x] Add parser/fallback/conflict/skipped/prompt-safety/unsafe-code/unauthorized regression tests.
  - [x] Run focused, adjacent, static, pre-commit and diff-check validation commands.
  - [x] Update Dev Agent Record, File List and Change Log.

### Review Findings

- [x] [Review][Patch] Coder completion `validation_errors` must be parsed and sanitized before accepting an artifact [`apps/chat-service/src/chat_service/coder.py`] — Fixed by coercing reported validation errors through bounded `CoderValidationError` models, rejecting unsafe raw/provider/secret-like text at the completion-payload level, returning `needs_clarification` for sanitized reported errors, and adding regression coverage.
- [x] [Review][Patch] Coder AST guard should reject blocked runtime symbol calls even when the code omits imports [`apps/chat-service/src/chat_service/coder.py`] — Fixed by detecting blocked runtime symbol roots such as `requests`, `socket`, `subprocess`, `pathlib`, `importlib`, `builtins`, and solver/provider-adjacent symbols in attribute-call expressions, with sanitized regression coverage.

## Dev Notes

### Source Context

- `_bmad-output/planning/epics.md:398` defines Epic 4.A goal: NL Chat with Router LLM classification, Formulator extraction and Coder code generation.
- `_bmad-output/planning/epics.md:1524` defines Story 4.A.4: Coder 生成可执行代码 (N4).
- `_bmad-output/planning/epics.md:1526` requires: Given Formulator 输出 / When Coder LLM 调用 / Then 输出 Python 代码 + Pydantic 验证.
- `_bmad-output/planning/prd.md:1489` defines FR N4 as v1 required: Coder can generate executable code.
- `_bmad-output/planning/prd.md:1012` defines pipeline order: Router LLM -> Formulator -> Planner/Coder -> sandbox -> Critic.
- `_bmad-output/planning/epics.md:1540` and `1544` place Critic validation and Sandbox execution in 4.B.1/4.B.2, after 4.A.4.
- `_bmad-output/planning/epics.md:1573` places Preview + confirm/edit/cancel UX in 4.C.1, after 4.A/4.B.
- `_bmad-output/planning/architecture.md:120` requires test environment LLM mock abstraction; CI must not call paid APIs.
- `_bmad-output/planning/architecture.md:2940` through `2942` keeps M3 prompts inside `apps/chat-service/prompts/` or code constants until later prompt-store.
- `_bmad-output/planning/architecture.md:2990` through `2999` requires prompt injection defense: user input stays out of system role, role tagging, pre-LLM filtering and no secret leakage.
- Story 4.A.3 established Formulator preview response shape, deterministic LLM fallback behavior, no Coder/Solver/Sandbox boundary, focused chat-service tests and validation commands.

### Current Repository Reality

- `apps/chat-service/src/chat_service/main.py` owns the only Chat endpoint: `POST /v1/chat/internal-beta/messages`.
- `main.py` currently validates internal beta access before `ChatInternalBetaMessageRequest.model_validate(...)`; this must not regress.
- `apps/chat-service/src/chat_service/llm_intent.py` wraps M3.8 `complete(...)` for `router_intent`, with canonical alias validation, prompt-construction fallback and conflict guardrails.
- `apps/chat-service/src/chat_service/formulator.py` wraps M3.8 `complete(...)` for `formulator_extraction`, returns `FormulatorRouteResult`, and skips when router task is `unknown`.
- `apps/chat-service/src/chat_service/router_preview.py` owns `SUPPORTED_TASK_TYPES`, locale detection, message excerpts and fallback classifier.
- `apps/chat-service/src/chat_service/schemas.py` currently defines `ChatInternalBetaMessageResponse` with `formulator_preview`; extend it minimally with `coder_preview`.
- `packages/shared-py/opticloud_shared/llm_router/providers.py` deterministic `coder_generation` text is not JSON code. 4.A.4 must parse it only as invocation evidence and, only for extracted Formulator data, produce a safe template artifact.

### Implementation Guidance

- Add `coder.py` with pure functions:
  - `build_coder_prompt(message, locale, prompt_id, formulator_preview) -> Prompt`
  - `parse_coder_completion(text, formulator_preview, original_message=None) -> CoderPreview | None`
  - `generate_code_with_llm(message, locale, prompt_id, formulator_preview, completion_func=complete, model_alias="deepseek-v3.5") -> CoderRouteResult`
  - `validate_code_artifact(artifact, original_message=None) -> list[CoderValidationError]`
- Use `Prompt.response_schema` with only safe generic JSON-schema keys (`type`, `properties`, `required`, `enum`, `items`, `minimum`, `maximum`). Avoid blocked keys such as token, api_key, raw payload keys or full prompt/customer prompt labels.
- Keep user NL input only in `PromptMessage(role="user")`. Do not place the full input in metadata, response fields, logs or reasoning.
- Serialize only the sanitized Formulator preview fields needed for code generation into the user message as structured context; metadata should contain only safe small values such as `formulator_task_type`.
- Use stdlib `ast` for syntax/safety checks. Do not use `exec`, `eval`, importlib, subprocess, temp files, or sandbox-runner to validate generated code in this story.
- Suggested generated artifact shape:

```json
{
  "status": "generated",
  "source": "llm_coder_internal_beta",
  "task_type": "lp",
  "artifact": {
    "language": "python",
    "entrypoint": "build_payload",
    "input_model": "LpInput",
    "output_model": "LpPayload",
    "imports": ["pydantic", "typing"],
    "code": "from pydantic import BaseModel\\n..."
  },
  "validation_errors": [],
  "supported_task_types": ["lp", "vrptw", "prediction", "schedule", "inventory", "unknown"]
}
```

- For deterministic M3.8 text, generate safe `template_coder_internal_beta` code only when Formulator has extracted structured fields; otherwise return `needs_clarification`.
- For a well-formed LP JSON completion, accept output only when the AST includes the declared input model, output model and entrypoint. Missing classes/functions or disallowed imports must become `needs_clarification`.
- For unsafe code output, preserve the high-level reason in `validation_errors` such as `artifact.imports` or `artifact.code`; do not expose raw exception text or the unsafe source snippet in the error message.
- Do not add model alias env config unless strictly needed; keep default deterministic/offline-safe.

### Boundary Rules

- No public Chat route.
- No SSE.
- No real provider request or API key use.
- No code execution.
- No Critic validation.
- No Solver/Sandbox invocation.
- No DB/Redis/outbox/billing/cost telemetry writes.
- No AIGC filter/watermark runtime call.
- No frontend changes.

### Story Review Rounds

### Round 1 - Data Consistency (2026-05-29)

Findings applied:

- Pinned `coder_preview` fields and explicitly excluded Coder `confidence` from the public response so it cannot drift into 4.B Critic confidence semantics.
- Pinned `artifact` nullability by status: `generated` requires artifact, `needs_clarification`/`skipped` require `artifact=null`.
- Added size limits for generated code, imports and validation errors so malformed LLM output cannot bloat response data.
- Clarified completion `confidence` may be accepted only as an internal parse guard and must not be returned.

Result: response data shape, generated/null states and bounded error payloads are explicit before implementation.

### Round 2 - Function / Dependency Consistency and Drift (2026-05-29)

Findings applied:

- Restricted `Prompt.metadata` to small non-sensitive fields so the M3.8 prompt validator and P70 input isolation are not bypassed by full payload copies.
- Added explicit Coder helper ownership (`validate_code_artifact`) and AST-only validation guidance; no execution, temp files, subprocesses, importlib or sandbox-runner are allowed in 4.A.4.
- Required Pydantic model inheritance, function annotations and non-async entrypoint to keep "Python code + Pydantic validation" concrete without drifting into runtime execution.
- Expanded dangerous import/call/dunder guards so Coder cannot quietly introduce solver, provider, filesystem or dynamic-execution dependencies.

Result: Coder remains a chat-service preview/validation module over M3.8, without cross-service runtime coupling or hidden execution paths.

### Round 3 - Boundary / Edge Cases / Closure (2026-05-29)

Findings applied:

- Clarified Formulator status gating: `skipped`, `unknown`, generic input and `needs_clarification` must not call Coder LLM or generate code.
- Required Coder clarification errors to point back to Formulator/missing fields so the preview chain remains actionable and closed.
- Added a guard against empty-shell generated artifacts when Formulator is technically `extracted` but lacks fields needed for code generation.
- Required unsafe-code failures to report sanitized high-level validation errors without leaking raw unsafe snippets or exception reprs.
- Reconfirmed closure commands and focused test expectations for endpoint contract, parser fallback, unsafe-code rejection and no-side-effect flags.

Result: Coder generation has explicit preconditions, failure surfaces and validation closure before implementation.

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

RED expectation for implementation: add tests for 4.A.4 Coder first, then confirm `uv run pytest apps/chat-service/tests -q` fails before wiring the implementation.

## Dev Agent Record

### Agent Model Used

GPT-5

### Debug Log References

- 2026-05-29 - Story 4.A.4 draft created after Story 4.A.3 merged in PR #95 and sprint status showed `4-a-4-coder-generate: backlog`.
- 2026-05-29 - Story moved to in-progress after three story review rounds; starting RED tests for 4.A.4 Coder generation preview.
- 2026-05-29 - RED focused test failed before implementation: `uv run pytest apps/chat-service/tests -q` failed with `ModuleNotFoundError: No module named 'chat_service.coder'`.
- 2026-05-29 - Implemented `coder.py`, Coder prompt construction, JSON/deterministic completion parsing, safe clarification/skip fallback, AST/Pydantic artifact validation, schema extension and endpoint wiring.
- 2026-05-29 - Focused validation passed: `uv run pytest apps/chat-service/tests -q` -> 58 passed.
- 2026-05-29 - Local Coder validation hardening added task-type-consistent template artifact plus entrypoint annotation/generator checks; focused Coder/internal-beta tests passed.
- 2026-05-29 - Post-implementation senior review completed; prompt minimization and Coder completion validation hardening findings were fixed with regression tests.

### Implementation Plan

- Reuse 4.A.3 internal beta endpoint, Router result and Formulator preview.
- Add Coder preview models in chat-service only; do not import solver/sandbox runtime modules.
- Add M3.8 `coder_generation` prompt wrapper with injectable completion, strict parser and AST/Pydantic validation.
- Return JSON-safe `coder_preview` with `generated`, `needs_clarification`, or `skipped` status.
- Preserve no-side-effect boundary and aggregate `llm_invoked` across Router/Formulator/Coder.

### Completion Notes List

- Story drafted from Epic 4.A, PRD N4, Architecture P68/P70, Story 4.A.3 completion learnings, current chat-service code and M3.8 deterministic LLM router contract.
- Dev implementation started with RED tests and completed focused chat-service validation.
- Added Coder generation preview after Formulator extraction for internal beta messages.
- Well-formed safe JSON code artifacts can produce `status="generated"` preview; M3.8 deterministic fixture text can produce a safe template artifact only when Formulator has extracted structured fields.
- Formulator `needs_clarification`, `skipped` and `unknown` states do not call Coder LLM and return `needs_clarification` or `skipped`.
- Generated code is validated by Pydantic schema and stdlib AST only; no generated code is executed.
- Endpoint still does not create conversations, call Critic/Solver/Sandbox/Billing/DB/Redis/provider, or expose provider/raw fields.
- Post-review hardening removed raw user request text from the Coder prompt payload and added regression coverage so prompt metadata stays limited to `formulator_task_type`.
- Post-review hardening now validates reported Coder `validation_errors`, rejects top-level raw/provider/secret-like completion fields, and blocks runtime symbol calls such as `requests.post(...)` even without imports.

### Senior Developer Review (AI)

Review scope: uncommitted Story 4.A.4 changes in `D:\优化预测网站`, with `_bmad-output/stories/4-a-4-coder-generate.md` as the governing spec.

Review method:

- Story process verification: confirmed story document exists, three pre-implementation review rounds are recorded and incorporated, and implementation started from a documented RED failure.
- Data consistency review: checked `coder_preview` response shape, status/artifact nullability, supported task type ordering, validation error bounds and provider/raw field exclusion.
- Function/dependency consistency review: checked Coder uses M3.8 `complete(...)`, keeps provider dependencies out of chat-service, keeps validation AST/Pydantic-only, and preserves Router/Formulator/Coder ownership separation.
- Drift/boundary/closure review: checked no public chat route, no SSE/frontend/DB/Redis/Billing/Solver/Sandbox/Critic side effects, no generated-code execution, and internal beta auth still gates before body validation.

Findings fixed:

- Raw user message was originally included in the Coder prompt JSON as `user_request`; fixed by removing it and passing only sanitized Formulator preview fields. Regression assertion verifies the raw user text is absent from the Coder prompt.
- Coder completion `validation_errors` were not parsed or sanitized before accepting otherwise valid artifacts; fixed with bounded coercion, unsafe text rejection, and `needs_clarification` fallback for reported errors.
- Top-level Coder completion raw/provider fields and unimported blocked runtime symbol calls were hardened to fail closed instead of being ignored.

Outcome: approved after fixes. No unresolved high/medium findings remain.

### Final Validation Results

- `uv run pytest apps/chat-service/tests -q` -> 64 passed.
- `uv run python scripts/validate_llm_router_contract.py` -> `llm router contract OK`.
- `uv run pytest tests/llm_router/test_implementations_parity.py -q` -> 14 passed.
- `uv run mypy apps packages` -> success, 100 source files.
- `uv tool run pre-commit run --all-files --show-diff-on-failure` -> passed.
- `git diff --check` -> passed.

### File List

- `_bmad-output/stories/4-a-4-coder-generate.md`
- `_bmad-output/stories/sprint-status.yaml`
- `apps/chat-service/src/chat_service/coder.py`
- `apps/chat-service/src/chat_service/main.py`
- `apps/chat-service/src/chat_service/schemas.py`
- `apps/chat-service/tests/test_coder.py`
- `apps/chat-service/tests/test_internal_beta.py`

### Change Log

- 2026-05-29 - Initial Story 4.A.4 created from Epic 4.A, PRD N4, Architecture prompt-safety constraints, Story 4.A.3 learnings and current chat-service implementation.
- 2026-05-29 - Completed three story review rounds and moved story to in-progress for implementation.
- 2026-05-29 - Implemented Coder code artifact preview for internal beta endpoint after RED tests and focused validation.
- 2026-05-29 - Completed post-implementation code review and applied prompt/completion/code-safety hardening fixes.
