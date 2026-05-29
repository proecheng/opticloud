# Story 4.A.5: 中英文混合输入 (N1)

Status: done

owner: Chat Platform / Backend

## Story

作为 internal beta Chat 用户，
我希望自然语言 Chat 可以理解中文、英文和中英文混合输入，并用同语种风格返回简短预览，
以便我在 AIGC 备案前的内部验证环境中确认 NL -> Router -> Formulator -> Coder 链路对双语输入的处理一致，同时每次回复都带有中英双语免责声明。

## Acceptance Criteria

1. 继续复用 4.A.1-4.A.4 internal beta endpoint 和访问边界。
   - 仍只暴露 `POST /v1/chat/internal-beta/messages`；不得新增公开 `/v1/chat`、SSE、conversation persistence、Chat public API、Critic、Sandbox runtime、Solver submission、Console Chat UI 或 frontend changes。
   - disabled、未签发 signoff、tenant/user/token 无效、allowlist 超过 5 人时，仍先于 body/schema 解析返回稀疏 404，不泄露 AIGC、router、formulator、coder、language response、allowlist 或 provider 细节。
   - `language_preview` 只存在于 internal beta JSON contract；不得把它暴露为正式用户可见 NL surface、SSE chunk、web UI copy、public API response 或 AIGC 备案后的出口替代品。
   - `GET /health` 保持不变。

2. 响应新增一个稳定的 response-only `language_preview` contract。
   - `ChatInternalBetaMessageResponse` 继续包含 `locale`、`router_preview`、`formulator_preview`、`coder_preview`、`aigc_gate`、`llm_invoked`、`provider_request_sent=false`、`solver_invoked=false`、`sandbox_invoked=false`。
   - 新增 `language_preview`，字段固定为 `status`、`source`、`response_locale`、`summary`、`disclaimer`、`validation_errors`、`supported_locales`。
   - `status` 只允许 `generated`、`fallback`；language preview 在本 story 中必须始终返回可见 `summary` 和固定 `disclaimer`，不得返回空 preview。
   - `source` 允许 `llm_language_internal_beta` 或 `heuristic_language_internal_beta`。
   - `status="generated"` 必须搭配 `source="llm_language_internal_beta"`，表示 LLM JSON summary 已通过安全解析；`status="fallback"` 必须搭配 `source="heuristic_language_internal_beta"`，表示 deterministic text、unsafe completion、non-stop finish reason、prompt/parse/router error 或 pre-call validation failure 后使用本地 deterministic summary。
   - `response_locale` 必须等于 endpoint resolved `locale`，即 `request.locale or detect_locale(request.message)`；显式 `locale="mixed"` 必须被尊重。
   - `supported_locales` 顺序固定为 `["zh-CN", "en-US", "mixed"]`。
   - `summary` 必须是 trim 后的短文本，长度 1-360 chars，不能为 Markdown，不能包含 provider/model/raw/usage/confidence/prompt 字段，不能完整回显用户原始 message，也不能包含 `message_excerpt` 的完整值。
   - `disclaimer` 固定 shape：`zh`、`en`、`bilingual`。`bilingual` 必须等于 `<zh> / <en>`。
   - 免责声明文本固定为：
     - `zh`: `AI 生成内容仅供参考，请在提交求解前核对。`
     - `en`: `AI-generated content is for reference only. Review it before submitting a solve.`
     - `bilingual`: `AI 生成内容仅供参考，请在提交求解前核对。 / AI-generated content is for reference only. Review it before submitting a solve.`
   - `validation_errors` 最多 10 条；单个 `field_path` 最多 128 chars，单个 `message` 最多 160 chars，单个 `remediation_hint_key` 最多 128 chars。

