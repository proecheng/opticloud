# NFR-S P0 Security Drills

Story 9.4 defines the governance loop for three quarterly P0 security drills:
`sandbox_privilege_escape`, `data_exfiltration`, and `billing_ledger_corruption`.
This runbook is static/operator guidance. CI validates contracts and redacted
evidence shape only; it does not run exploit, exfiltration, billing mutation, or
production incident automation.

## Local Commands

```powershell
uv run python scripts/validate_nfr_security_p0_drills.py
uv run pytest tests/test_nfr_security_p0_drills.py -q
git diff --check
```

For a real redacted evidence PR:

```powershell
uv run python scripts/validate_nfr_security_p0_drills.py --evidence reports/nfr-security-p0-drills/<run_id>/drill_manifest.json
```

## Cadence

Run the full `quarterly` flow for the standard program. For the lite program,
run `annual_lite` once per year and preserve the same evidence schema.

## Evidence Path

Real evidence must be committed only at:

```text
reports/nfr-security-p0-drills/<run_id>/drill_manifest.json
```

The directory name must equal `run_id`. Do not commit raw logs, raw SQL dumps,
raw ledger rows, raw prompts/files, provider payloads, production hostnames,
customer identifiers, credentials, webhook URLs, or exploit payloads.

## Quarterly Flow

1. Select one redacted `run_id`.
2. Run tabletop walkthroughs for all three P0 scenarios.
3. Record source snapshots for the current sandbox, privacy/data, and billing
   substrates.
4. Execute SOP gates: declare P0, assign incident commander, make containment
   decision, complete redaction review, assign postmortem owner, and review
   ticket closure.
5. Record containment actions and 24h timeline.
6. Prepare a public-safe postmortem template for each scenario.
7. Open tickets for every failed, blocked, or missing item.
8. Run validator before requesting release approval.

## Scenario SOPs

`sandbox_privilege_escape`: Use the M3.7 sandbox audit plan as the substrate.
Do not run fork bombs, mount commands, Docker socket probes, namespace probes,
or privilege escalation commands. The drill is a tabletop or redacted staging
walkthrough only.

`data_exfiltration`: Simulate unauthorized data access response without using
real customer data. Evidence must use redacted summaries and must not include
raw uploads, prompts, provider payloads, tenant/user/customer identifiers, or
production hosts.

`billing_ledger_corruption`: Simulate a Credits/Saga/reconciliation incident
using redacted summaries. Evidence must not include raw `credit_transactions`
rows, raw SQL dumps, customer balances, payment data, or user identifiers.

## 24h Timeline

Each scenario must record:

- `p0_declared_utc`
- `incident_commander_assigned_utc`
- `containment_started_utc`
- `status_page_decision_utc`
- `postmortem_due_utc`

`postmortem_due_utc` must be exactly 24h after `p0_declared_utc`.

## Ticket Policy

Every failed scenario, failed SOP gate, missing containment action, failed
timeline check, missing source snapshot, or incomplete postmortem section must
reference at least one ticket with owner, severity, due date, and status.

Unresolved P0/P1/P2 findings block release approval. `release approval` may be
true only when all P0/P1/P2 findings are resolved.

## Stop-Ship

Stop release when any of these are true:

- A scenario is failed or blocked without a ticket.
- A 24h postmortem timeline is invalid.
- Evidence contains sensitive material or exploit payloads.
- Redaction review is missing.
- Any P0/P1/P2 finding remains open, in progress, or deferred.

## Rollback

If evidence validation fails, remove the unsafe evidence file from the PR,
replace it with redacted summaries, reopen tickets for missing closure, and
rerun the validator. Do not weaken the contract or delete canonical scenarios
to pass CI.

## Dashboard Handoff

Story 9.7 should consume the latest validated NFR-S P0 drill evidence pointer
and status summary. Story 9.4 does not build the unified governance dashboard.
