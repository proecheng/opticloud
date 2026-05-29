# Story 4.A.1: NL 输入接收 + Chat MVP Internal Beta

Status: done

owner: Chat Platform / Backend

## Story

作为 Chat Platform 工程师，
我希望先提供一个仅限课题组 staging tenant 与最多 5 名受信学者使用的 NL Chat internal beta 输入入口，
以便在 AIGC 备案签发前验证自然语言输入、基础 task_type 分类和后续 4.A Router/Formulator 链路的数据合同，同时不公开 Chat 能力、不调用真实 LLM、不触发求解/计费/沙箱副作用。

## Acceptance Criteria

1. `apps/chat-service` 具备最小 FastAPI service 骨架。
   - 新增 `apps/chat-service/pyproject.toml` 并加入 root `uv` workspace。
   - 新增 `chat_service.main:app`，包含 `GET /health`。
   - 新增 `POST /v1/chat/internal-beta/messages`，只用于 internal beta；不得新增公开 `/v1/chat`、SSE、求解、Formulator、Coder 或 Sandbox runtime。
   - CI 增加 `chat-service-test` path-filter job，运行 `apps/chat-service/tests/`。

2. Internal beta gate 默认 fail closed，并满足 CM3/SC3。
   - 默认配置下 endpoint 不对外暴露，返回 404 或等价隐藏响应，不泄露 AIGC 备案状态或 allowlist 细节。
   - 只有 `CHAT_INTERNAL_BETA_ENABLED=true` 且 `CHAT_INTERNAL_BETA_SIGNOFF=founder-legal-approved` 时才允许进入 beta 认证。
   - 只允许一个 staging tenant，默认 `research-staging`，由 `X-Internal-Beta-Tenant` 传入。
   - 只允许 `CHAT_INTERNAL_BETA_USERS` 中最多 5 个命名 user id；配置超过 5 个时 service 必须 fail closed。
   - 内测访问必须提供 `X-Internal-Beta-User` 和 `X-Internal-Beta-Token`；token 使用常量时间比较，不记录、不回显。

3. NL 输入 schema 稳定且边界明确。
   - 请求体最少包含 `message`，支持可选 `locale` 和 `client_request_id`。
   - `message` trim 后必须 2 到 2000 字符；空白、过短、过长返回 422。
   - `locale` 仅允许 `zh-CN`、`en-US`、`mixed`，未提供时根据中英文字符做确定性检测。
   - 响应不得回显完整原文；最多返回短 `message_excerpt`，且长度固定上限。

4. Router preview 使用离线确定性分类，不提前实现 4.A.2 的真实 LLM Router。
   - 对 internal beta 输入返回 `router_preview`，字段为 `task_type`、`confidence`、`reasoning`、`source`、`supported_task_types`。
   - `source` 固定为 `heuristic_internal_beta`。
   - 支持 task_type 集合：`lp`、`vrptw`、`prediction`、`schedule`、`inventory`、`unknown`。
   - 中文输入 `"求最短路径..."` 或包含车辆/路径/路线语义时分类为 `vrptw`。
   - LP、预测、排程、库存关键词各有确定性分类；无法识别时返回 `unknown` 且 confidence 不高于 0.4。
   - 不调用 `opticloud_shared.llm_router.complete()`、DeepSeek、Qwen、外部网络或 API key。

5. AIGC gate 对内可审计、对外隐藏。
   - 成功响应包含 `mode="internal_beta"`、`public_access=false`、`aigc_gate.status="filing_pending"`、`aigc_gate.public_surface="hidden"`。
   - 未授权/未启用路径不得返回 `aigc_gate` 字段。
   - 此 story 不调用 AIGC filter/watermark module；4.B.5/8.B 后续 story 再接入 user-visible NL output 过滤。

6. 无业务副作用。
   - 不创建 DB table、migration、Redis stream、outbox event、billing charge、optimization task、sandbox execution 或 provider request。
   - 成功响应必须显式给出 `llm_invoked=false`、`solver_invoked=false`、`sandbox_invoked=false`。
   - 测试必须离线、确定性、无需 Postgres、Redis、Docker、外部 LLM、billing/auth/solver service。

