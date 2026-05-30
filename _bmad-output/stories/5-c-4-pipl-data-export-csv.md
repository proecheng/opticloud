---
story_key: 5-c-4-pipl-data-export-csv
epic_num: 5
story_num: C.4
epic_name: Billing - Refunds + PIPL Export
status: done
priority: High
type: PIPL CSV data portability export
created_by: bmad-create-story
created_at: 2026-05-30
sources:
  - _bmad-output/planning/epics.md (Story 5.C.4 / FR B10)
  - _bmad-output/planning/architecture.md (Data Export Aggregator; api-gateway data-export actor)
  - _bmad-output/planning/prd.md (PIPL privacy constraints)
  - _bmad-output/stories/5-c-3-pipl-data-export-json.md
  - apps/auth-service/src/auth_service/data_export.py
  - apps/auth-service/src/auth_service/routes.py
  - apps/auth-service/src/auth_service/schemas.py
  - apps/auth-service/src/auth_service/models.py
  - apps/auth-service/tests/test_data_exports.py
  - infra/local-init/01-schema.sql
---

# Story 5.C.4 - PIPL Data Export CSV

Status: done

## Story

**As** an authenticated OptiCloud user,
**I want** to request my PIPL data export in CSV format,
**so that** I can inspect my personal data and product history in spreadsheet tools while keeping parity with the JSON portability export.

## Context

Story 5.C.3 shipped the durable PIPL data export lifecycle for JSON: authenticated request/status/download endpoints, a worker, cross-domain read-only aggregation, recursive redaction, audit logs, and outbox evidence. Story 5.C.4 is the second format slice for the same FR B10 requirement: "用户 can export all data + history (JSON/CSV)".

The current repository still has no online `api-gateway`; therefore this story extends the existing v1 `auth-service` actor shape from Story 5.C.3 and keeps the same future migration guardrails. CSV must not fork the compliance lifecycle. It must reuse the same durable `data_export_requests` table, owner-scoped endpoints, worker claim semantics, audit/outbox patterns, and cross-service raw SQL boundary.

Because the export includes multiple sections, "CSV package" in this story means an authenticated zip download containing deterministic CSV files. The DB continues to store an internal JSONB package envelope for v1 operational simplicity; the download response for CSV returns zip bytes with `application/zip`.

## Scope

1. Allow users to choose `format="csv"` when creating a data export request while preserving `json` as the backward-compatible default.
2. Extend the durable lifecycle to support one active export per `(user, format)`, so JSON and CSV requests do not block each other.
3. Generate a deterministic CSV zip package from the same sanitized cross-domain snapshot used by JSON exports.
4. Include a `manifest.csv` that lists every export section, status, count, reason, and CSV path.
5. Include section CSV files for available non-empty sections, with nested objects serialized as canonical JSON cell values.
6. Protect CSV output against spreadsheet formula injection while preserving legitimate user-owned values.
7. Return CSV exports as authenticated owner-only zip downloads; keep JSON downloads unchanged.
8. Emit request/completion/failure audit logs and outbox evidence with `format="csv"` and package hash/size.
9. Keep soft-delete/tombstone compatibility and future `api-gateway` migration compatibility from Story 5.C.3.
10. Preserve no-body `POST /v1/auth/data-exports` compatibility for existing JSON clients; a missing body, `{}`, and `{"format":"json"}` are equivalent.
11. Keep CSV archive metadata and filenames static or section-derived only; no user-controlled value may influence a zip path, archive comment, or filename.
12. Avoid duplicating data aggregation logic. JSON and CSV must share a single canonical package-building path up to the final format rendering step.
13. Keep schema changes compatible with existing local databases and CI fixtures that already have the Story 5.C.3 JSON-only constraint/index.

## Out of Scope

- A portal UI for choosing the format; Story 5.C.5 owns self-service portal UX.
- Real email/SMS delivery provider integration.
- Object storage or signed unauthenticated URLs.
- XLSX, PDF, or localized invoice exports.
- Admin export of another user's data.
- New standalone `api-gateway` scaffolding.
- Changing the source-of-truth data sections introduced by Story 5.C.3 beyond what CSV serialization requires.
- Importing solver-orchestrator or billing-service ORM models into auth-service.

