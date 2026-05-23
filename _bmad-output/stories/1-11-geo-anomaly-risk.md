---
story_key: 1-11-geo-anomaly-risk
epic_num: 1
story_num: 1.11
epic_name: Account & Identity
status: done
priority: 🟠 High (NFR-S API Key 安全；异常地理风险评分 + 用户一键吊销)
sizing: M (~1 day; solver auth signal + auth API response + API Keys UI + tests)
type: implementation + security + ui + test
created_by: bmad-create-story
created_at: 2026-05-23
sources:
  - [Source: _bmad-output/planning/epics.md:1339]
  - [Source: _bmad-output/planning/epics.md:1341]
  - [Source: _bmad-output/planning/prd.md:748]
  - [Source: _bmad-output/planning/prd.md:1081]
  - [Source: _bmad-output/planning/prd.md:1628]
  - [Source: _bmad-output/planning/architecture.md:241]
  - [Source: _bmad-output/planning/architecture.md:497]
  - [Source: _bmad-output/planning/architecture.md:680]
  - [Source: _bmad-output/stories/1-5-risk-control-freeze.md]
  - [Source: _bmad-output/stories/1-10-language-switch-zh.md]
dependencies:
  upstream:
    - 1-3-api-keys-crud-complete (done) — API Key create/list/revoke and solver direct verification already exist
    - 1-5-risk-control-freeze (done) — risk_rules/risk_flags/user.risk_score scaffolding exists; geo anomaly must reuse it
    - 1-10-language-switch-zh (done) — key pages and API client now carry locale; this story keeps API Keys page copy focused and zh-CN baseline
  downstream:
    - 1-12-j7-fraud-freeze-vertical-slice — can use geo anomaly evidence when explaining a frozen/risky account
    - 8-a-4-user-audit-logs — future user-facing audit log can expose the same anomaly evidence
    - 8-b-2-rate-limit-per-plan — future API gateway can supply trusted edge geo headers and rate-limit anomalous keys
---

# Story 1.11 — 异常地理风险评分

## User Story

**As** an OptiCloud API Key owner,
**I want** the platform to detect when one of my API keys suddenly moves across abnormal geography, raise the account/key risk score, and show a clear warning with a one-click revoke action,
**so that** stolen keys can be contained quickly without waiting for a full account freeze or support workflow.

## Why this story

PRD requires API Key security to include hash-only storage, visible prefix, one-click revoke, and abnormal geography risk scoring. The base pieces already exist:

- `api_keys.last_used_at` is updated by solver-orchestrator on successful API-key use.
- `api_keys.last_used_ip` already exists in schema/model but is not populated.
- `users.risk_score` already exists and Story 1.5 introduced `risk_rules` / `risk_flags`.
- `/auth/api-keys` already lists own keys and can revoke a key.
- `/auth/api-keys` page already has a table and revoke action.

This story connects those pieces into the first useful v1 slice:

1. solver API-key verification records the successful caller IP and a deterministic geo bucket;
2. if a key moves from a known prior bucket to a different known current bucket, the key's geo risk score and the owning user's risk score increase;
3. the event is logged as a `risk_flags` row with rule code `geo_anomaly`;
4. the API Keys page shows a modal-style warning and lets the user revoke the suspicious key immediately.

## Out of Scope

- Full commercial IP geolocation database, MaxMind, ASN intelligence, VPN/proxy scoring, impossible-travel speed calculations, or device fingerprint fusion.
- Automatic account freeze from geo anomaly alone. Story 1.5's threshold remains separate; `geo_anomaly` starts as a recorded risk signal, not an enabled freeze rule.
- API gateway / CDN trusted geo header rollout. This story uses the request client IP available to solver-orchestrator and a tiny deterministic v1 mapping for known demo/test networks.
- Email/SMS/push notifications for anomalous keys.
- Admin console for tuning geo thresholds.
- Changing API key hash format, scope semantics, or revoke authorization rules.
- Rewriting the API Keys page into a full console dashboard.
- Revoking all keys automatically. The user chooses which flagged key to revoke.

## Acceptance Criteria

### AC1: Geo anomaly persistence is added without breaking existing keys

