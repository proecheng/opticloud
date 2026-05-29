# Story 4.A.2: Router LLM 分类 Intent

Status: done

owner: Chat Platform / Backend

## Story

作为 Chat Platform 工程师，
我希望在 4.A.1 internal beta NL 输入入口后接入 M3.8 的 `opticloud_shared.llm_router` 抽象来生成结构化 intent 分类，
以便验证 N2 Router LLM 数据合同可以输出稳定的 `task_type`、`confidence` 与 `reasoning`，同时保持 AIGC 未备案前的 internal-only 边界，并且不提前触发 Formulator、Coder、Solver、Sandbox、Billing 或外部真实 provider 副作用。

## Acceptance Criteria

1. 继续复用 4.A.1 internal beta endpoint 和访问边界。
   - 仍只暴露 `POST /v1/chat/internal-beta/messages`；不得新增公开 `/v1/chat`、SSE、Formulator、Coder、Solver、Sandbox runtime 或 Console Chat UI。
   - disabled、未签发 signoff、tenant/user/token 无效、allowlist 超过 5 人时，仍先于 body/schema 解析返回稀疏 404，不泄露 AIGC、allowlist、router 或 provider 细节。
   - `GET /health` 保持不变。

2. Router intent 使用 Story M3.8 LLM abstraction，而不是直接实现 provider client。
   - `apps/chat-service` 依赖 workspace package `opticloud-shared`，并通过 `opticloud_shared.llm_router.complete(prompt, model=...)` 或等价可注入 wrapper 调用 M3.8 router。
   - 构造 `Prompt(task="router_intent", locale=<detected/request locale>, messages=[system,user], response_schema=<router intent JSON schema>)`。
   - 默认 model alias 为 `deepseek-v3.5`；只允许 M3.8 canonical aliases，未知 alias fail closed。
   - 测试和 CI 必须使用 M3.8 离线 deterministic provider；不得读取或要求 API key，不得发外部网络请求。

3. `router_preview` 外部字段名保持兼容，内部来源升级为 LLM router guarded decision。
   - 响应仍包含 `router_preview`，字段仍为 `task_type`、`confidence`、`reasoning`、`source`、`supported_task_types`。
   - `source` 新增 `llm_router_internal_beta`，但不得删除 `heuristic_internal_beta` 类型兼容能力。
   - 支持 task_type 集合保持：`lp`、`vrptw`、`prediction`、`schedule`、`inventory`、`unknown`。
   - 对中文 `"求最短路径..."` / 车辆 / 路径 / 路线语义，成功响应输出 `task_type="vrptw"`、`confidence=0.92`、`source="llm_router_internal_beta"`。
   - `reasoning` 必须是短字符串，不包含完整原始 message、token、secret、provider raw payload 或 API 细节。

4. LLM completion 解析必须结构化、可审计、可降级。
   - 优先解析 JSON object：`task_type`、`confidence`、`reasoning`。
   - 兼容 M3.8 deterministic text envelope 中的 `task_type=... confidence=... reasoning=...`。
   - 如果 completion 缺字段、非法 task_type、confidence 越界、被 content filter、router error 或与 deterministic guardrail 明显冲突，则 fail closed 到 4.A.1 heuristic classifier，而不是返回 500 或错误分类。
   - 当降级到 heuristic 时，`source="heuristic_internal_beta"`，并保留 sparse、安全的 reasoning。
   - `llm_invoked` 语义必须明确：只有实际调用 M3.8 `complete(...)` 后才为 `true`；如果 canonical alias 校验在调用前失败，则为 `false` 并降级 heuristic。
   - `provider_request_sent` 在本 story 所有成功响应中固定为 `false`；不得新增 provider/model/raw_response 字段到 response body。
   - Guardrail conflict rule must be deterministic: if heuristic classification is not `unknown` and LLM classification differs with confidence below `0.95`, fallback to heuristic. This prevents the M3.8 deterministic router fixture from forcing every supported non-route message to `vrptw`.
   - If LLM returns `unknown`, keep `unknown` only when the heuristic classifier is also `unknown`; otherwise fallback to heuristic.
   - If heuristic classification is `unknown` and LLM returns a concrete task type from the deterministic offline fixture, fallback to `unknown` unless a future story adds grounded evidence extraction. This prevents generic business questions from being over-classified.

5. 无业务副作用边界清晰。
   - 成功响应可将 `llm_invoked=true` 表示 M3.8 router abstraction 被调用；同时必须继续返回 `solver_invoked=false`、`sandbox_invoked=false`。
   - 成功响应必须新增或保留可测试字段 `provider_request_sent=false`，证明本 story 不发送真实 provider request。
   - 不创建 DB table、migration、Redis stream、outbox event、billing charge、optimization task、sandbox execution、provider request 或 audit payload。
   - 不调用 Formulator、Coder、Critic、AIGC filter/watermark module；这些留给 4.A.3+、4.B、8.B。