## Acceptance Criteria

1. `POST /v1/auth/data-exports` accepts an optional request body with `format` equal to `json` or `csv`; omitted body or omitted format defaults to `json` and preserves existing clients.
2. A CSV request creates or reuses one active CSV export request for the authenticated user and returns request id, `format="csv"`, status, requested time, 7-day SLA deadline, and eventual download fields.
3. JSON and CSV active requests are independent: an active JSON export does not cause a CSV request to reuse the JSON row, and vice versa.
4. Repeated CSV requests while a queued/processing/completed-not-expired CSV export exists are idempotent and do not duplicate request audit logs or outbox request events.
5. The worker claims queued CSV requests with the same row-lock semantics as JSON and completes them exactly once from the user's perspective.
6. The CSV package is generated from the same sanitized Auth, Solver, Prediction, Billing, and explicit unavailable Chat sections as the JSON export through a shared canonical snapshot builder; absent optional tables remain unavailable sections rather than 500s.
7. The CSV zip contains a deterministic `manifest.csv` and section CSV files for available non-empty sections. File order, row order, headers, newline style, and zip entry metadata are stable for the same snapshot aside from the package generated timestamp.
8. Nested dictionaries/lists in row values are serialized into canonical JSON cell values; datetimes, UUIDs, and decimals use the same JSON-safe conversion rules as the JSON package.
9. CSV cells that could execute as spreadsheet formulas are escaped defensively, including values beginning with `=`, `+`, `-`, `@`, tab, carriage return, or line feed.
10. Export content never includes full API keys, key hashes, OTP values, JWTs, token hashes, pepper values, request body hashes, Authorization headers, internal service secrets, or raw email delivery credentials in any CSV cell, manifest value, filename, zip metadata, audit metadata, or outbox payload.
11. Completion stores the internal CSV package envelope, byte size, SHA-256 digest of the downloadable zip bytes, completion timestamp, expiry timestamp, and owner-scoped download URL on the request row.
12. `GET /v1/auth/data-exports/{export_id}/download` returns `application/zip` bytes for completed CSV exports using `Content-Disposition: attachment`; returns JSON for completed JSON exports; returns 409 for queued/processing exports, 410 for expired packages, and 404 for cross-tenant access.
13. Worker failures for CSV set `status="failed"` with bounded pointer-safe `last_error`, write no zip payload, and emit no completion outbox event.
14. CSV downloads never return the internal JSONB envelope or base64 payload as JSON; the envelope is persistence-only.
15. Unknown or unsupported formats return 422 validation errors and do not create audit or outbox records.
16. A completed CSV request is immutable: repeated worker runs or retries do not rewrite `completed_at`, archive bytes, hash, or outbox completion events.
17. If an export row stores `format="csv"` but lacks a valid archive envelope, download returns 409 instead of returning corrupted content or a server stack trace.
18. CLI/help text and OpenAPI summaries no longer describe the worker or endpoint as JSON-only once CSV support ships.
19. Schema initialization is idempotent for databases that already contain the Story 5.C.3 `ck_data_export_requests_format` constraint and `uq_data_export_requests_inflight_json` index.
20. Existing JSON export behavior and tests remain green.
21. Quality gates pass:
    - focused auth-service data export tests;
    - existing auth-service tests;
    - billing-service and solver-orchestrator regressions when touched by shared behavior;
    - ruff check / format check;
    - mypy;
    - Bandit pre-commit hook if dynamic SQL or archive payload handling changes;
    - `git diff --check`.

## Tasks / Subtasks