3. 同语种回应规则明确且可测试。
   - `zh-CN` 输入或显式 `locale="zh-CN"`：`summary` 主要为中文，可以包含任务类型英文缩写，例如 LP、VRPTW、SKU。
   - `en-US` 输入或显式 `locale="en-US"`：`summary` 主要为英文，可以包含用户域内原有中文专名但不得整段中文回复。
   - `mixed` 输入或显式 `locale="mixed"`：`summary` 必须同时包含中文和 English token，且语义上是同一条简短业务结果，不是两个互相矛盾的摘要。
   - 不论 `response_locale` 是什么，`disclaimer` 始终同时提供 `zh`、`en`、`bilingual`。
   - Router/Formulator/Coder 现有 preview 不需要改成双语；本 story 只新增最终 NL response preview，不重写前序 preview contract。

4. Language preview 使用 Story M3.8 LLM abstraction，而不是直接实现 provider client。
   - 通过 `opticloud_shared.llm_router.complete(prompt, model=...)` 或等价可注入 wrapper 调用 M3.8 router。
   - 构造 `Prompt(task="mixed_language_summary", locale=<resolved locale>, messages=[system,user], response_schema=<language preview JSON schema>)`。
   - `Prompt.metadata` 只能包含不敏感的小字段，例如 `response_locale`、`router_task_type`、`formulator_status`、`coder_status`；不得放完整用户 message、完整 preview payload、prompt text、raw completion 或 provider payload。
   - 默认 model alias 为 `deepseek-v3.5`；只允许 M3.8 canonical aliases，未知 alias fail closed。
   - `language_response.py` 必须沿用 4.A.2-4.A.4 的 `CompletionFunc = Callable[[Prompt, str], Completion]`、`CANONICAL_MODEL_ALIASES` 校验、`LLMRouterError` fallback 和 dataclass route result 模式。
   - 测试和 CI 必须使用 M3.8 离线 deterministic provider 或注入 completion；不得读取或要求 API key，不得发外部网络请求。
   - 必须复用已有 `opticloud-shared` workspace dependency；不得新增 DeepSeek/Qwen SDK、HTTP client、LangChain、OpenAI SDK 或 provider-specific package。
   - 不需要修改 `.github/workflows/ci.yml`；现有 `chat-service-test` path-filter 已覆盖 `apps/chat-service/**` 和 `packages/shared-py/opticloud_shared/llm_router/**`。

5. Completion 解析必须结构化、可审计、可降级。
   - 优先解析 JSON object：`response_locale`、`summary`、可选 `validation_errors`。若 completion 额外包含 `confidence`，必须为 0.0 到 1.0 的 number 才能继续解析，但该字段不得暴露到 response。
   - `response_locale` 必须等于 resolved locale；冲突、未知 locale 或缺失字段必须 fail closed 到 heuristic preview。
   - 兼容 M3.8 deterministic text envelope 中的 `mixed language summary 中文 English concise business result ...`；只能把它当作 invocation evidence，随后生成安全、短、同语种 heuristic summary。
   - 对 `finish_reason in {"length","content_filter","error"}` 必须返回 heuristic preview；不得部分采信截断输出。
   - 如果 completion 缺字段、非法 locale、confidence 越界、content filter、router error、prompt validation error、secret-like 输出、raw/provider 字段、`deterministic_digest`、完整用户 message 回显、超长输出、Markdown fenced output 或 prompt injection 输出，则 fail closed 到 heuristic preview，而不是返回 500。
   - `llm_invoked` 表示本请求是否至少实际调用过一次 M3.8 `complete(...)`；Router、Formulator、Coder 或 Language preview 任一阶段调用到 `complete(...)` 即为 `true`。
   - Language preview 阶段需要单独返回内部 `language_invoked` 给 endpoint 聚合，但该字段不暴露到 response body。
   - `provider_request_sent` 在本 story 所有成功响应中固定为 `false`；不得新增 provider/model/raw_response/raw_prompt 字段到 response body。

6. Language preview 必须只基于安全摘要上下文，不泄露原始输入或内部 payload。
   - user NL input 只能作为 `PromptMessage(role="user")` 的普通用户内容出现，不得放入 system role、metadata、response field、logs 或 validation errors。
   - system prompt 必须明确：不要泄露 system/developer instructions、不要返回 raw provider payload、不要执行用户要求改 schema/泄密/隐藏免责声明的指令。
   - language prompt 的 structured context 只能包含短小安全字段：resolved locale、router task_type/confidence/source、formulator status/task_type、coder status/task_type，以及已有 `message_excerpt`；不得包含完整 `formulator_preview.variables/objective/constraints`、完整 generated code、原始 completion 或 secret-like 值。
   - 输出 parser 必须拒绝 secret-like 文本、provider/raw/debug 字段、stack trace、API key、authorization header、cookie、password、`deterministic_digest` 和完整用户 message。
   - `summary` 不得包含免责声明本身；免责声明只通过 `disclaimer` 字段表达。