6. Regression 与 M3.8 合同闭环。
   - 4.A.1 focused tests 继续通过，并新增 4.A.2 tests 覆盖 LLM router success、JSON parser、deterministic text parser、invalid completion fallback、router error fallback、unknown model fail closed、unauthorized-before-body-validation。
   - Adjacent M3.8 validation 继续通过：`uv run python scripts/validate_llm_router_contract.py` 和 `uv run pytest tests/llm_router/test_implementations_parity.py -q`。
   - Static closure：`uv run pytest apps/chat-service/tests -q`、`uv run mypy apps packages`、`uv tool run pre-commit run --all-files --show-diff-on-failure`、`git diff --check`。
   - CI `chat-service-test` must also trigger when `packages/shared-py/opticloud_shared/llm_router/**`, `packages/shared-py/opticloud_shared/__init__.py`, or `packages/shared-py/pyproject.toml` changes, because chat-service now depends on the shared LLM router contract.

## Tasks / Subtasks

- [x] Task 1: Add chat-service dependency and prompt/router-intent module. (AC: 2, 6)
  - [x] Add `opticloud-shared` workspace dependency and source mapping to `apps/chat-service/pyproject.toml`.
  - [x] Update CI path filters so chat-service tests run on relevant shared LLM router package changes.
  - [x] Add a small `llm_intent.py` module that builds M3.8 `Prompt` objects and wraps `llm_router.complete`.
  - [x] Keep wrapper injectable so tests can simulate JSON, deterministic text, malformed output and router errors without network.
- [x] Task 2: Extend schemas while keeping 4.A.1 response contract compatible. (AC: 3, 5)
  - [x] Allow `RouterPreview.source` to be `heuristic_internal_beta` or `llm_router_internal_beta`.
  - [x] Change `llm_invoked` from literal false to bool and add `provider_request_sent=false`.
  - [x] Keep task_type enum, locale enum, excerpt behavior and no full prompt echo.
- [x] Task 3: Wire endpoint to internal beta LLM router intent. (AC: 1-5)
  - [x] Preserve access gate before body parsing.
  - [x] Build message_id/locale/excerpt as in 4.A.1.
  - [x] Call LLM intent wrapper only after internal beta gate and request validation pass.
  - [x] Fallback to existing heuristic classifier on unsafe/invalid LLM result.
- [x] Task 4: Add tests and validation evidence. (AC: 1-6)
  - [x] Add RED tests for route VRPTW LLM result with `confidence=0.92`.
  - [x] Add parser/fallback/model/unauthorized regression tests.
  - [x] Run focused, adjacent, static, pre-commit and diff-check validation commands.
  - [x] Update Dev Agent Record, File List and Change Log.

### Review Follow-ups (AI)

- [x] [Review][Patch] Prompt validation failures caused by secret-like NL input must fallback before LLM invocation instead of surfacing as 500.

## Dev Notes

### Source Context

- `_bmad-output/planning/epics.md:1516` defines Story 4.A.2: Router LLM 分类 intent (N2).
- `_bmad-output/planning/epics.md:1518` requires output like `{"task_type":"vrptw","confidence":0.92,"reasoning":"..."}` via Story M3.8 abstraction.
- `_bmad-output/planning/epics.md:772` through `776` keeps Chat MVP in internal beta while AIGC filing is not public.
- `_bmad-output/planning/architecture.md:113` constrains v1 LLM normal path to DeepSeek, with Qwen-Max only as incident fallback.
- `_bmad-output/planning/architecture.md:120` requires LLM mock abstraction in tests; CI must not call paid APIs.
- `_bmad-output/planning/architecture.md:3232` keeps M3 prompts inside `apps/chat-service` until a later prompt-store split.
- Story 4.A.1 established the internal beta gate, endpoint, request schema, `router_preview` field names, allowed task_type set, excerpt behavior and no-side-effect boundary.
- Story M3.8 implemented `opticloud_shared.llm_router` with `Prompt`, `Completion`, canonical aliases `deepseek-v3.5`, `qwen-max`, `mock-deterministic`, offline deterministic providers, and parity validators.

### Current Repository Reality

