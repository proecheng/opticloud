# Story 4.A.6: G6 Chat 延迟预算压测验证 (联动 Story M3.6abc)

Status: done

owner: Chat Platform / SRE / NFR-P owner

## Story

作为 Chat Platform 与 SRE 负责人，
我希望 Epic 4.A internal beta Chat 链路与 M3.6a 5 节点 staging 压测证据契约形成可验证闭环，
以便 G6 Chat 延迟预算 hard-gate 只能由真实 staging evidence 解锁，而不会被 internal beta JSON preview、single-node baseline、incident fallback drill 或示例 manifest 误判为已通过。

## Acceptance Criteria

1. 4.A.6 明确连接当前 Chat internal beta 链路与 M3.6a staging hard-gate。
   - 当前代码现实只暴露 `POST /v1/chat/internal-beta/messages` 和 `GET /health`；4.A.6 不得新增公开 `/v1/chat`、`/v1/chat/stream`、SSE、conversation persistence、Console Chat UI、frontend、DB/Redis/outbox/billing/cost telemetry、Critic、Solver、Sandbox 或 AIGC filter runtime。
   - 4.A.6 必须记录当前 Chat 链路已覆盖 Router -> Formulator -> Coder -> Language preview，但不得声称该 internal beta JSON endpoint 等同于 M3.6a 的 staging SSE endpoint。
   - 4.A.6 的验证资产必须把 M3.6a 作为唯一 G6 staging hard-gate evidence source；M3.6b single-node 只能是 advisory tuning reference，M3.6c incident fallback 只能是 drill evidence。
   - `provider_request_sent=false`、`solver_invoked=false`、`sandbox_invoked=false`、`public_access=false`、`aigc_gate.public_surface=hidden` 必须继续作为 internal beta response 边界，不得为了压测验证而改变。

2. 新增一个机器可校验的 G6 latency validation contract。
   - Add `tools/chat_load/g6_chat_latency_validation.json` with `dataset_version="g6_chat_latency_validation_v1"` and `source_story="4.A.6"`。
   - Contract 必须包含：
     - `linked_hard_gate_story="M3.6a"`。
     - `current_internal_beta_endpoint="/v1/chat/internal-beta/messages"`。
     - `target_staging_sse_endpoint="/v1/chat/stream"`。
     - `g6_status="requires_real_staging_evidence"`。
     - `real_evidence_required=true`。
     - `hard_gate_pass=false`。
     - `required_evidence_manifest="reports/chat-load/<run_id>/evidence_manifest.json"`。
     - `required_validator_mode="--evidence"`。
     - `required_profiles=["baseline","stress","soak"]`。
     - `required_story_chain=["4.A.1","4.A.2","4.A.3","4.A.4","4.A.5","M3.6a","M3.6b","M3.6c"]`。
   - Contract 必须复用 `tools/chat_load/prompts_v1.json` 的 canonical SHA-256；不得复制第二套 prompt fixture。
   - Contract 必须 pin G6 hard-gate thresholds：first-token P95 `< 3000 ms`、streaming `>= 20 token/s`、E2E solve P95 `<= 90000 ms`。
   - Contract 必须 pin stress profile 为 100 concurrent users / 1800 seconds / 100 RPS，并和 `tools/chat_load/staging_profiles.json` 保持一致。
   - Contract 必须列出 internal beta response flag invariants：`public_access=false`、`provider_request_sent=false`、`solver_invoked=false`、`sandbox_invoked=false`、`aigc_public_surface="hidden"`。
   - Contract 必须显式禁止 `example_only=true` evidence、single-node evidence、incident fallback evidence 或 docs-only checklist 解锁 G6。

3. Static validator 必须覆盖 4.A.6 contract，并防止数据/函数漂移。
   - Extend `scripts/validate_chat_load_plan.py` default validation to load and validate `tools/chat_load/g6_chat_latency_validation.json`。
   - Validator 必须检查 G6 contract 的 metadata、story chain、endpoint vocabulary、evidence path/mode、profile set、stress 100 concurrent users、hard-gate thresholds、prompt fixture hash、internal beta response flag invariants 和 blocked unlock sources。
   - Validator 必须 reject：
     - `hard_gate_pass=true` 或任意嵌套 hard-gate/staging pass claim。
     - `g6_status` 被改成 `passed`、`ready` 或其他非 `requires_real_staging_evidence` 值。
     - 使用 `reports/chat-single-node/**`、`reports/chat-incident-fallback/**`、example manifest 或 docs-only checklist 作为 G6 unlock source。
     - threshold 单位漂移，例如把 `first_token_p95_max_ms` 改成秒字段或数值不是 `3000`。
     - profile set、stress users、target RPS、run time 与 M3.6a drift。
     - prompt hash 与 `prompts_v1.json` drift。
   - Existing M3.6a/M3.6b/M3.6c validator behavior must remain unchanged.