- [x] T1: Extend request contract and lifecycle for CSV (AC: 1-4, 11)
  - [x] Add `DataExportCreateRequest` with `format: json|csv` defaulting to `json`.
  - [x] Update response schema to allow `format="csv"`.
  - [x] Update DB schema/model check constraints and indexes for CSV.
  - [x] Drop/recreate existing JSON-only check constraint/index safely in `infra/local-init/01-schema.sql`.
  - [x] Ensure active request idempotency is scoped by `(user_id_snapshot, format)`.

- [x] T2: Implement deterministic CSV package builder (AC: 5-11, 13)
  - [x] Reuse the Story 5.C.3 cross-domain aggregation and sanitization path.
  - [x] Refactor the JSON builder into a canonical snapshot builder plus JSON/CSV renderers.
  - [x] Create deterministic `manifest.csv`.
  - [x] Create section CSV files for available non-empty sections.
  - [x] Serialize nested values as canonical JSON cells.
  - [x] Escape formula-like CSV cells.
  - [x] Build deterministic zip bytes and store them in an internal JSONB envelope.
  - [x] Hash and size the actual downloadable zip bytes.

- [x] T3: Update worker and download behavior (AC: 5, 11-13)
  - [x] Complete queued requests according to their stored format.
  - [x] Emit format-aware audit/outbox evidence.
  - [x] Return JSON for JSON exports and zip bytes for CSV exports.
  - [x] Preserve owner-only 404, queued 409, expired 410, and failure behavior.
  - [x] Update CLI docstring/description and route summaries from JSON-only to data export / JSON+CSV.

- [x] T4: Add focused tests and run gates (AC: 1-15)
  - [x] Test default JSON request remains backward compatible.
  - [x] Test CSV request creation/idempotency and JSON/CSV active request independence.
  - [x] Test CSV zip package contents, manifest, section files, redaction, and formula escaping.
  - [x] Test CSV download media type and expired/queued/cross-tenant behavior.
  - [x] Test no-body POST remains JSON and unsupported formats do not create rows/events.
  - [x] Test completed CSV immutability under repeated worker runs.
  - [x] Test malformed/missing CSV archive envelope returns 409.
  - [x] Test CSV worker failure does not emit completion outbox.
  - [x] Run regression and static gates.

## Dev Notes

### Existing Patterns To Reuse

- Story 5.C.3 `auth_service.data_export` is the implementation anchor. Extend it rather than creating a second export service.
- Keep `auth-service` from importing solver-orchestrator or billing-service ORM models. Cross-domain reads must stay raw SQL with table-existence checks.
- Keep request/status/download endpoints owner-scoped through `_resolve_user_from_jwt`.
- Keep advisory lock idempotency for direct request creation, now keyed by `(user, format)`.
- Keep worker row locking with `FOR UPDATE SKIP LOCKED`.
- Keep recursive redaction via `sanitize_export_value`.
- Keep unavailable Chat section explicit (`not_persisted_v1`).

### Migration Compatibility

`infra/local-init/01-schema.sql` is used as idempotent local/CI bootstrap, not a linear migration runner. If changing constraints or indexes added by Story 5.C.3, use `ALTER TABLE ... DROP CONSTRAINT IF EXISTS` and `DROP INDEX IF EXISTS` before recreating the CSV-compatible definitions. Do not leave both JSON-only and JSON/CSV constraints active.

### CSV Package Shape

For `format="csv"`, store an internal JSONB envelope similar to:

```json
{
  "schema_version": "pipl_export_csv_v1",
  "format": "csv",
  "generated_at": "2026-05-30T00:00:00Z",
  "subject": {"user_id": "..."},
  "manifest": {
    "sections": {
      "auth.profile": {"status": "available", "count": 1, "path": "auth/profile.csv"},
      "chat.messages": {"status": "unavailable", "count": 0, "reason": "not_persisted_v1"}
    },
    "files": [
      {"path": "manifest.csv", "rows": 12, "sha256": "..."},
      {"path": "auth/profile.csv", "rows": 1, "sha256": "..."}
    ]
  },
  "archive": {
    "media_type": "application/zip",
    "filename": "opticloud-pipl-data-export-csv.zip",
    "encoding": "base64",
    "sha256": "...",
    "bytes": 1234,
    "content_base64": "..."
  }
}
```

