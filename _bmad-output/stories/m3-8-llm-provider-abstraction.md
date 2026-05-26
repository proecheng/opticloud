# Story M3.8: LLM Provider Abstraction Layer

Status: done

owner: Architect / Chat Platform

## Story

As a Chat Platform engineer,
I want a provider-agnostic LLM router contract with stable Prompt / Completion schemas, three offline-testable provider implementations, deterministic incident fallback behavior, and behavior parity evidence,
so that future Chat and NL agents can switch from DeepSeek primary to Qwen-Max incident fallback without schema drift, hidden live API dependencies, or fabricated provider-quality claims.

## Acceptance Criteria

1. Provider-agnostic Prompt / Completion schemas are the canonical contract for M3.8.
   - Add Pydantic v2 schemas under `packages/shared-py/opticloud_shared/llm_router/`.
   - `Prompt` must validate a non-empty ordered message list with roles limited to `system`, `user`, `assistant`, or `tool`.
   - `Prompt` must carry stable metadata: `prompt_id`, `task`, `locale`, `response_schema`, and `metadata`.
   - `Completion` must normalize provider output into one shape with `text`, `model`, `provider`, `finish_reason`, `usage`, `latency_ms`, and `raw_response_redacted`.
   - `CompletionUsage` must expose `prompt_tokens`, `completion_tokens`, and `total_tokens`, with `total_tokens` equal to the two token counts.
   - Schemas must reject blank messages, unsupported roles, negative token counts, secret-like metadata keys, raw API keys, bearer tokens, cookies, provider request payloads, and unredacted provider response payloads.
   - `raw_response_redacted` must allow only small diagnostic metadata such as logical alias, provider ID, fallback reason, finish reason, and deterministic hashes. It must reject nested raw provider payloads.
   - The schema contract must not depend on `apps/chat-service`, a database, Redis, Docker, cloud credentials, or live provider APIs.

2. `llm_router.complete(prompt: Prompt, model: str) -> Completion` is exposed as the shared API.
   - Export `Prompt`, `PromptMessage`, `Completion`, `CompletionUsage`, `LLMRouter`, `LLMProvider`, `ModelConfig`, `ProviderConfig`, `LLMRouterError`, and `complete` from `opticloud_shared.llm_router`.
   - `complete(prompt, model="deepseek-v3.5")` must return a `Completion`.
   - Unknown model aliases must fail closed with `LLMRouterError` and must not silently fall back.
   - Provider exceptions, malformed provider envelopes, and missing normalized text must raise `LLMRouterError` with a redacted diagnostic message.
   - `complete()` must never return provider-specific response classes or raw dicts.
   - The default router must be deterministic and offline. It must not read provider API keys or open network connections during tests.
   - The API must support explicit router injection for future `apps/chat-service` use, but this story must not create production Chat runtime endpoints.

3. Exactly three provider implementations are available behind one interface.
   - Implement `MockLLMProvider`, `DeepSeekCompatibleProvider`, and `QwenCompatibleProvider`.
   - Canonical provider IDs must be exactly `mock`, `deepseek-compatible`, and `qwen-compatible`.
   - Canonical implementation IDs must be exactly `mock-deterministic`, `deepseek-openai-compatible`, and `qwen-openai-compatible`.
   - Each provider must implement the same `LLMProvider.complete(prompt, model_config) -> Completion` protocol.
   - DeepSeek and Qwen providers must be OpenAI-compatible adapters with injectable transport or deterministic offline transport.
   - OpenAI-compatible response normalization must read from `choices[0].message.content` for chat envelopes and `choices[0].text` for completion-style envelopes.
   - Finish reasons must normalize to one of `stop`, `length`, `content_filter`, or `error`.
   - Usage fields must be computed from provider envelope usage when present, or deterministically estimated from prompt/completion tokens when absent.
   - Tests must prove all three providers return schema-compatible `Completion` objects for the same prompt.
   - Tests must prove the DeepSeek/Qwen adapters normalize OpenAI-compatible response envelopes into the same `Completion` schema.
   - DeepSeek/Qwen adapter constructors must accept base URLs and API-key provider callables for future use, but default tests must use offline transports and must not read environment variables.
   - CI must not call DeepSeek, DashScope, Model Studio, OpenAI, Anthropic, or any external LLM provider.

