# WCAG 2.2 Upgrade Path Runbook

Story 9.5 owns the WCAG 2.1 AA v1 to WCAG 2.2 v1.5+ upgrade path for NFR-A.

## Local Commands

```bash
uv run python scripts/validate_wcag_2_2_upgrade_path.py
uv run pytest tests/test_wcag_2_2_upgrade_path.py -q
pnpm --filter @opticloud/ui test -- src/hooks/useA11y.wcag22.test.tsx
pnpm --filter @opticloud/ui test:a11y
pnpm --filter @opticloud/ui typecheck
```

Use optional real evidence mode only for redacted operator evidence:

```bash
uv run python scripts/validate_wcag_2_2_upgrade_path.py --evidence reports/wcag-2-2-upgrade/<run_id>/upgrade_manifest.json
```

## Scope Boundary

WCAG 2.2 adds 9 success criteria compared with WCAG 2.1. This project story is a P78 4-criteria engineering gate, not a full WCAG 2.2 AA conformance claim.

The Story 9.5 project criteria are:

| Criterion | Level | Story 9.5 meaning |
|---|---:|---|
| 2.4.11 Focus Not Obscured (Minimum) | AA | Standard a11y Hook v2 readiness plus modal evidence |
| 2.4.12 Focus Not Obscured (Enhanced) | AAA | Tier 1.5+ enhanced readiness, not an AA-only claim |
| 2.5.7 Dragging Movements | AA | ExcelDropZone non-drag FilePicker alternative evidence |
| 3.2.6 Consistent Help | A | Console help placement audit and rollout evidence |

Deferred WCAG 2.2 criteria remain outside this P78 gate: 2.4.13, 2.5.8, 3.3.7, 3.3.8, and 3.3.9. Criteria 2.5.8 and 3.3.8 are full-WCAG-2.2-AA blockers, so this runbook does not prove full WCAG 2.2 AA conformance.

Story 9.1 remains the upstream WCAG 2.1 AA quarterly audit. Story 9.5 extends the upgrade path and does not mutate the Story 9.1 audit scope.

## Operator Flow

1. Run the local commands above from the repository root.
2. Confirm `tools/wcag_2_2_upgrade/wcag_2_2_upgrade_contract.json` still records W3C 9-vs-project-4 boundary.
3. Review Standard a11y Hook v2 readiness:
   - `focus_not_obscured`
   - `consistent_help_id`
   - `dragging_alternative`
4. Review component refactor evidence:
   - `useA11y`
   - `ConfirmationModal`
   - `ExcelDropZone`
   - `FilePicker`
   - `Console consistent help placement`
5. Record only redacted evidence under `reports/wcag-2-2-upgrade/<run_id>/upgrade_manifest.json`.
6. Run the validator with `--evidence` before using that evidence for release review.

## Evidence Rules

Evidence must be public-safe. Do not include tenant IDs, user IDs, customer IDs, participant identifiers, emails, phone numbers, API keys, bearer tokens, cookies, passwords, credentialed URLs, production hostnames, absolute local paths, raw browser logs, prompt payloads, or provider payloads.

Static examples must keep:

- `example_only=true`
- `real_wcag_2_2_conformance_claimed=false`
- `real_third_party_audit_completed=false`
- `real_component_refactor_completed=false`
- `release_approved=false`

Real evidence must include all four project criteria, all hook v2 checks, all component checks, all source snapshots, redaction review, and findings. Any failed criterion, hook check, component check, or stale source snapshot must link to a finding with ticket refs.

## Stop-Ship Policy

Do not mark `release_approved=true` while any P0/P1/P2 NFR-A finding is open, in progress, or deferred.

Do not claim full WCAG 2.2 AA conformance from this story. A full conformance claim requires all WCAG 2.2 AA requirements, including deferred blockers such as 2.5.8 and 3.3.8, plus the future audit scope defined outside Story 9.5.

## Rollback

If the hook readiness change causes UI regressions, revert only the affected `packages/ui` hook/component changes and rerun:

```bash
pnpm --filter @opticloud/ui test -- src/hooks/useA11y.wcag22.test.tsx
pnpm --filter @opticloud/ui test:a11y
pnpm --filter @opticloud/ui typecheck
uv run python scripts/validate_wcag_2_2_upgrade_path.py
```

Keep the governance contract and failing evidence visible until the rollback or follow-up ticket is closed.