- `apps/chat-service` is now a workspace FastAPI package with local pytest config.
- `apps/chat-service/src/chat_service/main.py` manually validates internal beta access before request body parsing. This must not regress.
- `apps/chat-service/src/chat_service/router_preview.py` contains the 4.A.1 deterministic classifier and should be reused as fallback, not duplicated.
- `apps/chat-service/src/chat_service/schemas.py` currently has `RouterPreview.source = Literal["heuristic_internal_beta"]` and `llm_invoked = Literal[False]`; 4.A.2 must evolve these intentionally.
- `packages/shared-py/opticloud_shared/llm_router/providers.py` deterministic `router_intent` output includes `task_type=vrptw confidence=0.92`; this satisfies the VRPTW AC but can be wrong for non-route inputs if blindly trusted.
- Because of that deterministic provider behavior, implementation must parse LLM output and apply guardrails/fallback so 4.A.1 non-route task_type regressions do not collapse to VRPTW.

### Implementation Guidance

- Add `llm_intent.py` with pure functions:
  - `build_router_prompt(message, locale, prompt_id)` returning M3.8 `Prompt`.
  - `parse_router_completion(text)` returning validated `RouterPreview` data or a typed failure.
  - `route_intent_with_llm(message, locale, prompt_id, completion_func=complete, model_alias="deepseek-v3.5")`.
- Use `Prompt.response_schema` with only safe generic JSON-schema keys (`type`, `properties`, `required`, `enum`, `minimum`, `maximum`). Avoid metadata keys blocked by M3.8 (`token`, `api_key`, raw payload keys, etc.).
- Keep reasoning terse; cap length in parser or schema to prevent full prompt echo.
- Do not include the full user message in system prompt metadata or response metadata. Only the user prompt message may contain the NL input because M3.8 `PromptMessage` is the intended provider-neutral prompt surface.
- Treat `finish_reason != "stop"` as unsafe and fallback to heuristic.
- Do not log token, prompt, raw completion, raw_response_redacted, API response, or full message in this story.
- If adding env config for model alias, keep default deterministic and canonical. Unknown alias should fail closed or fallback safely; tests must pin the behavior.

### Boundary Rules

- No public Chat route.
- No SSE.
- No real provider request or API key use.
- No Formulator extraction.
- No Coder generation.
- No Critic validation.
- No Solver/Sandbox invocation.
- No DB/Redis/outbox/billing/cost telemetry writes.
- No AIGC filter/watermark runtime call.
- No frontend changes.

### Story Review Rounds

### Round 1 - Data Consistency (2026-05-29)

Findings applied:

- Pinned `llm_invoked` semantics to "M3.8 `complete(...)` was actually called" so parser fallback, router error fallback, and pre-call config rejection are testable.
- Pinned `provider_request_sent=false` as a response-level no-side-effect field for every successful 4.A.2 response.
- Explicitly prohibited provider/model/raw response fields in the endpoint response body, keeping `router_preview` as the only intent classification surface.

Result: LLM attempt state, provider side-effect evidence, and fallback source semantics are explicit before implementation.

### Round 2 - Function / Dependency Consistency and Drift (2026-05-29)

Findings applied:

- Required `opticloud-shared` as a workspace dependency instead of copying M3.8 schemas or providers into `apps/chat-service`.
- Required a thin injectable wrapper around `llm_router.complete(...)` so tests can simulate success/failure without changing M3.8 shared package behavior.
- Added CI path-filter requirement so `chat-service-test` runs when shared LLM router files change; otherwise 4.A.2 could silently drift from M3.8.
- Kept provider alias handling limited to M3.8 canonical aliases; no new DeepSeek/Qwen client, API key loading, or provider transport in chat-service.

Result: 4.A.2 consumes M3.8 through the existing abstraction and adds no duplicate provider stack or hidden external dependency.

### Round 3 - Boundary / Edge Cases / Closure (2026-05-29)

Findings applied:

- Added deterministic conflict guardrails so non-route supported inputs from 4.A.1 cannot all collapse to `vrptw` just because the M3.8 offline `router_intent` fixture emits `vrptw`.
- Added unknown-input guardrail so generic business questions do not become VRPTW without grounded task evidence.
- Added explicit handling for LLM `unknown`, low confidence, malformed output, non-stop finish reasons, and router errors.
- Clarified that the full NL input may appear only as the M3.8 user prompt message, not in metadata, response fields, logs, reasoning, or raw diagnostics.
- Confirmed closure requires focused chat-service tests, adjacent M3.8 validators, mypy, pre-commit, and diff-check.

Result: public/internal boundary, prompt-safety, fallback correctness, and validation closure are explicit before implementation.

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

RED expectation for implementation: add tests for 4.A.2 LLM router intent first, then confirm `uv run pytest apps/chat-service/tests -q` fails before wiring the implementation.

## Dev Agent Record

### Agent Model Used

GPT-5

### Debug Log References