7. 验证闭环。
   - RED: `uv run pytest apps/chat-service/tests -q` 在实现前应因缺少 service/tests 失败。
   - Focused: `uv run pytest apps/chat-service/tests -q`
   - Adjacent: `uv run python scripts/validate_llm_router_contract.py` 和 `uv run pytest tests/llm_router/test_implementations_parity.py -q`
   - Static: `uv run mypy apps packages`、`uv tool run pre-commit run --all-files --show-diff-on-failure`、`git diff --check`

## Tasks / Subtasks

- [x] Task 1: Scaffold chat-service package and CI. (AC: 1, 7)
  - [x] Add `apps/chat-service/pyproject.toml`.
  - [x] Add `apps/chat-service/src/chat_service/`.
  - [x] Add focused chat-service CI job.
- [x] Task 2: Implement internal beta gate. (AC: 2, 5, 6)
  - [x] Parse env config with fail-closed defaults.
  - [x] Validate signoff, tenant, user allowlist and token.
  - [x] Ensure disabled/unauthorized paths hide AIGC/internal policy details.
- [x] Task 3: Implement NL input schema and deterministic router preview. (AC: 3, 4, 6)
  - [x] Add request/response schemas.
  - [x] Add locale detection and message excerpt behavior.
  - [x] Add deterministic keyword classifier for allowed task_type values.
- [x] Task 4: Add tests and validation records. (AC: 1-7)
  - [x] Add focused tests for health, gating, validation, classification and no side effects.
  - [x] Run focused, adjacent and static validation commands.
  - [x] Update Dev Agent Record, File List and Change Log.

### Review Follow-ups (AI)

- [x] [Review][Patch] Move request-body parsing after internal beta access gate so disabled or unauthorized callers receive sparse 404 even when the body is invalid.

## Dev Notes

### Source Context

- `_bmad-output/planning/epics.md:1512` defines Story 4.A.1 as NL input receiving plus Chat MVP Internal beta.
- `_bmad-output/planning/epics.md:772` through `776` defines CM3: Chat MVP internal beta for 课题组 + <=5 trusted scholars while AIGC filing is not public.
- `_bmad-output/planning/epics.md:2003` adds SC3: internal user pool <=5 named individuals, one staging tenant, Founder + legal sign-off.
- `_bmad-output/planning/epics.md:1516` through `1522` reserves real Router LLM and Formulator for later 4.A.2/4.A.3 stories.
- `_bmad-output/planning/architecture.md:113` says v1 normal LLM path is single DeepSeek, Qwen-Max incident only.
- `_bmad-output/planning/architecture.md:120` requires LLM mock abstraction for tests; CI must not call paid APIs.
- `_bmad-output/planning/architecture.md:3232` places M1-M3 prompts inside `apps/chat-service`, with prompt-store centralization only later.
- Story M3.8 already implemented `opticloud_shared.llm_router`; 4.A.1 must not change that contract.

### Current Repository Reality

- `apps/chat-service` currently contains only `.gitkeep`.
- `.github/workflows/ci.yml` already has a `chat_service` path filter output but no `chat-service-test` job.
- Root `pyproject.toml` workspace members do not yet include `apps/chat-service`.
- Existing service patterns:
  - `apps/sandbox-runner` is a lightweight FastAPI service with local tests and `PYTHONPATH` in CI.
  - `apps/auth-service` and `apps/solver-orchestrator` use workspace package membership and `uv sync --all-packages --extra dev`.
- `packages/shared-py/opticloud_shared/llm_router` is available for adjacent contract validation but should not be invoked by 4.A.1 runtime.

### Implementation Guidance

- Keep the classifier deterministic and small. It is an internal beta preview, not a model-quality claim.
- Keep endpoint name visibly internal: `/v1/chat/internal-beta/messages`.
- Use FastAPI `Header(...)` for internal beta headers and Pydantic models for request/response.
- Use `secrets.compare_digest()` for token comparison.
- Keep unauthorized errors sparse. Public callers should not learn whether AIGC filing, tenant, user id or token caused the rejection.
- Prefer pure functions in `gate.py` and `router_preview.py` so tests can validate without running network/services.
- Do not persist messages in this story.

### Boundary Rules