4. Logical model aliases prevent provider model-name drift.
   - `deepseek-v3.5` is a logical project alias for the v1 primary path, not a hard guarantee about the current provider model string.
   - `qwen-max` is a logical project alias for the incident fallback path, not proof that the provider catalog cannot change.
   - Add a model registry that maps aliases to provider IDs and provider model names.
   - The registry must include `deepseek-v3.5`, `qwen-max`, and `mock-deterministic`.
   - The canonical alias mapping must be: `deepseek-v3.5 -> deepseek-compatible`, `qwen-max -> qwen-compatible`, and `mock-deterministic -> mock`.
   - Each registry entry must include `alias`, `provider_id`, `provider_model`, `implementation_id`, `request_timeout_ms`, `max_output_tokens`, `is_fallback_eligible`, and `notes`.
   - The committed default registry may include current known OpenAI-compatible provider endpoints, but tests must assert aliases and schema behavior rather than live provider reachability.
   - Tests must reject alias drift, duplicate aliases, missing providers, missing model names, and unsupported provider IDs.

5. Simulated DeepSeek incident fallback preserves schema and output shape.
   - Add a deterministic incident mode that routes a `deepseek-v3.5` logical request to `qwen-max` when the primary provider is marked unavailable by explicit configuration.
   - Incident fallback must be opt-in and explicit; normal calls to `deepseek-v3.5` must not automatically use Qwen unless incident mode is configured.
   - Incident mode must record a redacted fallback reason in `Completion.raw_response_redacted` without exposing provider payloads, keys, URLs with credentials, or user PII.
   - Fallback completions must keep the same `Completion` schema and usage semantics.
   - The returned `Completion.model` must report the logical model actually used (`qwen-max`) and `Completion.provider` must report the fallback provider.
   - The fallback path must not claim normal multi-LLM routing or customer-facing SLO improvement.

6. Behavior parity is deterministic, offline, and pinned to 100 reference prompts.
   - Add exactly 100 reference prompts for M3.8 under `tools/llm_router/reference_prompts_v1.json`.
   - The prompt fixture must include `dataset_version=llm_router_reference_prompts_v1`, `source_story=M3.8`, `prompt_count=100`, and `prompts`.
   - Prompt IDs must be stable, unique, sorted, and use the pattern `llm-router-ref-001` through `llm-router-ref-100`.
   - The 100 prompts must be distributed exactly 20 each across `router_intent`, `formulator_extraction`, `coder_generation`, `critic_validation`, and `mixed_language_summary`.
   - Add parity logic that runs the same 100 prompts through DeepSeek-compatible and Qwen-compatible offline implementations.
   - Similarity must use cosine similarity over deterministic token vectors implemented with the Python standard library.
   - Deterministic provider outputs must be prompt-derived and task-aware. They may not be one identical canned sentence for all prompts.
   - The parity report must include output hashes or redacted output summaries for both compared aliases so tests can detect global canned-output shortcuts.
   - Every prompt pair must have cosine similarity `>= 0.85`; the aggregate report must include count, minimum, average, maximum, threshold, and per-prompt deviations.
   - The deterministic example report must be committed under `tools/llm_router/parity_report.example.json`.
   - The report must include `report_version=llm_router_behavior_parity_v1`, `source_story=M3.8`, `example_only=true`, `reference_prompts_sha256`, `primary_alias=deepseek-v3.5`, `fallback_alias=qwen-max`, `prompt_count=100`, `threshold=0.85`, `minimum_similarity`, `average_similarity`, `maximum_similarity`, `passed`, and ordered per-prompt `deviations`.
   - `reference_prompts_sha256` in the report must match the canonical SHA-256 of `tools/llm_router/reference_prompts_v1.json`.
   - The report must be labeled as offline deterministic parity evidence, not real provider-quality evidence.