- Add migration `infra/local-init/09-geo-anomaly-risk.sql`.
- `api_keys` gains:
  - `last_used_geo_bucket VARCHAR(64) NULL`;
  - `geo_risk_score NUMERIC(3,2) NOT NULL DEFAULT 0.00`;
  - `geo_anomaly_at TIMESTAMPTZ NULL`;
  - `geo_anomaly_metadata JSONB NOT NULL DEFAULT '{}'::jsonb`.
- `risk_rules` gains `geo_anomaly` with `enabled=false` by default.
- Existing rows get safe defaults and remain valid.
- Add or update indexes only where useful for list/query paths, for example `idx_api_keys_geo_anomaly_user`.
- Update `infra/local-init/01-schema.sql` so fresh local databases include the same columns.
- Wire `09-geo-anomaly-risk.sql` into auth-service and solver-orchestrator CI schema setup.
- Update `.github/workflows/ci.yml` path filters so changes to `09-geo-anomaly-risk.sql` trigger both auth-service and solver-orchestrator tests.

### AC2: Solver API-key verification records successful caller IP and geo bucket

- `solver_orchestrator.auth.verify_api_key()` accepts an optional `client_ip`.
- Solver routes that already have `Request` pass `request.client.host` when verifying API keys:
  - `POST /v1/optimizations`;
  - `POST /v1/reproduce/{voucher_id}/rerun`;
  - `GET /v1/optimizations/{optimization_id}`.
- On successful key verification:
  - `api_keys.last_used_at` is updated as before;
  - if `client_ip` is a valid IP, `api_keys.last_used_ip` is updated;
  - if the IP maps to a known geo bucket, `api_keys.last_used_geo_bucket` is updated.
- The update, risk-score change, risk flag insert, and audit log insert all happen in the same `AsyncSession` used by the request so downstream rollback semantics remain consistent.
- Invalid, missing, private, loopback, or unknown IPs must not create false geo anomalies.
- Revoke, expired, malformed, or invalid-key failures do not update last-use or risk fields.

### AC3: Geo anomaly scoring is deterministic and bounded

- Add a small pure helper module such as `solver_orchestrator.geo_risk`.
- v1 geo bucket mapping must be deterministic and dependency-free. It may include a minimal allowlist sufficient for product/test examples, including:
  - a Beijing/CN demo bucket;
  - a Singapore/SG demo bucket.
- Use Python standard library `ipaddress`; do not add a third-party geolocation dependency.
- If a key has a known previous bucket and a different known current bucket, record a geo anomaly.
- Each anomaly raises `api_keys.geo_risk_score` by a bounded delta, for example `+0.35`, capped at `1.00`.
- The owning `users.risk_score` increases to at least the key's new geo risk score and never decreases.
- Same-bucket repeated use does not increase risk.
- Unknown-to-known first use establishes a baseline but does not trigger anomaly.
- Known-to-unknown use does not trigger anomaly.

### AC4: Risk evidence is recorded without auto-freezing users

- On a geo anomaly, insert a `risk_flags` row:
  - `user_id = api_keys.user_id`;
  - `rule_code = "geo_anomaly"`;
  - `source = "auto"`;
  - `metadata` includes `api_key_id`, previous/current geo buckets, previous/current IPs where available, risk delta, and detector version.
- The event must also write an audit log row or equivalent metadata in the same transaction.
- Audit metadata should use `resource_type="api_key"` and `resource_id=api_keys.id` so later audit-log surfaces can link the event to the key without exposing the full secret.
- `geo_anomaly` stays `enabled=false` in `risk_rules`, so Story 1.5 freeze threshold does not auto-freeze accounts from this signal in v1.
- The implementation must be idempotent enough for normal repeated calls: repeated same-bucket calls should not spam risk flags.

### AC5: Auth API key list exposes user-safe risk warning data

- `GET /v1/auth/api_keys` includes the following new fields per key:
  - `last_used_ip: string | null`;
  - `last_used_geo_bucket: string | null`;
  - `geo_risk_score: number`;
  - `geo_anomaly_at: datetime | null`;
  - `geo_anomaly: object | null` or equivalent compact warning object.