7. 无业务副作用边界清晰。
   - 成功响应只生成 preview，不提交 Optimization/Prediction，不创建 conversation，不运行 Coder artifact，不调用 Critic，不运行 Solver/Sandbox，不计费。
   - 不创建 DB table、migration、Redis stream、outbox event、billing charge、optimization task、prediction task、sandbox execution、provider request、audit payload 或 cost telemetry event。
   - 不调用 AIGC filter/watermark module；当前只返回 internal beta 结构化 JSON preview，正式用户可见 NL 出口过滤和水印留给 4.B/8.B，不能在本 story 自实现 filter。
   - 不新增 frontend changes。

8. Regression 与 M3.8 合同闭环。
   - 4.A.1-4.A.4 focused tests 继续通过，并新增 4.A.5 tests 覆盖 auto-detected `zh-CN`、`en-US`、`mixed`，显式 locale override，LLM JSON summary，M3.8 deterministic text fallback，non-stop finish reason fallback，unsafe completion fallback，prompt metadata 限制，完整原文不回显，unauthorized-before-body-validation。
   - Adjacent M3.8 validation 继续通过：`uv run python scripts/validate_llm_router_contract.py` 和 `uv run pytest tests/llm_router/test_implementations_parity.py -q`。
   - Static closure：`uv run pytest apps/chat-service/tests -q`、`uv run mypy apps packages`、`uv tool run pre-commit run --all-files --show-diff-on-failure`、`git diff --check`。
   - 实施完成后必须执行 post-implementation code review，至少覆盖数据一致性、函数/依赖一致性、漂移/边界、prompt injection、raw/provider 泄露、fallback 闭环和测试证据；发现项必须先修复再进入 commit/push/PR。
   - CI `chat-service-test` must continue to trigger when `packages/shared-py/opticloud_shared/llm_router/**`, `packages/shared-py/opticloud_shared/__init__.py`, or `packages/shared-py/pyproject.toml` changes.

## Tasks / Subtasks

- [x] Task 1: Add language preview schemas and pure language response module. (AC: 2-6, 8)
  - [x] Add `ChatDisclaimer`, `LanguagePreview`, `LanguageValidationError` and related literals to `apps/chat-service/src/chat_service/schemas.py`.
  - [x] Add `apps/chat-service/src/chat_service/language_response.py` with `build_language_response_prompt(...)`, `parse_language_response_completion(...)`, `generate_language_response_with_llm(...)`, `heuristic_language_preview(...)`, and bounded validation helpers.
  - [x] Keep completion wrapper injectable so tests can simulate JSON, deterministic text, malformed output, content-filter finish reason and router errors without network.
  - [x] Reuse `ChatLocale`, `SUPPORTED_TASK_TYPES`, existing preview models and 4.A.2-4.A.4 safe fallback patterns; do not duplicate locale/task lists except for explicit `SUPPORTED_LOCALES`.
  - [x] Do not add new dependencies; use stdlib + Pydantic + existing `opticloud-shared`.
- [x] Task 2: Wire language preview into internal beta endpoint after Coder. (AC: 1-3, 5, 7)
  - [x] Preserve internal beta access gate before body parsing.
  - [x] Resolve locale exactly as current endpoint does: `request.locale or detect_locale(request.message)`.
  - [x] Call Language preview after Router, Formulator and Coder previews exist so it can summarize chain state without mutating earlier previews.
  - [x] Aggregate LLM invocation semantics across Router/Formulator/Coder/Language while keeping `provider_request_sent=false`.