4. Tests 先红后绿，覆盖 G6 closure boundary。
   - Add tests to `tests/test_chat_load_plan.py` for valid G6 contract and negative drift cases。
   - Negative tests must cover hard-gate pass claim, wrong evidence path source, threshold drift, prompt hash drift, and stress profile drift。
   - Add focused Chat service regression covering that an authorized internal beta response still has the required G6 response flags and does not expose provider/raw/pass-evidence fields。
   - The tests must not require Kubernetes, Grafana, Locust runtime against a live service, staging URL, cloud credentials, external network, provider API keys, DB, Redis, Solver, Sandbox, or AIGC filing.

5. Operator handoff documents 4.A.6 interpretation without fabricating evidence。
   - Update `docs/runbooks/chat-staging-load-test.md` with a short 4.A.6 section explaining:
     - 4.A.6 validates readiness/closure semantics, not a real G6 pass.
     - Real G6 pass still requires `reports/chat-load/<run_id>/evidence_manifest.json` with `example_only=false` and `cluster.node_count=5` validated via `uv run python scripts/validate_chat_load_plan.py --evidence ...`。
     - If no real evidence manifest exists, G6 remains `requires_real_staging_evidence`。
     - If evidence fails, follow M3.6a failure handling: critic async/deferred, AIGC Layer 2 offline/deferred, provider fallback investigation, capacity tuning, sandbox warm pool, API gateway/network isolation.

6. Workflow tracking and closure are explicit。
   - This story records three pre-implementation story review rounds and applies fixes after each round before implementation。
   - `_bmad-output/stories/sprint-status.yaml` moves `4-a-6-g6-chat-latency-validation` to `ready-for-dev` only after all three story review rounds pass。
   - During implementation, move the story through `in-progress`, `code-review`, and `done` only when corresponding gates pass。
   - Implementation must run post-implementation code review before commit/push/PR, covering data consistency, function/dependency consistency, drift/boundary issues, evidence semantics, threshold units, false-pass paths, and regression evidence。
   - This story must not fabricate real staging evidence, commit real Locust/Grafana artifacts, or claim G6 passed unless a future real operator evidence PR supplies valid non-example 5-node evidence。

## Tasks / Subtasks

- [x] Task 1: Add 4.A.6 G6 validation contract. (AC: 1, 2)
  - [x] Add `tools/chat_load/g6_chat_latency_validation.json` with source story, status, endpoints, evidence path/mode, story chain, profile refs, thresholds, prompt hash, response invariants, and blocked unlock sources.
  - [x] Reuse M3.6a prompt fixture hash and staging profile values; do not duplicate prompt data.
  - [x] Keep status as `requires_real_staging_evidence`; do not add real pass artifacts.
- [x] Task 2: Extend static validator. (AC: 2, 3)
  - [x] Add a dedicated `validate_g6_chat_latency_validation(...)` path to `scripts/validate_chat_load_plan.py`.
  - [x] Validate contract metadata, thresholds, stress profile coupling, prompt hash, evidence source boundaries, response flag invariants, and no hard-gate/staging pass claims.
  - [x] Preserve existing M3.6a/M3.6b/M3.6c CLI behavior and evidence modes.
- [x] Task 3: Add RED tests and focused Chat response regression. (AC: 3, 4)
  - [x] Add failing tests for the new G6 contract success and negative cases in `tests/test_chat_load_plan.py`.
  - [x] Add or extend Chat service test coverage for internal beta response flags needed by G6 closure semantics.
  - [x] Confirm focused tests fail before implementation, then pass after implementation.
- [x] Task 4: Update operator runbook. (AC: 5)
  - [x] Add a 4.A.6 interpretation section to `docs/runbooks/chat-staging-load-test.md`.
  - [x] Keep runbook clear that default CI/static validation is not real staging proof.