- The warning object is present only when the key has an unresolved geo anomaly and is not revoked.
- "Unresolved" in v1 means `geo_anomaly_at IS NOT NULL AND revoked_at IS NULL`. No separate acknowledgement state is required in this story.
- The response must not expose the full API key or key hash.
- Cross-tenant isolation remains unchanged: users only see their own keys.
- Revoked keys remain listable but no longer appear as actionable anomaly warnings.
- After the user revokes a flagged key, the next list response still shows historical risk fields but `geo_anomaly` is `null`, so the modal does not re-open for that revoked key.

### AC6: API Keys page shows warning and one-click revoke

- `/auth/api-keys` displays a modal-style warning when any active key has a geo anomaly warning.
- The warning identifies the key by label and visible prefix, explains the abnormal geography in concise zh-CN copy, and avoids panic wording.
- The modal includes:
  - a primary revoke action for the flagged key;
  - a secondary dismiss/keep action.
- Revoke uses the existing `DELETE /v1/auth/api_keys/{key_id}` path and refreshes the list after success.
- The table also shows a compact risk badge/score for flagged keys.
- Existing create/list/revoke behavior remains usable when there is no anomaly.
- The user can re-open a dismissed warning from the flagged key's table row during the same page session.
- The warning UI should use stable `data-testid` hooks for focused Vitest coverage and must not depend on browser `confirm()`.

### AC7: Tests prove backend, API, and UI behavior

- Solver tests cover:
  - first known bucket use records baseline without anomaly;
  - known bucket change raises key/user risk and records a `geo_anomaly` flag;
  - repeated same-bucket use does not add new anomaly flags;
  - invalid/revoked key does not update last-use/risk fields.
- Auth-service tests cover:
  - `GET /v1/auth/api_keys` returns the new risk fields;
  - revoked flagged keys are not returned as actionable warnings;
  - cross-tenant isolation still holds.
- Web tests cover:
  - API type/client compatibility for new fields;
  - API Keys page renders the warning, dismisses it, re-opens it from the row, and calls revoke for the flagged key.
- Web component/page tests may use a file-level `// @vitest-environment happy-dom` directive, matching the existing `apps/web/src/app/console/repro/page.test.tsx` pattern.
- Focused quality gates:
  - relevant auth-service tests;
  - relevant solver-orchestrator tests;
  - `pnpm --filter @opticloud/web test -- api`;
  - `pnpm --filter @opticloud/web typecheck`;
  - `uv run mypy apps packages` or focused mypy if full suite is blocked by unrelated work;
  - `git diff --check`.

## Tasks / Subtasks

- [x] Task 1: Add persistence and schema wiring (AC: 1)
  - [x] Add `09-geo-anomaly-risk.sql`.
  - [x] Update `01-schema.sql` with the new `api_keys` columns.
  - [x] Update auth-service ORM `APIKey`.
  - [x] Update auth-service local test schema bootstrap for older local DBs.
  - [x] Wire the migration into CI schema setup and path filters.

- [x] Task 2: Implement deterministic geo-risk helper and solver auth integration (AC: 2, 3, 4)
  - [x] Add `solver_orchestrator.geo_risk` with pure IP normalization, bucket mapping, and scoring helpers.
  - [x] Extend `verify_api_key()` to accept optional `client_ip`.
  - [x] Update solver routes to pass request client IP.
  - [x] Persist `last_used_ip`, `last_used_geo_bucket`, bounded key risk score, user risk score, risk flag, and audit evidence on anomaly.
  - [x] Preserve existing invalid/revoked/expired key behavior.
  - [x] Use `Decimal` for DB `NUMERIC(3,2)` arithmetic or explicitly convert at DB boundaries; do not accumulate binary-float artifacts in stored risk scores.

- [x] Task 3: Expose risk warning through auth API (AC: 5)
  - [x] Extend `APIKeyListItem` schema with safe risk fields.
  - [x] Update `list_api_keys()` to populate risk data and warning object.
  - [x] Ensure revoked flagged keys are not actionable warnings.
  - [x] Add/update auth-service tests.

- [x] Task 4: Add API Keys warning UI and one-click revoke (AC: 6)
  - [x] Extend web `APIKeyListItem` type.
  - [x] Render modal-style warning for active geo-anomaly keys.
  - [x] Add risk badge/score to the table.
  - [x] Reuse existing revoke endpoint and refresh behavior.
  - [x] Add/update web tests for the warning and revoke path using happy-dom only for the component/page test file that needs DOM.