- [x] Task 3: Implement same-language/fallback behavior and safety parser. (AC: 2-7)
  - [x] Accept safe JSON summary only when locale, length, schema and no-leak checks pass.
  - [x] Convert deterministic M3.8 text and unsafe/non-stop completions to heuristic preview, never 500.
  - [x] Generate deterministic summaries for `zh-CN`, `en-US` and `mixed` using safe task/status labels, not full user input.
  - [x] Always include the fixed bilingual disclaimer and keep disclaimer out of `summary`.
- [x] Task 4: Add RED tests and validation evidence. (AC: 1-8)
  - [x] Add failing tests first for `language_preview` schema and endpoint mixed-language response.
  - [x] Add parser/fallback/prompt-safety/locale override/no-raw-echo/unauthorized regression tests.
  - [x] Run focused, adjacent, static, pre-commit and diff-check validation commands.
  - [x] Update Dev Agent Record, File List and Change Log.

### Review Findings

- [x] [Review][Patch] `LanguagePreview.supported_locales` order was only guaranteed by constructors, not by schema validation. Fixed with schema-level canonical order validation and regression coverage.
- [x] [Review][Patch] Endpoint `provider_request_sent` aggregation initially only surfaced Router's field. Fixed by aggregating Router/Formulator/Coder/Language route results while preserving the public `Literal[False]` contract.
- [x] [Review][Patch] Language completion parser accepted unknown top-level JSON keys if they were not blocked raw/provider names. Fixed by allowing only `response_locale`, `summary`, `confidence`, and `validation_errors`, with regression coverage.

## Dev Notes

### Source Context

- `_bmad-output/planning/epics.md:398` defines Epic 4.A goal: NL Chat with Chinese / English / mixed input plus Router/Formulator/Coder.
- `_bmad-output/planning/epics.md:1528` defines Story 4.A.5: 中英文混合输入 (N1).
- `_bmad-output/planning/epics.md:1530` requires: Given NL 混合 / When LLM 处理 / Then 同语种回应 + 中英双语 disclaimer.
- `_bmad-output/planning/prd.md:1486` defines FR N1 as v1 required: 用户 can converse in NL (中/英/中英混).
- `_bmad-output/planning/prd.md:1787` requires Chat mixed input and same-language LLM response.
- `_bmad-output/planning/epics.md:772` through `776` keep Chat internal beta while AIGC filing is pending.
- `_bmad-output/planning/architecture.md:113` through `114` state v1 LLM path uses DeepSeek and i18n is zh + key en fallback.
- `_bmad-output/planning/architecture.md:120` requires test environment LLM mock abstraction; CI must not call paid APIs.
- `_bmad-output/planning/architecture.md:140` anchors i18n / bilingual behavior through Accept-Language / NL Summary / Critic reasoning.
- `_bmad-output/planning/architecture.md:2990` through `2999` requires prompt injection defense: user input stays out of system role, role tagging, pre-LLM filtering and no secret leakage.
- `_bmad-output/planning/architecture.md:3232` keeps M1-M3 prompts inside chat-service code/constants until later prompt-store.

### Current Repository Reality

- `apps/chat-service/src/chat_service/main.py` owns the only Chat endpoint: `POST /v1/chat/internal-beta/messages`.
- `main.py` currently validates internal beta access before `ChatInternalBetaMessageRequest.model_validate(...)`; this must not regress.
- `apps/chat-service/src/chat_service/router_preview.py` owns `detect_locale(message)`, which returns `zh-CN`, `en-US` or `mixed`; mixed means both CJK and ASCII letters exist.
- `apps/chat-service/src/chat_service/router_preview.py` owns `SUPPORTED_TASK_TYPES`; keep task order unchanged.
- `apps/chat-service/src/chat_service/llm_intent.py`, `formulator.py` and `coder.py` already wrap M3.8 `complete(...)` with injectable completion and safe fallback patterns.
- `apps/chat-service/src/chat_service/schemas.py` currently defines `ChatLocale = Literal["zh-CN", "en-US", "mixed"]` and `ChatInternalBetaMessageResponse` with `coder_preview`; extend it minimally with `language_preview`.
- `packages/shared-py/opticloud_shared/llm_router/providers.py` deterministic provider already supports task `mixed_language_summary` and returns text beginning with `mixed language summary 中文 English concise business result ...`.
- `tests/llm_router/test_implementations_parity.py` already includes exactly 20 `mixed_language_summary` reference prompts; keep adjacent contract passing.
- `apps/solver-orchestrator/src/solver_orchestrator/schemas.py` has a prediction disclaimer pattern, but 4.A.5 should define a chat-service disclaimer locally rather than importing solver-orchestrator runtime.