7. Validator and tests close data consistency, function drift, and boundary gaps.
   - Add `scripts/validate_llm_router_contract.py`.
   - Add `tests/llm_router/test_implementations_parity.py`.
   - The validator must check registry aliases, canonical provider IDs, implementation IDs, provider count, reference prompt count, prompt task distribution, prompt ID order/uniqueness, report schema, prompt fixture hash binding, similarity threshold, example-only boundaries, forbidden secrets, and offline-only behavior.
   - Tests must cover positive validation and negative cases for unknown alias, provider count drift, missing implementation, schema drift, prompt count drift, duplicate prompt IDs, below-threshold parity, global canned-output parity, malformed OpenAI-compatible envelopes, provider exception redaction, fake real-provider evidence claims, and unsafe metadata.
   - Tests must prove no external HTTP client is needed to satisfy M3.8.
   - Validator/tests must reject committed parity reports that set `example_only=false`, claim live provider evaluation, include API keys, include customer prompts, include raw provider payloads, or point to generated reports under `reports/**`.

8. Runbook and CI make the abstraction operational without live providers.
   - Add `docs/runbooks/llm-provider-abstraction.md`.
   - The runbook must describe logical aliases, default offline mode, future live-provider injection, incident fallback boundaries, parity report interpretation, redaction rules, and failure response.
   - The runbook must state that CI validates schemas/adapters/offline parity only and does not prove real DeepSeek/Qwen semantic equivalence.
   - The runbook must define failure handling: schema drift, alias drift, parity below threshold, unsafe metadata, or accidental live-provider dependency blocks the PR until fixed.
   - Future real provider parity, if needed, must be introduced by a separate operator evidence story/PR with redaction review; M3.8 commits only deterministic offline evidence.
   - Extend `.github/workflows/ci.yml` with an `llm_router` path filter and a focused validation job.
   - CI must run the validator and `pytest tests/llm_router/test_implementations_parity.py` without provider keys, network, paid APIs, Docker, database, Redis, or `apps/chat-service`.

9. Workflow tracking and boundaries are explicit.
   - This story records three pre-implementation story review rounds and fixes after each round before implementation.
   - `_bmad-output/stories/sprint-status.yaml` moves `m3-8-llm-provider-abstraction` to `ready-for-dev` only after all three story review rounds pass.
   - During implementation, move the story through `in-progress`, `code-review`, and `done` only when corresponding gates pass.
   - This story must not implement production Chat endpoints, SSE streaming, real provider API calls, API key management, Provider Health UI, automatic SLO-changing multi-LLM routing, or real incident evidence.
   - This story must not commit generated files under `reports/**`, pytest caches, `__pycache__`, live-provider logs, environment files, provider request/response captures, or customer/user prompts.
   - Final completion must update the Dev Agent Record, file list, validation evidence, post-implementation review findings/fixes, and sprint status.

## Tasks / Subtasks

- [x] Build shared schemas and public API. (AC: 1, 2)
  - [x] Add `packages/shared-py/opticloud_shared/llm_router/` package.
  - [x] Implement Prompt / Completion / usage schemas and public exports.
  - [x] Provide deterministic default `complete(prompt, model)` API.
- [x] Build provider registry and three implementations. (AC: 3, 4, 5)
  - [x] Implement model/provider config registry with logical aliases.
  - [x] Implement `MockLLMProvider`, `DeepSeekCompatibleProvider`, and `QwenCompatibleProvider`.
  - [x] Implement explicit incident fallback configuration.
- [x] Build reference prompt and parity assets. (AC: 6)
  - [x] Add `tools/llm_router/reference_prompts_v1.json` with exactly 100 prompts.
  - [x] Add deterministic parity computation.
  - [x] Add `tools/llm_router/parity_report.example.json`.