- [x] Task 5: Verification and story tracking (AC: 7)
  - [x] Run focused backend tests.
  - [x] Run focused web tests and typecheck.
  - [x] Run mypy or focused type checks.
  - [x] Run `git diff --check`.
  - [x] Update Dev Agent Record, File List, Change Log.
  - [x] Move sprint status to `code-review` only after implementation and tests.

## Dev Notes

- Do not add a heavyweight geolocation dependency in v1. Keep the detector pure, deterministic, and easy to test.
- Do not trust arbitrary client-provided geo headers in this story. Use `Request.client.host`; trusted gateway/CDN geo headers belong in API gateway work.
- Be conservative with false positives. Localhost/private/unknown IPs should update `last_used_at` and possibly `last_used_ip`, but should not raise risk.
- Use "known previous bucket + different known current bucket" as the only v1 anomaly trigger.
- Use a bounded additive score on the key (`min(1.00, old + delta)`) and raise `users.risk_score` to at least that score.
- Keep `geo_anomaly` disabled in `risk_rules`; it is evidence and user warning in this story, not an automatic freeze trigger.
- If `risk_rules` is missing `geo_anomaly` in a stale local DB, the migration/test bootstrap must create it. Do not allow a successful API request to crash because risk metadata cannot be inserted.
- Preserve the existing tuple return shape of `verify_api_key()` so solver route call sites and tests remain mostly stable.
- Raw SQL is acceptable in solver-orchestrator auth because it already verifies against auth-service tables through raw SQL.
- `last_used_ip` is an `INET` column; validate IP strings before casting.
- Keep raw SQL parameterized. Do not interpolate IP strings, geo buckets, or UUIDs into SQL.
- Do not expose full IP history to the UI. A current/previous bucket label plus visible key prefix is enough for user action.
- Existing `revokeAPIKey()` in `apps/web/src/lib/api.ts` currently uses raw `fetch`; if touched, preserve the void-return contract or improve error handling with focused tests.

### Project Structure Notes

- Solver auth: `apps/solver-orchestrator/src/solver_orchestrator/auth.py`
- Solver routes: `apps/solver-orchestrator/src/solver_orchestrator/routes.py`
- New solver helper: `apps/solver-orchestrator/src/solver_orchestrator/geo_risk.py`
- Auth models: `apps/auth-service/src/auth_service/models.py`
- Auth schemas: `apps/auth-service/src/auth_service/schemas.py`
- Auth routes: `apps/auth-service/src/auth_service/routes.py`
- Auth tests: `apps/auth-service/tests/test_api_keys_routes.py`
- Solver tests: `apps/solver-orchestrator/tests/test_billing_integration.py` or a focused new `test_geo_risk.py`
- If adding solver tests that mutate the same seeded API key repeatedly, use a fresh key per test or reset geo fields to avoid order-dependent risk state.
- Web API client: `apps/web/src/lib/api.ts`
- Web API Keys page: `apps/web/src/app/auth/api-keys/page.tsx`
- Web tests: add or update `apps/web/src/lib/*.test.ts` / app component tests if existing config supports it
- Schema: `infra/local-init/01-schema.sql`, `infra/local-init/09-geo-anomaly-risk.sql`
- CI: `.github/workflows/ci.yml`

### Risks & Mitigations

| Risk | Mitigation |
|---|---|
| IP geolocation is inaccurate without a provider | Use deterministic known-bucket v1 mapping only; no anomaly for unknowns |
| A spoofed header creates false risk | Do not consume arbitrary geo headers in this story |
| Geo anomaly accidentally freezes an account | Seed `geo_anomaly` as `enabled=false`; only score and warn |
| Repeated calls spam risk flags | Only flag when known bucket changes; same-bucket calls are no-op for risk |
| API Keys page leaks secrets | Continue exposing only id/prefix/label/scope/status and safe risk metadata |
| Cross-service schema drift breaks CI | Add migration to both auth and solver schema setup |
| Existing tests that call `verify_api_key()` break | Keep optional `client_ip=None` and tuple return unchanged |
| Local/private E2E IPs generate noisy warnings | Treat private/loopback/unknown IPs as non-anomalous |
| Numeric risk scores drift due float math | Use `Decimal` or SQL-side bounded arithmetic |
| Schema-only changes do not trigger CI jobs | Add `09-geo-anomaly-risk.sql` to auth and solver path filters |
| Solver integration tests share seeded keys and become order-dependent | Use fresh keys for geo tests or reset geo/risk fields in each test |