The download endpoint must return the decoded zip bytes, not this envelope. The envelope is only the v1 persistence representation.

Archive file names must be deterministic and non-user-controlled:

- `manifest.csv`
- `auth/profile.csv`
- `auth/api_keys.csv`
- `auth/account_deletion_requests.csv`
- `auth/account_merge_proposals.csv`
- `auth/account_freeze_appeals.csv`
- `auth/risk_flags.csv`
- `auth/audit_logs.csv`
- `solver/optimizations.csv`
- `solver/optimization_batches.csv`
- `solver/predictions.csv`
- `billing/saga_instances.csv`
- `billing/credit_transactions.csv`
- `billing/subscriptions.csv`

Unavailable sections appear only in `manifest.csv` unless they later gain persisted rows.

### CSV Serialization Rules

- Use Python's `csv` module, never manual comma joining.
- Use `\n` line endings and UTF-8 encoding.
- Sort section names, file paths, row headers, and rows according to the deterministic order already enforced by SQL ordering.
- For each available non-empty section, derive headers from the union of row keys and sort headers lexicographically.
- Convert nested dict/list cells to canonical JSON strings with sorted keys and compact separators.
- Prefix formula-like string cells with a single quote when they begin with `=`, `+`, `-`, `@`, tab, carriage return, or newline.
- Apply formula escaping after nested JSON serialization and after secret redaction.
- Do not include file names derived from user-controlled values.
- Build zip entries with stable timestamps, no archive comments, no per-file comments, and sorted file order.

### Data Consistency And Idempotency Rules

- Active request semantics are per format: `status in ('queued', 'processing', 'completed')` and `expires_at is null or expires_at > now`.
- JSON and CSV can both be active for the same user.
- A new CSV request after CSV expiry is allowed and creates a new row; expired rows remain compliance traces.
- Worker completion must not rewrite already completed packages.
- Package SHA-256 and byte size are computed over the exact downloadable bytes.
- Request-time advisory locks must include the requested format, otherwise concurrent JSON and CSV requests can unnecessarily serialize or reuse the wrong row.
- The database uniqueness guarantee must be generalized from `uq_data_export_requests_inflight_json` to a format-aware active/in-flight index without breaking existing rows.
- Renderer failures after snapshot construction must fail only the current request and must not emit partial package data.
- Audit and outbox payloads must remain pointer-safe and should include only counts, hashes, ids, format, and download URL; never include CSV archive base64 or row-level export content.
- `package_json` may contain base64 archive content for v1 persistence, but audit/outbox metadata must not.

### Refactor Guardrail

The preferred implementation shape is:

1. Build one canonical sanitized export snapshot with `schema_version="pipl_export_snapshot_v1"` and no format-specific archive payload.
2. Render JSON from that snapshot with the existing `pipl_export_json_v1` schema.
3. Render CSV zip from that snapshot with `pipl_export_csv_v1`.

This prevents the JSON and CSV section sets from drifting.

### API Compatibility

Request examples:

```json
{}
```

```json
{"format": "csv"}
```

No body is also valid and equals `{}`. Do not require `Content-Type: application/json` for existing no-body clients.

### Suggested Test Commands

```powershell
$env:PYTHONPATH='packages/shared-py;apps/auth-service/src;apps/solver-orchestrator/src;apps/billing-service/src'; uv run pytest apps/auth-service/tests/test_data_exports.py -q
$env:PYTHONPATH='packages/shared-py;apps/auth-service/src;apps/solver-orchestrator/src;apps/billing-service/src'; uv run pytest apps/auth-service/tests/ -q
uv run ruff check apps/auth-service apps/solver-orchestrator apps/billing-service
uv run ruff format --check apps/auth-service apps/solver-orchestrator apps/billing-service
$env:PYTHONPATH='packages/shared-py;apps/auth-service/src;apps/solver-orchestrator/src;apps/billing-service/src'; uv run mypy apps/auth-service apps/solver-orchestrator apps/billing-service
uv tool run pre-commit run bandit --all-files
git diff --check
```