### Previous Story Intelligence

- 4.A.1 established internal beta gate defaults fail closed; unauthorized/disabled requests return sparse 404 before body validation. This is a hard regression boundary.
- 4.A.2 established use of `opticloud_shared.llm_router.complete(...)` through thin injectable wrappers; prompt construction failures fail closed; `llm_invoked` means actual `complete(...)` was called.
- 4.A.3 established Formulator parser safety: reject secret/raw/original-message echoes and oversized nested payloads; unknown router task skips downstream.
- 4.A.4 established Coder prompt hardening: raw user message must not be embedded in structured metadata; completion payload, validation errors, raw/provider fields and dangerous code fail closed.
- 4.A.4 final validation passed with 64 chat-service tests plus M3.8 contract, mypy, pre-commit and diff-check.

### Implementation Guidance

- Add `language_response.py` with pure functions:
  - `build_language_response_prompt(message, locale, prompt_id, message_excerpt, router_preview, formulator_preview, coder_preview) -> Prompt`
  - `parse_language_response_completion(text, locale, original_message=None) -> LanguagePreview | None`
  - `heuristic_language_preview(locale, router_preview, formulator_preview, coder_preview, validation_errors=None) -> LanguagePreview`
  - `generate_language_response_with_llm(message, locale, prompt_id, message_excerpt, router_preview, formulator_preview, coder_preview, completion_func=complete, model_alias="deepseek-v3.5") -> LanguageRouteResult`
- Define `LanguageRouteResult` as a frozen dataclass with `preview: LanguagePreview`, `language_invoked: bool` and `provider_request_sent: Literal[False] = False`, matching Router/Formulator/Coder route-result style.
- Define `SUPPORTED_LOCALES: tuple[ChatLocale, ...] = ("zh-CN", "en-US", "mixed")` in `language_response.py` or a clearly owned chat-service module; do not create a separate shared package just for this story.
- Use a local `LANGUAGE_RESPONSE_SCHEMA` with safe JSON-schema keys only (`type`, `properties`, `required`, `enum`, `items`, `minimum`, `maximum`). Do not include blocked labels such as token, api_key, raw payload, provider payload, full prompt, customer prompt or hidden reasoning.
- Keep full user input only in `PromptMessage(role="user")`. The structured summary context should use `message_excerpt` plus task/status fields only.
- Suggested successful response shape:

```json
{
  "language_preview": {
    "status": "generated",
    "source": "llm_language_internal_beta",
    "response_locale": "mixed",
    "summary": "已识别 route optimization intent and generated an internal beta preview.",
    "disclaimer": {
      "zh": "AI 生成内容仅供参考，请在提交求解前核对。",
      "en": "AI-generated content is for reference only. Review it before submitting a solve.",
      "bilingual": "AI 生成内容仅供参考，请在提交求解前核对。 / AI-generated content is for reference only. Review it before submitting a solve."
    },
    "validation_errors": [],
    "supported_locales": ["zh-CN", "en-US", "mixed"]
  }
}
```

- For `zh-CN` heuristic summary, use a concise Chinese sentence such as `已识别为 <task_label> 请求，并生成 internal beta 预览。`
- For `en-US` heuristic summary, use a concise English sentence such as `Detected a <task_label> request and prepared an internal beta preview.`
- For `mixed` heuristic summary, include both languages in one sentence, for example `已识别为 <task_label> request，并生成 internal beta preview。`
- Do not add model alias env config unless strictly needed; keep default deterministic/offline-safe.
- Do not import solver-orchestrator just to reuse its disclaimer model; that would create an unnecessary runtime dependency.

### Boundary Rules