- 2026-05-29 - Story 4.A.2 draft created after Story 4.A.1 merged in PR #93 and sprint status showed `4-a-2-router-llm-intent: backlog`.
- 2026-05-29 - Story moved to in-progress; starting RED tests for 4.A.2 LLM router intent.
- 2026-05-29 - RED focused test failed before implementation: `uv run pytest apps/chat-service/tests -q` failed with `ModuleNotFoundError: No module named 'opticloud_shared'`.
- 2026-05-29 - Implemented `llm_intent.py`, M3.8 prompt construction, JSON/deterministic completion parsing, guarded fallback, schema evolution, endpoint wiring, workspace dependency and CI path filter update.
- 2026-05-29 - Focused validation passed: `uv run pytest apps/chat-service/tests -q` -> 33 passed.
- 2026-05-29 - Adjacent M3.8 validation passed: `uv run python scripts/validate_llm_router_contract.py` -> `llm router contract OK`; `uv run pytest tests/llm_router/test_implementations_parity.py -q` -> 14 passed.
- 2026-05-29 - Static validation passed: `uv run mypy apps packages`, `uv tool run pre-commit run --all-files --show-diff-on-failure`, and `git diff --check`.
- 2026-05-29 - Post-implementation code review found and fixed one prompt-safety boundary issue: M3.8 `PromptMessage` validation failures now fallback before LLM invocation.
- 2026-05-29 - Post-review validation passed: `uv run pytest apps/chat-service/tests -q` -> 34 passed; M3.8 adjacent validators passed; mypy, pre-commit and diff-check passed.

### Implementation Plan

- Reuse 4.A.1 internal beta endpoint and heuristic classifier.
- Add M3.8 LLM router intent wrapper with strict parser and fallback.
- Evolve response schema minimally for LLM source and provider-request evidence.
- Add focused parser/endpoint tests plus adjacent M3.8 contract validation.

### Completion Notes List

- Story drafted and reviewed through three pre-implementation rounds.
- Dev implementation started with RED tests and completed through focused, adjacent, static, pre-commit and diff-check validation.
- Added M3.8 LLM router intent wrapper that constructs safe `Prompt(task="router_intent")`, parses JSON and deterministic text completions, and falls back to 4.A.1 heuristic classifier on malformed output, router errors, non-stop finish reasons, unknown aliases and conflict guardrails.
- Prompt validation failures from secret-like NL input now fallback to heuristic with `llm_invoked=false` instead of surfacing a 500.
- Endpoint now returns `llm_invoked=true` when M3.8 `complete(...)` is called, `provider_request_sent=false` for no live provider side effects, and keeps `solver_invoked=false` / `sandbox_invoked=false`.
- 4.A.1 internal beta gate-before-body-validation behavior remains covered by regression tests.

### File List

- `_bmad-output/stories/4-a-2-router-llm-intent.md`
- `_bmad-output/stories/sprint-status.yaml`
- `.github/workflows/ci.yml`
- `apps/chat-service/pyproject.toml`
- `apps/chat-service/src/chat_service/llm_intent.py`
- `apps/chat-service/src/chat_service/main.py`
- `apps/chat-service/src/chat_service/schemas.py`
- `apps/chat-service/tests/test_internal_beta.py`
- `apps/chat-service/tests/test_llm_intent.py`
- `uv.lock`

### Change Log

- 2026-05-29 - Initial Story 4.A.2 created from Epic 4.A, M3.8 LLM router contract, Architecture LLM constraints, and Story 4.A.1 completion learnings.
- 2026-05-29 - Dev implementation started; status moved to in-progress.
- 2026-05-29 - Implemented guarded M3.8 LLM router intent classification for internal beta endpoint; status moved to code-review after validation passed.
- 2026-05-29 - Addressed code review prompt-validation fallback finding.

### Senior Developer Review (AI)

Review date: 2026-05-29

Outcome: Approve after fixes.

Review layers executed locally: data/contract consistency, function/dependency drift, boundary/edge cases, acceptance closure.

Findings:

- [x] Patch - Secret-like NL input could make M3.8 `PromptMessage` validation fail during prompt construction and bubble out as a 500. Fixed by catching prompt construction `ValidationError`, falling back to the 4.A.1 heuristic classifier before invocation, and adding a regression test that verifies `llm_invoked=false`.

Validation after review fix:

- `uv run pytest apps/chat-service/tests -q` -> 34 passed.
- `uv run python scripts/validate_llm_router_contract.py` -> `llm router contract OK`.
- `uv run pytest tests/llm_router/test_implementations_parity.py -q` -> 14 passed.
- `uv run mypy apps packages` -> success, no issues found in 98 source files.
- `uv tool run pre-commit run --all-files --show-diff-on-failure` -> passed.
- `git diff --check` -> passed.