- [x] Add validator and tests. (AC: 7)
  - [x] Add `scripts/validate_llm_router_contract.py`.
  - [x] Add `tests/llm_router/test_implementations_parity.py`.
  - [x] Cover schema, alias, provider, fallback, parity, and boundary failures.
- [x] Add runbook and CI wiring. (AC: 8)
  - [x] Add `docs/runbooks/llm-provider-abstraction.md`.
  - [x] Add `llm_router` path filter and focused CI validation job.
- [x] Update workflow records and validation evidence. (AC: 9)
  - [x] Record implementation notes, file list, change log, validation commands, and code review fixes.
  - [x] Move sprint status only after gates pass.

## Dev Notes

### Source Context

- `_bmad-output/planning/epics.md:339` adds M3.8 for DeepSeek/Qwen-Max prompt/schema abstraction, mock, and LLM router agnostic interface.
- `_bmad-output/planning/epics.md:1212` through `1221` define M3.8 acceptance criteria: `llm_router.complete`, three implementations, Prompt / Completion schemas, DeepSeek incident simulation to Qwen-Max, and 100-prompt behavior parity with cosine similarity `>= 0.85`.
- `_bmad-output/planning/epics.md:1518` states future Epic 4.A.2 Router LLM depends on M3.8 and expects normalized structured output such as `{"task_type":"vrptw","confidence":0.92,"reasoning":"..."}`.
- `_bmad-output/planning/epics.md:1966` maps CRG10 to M3.8 behavior parity cosine similarity `>= 0.85`.
- `_bmad-output/planning/prd.md:514` states v1 normal LLM path is single DeepSeek and Qwen-Max is incident emergency fallback only, not normal SLO.
- `_bmad-output/planning/prd.md:796` defines DeepSeek primary, Qwen-Max incident fallback, and GPT/Claude/self-hosted options as later.
- `_bmad-output/planning/prd.md:1372` states v1 does not do full multi-LLM switching.
- `_bmad-output/planning/architecture.md:113` states LLM Router is single DeepSeek with Qwen-Max incident emergency only.
- `_bmad-output/planning/architecture.md:120`, `633` require LLM mock abstraction in test environments because CI must not call paid APIs or heavy compute.
- `_bmad-output/planning/architecture.md:1326` describes `chat-service` as future M3 runtime context; this repo does not yet have a production `apps/chat-service`.

### Previous Story Intelligence

- M3.6a explicitly required Chat load CI to avoid external LLM APIs and did not implement runtime Chat/provider fallback.
- M3.6c created a DeepSeek-to-Qwen incident drill contract but explicitly deferred provider abstraction/runtime router to M3.8.
- M2.3 established the pattern for service-agnostic shared Python substrate when the consuming service does not yet exist.
- M3.7 established the current pattern: static contract assets, validator, negative tests, runbook, CI gate, three pre-implementation story review rounds, then post-implementation code review and fixes.

### Architecture / External Constraints

- Implementation belongs in `packages/shared-py/opticloud_shared/llm_router/` and tests under `tests/llm_router/`.
- Do not create `apps/chat-service` or production endpoints in this story.
- Use Pydantic v2, stdlib JSON/path/hash/math utilities, and existing repo tooling. Do not add new dependencies unless a failing gate proves they are required.
- DeepSeek official docs describe an OpenAI-compatible API base URL and current model names while also marking older `deepseek-chat` / `deepseek-reasoner` names for deprecation on 2026-07-24; therefore implementation must use project logical aliases plus configurable provider model names.
- Alibaba Cloud Model Studio official docs describe OpenAI-compatible APIs with region-specific DashScope base URLs and current Qwen flagship model families; therefore implementation must not hard-code one endpoint as the only valid Qwen truth.
- Treat all provider facts as configuration defaults for request construction and normalization, not live reachability assertions.

### File Structure Requirements