## Dev Agent Record

### Agent Model Used

GPT-5

### Debug Log References

- `uv run ruff check apps/solver-orchestrator/src/solver_orchestrator/auth.py apps/solver-orchestrator/src/solver_orchestrator/geo_risk.py apps/solver-orchestrator/src/solver_orchestrator/routes.py apps/solver-orchestrator/tests/test_geo_risk.py apps/auth-service/src/auth_service/models.py apps/auth-service/src/auth_service/routes.py apps/auth-service/src/auth_service/schemas.py apps/auth-service/tests/test_api_keys_routes.py apps/auth-service/tests/test_risk_freeze.py apps/auth-service/tests/conftest.py` — passed.
- `uv run python -m py_compile apps/solver-orchestrator/src/solver_orchestrator/auth.py apps/solver-orchestrator/src/solver_orchestrator/geo_risk.py apps/auth-service/src/auth_service/models.py apps/auth-service/src/auth_service/routes.py apps/auth-service/src/auth_service/schemas.py` — passed.
- `pnpm install` — restored node_modules links in the new worktree.
- `uv sync --all-packages --extra dev` — restored Python workspace dependencies in the new worktree.
- `pnpm --filter @opticloud/web test -- signup api-keys` — 5 passed.
- `pnpm --filter @opticloud/web test` — 64 passed.
- `pnpm --filter @opticloud/web typecheck` — passed.
- `$env:PYTHONPATH='<repo>/apps/auth-service/src;<repo>/apps/solver-orchestrator/src;<repo>/packages/shared-py'; uv run pytest apps/auth-service/tests/test_api_keys_routes.py -q` — 11 passed.
- `$env:PYTHONPATH='<repo>/apps/auth-service/src;<repo>/apps/solver-orchestrator/src;<repo>/packages/shared-py'; uv run pytest apps/auth-service/tests -q` — 62 passed.
- `$env:PYTHONPATH='<repo>/apps/solver-orchestrator/src;<repo>/packages/shared-py'; uv run pytest apps/solver-orchestrator/tests/test_geo_risk.py -q` — 5 passed.
- `$env:PYTHONPATH='<repo>/apps/solver-orchestrator/src;<repo>/packages/shared-py'; uv run pytest apps/solver-orchestrator/tests/test_billing_integration.py apps/solver-orchestrator/tests/test_reproduction_rerun.py apps/solver-orchestrator/tests/test_geo_risk.py -q` — 29 passed, 5 deprecation warnings.
- `uv run mypy apps packages` — passed, 71 source files checked.
- `git diff --check` — passed.

### Completion Notes List

- Added idempotent geo-anomaly migration, fresh-schema columns, auth ORM fields, local auth test bootstrap compatibility, and CI schema/path-filter wiring.
- Added deterministic solver geo-risk helper, optional client IP tracking in API-key verification, bounded risk scoring, risk flag/audit evidence, and solver tests.
- Extended auth API key list schema/route with safe geo-risk warning fields and backend tests for active vs revoked warning behavior.
- Added API Keys warning modal/risk badge, typed geo-risk fields in the web client, 204-safe revoke handling, and focused happy-dom UI coverage.
- Updated legacy risk-rule seed regression to include the disabled `geo_anomaly` signal.
- Code review fixed the warning copy to expose user-friendly Chinese geo labels instead of internal bucket codes.

### File List

- `.github/workflows/ci.yml`
- `_bmad-output/stories/1-11-geo-anomaly-risk.md`
- `_bmad-output/stories/sprint-status.yaml`
- `apps/auth-service/src/auth_service/models.py`
- `apps/auth-service/src/auth_service/routes.py`
- `apps/auth-service/src/auth_service/schemas.py`
- `apps/auth-service/tests/conftest.py`
- `apps/auth-service/tests/test_api_keys_routes.py`
- `apps/auth-service/tests/test_risk_freeze.py`
- `apps/solver-orchestrator/src/solver_orchestrator/auth.py`
- `apps/solver-orchestrator/src/solver_orchestrator/geo_risk.py`
- `apps/solver-orchestrator/src/solver_orchestrator/routes.py`
- `apps/solver-orchestrator/tests/test_geo_risk.py`
- `apps/web/src/app/auth/api-keys/page.tsx`
- `apps/web/src/app/auth/api-keys/page.test.tsx`
- `apps/web/src/lib/api.ts`
- `apps/web/src/lib/signup.test.ts`
- `infra/local-init/01-schema.sql`
- `infra/local-init/09-geo-anomaly-risk.sql`

