# Sandbox Security Audit Runbook

Owner: Security / Architect

Status: M3.7 static audit contract ready; real runtime validation and third-party pentest evidence are produced by future operator PRs only.

## Purpose

M3.7 defines the sandbox security audit contract for gVisor, AppArmor, seccomp, capability drop, deny-all egress, and CRG6 supply-chain checks. CI is static/structural and does not prove real gVisor, AppArmor, seccomp, Kubernetes, or kernel enforcement.

## Local Validation

Run:

```bash
uv run python scripts/validate_sandbox_security_audit.py
uv run pytest tests/sandbox/security -q
```

These commands validate committed metadata, manifests, profiles, and evidence examples. They must not run exploit payloads, fork bombs, Docker socket probes, host namespace probes, registry pulls, or network calls.

## Runtime Validation

For staging/runtime validation, an operator must deploy the manifest to a configured cluster where `runtimeClassName: gvisor` maps to runsc. Validate AppArmor profile loading, seccomp RuntimeDefault, drop-all capabilities, read-only root filesystem, deny-all egress, and absence of host namespace/hostPath/Docker socket drift.

## Third-Party Pentest Evidence

Future third-party pentest evidence must be submitted under:

```text
reports/sandbox-security/<run_id>/pentest_evidence.json
```

Evidence must bind to the committed audit plan, attack scenarios, supply-chain policy, hardening manifest, and AppArmor profile SHA-256 values. Submit only redacted artifacts. Do not commit generated reports in this implementation. Do not commit raw third-party report text, customer data, credentials, exploit payloads, or host details.

## Failure Response

If runtime escape, privileged drift, missing redaction, or supply-chain policy failure is found, stop the run and open a P0/P1 security investigation before retry. Include the scenario ID, run ID, sanitized artifact references, owner, suspected cause, and immediate containment action.

## Boundary

M3.7 does not change sandbox-runner execution behavior and does not prove quarterly P0 escape rate. It creates audit contracts, static validators, and evidence structure for future operator and pentest work.