- No public Chat route.
- No SSE.
- No real LLM provider call.
- No `llm_router.complete()` call in request handling.
- No Formulator, Coder, Critic, Sandbox or Solver invocation.
- No DB migration.
- No billing or cost attribution side effect.
- No web Console Chat UI; `ChatInterface` Tier 2 belongs to 4.C.6.
- No AIGC watermark/filter runtime call; user-visible NL filtering belongs to later 4.B.5 / 8.B stories.

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

## Story Review Rounds

### Round 1 - Data Consistency (2026-05-29)

Findings applied:

- Added explicit internal beta request/response fields instead of a vague "NL input" interface.
- Pinned allowed `task_type` values and `router_preview` field names so 4.A.2 can replace internals without changing the external beta contract.
- Added locale enum and excerpt limit to avoid full prompt echo or mixed-language ambiguity.
- Required success response booleans for `llm_invoked`, `solver_invoked`, and `sandbox_invoked` so no-side-effect behavior is machine-testable.

Result: NL input, gate, router preview and no-side-effect data contracts are explicit.

### Round 2 - Function / Dependency Consistency and Drift (2026-05-29)

Findings applied:

- Kept classification heuristic-only and test-local; real LLM routing remains 4.A.2.
- Required adjacent M3.8 validator/tests to prove the existing shared LLM router contract still works without being modified.
- Added root workspace and CI requirements for `apps/chat-service` so local and GitHub validation run the same service package.
- Explicitly prohibited DB/Redis/billing/solver/sandbox dependencies to avoid premature cross-service drift.

Result: 4.A.1 opens the Chat service without duplicating or bypassing M3.8 and without creating hidden runtime dependencies.

### Round 3 - Boundary / Edge Cases / Closure (2026-05-29)

Findings applied:

- Added fail-closed defaults, signoff gate, one staging tenant, max 5 users and sparse unauthorized errors.
- Added disabled path behavior that hides AIGC filing status from public callers.
- Added validation for blank/short/long messages, unsupported locale, unauthorized tenant/user/token and over-sized allowlist.
- Added focused, adjacent, static and diff-check closure commands.

Result: public exposure, AIGC gating, access boundaries and validation closure are explicit before implementation.

## Dev Agent Record

### Agent Model Used

GPT-5

### Debug Log References

- 2026-05-29 - Story 4.A.1 draft created from sprint status, Epic 4.A, CM3/SC3 internal beta requirements, Architecture Chat/LLM constraints, M3.8 LLM router story, and current `apps/chat-service` skeleton.
- 2026-05-29 - Story review Round 1 completed and applied: stable request/response data contract, task_type set, locale/excerpt and no-side-effect flags.
- 2026-05-29 - Story review Round 2 completed and applied: heuristic-only router preview, M3.8 adjacent validation, workspace/CI requirement, no new cross-service dependencies.
- 2026-05-29 - Story review Round 3 completed and applied: fail-closed access gate, hidden public AIGC status, boundary validation and closure commands.
- 2026-05-29 - RED phase completed: focused chat-service tests failed because `apps/chat-service/tests` did not exist; story and sprint status moved to in-progress.
- 2026-05-29 - Implemented minimal FastAPI chat-service package with `/health` and internal-only `/v1/chat/internal-beta/messages`.
- 2026-05-29 - Added fail-closed internal beta env config, tenant/user/token gate, sparse 404 unauthorized behavior, deterministic router preview, response no-side-effect flags, workspace membership, lockfile update and chat-service CI job.
- 2026-05-29 - Focused validation passed: `uv run pytest apps/chat-service/tests -q` -> 20 passed.
- 2026-05-29 - Adjacent validation passed: `uv run python scripts/validate_llm_router_contract.py` -> `llm router contract OK`; `uv run pytest tests/llm_router/test_implementations_parity.py -q` -> 14 passed.
- 2026-05-29 - Static validation passed: `uv run mypy apps packages`; `uv tool run pre-commit run --all-files --show-diff-on-failure`; `git diff --check`.
- 2026-05-29 - Post-implementation code review found and fixed one boundary leak: request body validation now occurs only after the internal beta gate accepts tenant/user/token.
- 2026-05-29 - GitHub CI lint follow-up: changed empty-token check from string literal comparison to truthiness to satisfy Linux Bandit B105 without changing fail-closed behavior.

### Implementation Plan