- [x] Task 5: Validate, review, and close. (AC: 6)
  - [x] Run focused validation commands.
  - [x] Run post-implementation code review and apply fixes.
  - [x] Update Dev Agent Record, File List, Change Log, and sprint status.

## Dev Notes

### Source Context

- `_bmad-output/planning/epics.md:398` defines Epic 4.A goal: NL Chat with Router/Formulator/Coder.
- `_bmad-output/planning/epics.md:1532` defines Story 4.A.6 as G6 Chat 延迟预算压测验证, linked with M3.6abc.
- `_bmad-output/planning/epics.md:1534` says: Given 4.A.1-4.A.4 + M3.6a 5 节点 K8s 压测 / When 100 concurrent users / Then P95 first-token <3s.
- `_bmad-output/planning/architecture.md:1993` defines G6 as Chat latency budget risk and says failures require architecture work such as critic async or AIGC Layer 2 offline/deferred.
- `_bmad-output/planning/architecture.md:2437` defines G6 hard-gate thresholds: first-token P95 < 3s, streaming >= 20 Token/s, E2E <= 90s.
- `_bmad-output/planning/prd.md:1594` defines Chat latency testing through Locust, SSE first-token timestamps, and streaming load tests.
- `_bmad-output/planning/prd.md:1599` says M3 starts instrumentation/monitoring, while M5 is KPI attainment gate.
- `_bmad-output/stories/m3-6a-chat-staging-load-test.md` already owns the 5-node staging harness and evidence manifest contract.
- `_bmad-output/stories/m3-6b-chat-single-node-baseline.md` owns advisory single-node evidence only.
- `_bmad-output/stories/m3-6c-chat-incident-fallback.md` owns incident fallback drill evidence only.

### Current Repository Reality

- `apps/chat-service/src/chat_service/main.py` currently exposes only `POST /v1/chat/internal-beta/messages` plus `GET /health`.
- Current internal beta flow is Router -> Formulator -> Coder -> Language preview.
- Gate-before-body-validation is a hard boundary: disabled/unauthorized internal beta requests return sparse 404 before request body parsing.
- `apps/chat-service/src/chat_service/schemas.py` already has `LanguagePreview` and `ChatInternalBetaMessageResponse` with `provider_request_sent: Literal[False]`, `solver_invoked: Literal[False]`, and `sandbox_invoked: Literal[False]`.
- `tools/chat_load/locustfile.py` targets configurable `CHAT_LOAD_ENDPOINT`, defaulting to `/v1/chat/stream`; that endpoint is not implemented by 4.A.6.
- `scripts/validate_chat_load_plan.py` already validates M3.6a/M3.6b/M3.6c plan assets and optional future real evidence manifests.
- `.github/workflows/ci.yml` already runs `chat-load-plan-validation` for `tools/chat_load/**`, `scripts/validate_chat_load_plan.py`, `tests/test_chat_load_plan.py`, the three chat runbooks, and report directories.
- `reports/chat-load/`, `reports/chat-single-node/`, and `reports/chat-incident-fallback/` currently contain no committed real evidence manifest files.

### Previous Story Intelligence

- 4.A.1 established internal beta access fail-closed behavior and sparse 404 before body/schema validation.
- 4.A.2 established M3.8 LLM router usage through injectable wrappers and offline deterministic testing.
- 4.A.3/4.A.4 established safe preview parsing and no Solver/Sandbox side effects.
- 4.A.5 added language preview and preserved `provider_request_sent=false`, no frontend, no public Chat, no SSE, no AIGC filter call.
- M3.6a post-review fixes must be preserved: example evidence cannot be accepted as real pass evidence; real evidence threshold checks use ms; artifact paths stay under the matching run_id; hard-gate checks apply only to real staging evidence.
- M3.6b and M3.6c are explicitly non-hard-gate lanes; 4.A.6 must not let them unlock G6.

### Implementation Guidance

- Prefer adding one small JSON contract and one dedicated validator function over inventing a new evidence framework.
- Suggested JSON shape:

