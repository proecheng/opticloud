# Error i18n Quarterly Audit Runbook

## Purpose

Story 9.6 turns FG1.3 error-message i18n into a quarterly governance loop. The static CI gate proves the audit contract, dictionary/catalog parity, legacy backlog register, evidence shape, and redaction rules. It does not claim that a real quarterly audit has already run or that every legacy backend `HTTPException(detail=...)` has been migrated.

Static validation:

```bash
uv run python scripts/validate_error_i18n_audit.py
uv run pytest tests/test_error_i18n_audit.py -q
uv run python scripts/error_message_i18n_single_source.py
uv run pytest tests/test_error_i18n_single_source.py -q
```

Real evidence validation, when a redacted operator manifest exists:

```bash
uv run python scripts/validate_error_i18n_audit.py \
  --evidence reports/error-i18n-audit/<run_id>/audit_manifest.json
```

## Audit Scope

The hardcoded error string count = 0 gate applies to public FG1.3 error-contract surfaces:

- `typescript_problem_detail`: production TS/TSX RFC 7807 problem-detail construction, enforced by `error-message-i18n-single-source`.
- `i18n_dictionary_parity`: `packages/i18n/errors.zh-CN.yaml` and `errors.en-US.yaml` key parity with non-empty `title`, `detail`, and `remediation`.
- `solver_error_catalog`: solver-orchestrator `ERROR_CATALOG` remediation keys must exist in both dictionaries.
- `billing_problem_details`: billing RFC 7807 helper generic keys must exist in both dictionaries.
- `shared_rfc7807_helper`: shared helper stays shape-only and does not introduce unregistered keys.
- `sdk_preservation_fixture`: SDK RFC 7807 fixture remediation keys must exist in both dictionaries.
- `legacy_http_exception_register`: production FastAPI `HTTPException(detail=literal)` backlog is discovered and pinned, but not migrated by this story.

Internal Python `ValueError`, `RuntimeError`, `AssertionError`, CLI diagnostics, tests, Storybook stories, story markdown, and developer-only validation messages are excluded from the public FG1.3 count.

## Operator Flow

1. Create a run id such as `error-i18n-audit-2026q2`.
2. Run the static validator and focused tests from the Purpose section.
3. Review every scan class result and record it in `reports/error-i18n-audit/<run_id>/audit_manifest.json`.
4. For the legacy_http_exception_register, record the current count and create ticket-backed findings until each public legacy route is migrated or explicitly accepted.
5. Add dictionary entries before introducing new production `remediation_hint_key` values.
6. Validate the evidence manifest before opening an evidence PR.

## Evidence Rules

Do not commit tenant IDs, user IDs, customer IDs, account IDs, emails, phone numbers, API keys, bearer tokens, cookies, passwords, secrets, credentialed URLs, production hostnames, absolute local paths, raw logs, raw error payloads, prompts, provider requests, or provider responses.

Allowed evidence is limited to:

- `audit_manifest.json`
- redacted scan summaries
- public-safe finding summaries
- ticket references with owner, severity, due date, and status

## Ticket Policy

Every failed, missing, or stale scan class must reference at least one finding. Any nonzero legacy public HTTPException backlog in real evidence must reference a finding. A valid ticket reference includes ticket ID, owner, severity, due date, and status.

P0/P1/P2 FG1.3 findings are stop-ship until resolved. The manifest must not mark release approval while unresolved P0/P1/P2 findings remain open, in progress, or deferred.

## Rollback

If the CI gate or evidence validator fails:

1. Stop release approval for the affected change.
2. Fix the dictionary, catalog, source drift, manifest, or redaction issue.
3. Rerun `uv run python scripts/validate_error_i18n_audit.py`.
4. Rerun `uv run pytest tests/test_error_i18n_audit.py -q`.
5. Rerun Story 8.B.5 gates:
   - `uv run python scripts/error_message_i18n_single_source.py`
   - `uv run pytest tests/test_error_i18n_single_source.py -q`
6. Keep the evidence PR open until missing or failed scan classes have ticket references and stop-ship findings are resolved.

## Boundaries

- Story 8.B.5 owns the single-source TS gate foundation.
- Story 8.B.6 owns SDK `errors[]` preservation.
- Story 9.6 owns the quarterly audit contract and evidence gate.
- Story 9.7 owns the unified governance dashboard.
- This runbook does not create real tickets automatically and does not complete full backend runtime i18n migration.