- `packages/shared-py/opticloud_shared/llm_router/` for schemas, providers, router, registry, and parity logic.
- `tests/llm_router/` for M3.8 top-level acceptance/contract tests, matching the epic validated outcome.
- `tools/llm_router/` for reference prompt fixture and deterministic example parity report.
- `scripts/validate_llm_router_contract.py` for standalone static validation.
- `docs/runbooks/llm-provider-abstraction.md` for operator/developer guidance.
- `.github/workflows/ci.yml` for path filter and focused validation job.

### Testing / Validation Notes

Expected local commands after implementation:

```bash
uv run python scripts/validate_llm_router_contract.py
uv run pytest tests/llm_router/test_implementations_parity.py -q
uv run ruff check packages/shared-py/opticloud_shared/llm_router tests/llm_router scripts/validate_llm_router_contract.py
uv run ruff format --check packages/shared-py/opticloud_shared/llm_router tests/llm_router scripts/validate_llm_router_contract.py
uv run mypy packages/shared-py/opticloud_shared/llm_router
uv run pre-commit run --all-files --show-diff-on-failure
git diff --check
```

If the full monorepo pytest suite is attempted, record existing collection/PYTHONPATH failures separately from M3.8 scoped gates.

### Risks / Decisions

- Data consistency risk: registry aliases, provider IDs, reference prompt IDs, report schema, tests, runbook, and CI filters can drift. Validator must pin canonical values.
- Function consistency risk: DeepSeek/Qwen adapters might return provider-specific fields or inconsistent usage semantics. Tests must assert normalized `Completion` objects.
- Drift risk: logical alias `deepseek-v3.5` can be confused with a live provider model string. The code must keep aliases separate from provider model names.
- Boundary risk: CI might accidentally require real API keys or network. Tests and validator must run offline and reject fake real-provider claims.
- Closure risk: deterministic parity evidence can be misrepresented as real provider quality evidence. Report/runbook/story must label it as offline deterministic parity only.

## Story Review Log

### Round 1: Data Consistency Review

Findings fixed:
- Added canonical provider IDs and implementation IDs so the three implementations cannot drift by class naming or ad hoc provider strings.
- Added exact logical alias mapping from `deepseek-v3.5`, `qwen-max`, and `mock-deterministic` to provider IDs.
- Added required registry fields so alias, provider model name, fallback eligibility, timeout, token budget, and explanatory notes share one data vocabulary.
- Added prompt fixture metadata, exact prompt ID pattern, and exact 20/20/20/20/20 task distribution for the 100 reference prompts.
- Added parity report schema fields and `reference_prompts_sha256` binding so the report cannot drift from the committed fixture.
- Expanded validator requirements to cover provider IDs, implementation IDs, prompt task distribution, and prompt hash binding.

Status: PASS after fixes.

### Round 2: Function Consistency / Drift Review

Findings fixed:
- Added explicit `LLMRouterError` behavior for provider exceptions, malformed provider envelopes, and missing normalized text so provider failures cannot leak raw payloads or return partial dicts.
- Required `complete()` to always return `Completion`, never provider-specific classes or raw dictionaries.
- Pinned OpenAI-compatible normalization paths for chat-style and completion-style envelopes, including finish-reason normalization and deterministic usage estimation.
- Added redacted incident fallback reason recording so fallback behavior is observable without leaking provider payloads or secrets.
- Added a guard against identical canned parity output by requiring prompt-derived, task-aware deterministic outputs and per-alias output hashes or redacted summaries.
- Expanded tests to catch malformed envelopes, provider exception redaction, and global canned-output parity shortcuts.

Status: PASS after fixes.

### Round 3: Boundary / Closure Review

Findings fixed:
- Restricted `raw_response_redacted` to small diagnostic metadata and deterministic hashes so raw provider envelopes cannot be smuggled into the normalized schema.
- Required DeepSeek/Qwen adapter constructors to support future base URL/API-key injection while keeping tests offline and environment-variable-free.
- Added validator/test rejection for `example_only=false`, live-provider claims, API keys, customer prompts, raw provider payloads, and generated `reports/**` artifacts.
- Added runbook failure handling for schema drift, alias drift, parity failures, unsafe metadata, and accidental live-provider dependencies.
- Clarified that real provider parity evidence belongs to a separate future operator evidence PR, not this deterministic offline contract.
- Explicitly forbade committing caches, live-provider logs, environment files, provider captures, and customer/user prompts.
- Reaffirmed final bookkeeping requirements for Dev Agent Record, validation evidence, post-implementation code review fixes, and sprint status.