## Definition Of Done

- Story file has passed 3 pre-implementation adversarial review rounds and revisions.
- Implementation satisfies every Acceptance Criterion without adding out-of-scope API surfaces.
- Post-implementation code review is completed and findings are fixed or explicitly documented.
- Local quality gates and GitHub CI pass.
- Story and sprint status are updated to `done` only after review and gates.
- Branch is pushed, PR is created, merged to `main`, remote branch is deleted, and local `main` is synced.

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Debug Log References

- Baseline commit: `1c811f55d6eb5dd0d653887fab1e746c34508f4b`.
- Pre-existing focused data export tests passed before implementation: 6 tests.
- Red phase: CSV request/body/download tests failed before implementation because only JSON was supported.
- Green phase: focused data export tests passed after implementation: 11 tests.
- Full auth-service regression passed after implementation: 83 tests.
- Full billing-service regression passed: 271 tests.
- Full solver-orchestrator regression passed: 283 tests.
- Static gates passed: ruff check, ruff format --check, mypy, Bandit pre-commit hook, and `git diff --check`.
- Post-implementation code review found one CSV usability defect: negative numeric amounts were formula-escaped as text because Decimals were already JSON-normalized to strings before CSV rendering. Patched formula escaping to leave numeric literals unescaped while still escaping formula-like strings, with a regression assertion.

### Completion Notes List

- Added optional `format` request body for `POST /v1/auth/data-exports`; no-body calls remain JSON.
- Generalized `data_export_requests` schema/model constraints and active-request uniqueness from JSON-only to JSON/CSV.
- Refactored export generation into a canonical sanitized snapshot plus JSON and CSV renderers.
- Added deterministic CSV zip archive generation with manifest, section files, stable zip metadata, redaction, formula-string escaping, and persistence-only base64 envelope.
- Updated download endpoint to return JSON for JSON exports and authenticated `application/zip` attachment bytes for CSV exports.
- Updated worker/CLI/docs strings and focused tests for CSV idempotency, archive content, malformed envelopes, immutability, and existing JSON compatibility.
- Completed post-implementation code review, patched numeric CSV escaping, ran regression/static gates, and marked story done.

### File List

- `_bmad-output/stories/5-c-4-pipl-data-export-csv.md`
- `_bmad-output/stories/sprint-status.yaml`
- `infra/local-init/01-schema.sql`
- `apps/auth-service/src/auth_service/data_export.py`
- `apps/auth-service/src/auth_service/data_export_cli.py`
- `apps/auth-service/src/auth_service/models.py`
- `apps/auth-service/src/auth_service/routes.py`
- `apps/auth-service/src/auth_service/schemas.py`
- `apps/auth-service/tests/test_data_exports.py`

## Change Log

- 2026-05-30 - Story created with CSV format scope, deterministic zip package contract, and 5.C.3 lifecycle reuse.
- 2026-05-30 - Implemented CSV export request/status/download lifecycle, deterministic zip package renderer, schema compatibility update, and focused tests; status set to code-review.
- 2026-05-30 - Completed post-implementation review, patched numeric CSV escaping, ran full gates, and marked story done.

## Pre-Implementation Adversarial Review

### Round 1 - Boundary, Scope, CSV Safety, And Download Semantics

Findings:

1. The initial story accepted an optional body but did not explicitly preserve no-body POST compatibility; FastAPI can regress existing clients if the body is made required.
2. CSV package naming was underspecified; user-controlled names must not influence zip paths or archive metadata.
3. `application/zip` response behavior lacked `Content-Disposition`, making browser/download behavior ambiguous.
4. The internal JSONB envelope could be accidentally returned by the download endpoint unless the story explicitly forbids it.
5. Unsupported format handling was missing; malformed requests must not create audit/outbox noise.
6. Formula escaping needed to be ordered after redaction and nested serialization, or serialized JSON strings can still begin with dangerous spreadsheet prefixes.
7. Zip determinism mentioned timestamps but not archive comments or per-file comments.
8. Unavailable sections could produce empty CSV files that look like exported data; manifest-only representation is clearer.
9. Backward compatibility for `{"format":"json"}` versus `{}` versus no body needed to be explicit.
10. Tests did not yet require no-body compatibility or unsupported-format no-side-effect behavior.