- No public Chat route.
- No SSE.
- No real provider request or API key use.
- No code execution.
- No Critic validation.
- No Solver/Sandbox invocation.
- No DB/Redis/outbox/billing/cost telemetry writes.
- No AIGC filter/watermark runtime call.
- No self-implemented AIGC filter or watermark copy.
- No treating internal beta JSON `language_preview` as final public user-facing NL output.
- No frontend changes.

### Story Review Rounds

### Round 1 - Data Consistency (2026-05-29)

Findings applied:

- Removed ambiguous `skipped` status from `language_preview`; 4.A.5 must always return a visible summary plus bilingual disclaimer, either from accepted LLM JSON (`generated`) or deterministic local fallback (`fallback`).
- Pinned `status` to `source` mapping so LLM and heuristic outputs cannot be mislabeled.
- Clarified fallback is the required behavior for deterministic text, unsafe completion, non-stop finish reason, prompt/parse/router error and pre-call validation failure.
- Tightened summary safety: trim bounds are explicit, and the output must not contain the full original message or the full `message_excerpt`.

Result: response data shape, status semantics, disclaimer presence and no-raw-echo constraints are explicit before implementation.

### Round 2 - Function / Dependency Consistency (2026-05-29)

Findings applied:

- Pinned `language_response.py` to the existing chat-service wrapper pattern: injectable `CompletionFunc`, `CANONICAL_MODEL_ALIASES` check, `LLMRouterError` fallback and route-result dataclass.
- Pinned `mixed_language_summary` as the only M3.8 task for this story; no new provider client, SDK, HTTP dependency or shared package is needed.
- Added explicit `LanguageRouteResult`, `SUPPORTED_LOCALES` and `LANGUAGE_RESPONSE_SCHEMA` ownership guidance so implementers do not scatter locale constants or schema fragments.
- Confirmed `.github/workflows/ci.yml` already covers `apps/chat-service/**` and `packages/shared-py/opticloud_shared/llm_router/**`; this story should not churn CI config unless implementation unexpectedly changes path filters.

Result: language preview remains a narrow chat-service extension over the existing M3.8 abstraction, without dependency or CI drift.

### Round 3 - Drift / Boundary / Closure (2026-05-29)

Findings applied:

- Clarified `language_preview` is internal beta JSON only; it must not become public Chat, SSE chunking, frontend copy, conversation persistence or a substitute for post-filing user-visible NL output.
- Reconciled AIGC architecture drift: this story must not call or reimplement AIGC filter/watermark; formal user-visible NL filtering remains owned by 4.B/8.B.
- Reconfirmed gate-before-body-validation as a hard boundary and added regression expectations for unauthorized invalid-body requests.
- Added explicit post-implementation code review requirement before commit/push/PR, covering data/function consistency, drift, prompt injection, raw/provider leakage, fallback closure and test evidence.

Result: story has clear scope boundaries, failure modes, validation closure and implementation-review closure before development begins.

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

RED expectation for implementation: add tests for 4.A.5 language preview first, then confirm `uv run pytest apps/chat-service/tests -q` fails before wiring the implementation. After implementation, perform code review and apply fixes before final validation and GitHub sync.

## Dev Agent Record

### Agent Model Used

GPT-5

### Debug Log References

- 2026-05-29 - Story 4.A.5 draft created from Epic 4.A, PRD N1, Architecture bilingual/prompt-safety constraints, Story 4.A.4 learnings, current chat-service implementation and M3.8 deterministic `mixed_language_summary` contract.
- 2026-05-29 - Story moved to in-progress after three story review rounds; starting RED tests for 4.A.5 language preview.
- 2026-05-29 - RED focused test failed before implementation: `uv run pytest apps/chat-service/tests -q` failed with `ModuleNotFoundError: No module named 'chat_service.language_response'`.
- 2026-05-29 - Implemented `language_response.py`, language preview schemas, endpoint wiring, same-language heuristic fallback and parser safety checks.
- 2026-05-29 - Focused validation passed after implementation: `uv run pytest apps/chat-service/tests -q` -> 82 passed.
- 2026-05-29 - Static validation initially found mypy Literal errors for disclaimer constants; fixed by typing disclaimer constants as Literals.
- 2026-05-29 - Post-implementation code review completed; supported locale order validation, provider_request_sent aggregation and parser top-level key hardening findings were fixed with regression tests.

