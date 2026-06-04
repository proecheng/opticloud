# Quarterly Accessibility Audit Runbook

## Purpose

Story 9.1 turns the existing `packages/ui` axe-core / jest-axe baseline into a quarterly NFR-A governance loop. The static CI gate proves wiring and evidence shape; it does not prove that a real quarterly panel has already happened.

Current automated gate:

```bash
pnpm --filter @opticloud/ui test:a11y
```

Static contract validation:

```bash
uv run python scripts/validate_a11y_quarterly_audit.py
uv run pytest tests/test_a11y_quarterly_audit.py -v
```

## Operator Flow

1. Start the quarterly audit six weeks before the quarter close.
2. Confirm the `packages/ui` `test:a11y` script includes every committed `packages/ui/src/components/**/*.a11y.test.tsx` file.
3. Run the automated axe gate locally and in CI.
4. Build the six-profile x four-sub-persona manual sampling matrix:
   - profiles: screen reader, keyboard-only, high contrast, low vision, motor, cognitive
   - sub-personas: Li Gong cURL, Lina CSV, Lao Zhang Excel, Chen Architect SDK
5. Record only public-safe summaries and finding IDs in `reports/a11y-quarterly/<run_id>/audit_manifest.json`.
6. Validate the evidence manifest before opening an evidence PR:

```bash
uv run python scripts/validate_a11y_quarterly_audit.py \
  --evidence reports/a11y-quarterly/<run_id>/audit_manifest.json
```

## Panel SOP

- Cadence: quarterly.
- Recruitment lead time: 6 weeks.
- Target: at least 5 participants per sub-persona.
- Backup pool: at least 3x target capacity.
- Channels: logistics engineering group, data analyst community, manufacturing engineering LinkedIn, and SaaS architect community.
- Compensation is a placeholder until finance and legal approval exist.
- This is sub-persona workflow sampling. Do not represent it as disabled-user panel completion.

## Evidence Rules

Do not commit participant names, emails, phone numbers, tenant IDs, customer IDs, user IDs, API keys, bearer tokens, cookies, provider payloads, prompts, credentialed URLs, absolute local paths, raw browser logs, screen recordings, or unredacted interview notes.

Allowed evidence is limited to:

- `audit_manifest.json`
- public-safe finding summaries
- ticket references with owner, severity, due date, and status
- redacted notes that cannot identify a participant or customer

## Ticket Policy

Every failed automated or manual check must reference at least one ticket. A valid ticket reference includes:

- ticket ID
- owner
- severity
- due date
- status

P0/P1/P2 findings are stop-ship until resolved. The manifest must not mark release approval while unresolved P0/P1/P2 accessibility findings remain open, in progress, or deferred.

## Rollback

If the CI gate or evidence validator fails:

1. Stop release approval for the affected UI change.
2. Revert or fix the package/script/manifest drift.
3. Rerun `uv run python scripts/validate_a11y_quarterly_audit.py`.
4. Rerun `pnpm --filter @opticloud/ui test:a11y`.
5. Keep the evidence PR open until findings have ticket references and stop-ship findings are resolved.

## Boundaries

- This runbook does not run Lighthouse, Storybook Chromatic, external axe SaaS, screen reader recordings, or production telemetry.
- This runbook does not create GitHub or Linear tickets automatically.
- This runbook does not approve WCAG 2.2 compliance.
- WCAG 2.2 upgrade planning and criteria are owned by Story 9.5.