- Scaffold `apps/chat-service` as a minimal FastAPI package.
- Implement fail-closed internal beta config and header gate.
- Implement Pydantic request/response schemas and deterministic task_type preview classifier.
- Add focused tests and CI job, then run focused/adjacent/static validations.

### Completion Notes List

- Implemented `apps/chat-service` as a FastAPI workspace package with local pytest config and CI coverage.
- Added `GET /health` and `POST /v1/chat/internal-beta/messages`; no public chat route, SSE, solver, sandbox, billing, DB, Redis or external LLM provider calls were added.
- Internal beta access defaults fail closed and requires `CHAT_INTERNAL_BETA_ENABLED=true`, `CHAT_INTERNAL_BETA_SIGNOFF=founder-legal-approved`, the single staging tenant, <=5 configured named users, `X-Internal-Beta-User` and a constant-time token comparison.
- Unauthorized, disabled, misconfigured and over-allowlist paths return sparse 404 without `aigc_gate` or allowlist details, including when the request body itself is invalid.
- NL input validation enforces trimmed message length 2-2000, locale enum, forbidden extra fields, deterministic locale detection and bounded excerpts that do not echo the full prompt.
- Router preview is deterministic heuristic-only and returns only `lp`, `vrptw`, `prediction`, `schedule`, `inventory` or `unknown`; M3.8 `opticloud_shared.llm_router.complete()` remains untouched.
- Successful responses expose `mode="internal_beta"`, `public_access=false`, filing-pending hidden AIGC gate and explicit `llm_invoked=false`, `solver_invoked=false`, `sandbox_invoked=false`.

### Senior Developer Review (AI)

Review date: 2026-05-29

Outcome: Approve after fixes.

Review layers executed locally: data/contract consistency, function/dependency drift, boundary/edge cases, acceptance closure. External subagent spawning was not used because the available multi-agent tool requires explicit user authorization for delegation.

Findings:

- [x] Patch - Disabled or unauthorized callers could have received request schema validation errors before the handler-level gate ran, revealing the internal route shape. Fixed by moving JSON/body model validation inside the endpoint after `validate_internal_beta_access(...)`, then adding regressions for disabled and bad-token callers with invalid bodies.

Validation after review fix:

- `uv run pytest apps/chat-service/tests -q` -> 20 passed.
- `uv run ruff check apps/chat-service --fix` -> passed.
- `uv run ruff format apps/chat-service` -> passed.
- `uv run python scripts/validate_llm_router_contract.py` -> `llm router contract OK`.
- `uv run pytest tests/llm_router/test_implementations_parity.py -q` -> 14 passed.
- `uv run mypy apps packages` -> success, no issues found in 97 source files.
- `uv tool run pre-commit run --all-files --show-diff-on-failure` -> passed.
- `git diff --check` -> passed.
- GitHub PR #93 first run: all checks passed except `lint`; lint failure was Bandit B105 on empty-token comparison in `config.py` and was patched.

### File List

- `.github/workflows/ci.yml`
- `_bmad-output/stories/4-a-1-nl-chat-input-internal-beta.md`
- `_bmad-output/stories/sprint-status.yaml`
- `apps/chat-service/pyproject.toml`
- `apps/chat-service/src/chat_service/__init__.py`
- `apps/chat-service/src/chat_service/config.py`
- `apps/chat-service/src/chat_service/gate.py`
- `apps/chat-service/src/chat_service/main.py`
- `apps/chat-service/src/chat_service/router_preview.py`
- `apps/chat-service/src/chat_service/schemas.py`
- `apps/chat-service/tests/test_internal_beta.py`
- `pyproject.toml`
- `uv.lock`

### Change Log

- 2026-05-29 - Initial Story 4.A.1 created and reviewed through three pre-implementation rounds; sprint status moved from backlog to ready-for-dev.
- 2026-05-29 - Dev implementation started; status moved to in-progress after RED focused test failure.
- 2026-05-29 - Implemented internal beta chat-service entrypoint with fail-closed gate, deterministic router preview, focused CI and offline tests.
- 2026-05-29 - Addressed post-implementation review finding by gating before request body validation; story marked done after focused, adjacent, static, pre-commit and diff-check validation passed.
- 2026-05-29 - Addressed GitHub CI Bandit lint finding on empty-token comparison; no behavior change.