### Implementation Plan

- Reuse 4.A.4 internal beta endpoint, Router, Formulator and Coder previews.
- Add a response-only `language_preview` contract in chat-service.
- Use M3.8 `mixed_language_summary` prompt wrapper with injectable completion, strict parser and heuristic fallback.
- Preserve no-side-effect boundary and aggregate `llm_invoked` across Router/Formulator/Coder/Language.

### Completion Notes List

- Story drafted and three story review rounds completed before implementation.
- Added `language_preview` response-only contract to internal beta Chat messages.
- `language_preview` always returns a same-locale summary and fixed bilingual disclaimer; fallback summaries are deterministic and do not echo the full message or excerpt.
- M3.8 `mixed_language_summary` is used through the existing injectable `complete(...)` abstraction; deterministic text and unsafe/non-stop completions fall back safely.
- Endpoint still gates before body validation and still does not expose public Chat, SSE, frontend UI, conversation persistence, DB/Redis/Billing/Solver/Sandbox/Critic, provider request, AIGC filter or watermark side effects.
- Post-review hardening validates `supported_locales` order at schema level, aggregates all route-result `provider_request_sent` fields, and rejects unknown top-level language completion keys.

### Senior Developer Review (AI)

Review scope: Story 4.A.5 implementation in `D:\优化预测网站`, with `_bmad-output/stories/4-a-5-zh-en-mixed.md` as governing spec.

Review method:

- Data consistency review: checked `language_preview` response fields, status/source mapping, fixed disclaimer literals, locale semantics, supported locale order, validation error bounds and no raw message/excerpt echo.
- Function/dependency consistency review: checked use of M3.8 `complete(...)`, `mixed_language_summary`, injectable completion, `CANONICAL_MODEL_ALIASES`, no new dependencies and no CI workflow churn.
- Drift/boundary review: checked no public route, no SSE/frontend/conversation persistence, no AIGC filter/watermark self-implementation, no Solver/Sandbox/Critic/Billing/DB/Redis side effects, and internal beta auth still gates before body validation.
- Safety/fallback review: checked deterministic text, non-stop finish reasons, router errors, prompt validation, unsafe/raw/provider fields, top-level completion key drift and prompt metadata limits.

Findings fixed:

- `LanguagePreview.supported_locales` needed schema-level canonical order validation.
- Endpoint `provider_request_sent` should aggregate all pipeline stage route results while preserving `false`.
- Language completion parser needed a strict top-level field allowlist to reject ignored debug/provider payloads.

Outcome: approved after fixes. No unresolved high/medium findings remain.

### Final Validation Results

- `uv run pytest apps/chat-service/tests -q` -> 84 passed.
- `uv run python scripts/validate_llm_router_contract.py` -> `llm router contract OK`.
- `uv run pytest tests/llm_router/test_implementations_parity.py -q` -> 14 passed.
- `uv run mypy apps packages` -> success, 101 source files.
- `uv tool run pre-commit run --all-files --show-diff-on-failure` -> passed.
- `git diff --check` -> passed.

### File List

- `_bmad-output/stories/4-a-5-zh-en-mixed.md`
- `_bmad-output/stories/sprint-status.yaml`
- `apps/chat-service/src/chat_service/language_response.py`
- `apps/chat-service/src/chat_service/main.py`
- `apps/chat-service/src/chat_service/schemas.py`
- `apps/chat-service/tests/test_internal_beta.py`
- `apps/chat-service/tests/test_language_response.py`

### Change Log

- 2026-05-29 - Initial Story 4.A.5 draft created.
- 2026-05-29 - Completed three story review rounds and incorporated data, dependency and boundary/closure fixes.
- 2026-05-29 - Started implementation after story reached ready-for-dev.
- 2026-05-29 - Implemented 4.A.5 language preview and completed post-implementation review fixes.