Status: PASS after fixes. Story is ready for development.

## Dev Agent Record

### Implementation Notes

- Added `opticloud_shared.llm_router` with Pydantic Prompt / Completion schemas, redacted diagnostics, canonical model/provider configs, deterministic router API, three providers, OpenAI-compatible envelope normalization, and explicit DeepSeek-to-Qwen incident fallback.
- Added deterministic offline parity utilities with stdlib token-vector cosine similarity and prompt-derived task-aware provider outputs. The committed 100-prompt report has minimum similarity `0.909122`, average `0.918107`, and no global canned-output shortcut.
- Added 100 reference prompts under `tools/llm_router/`, split exactly 20 each across router intent, formulator extraction, coder generation, critic validation, and mixed-language summary.
- Added standalone validator covering canonical aliases/providers, fixture count/order/distribution, parity report hash binding, threshold, example-only boundary, forbidden live-provider claims, and canned-output detection.
- Added focused acceptance tests for schemas, registry, three providers, OpenAI-compatible normalization, provider error redaction, incident fallback, prompt fixture, parity report, validator drift cases, and no live provider dependency.
- Wired `.github/workflows/ci.yml` with `llm_router` path filtering and a focused validation job using `PYTHONPATH=packages/shared-py`.
- Added runbook documenting offline mode, logical aliases, future live-provider injection, incident fallback boundary, parity interpretation, and failure response.
- CI lint follow-up: removed per-prompt hash/digest fields from parity evidence and used prompt-ID-prefixed redacted output summary uniqueness for canned-output detection, avoiding high-entropy secret-scan false positives; added a narrow detect-secrets exclusion for the public reference prompt fixture SHA-256.

### File List

- `.github/workflows/ci.yml`
- `_bmad-output/stories/m3-8-llm-provider-abstraction.md`
- `_bmad-output/stories/sprint-status.yaml`
- `docs/runbooks/llm-provider-abstraction.md`
- `packages/shared-py/opticloud_shared/__init__.py`
- `packages/shared-py/opticloud_shared/llm_router/__init__.py`
- `packages/shared-py/opticloud_shared/llm_router/parity.py`
- `packages/shared-py/opticloud_shared/llm_router/providers.py`
- `packages/shared-py/opticloud_shared/llm_router/registry.py`
- `packages/shared-py/opticloud_shared/llm_router/router.py`
- `packages/shared-py/opticloud_shared/llm_router/schemas.py`
- `scripts/validate_llm_router_contract.py`
- `tests/llm_router/test_implementations_parity.py`
- `tools/llm_router/parity_report.example.json`
- `tools/llm_router/reference_prompts_v1.json`

### Validation Evidence