Revision after Round 1:

- Added no-body JSON compatibility and unsupported-format no-side-effect requirements.
- Fixed CSV archive naming to a deterministic section-derived allowlist.
- Added `Content-Disposition`, persistence-only envelope, stable zip metadata, and manifest-only unavailable sections.
- Clarified formula escaping order and expanded focused tests.

### Round 2 - Drift, Data Consistency, Idempotency, And Immutability

Findings:

1. CSV could fork the JSON aggregation logic and silently drift in section coverage.
2. The story did not require a single canonical sanitized snapshot before format rendering.
3. Existing advisory lock language did not explicitly include format; JSON and CSV concurrency could serialize unnecessarily or reuse the wrong active row.
4. The DB uniqueness constraint was named and scoped for JSON only; CSV needs a generalized format-aware guarantee.
5. Completed CSV package immutability was implied but not test-required.
6. A corrupt or missing CSV archive envelope path was not specified, risking a 500 or leaked persistence structure.
7. Renderer failures after snapshot build needed explicit failure semantics.
8. Tests did not assert repeated worker runs leave completed CSV hash/outbox unchanged.
9. Package byte/hash semantics were correct but needed to be tied to the downloadable zip bytes in tests.
10. Refactoring could accidentally change JSON package schema; the story needed a guardrail to preserve JSON output shape.

Revision after Round 2:

- Added a canonical snapshot builder requirement and JSON/CSV renderer split.
- Added format-aware request locks and uniqueness rules.
- Added completed CSV immutability, malformed-envelope 409 behavior, and renderer failure semantics.
- Expanded tests for immutability and corrupt archive handling.

### Round 3 - Dependency Consistency, Schema Compatibility, Audit Closure, And Delivery

Findings:

1. The JSON-only check constraint in `infra/local-init/01-schema.sql` would reject CSV rows unless explicitly replaced.
2. The JSON-only unique index name/scope could leave stale constraints in local DBs if not dropped and recreated.
3. CLI and endpoint summaries still said JSON-only; that would create OpenAPI/docs drift.
4. Outbox payload requirements did not explicitly forbid embedding the CSV archive/base64 content.
5. `package_json` base64 storage is acceptable for v1, but audit/outbox must stay pointer-only.
6. FastAPI body parsing can accidentally require `Content-Type: application/json`; no-body clients need an explicit compatibility test.
7. The story did not mention local bootstrap idempotency, which is how this repo applies schema changes in tests.
8. Section count evidence in outbox should remain counts-only, not row dumps.
9. Definition of Done included GitHub sync, but tasks did not require updating CLI/docs surfaces.
10. A CSV-compatible schema change must not break existing JSON rows or JSON response validation.

Revision after Round 3:

- Added schema migration compatibility requirements for the JSON-only constraint/index.
- Added CLI/OpenAPI wording updates and no-body API compatibility guidance.
- Added pointer-safe audit/outbox constraints for CSV archive content.
- Added explicit tests and tasks for schema idempotency, docs drift, and JSON compatibility.

## Senior Developer Review (AI)

Findings:

- [x] [Review][Patch] CSV formula escaping treated already-normalized negative numeric values such as `-10.0000` as spreadsheet formulas and prefixed them with a single quote. That made billing amounts harder to use in spreadsheets. Patched `_needs_csv_formula_escape` to leave signed numeric literals unescaped while still escaping strings beginning with `=`, `@`, tab/newline, and non-numeric `+`/`-` prefixes. Added a regression assertion that charged negative amounts remain numeric in CSV while a string `=SUM(1,1)` is escaped.

Decision: Approved after patch.
