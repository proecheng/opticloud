# Graded Protection Evidence Runbook

Story 9.8 owns the offline graded-protection evidence aggregation contract for MLPS Level 2 readiness. It does not prove a real certificate, public-security filing, TSA issuance, blockchain preservation, legal signature, vendor assessment, external ticket, or production release approval by itself.

## Local Commands

```powershell
uv run python scripts/validate_graded_protection_evidence.py
uv run pytest tests/test_graded_protection_evidence.py -q
uv run ruff check scripts/validate_graded_protection_evidence.py tests/test_graded_protection_evidence.py
git diff --check
```

Validate committed real evidence only when a redacted quarterly manifest exists:

```powershell
uv run python scripts/validate_graded_protection_evidence.py --evidence reports/graded-protection-evidence/<run_id>/evidence_manifest.json
```

## Quarterly Flow

1. Collect redacted evidence artifacts for the required domains in the Story 9.8 contract.
2. Produce one hash manifest entry for every non-deferred artifact.
3. Record TSA receipt metadata only after an operator has a real RFC 3161 timestamp token.
4. Record one selected blockchain receipt only after an operator has a real AntChain or Tencent Zhixin Chain preservation receipt.
5. Record Legal, Compliance, Security, and SRE review outcomes.
6. Add findings and ticket refs for every missing, stale, failed, yellow, red, or deferred item.
7. Update the Story 9.7 governance dashboard handoff with the graded-protection rollup.

## MLPS Level 2 Boundary

The contract references GB/T 22239-2019 as reference-only context. It is not legal advice, not a measurement institution deliverable, and not a certificate. Standard-track M5 release approval requires a real MLPS Level 2 certificate artifact. Simplified-track v1.5 deferral must carry a ticket-backed finding.

## TSA And Blockchain

TSA receipts must record provider, artifact id, hash, timestamp, policy/profile, certificate reference, receipt artifact path, and verification status. Blockchain receipts must record selected provider, artifact id, hash, chain receipt id, preservation time, receipt artifact path, and verification status.

CI must not call TSA, AntChain, Tencent Zhixin Chain, legal e-signature, assessment vendor, or external ticket APIs.

## Redaction

Do not commit tenant/user/customer ids, emails, phone numbers, API keys, bearer tokens, cookies, passwords, secrets, private keys, TSA credentials, blockchain API credentials, legal signature private material, credentialed URLs, production hostnames, absolute local paths, raw logs, raw screenshots, raw vulnerability payloads, raw network maps, prompt/provider payloads, raw metric labels, or raw customer-identifying dimensions.

## Ticket Policy

Every missing, stale, failed, yellow, red, or deferred domain, artifact, preservation receipt, legal review, or dashboard handoff must reference at least one finding. Every finding must include ticket refs with owner, severity, due date, and status.

## Release Gates

Unresolved P0/P1/P2 findings block release approval. Failed redaction blocks release approval. Standard M5 release approval also requires the MLPS Level 2 certificate flag and certificate artifact id. Simplified v1.5 without a certificate must remain a deferral with a finding.

## Rollback

If evidence is unsafe or incorrect, remove the unsafe `reports/graded-protection-evidence/<run_id>/` directory from the change, rerun the validator, and keep the static contract as the source of truth. Revert only graded-protection evidence files involved in the failed release.

## Story 9.7 Handoff

Story 9.7 owns the governance dashboard. Story 9.8 records the dashboard version, dashboard manifest path, rollup status, finding ids, and graded-protection handoff flag so the dashboard can expose MLPS evidence readiness without claiming real certification.