```json
{
  "dataset_version": "g6_chat_latency_validation_v1",
  "source_story": "4.A.6",
  "linked_hard_gate_story": "M3.6a",
  "g6_status": "requires_real_staging_evidence",
  "real_evidence_required": true,
  "hard_gate_pass": false,
  "current_internal_beta_endpoint": "/v1/chat/internal-beta/messages",
  "target_staging_sse_endpoint": "/v1/chat/stream",
  "required_evidence_manifest": "reports/chat-load/<run_id>/evidence_manifest.json",
  "required_validator_mode": "--evidence",
  "prompt_fixture": "tools/chat_load/prompts_v1.json",
  "prompt_fixture_sha256": "<canonical hash>",
  "hard_gate_thresholds": {
    "first_token_p95_max_ms": 3000,
    "streaming_min_tokens_per_second": 20,
    "e2e_solve_p95_max_ms": 90000
  },
  "stress_profile": {
    "profile": "stress",
    "users": 100,
    "run_time_seconds": 1800,
    "target_rps": 100,
    "first_token_p95_max_ms": 3000
  }
}
```

- Validator should reject pass-like keys anywhere in the G6 contract when their values are truthy, including `hard_gate_pass`, `staging_pass`, `g6_pass`, and `passed`.
- Validator should not scan the whole repository for real evidence by default; absence of real evidence is normal for this story. Future real evidence remains explicit via `--evidence`.
- Keep tests local/static. If adding a Chat service response regression, use the existing FastAPI TestClient pattern and internal beta env fixture from `apps/chat-service/tests/test_internal_beta.py`.
- Do not alter `tools/chat_load/locustfile.py` request payload shape in this story unless tests show a strict need; SSE/public endpoint work belongs to 4.C.2.

### Boundary Rules

- No new public Chat route.
- No SSE implementation.
- No real staging run.
- No fabricated Locust/Grafana artifacts.
- No hard-gate pass claim.
- No single-node or incident fallback evidence unlocking G6.
- No provider API calls or external network.
- No API key, real staging URL, bearer token, cookie, tenant identifier, raw customer prompt, provider payload, or Grafana token in committed assets.
- No DB/Redis/outbox/billing/cost telemetry writes.
- No Solver/Sandbox/Critic/AIGC filter runtime calls.
- No frontend changes.

### Story Review Rounds

### Round 1 - Data Consistency Review (2026-05-29)

Findings applied:
- Source AC references 4.A.1-4.A.4, but repository reality now includes 4.A.5 language preview in the live internal beta response. Story now records both: the G6 source anchor remains 4.A.1-4.A.4 + M3.6a, while the contract protects current 4.A.1-4.A.5 response invariants.
- Pinned all latency threshold units as numeric ms/token-per-second fields: `first_token_p95_max_ms=3000`, `streaming_min_tokens_per_second=20`, and `e2e_solve_p95_max_ms=90000`.
- Pinned stress profile data to M3.6a: 100 users, 1800 seconds, 100 RPS, P95 first-token < 3000 ms.
- Added canonical prompt fixture hash binding so the new 4.A.6 contract cannot drift away from `tools/chat_load/prompts_v1.json`.
- Required `g6_status="requires_real_staging_evidence"` and `hard_gate_pass=false` so the data model cannot imply pass without real evidence.

Status: PASS after fixes.

### Round 2 - Function / Dependency Consistency Review (2026-05-29)

Findings applied:
- Scoped implementation to a JSON contract plus extension of the existing `scripts/validate_chat_load_plan.py`, reusing the M3.6a validator and CI job instead of adding another validation island.
- Explicitly kept M3.6a/M3.6b/M3.6c evidence modes separate: staging `--evidence` is the only G6 hard-gate lane; single-node and incident fallback remain non-unlock sources.
- Added response flag invariants for the current internal beta endpoint so Chat implementation cannot change side-effect semantics while adding validation closure.
- Confirmed no new dependency, provider SDK, Locust runtime in CI, K8s dependency, Grafana dependency, DB/Redis dependency, or workflow job is needed.

Status: PASS after fixes.

### Round 3 - Drift / Boundary / Closure Review (2026-05-29)

Findings applied:
- Clarified that `/v1/chat/stream` is the target staging SSE endpoint from M3.6a but is not implemented by 4.A.6.
- Added explicit false-pass blockers for `example_only=true`, docs-only checklists, `reports/chat-single-node/**`, and `reports/chat-incident-fallback/**`.
- Added runbook interpretation text so operators understand 4.A.6 validates readiness/closure semantics, not real G6 pass evidence.
- Added post-implementation code review requirement covering threshold units, data/function consistency, drift/boundary issues, false-pass paths, and regression evidence before commit/push/PR.