### Change Log

- 2026-05-23 — Created Story 1.11 with implementation-ready scope and initial acceptance criteria.
- 2026-05-23 — Round 1 story review clarified unresolved warning semantics, post-revoke behavior, and modal testability.
- 2026-05-23 — Round 2 story review added transaction, parameterized SQL, Decimal scoring, and CI path-filter guardrails.
- 2026-05-23 — Round 3 story review clarified happy-dom page-test pattern and solver test fixture isolation.
- 2026-05-23 — Implemented Task 1 schema, ORM, test-bootstrap, and CI wiring.
- 2026-05-23 — Implemented Tasks 2-3 solver geo-risk recording and auth API warning surface.
- 2026-05-23 — Implemented Task 4 API Keys warning UI, typed API client fields, and web tests.
- 2026-05-23 — Verification passed and story moved to code-review.
- 2026-05-23 — Code review completed; geo warning labels patched; story moved to done.

## Senior Developer Review (AI)

### Review Date

2026-05-23

### Review Result

Approved after fixes. No unresolved decision-needed, patch, or deferred findings remain.

### Review Findings

- [x] [Review][Patch] API Keys warning UI showed internal bucket codes (`CN-BJ`, `SG-SG`) rather than user-friendly zh-CN geography labels — fixed by adding `previous_geo_label_zh` / `current_geo_label_zh` to solver metadata, auth API schema, and web display fallback.

### Verification

- `$env:PYTHONPATH='<repo>/apps/solver-orchestrator/src;<repo>/packages/shared-py'; uv run pytest apps/solver-orchestrator/tests/test_geo_risk.py -q` — pass, 5 tests.
- `$env:PYTHONPATH='<repo>/apps/auth-service/src;<repo>/apps/solver-orchestrator/src;<repo>/packages/shared-py'; uv run pytest apps/auth-service/tests/test_api_keys_routes.py apps/auth-service/tests/test_risk_freeze.py -q` — pass, 21 tests.
- `pnpm --filter @opticloud/web test -- signup api-keys` — pass, 5 tests.
- `pnpm --filter @opticloud/web typecheck` — pass.
- `uv run mypy apps packages` — pass, 71 source files.
- `uv run ruff check ...` — pass for touched Python files.
- `$env:PYTHONPATH='<repo>/apps/auth-service/src;<repo>/apps/solver-orchestrator/src;<repo>/packages/shared-py'; uv run pytest apps/auth-service/tests -q` — pass, 62 tests.
- `pnpm --filter @opticloud/web test` — pass, 64 tests.
- `git diff --check` — pass.

## Story Review Log

### Round 1 — Product Scope / UX Acceptance Review

- [x] Clarified that unresolved v1 anomaly warnings are derived from `geo_anomaly_at` plus non-revoked key state, avoiding a new acknowledgement table.
- [x] Required revoked flagged keys to keep historical risk fields but stop returning actionable warning objects.
- [x] Required the warning modal to be dismissible, re-openable from the row, and testable without relying on browser `confirm()`.

### Round 2 — Architecture / Security Contract Review

- [x] Required geo risk updates and risk evidence inserts to share the same request `AsyncSession` as API-key verification.
- [x] Required standard-library IP parsing, parameterized SQL, and no third-party geolocation dependency in v1.
- [x] Added `Decimal`/NUMERIC guardrail for bounded risk scoring and CI path-filter wiring for the new schema file.

### Round 3 — Implementation Readiness Review

- [x] Confirmed web page/component tests can use file-level `// @vitest-environment happy-dom`, matching an existing test pattern.
- [x] Required geo-risk solver tests to use fresh API keys or reset state so risk/anomaly assertions are not order-dependent.
- [x] Kept focused quality gates scoped to auth-service, solver-orchestrator, web tests/typecheck, mypy, and diff-check.