- `uv run pytest tests\llm_router\test_implementations_parity.py -q` -> RED confirmed before implementation: `ModuleNotFoundError: No module named 'opticloud_shared'`.
- `uv run python scripts\validate_llm_router_contract.py` -> PASS (`llm router contract OK`)
- `uv run pytest tests\llm_router\test_implementations_parity.py -q` -> PASS (14 passed)
- `uv run ruff check packages\shared-py\opticloud_shared\llm_router tests\llm_router scripts\validate_llm_router_contract.py` -> PASS
- `uv run ruff format --check packages\shared-py\opticloud_shared\llm_router tests\llm_router scripts\validate_llm_router_contract.py` -> PASS
- `uv run mypy packages\shared-py\opticloud_shared\llm_router` -> PASS
- `uv run pytest tests\llm_router\test_implementations_parity.py::test_provider_errors_and_malformed_envelopes_are_redacted -q` -> RED during code review before fix: provider exception redaction missed bearer/cookie text.
- `uv run pytest tests\llm_router\test_implementations_parity.py::test_provider_errors_and_malformed_envelopes_are_redacted -q` -> PASS after code review redaction fix.
- `uv run pytest packages\shared-py\tests -q` -> PASS (32 passed)
- `uv run mypy apps packages` -> PASS
- `uv run pre-commit run --all-files --show-diff-on-failure` -> PASS
- `git diff --check` -> PASS
- `uv run pytest -q` -> FAIL due to existing monorepo collection/PYTHONPATH issues: duplicate `tests.conftest` imports across app packages, missing service package import roots such as `sandbox_runner`, missing `opticloud`, and top-level `tests.*` import mismatches. M3.8 scoped tests and configured CI job pass.
- `uv run python scripts\validate_llm_router_contract.py` -> PASS after CI lint follow-up.
- `uv run pytest tests\llm_router\test_implementations_parity.py -q` -> PASS (14 passed) after CI lint follow-up.
- `uv run ruff check packages\shared-py\opticloud_shared\llm_router tests\llm_router scripts\validate_llm_router_contract.py` -> PASS after CI lint follow-up.
- `uv run ruff format --check packages\shared-py\opticloud_shared\llm_router tests\llm_router scripts\validate_llm_router_contract.py` -> PASS after CI lint follow-up.
- `uv run pre-commit run --all-files --show-diff-on-failure` -> PASS after CI lint follow-up.
- `uv run python scripts\validate_llm_router_contract.py` -> PASS after replacing parity output hashes/digests with summary uniqueness.
- `uv run pytest tests\llm_router\test_implementations_parity.py -q` -> PASS (14 passed) after replacing parity output hashes/digests with summary uniqueness.
- `uv run ruff check packages\shared-py\opticloud_shared\llm_router tests\llm_router scripts\validate_llm_router_contract.py` -> PASS after replacing parity output hashes/digests with summary uniqueness.
- `uv run ruff format --check packages\shared-py\opticloud_shared\llm_router tests\llm_router scripts\validate_llm_router_contract.py` -> PASS after replacing parity output hashes/digests with summary uniqueness.
- `uv run pre-commit run --all-files --show-diff-on-failure` -> PASS after replacing parity output hashes/digests with summary uniqueness.

## Senior Developer Review (AI)

Review date: 2026-05-26

Outcome: Approved after fix

Findings fixed:
- Provider exception redaction was incomplete. `_redact()` masked `sk-` and `api_key` patterns but allowed bearer authorization and cookie fragments to appear in `LLMRouterError` text. Added a failing regression covering `Authorization: Bearer ...` and `cookie=...`, then expanded redaction patterns in `providers.py`.
- CI lint flagged per-prompt output hash/digest values in deterministic parity evidence as high-entropy strings. Removed per-prompt hash/digest fields, used prompt-ID-prefixed redacted output summaries for canned-output detection, and kept only the reference fixture SHA-256 with an explicit public-hash exclusion.

Residual risk:
- M3.8 parity evidence is intentionally deterministic offline evidence. It does not prove live DeepSeek/Qwen semantic equivalence; future real provider evidence must be handled by a separate redacted operator evidence PR.

### Change Log

- 2026-05-26: Initial draft created for M3.8 story context.
- 2026-05-26: Completed three pre-implementation story review rounds and moved story to ready-for-dev.
- 2026-05-26: Started implementation and moved story to in-progress.
- 2026-05-26: Implemented shared LLM router schemas/providers/registry/parity, 100-prompt fixture, validator, runbook, CI job, and scoped validation evidence; moved story to code-review.
- 2026-05-26: Completed post-implementation code review, fixed provider exception redaction gap, and moved story to done.
- 2026-05-26: Fixed PR CI lint false positive by removing per-prompt parity output hash/digest fields, using prompt-ID-prefixed summary uniqueness for canned-output detection, and allowlisting the public reference fixture SHA-256.