Status: PASS after fixes. Story is ready for development.

### Test / Validation Notes

Expected commands:

```bash
uv run python scripts/validate_chat_load_plan.py
uv run pytest tests/test_chat_load_plan.py -q
uv run pytest apps/chat-service/tests -q
uv run python scripts/validate_llm_router_contract.py
uv run pytest tests/llm_router/test_implementations_parity.py -q
uv run mypy apps packages
uv tool run pre-commit run --all-files --show-diff-on-failure
git diff --check
```

RED expectation: add tests for the G6 contract first and confirm they fail before adding `tools/chat_load/g6_chat_latency_validation.json` and validator support.

## Dev Agent Record

### Agent Model Used

GPT-5

### Debug Log References

- 2026-05-29 - Story 4.A.6 created from Epic 4.A source AC, PRD latency SLO, Architecture G6 hard-gate thresholds, M3.6a/b/c evidence contracts, current chat-service internal beta endpoint, and prior 4.A.5 learnings.
- 2026-05-29 - Story moved to in-progress after three story review rounds; starting RED tests for G6 latency validation contract and internal beta response invariants.
- 2026-05-29 - RED confirmed: `uv run pytest tests/test_chat_load_plan.py -q` failed because `tools/chat_load/g6_chat_latency_validation.json` did not exist; internal beta boundary regression already passed.
- 2026-05-29 - Added G6 JSON contract, validator support, negative drift tests, internal beta response boundary regression, and runbook interpretation section.
- 2026-05-29 - Focused validation passed: `uv run pytest tests/test_chat_load_plan.py -q`, `uv run python scripts/validate_chat_load_plan.py`, and `uv run pytest apps/chat-service/tests/test_internal_beta.py -q`.
- 2026-05-29 - Full related validation passed before code review: chat load validator/tests, chat-service tests, LLM router contract/parity, mypy, pre-commit, and diff-check.
- 2026-05-29 - Post-implementation code review found and fixed one false-pass gap: the G6 contract now pins `blocked_unlock_conditions=["example_only=true"]`, and the validator rejects nested `example_only=true` evidence claims.
- 2026-05-29 - Closure validation passed: `uv run pytest tests/test_chat_load_plan.py -q`, `uv run python scripts/validate_chat_load_plan.py`, `uv run pytest apps/chat-service/tests/test_internal_beta.py -q`, `uv run pytest apps/chat-service/tests -q`, `uv run python scripts/validate_llm_router_contract.py`, `uv run pytest tests/llm_router/test_implementations_parity.py -q`, `uv run mypy apps packages`, `uv tool run pre-commit run --all-files --show-diff-on-failure`, and `git diff --check`.

### Completion Notes

- Implemented 4.A.6 as a false-pass prevention and evidence-closure contract, not as real staging evidence.
- G6 hard-gate remains `requires_real_staging_evidence`; the only unlock path is a future non-example 5-node staging manifest under `reports/chat-load/<run_id>/evidence_manifest.json` validated with `--evidence`.
- Preserved M3.6a/M3.6b/M3.6c evidence mode separation and current internal beta Chat side-effect boundaries.
- Post-review hardened the machine contract so `example_only=true` cannot be embedded as a G6 unlock condition or nested evidence claim.

### File List

- `tools/chat_load/g6_chat_latency_validation.json`
- `scripts/validate_chat_load_plan.py`
- `tests/test_chat_load_plan.py`
- `apps/chat-service/tests/test_internal_beta.py`
- `docs/runbooks/chat-staging-load-test.md`
- `_bmad-output/stories/4-a-6-g6-chat-latency-validation.md`
- `_bmad-output/stories/sprint-status.yaml`

### Change Log

- Added 4.A.6 G6 latency validation contract and static validation.
- Added regression tests for false-pass claims, wrong unlock sources, threshold/hash/profile drift, and internal beta response boundaries.
- Updated staging load-test runbook with 4.A.6 interpretation and real evidence requirements.
- Post-review hardened example-only evidence blocking and closed story status after full validation.
