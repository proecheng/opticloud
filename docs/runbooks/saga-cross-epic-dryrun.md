# Saga Cross-Epic Dry-Run

This runbook is offline only. It validates the static 5.A.0c dry-run package and does not run billing-service or solver-orchestrator, call live endpoints, open DB connections, or prove real committee approval.

## Scope

- Validate `tools/saga_cross_epic_dryrun/dryrun_plan.json`.
- Validate `tools/saga_cross_epic_dryrun/owner_signoff.example.json`.
- Recompute the 5.A.0b fixture manifest hash from `CONTRACT_FIXTURE_MANIFEST`.
- Confirm the owner process covers Billing Lead, Solver Lead, SRE, and the consulted Provider Interface Lead.
- Confirm the decision is `standard_first_simplified_fallback`.

## Commands

```powershell
$env:PYTHONPATH='packages/shared-py'
uv run python scripts/validate_saga_cross_epic_dryrun.py

$env:PYTHONPATH='packages/shared-py'
uv run pytest tests/test_saga_cross_epic_dryrun.py -q
```

## Boundaries

- The example sign-off status must remain `not_a_real_signoff`.
- The example does not prove real committee approval, CI status, release approval, or production dry-run evidence.
- Do not add personal names, email addresses, tenant identifiers, account identifiers, service URLs, bearer tokens, prompts, raw inputs, or optimization payloads.
- Keep 5.A.0c changes in static assets, validator, tests, and story tracking only.

## Owner Checklist

- Billing Lead reviews charge, refund, rollback, idempotency, and the non-executable budget pause gap.
- Solver Lead reviews reserve/finalize call semantics already locked by Epic 3 tests.
- SRE reviews timeout, outbox/reconciler observability, rollback, and incident-path boundaries.
- Provider Interface Lead is consulted for future SC9 compatibility and is non-blocking for this story.
