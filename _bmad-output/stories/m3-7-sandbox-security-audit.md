# Story M3.7: Sandbox Security Audit

Status: done

owner: Security / Architect

## Story

As a Security / Architect,
I want a sandbox security audit contract with 15 attack scenarios, runtime hardening manifests, validator tests, CI gates, operator runbooks, and future pentest evidence binding,
so that NFR-S P0 sandbox privilege escalation and escape risk can be engineered toward zero incidents per quarter without pretending that static CI proves real gVisor isolation.

## Acceptance Criteria

1. Sandbox security audit plan is explicit and traceable to PMR3 / CRG6.
   - Add `infra/sandbox-security/audit_plan.json` as the M3.7 source of truth.
   - The plan must set `audit_version=sandbox_security_audit_v1`, `source_story=M3.7`, `source_decision=PMR3`, and `source_gap=CRG6`.
   - The plan must define exactly 15 attack scenarios: 12 container escape / policy bypass scenarios and 3 supply-chain attack scenarios.
   - The plan must list the scenario IDs in canonical order and the validator must require the same ordered ID list in `attack_scenarios.json`.
   - The plan must tie each scenario to an expected guard: gVisor runtime class, AppArmor, seccomp, capability drop, read-only filesystem, deny-all egress, no host paths, SBOM diff, or dependency allow/deny rules.
   - Every expected guard listed in the plan must be validated by at least one concrete validator rule or named test.
   - The plan must not contain live exploit code, production hostnames, credentials, customer data, real pentest notes, or third-party report text.
   - Attack scenarios must be descriptive metadata only; no scenario asset may include executable exploit payloads, shell fork bombs, mount commands, Docker socket commands, credential probes, or host traversal scripts.

2. The 12 sandbox escape / policy bypass scenarios are deterministic and local-testable.
   - Add machine-readable scenario definitions under `infra/sandbox-security/attack_scenarios.json`.
   - The scenario set must include: fork bomb, root filesystem write, external network egress, Docker socket access, `SYS_PTRACE`, mount namespace escape, host path mount, privileged container request, host PID/IPC/network request, Linux capability escalation, kernel module load, and `/proc` host inspection.
   - Each scenario must define `scenario_id`, `category=container_escape`, `attack_vector`, `expected_guard`, `expected_result=blocked`, and `automation_mode`.
   - Scenario IDs must be stable and unique, use the prefix `escape-`, and must be referenced by the audit plan.
   - Local CI must validate scenario metadata and guard coverage only. It must not run real container escapes, fork bombs, Docker socket probes, or host namespace probes.
   - Tests may use mutated JSON/YAML fixtures but must not invoke shell commands that attempt privileged operations.

3. The 3 CRG6 supply-chain attack scenarios are covered without pulling from the network.
   - The scenario set must include: typosquat PyPI package, poisoned base image, and dependency hijack via SBOM diff.
   - Add a static SBOM / dependency policy file under `infra/sandbox-security/supply_chain_policy.json`.
   - The policy must define allowed package names, denied typosquat patterns, allowed base image digests or digest placeholders, and SBOM diff rules.
   - Supply-chain scenario IDs must be stable and unique, use the prefix `supply-chain-`, and must be referenced by the audit plan.
   - Tests must prove typosquat, poisoned image digest drift, and unexpected dependency additions are rejected by the validator.
   - CI must not call PyPI, Docker Hub, registries, vulnerability feeds, or external network services.

4. Runtime hardening manifests encode the intended sandbox deployment posture.
   - Add a Kubernetes manifest or manifest fragment under `infra/sandbox-security/k8s/` for sandbox-runner hardening.
   - The manifest must require `runtimeClassName: gvisor` for sandbox-runner pods.
   - The container security context must set `allowPrivilegeEscalation=false`, `readOnlyRootFilesystem=true`, `runAsNonRoot=true`, `seccompProfile.type=RuntimeDefault`, `capabilities.drop=["ALL"]`, and no added capabilities.
   - The pod or container must specify an AppArmor profile using current Kubernetes `appArmorProfile` fields rather than deprecated-only annotations.
   - The manifest must not set `privileged=true`, `hostPID=true`, `hostIPC=true`, `hostNetwork=true`, `hostPath`, Docker socket mounts, or broad writable host volumes.
   - The manifest must keep resource limits aligned with M3.1 / PRD sandbox constraints: 1 vCPU, 1 GiB memory, and no production credentials.
   - Add or validate a sandbox-runner deny-all egress `NetworkPolicy` fragment under `infra/sandbox-security/k8s/`; DNS allowance, if any, must be explicit and justified.

5. AppArmor / seccomp / capability-drop requirements are auditable.
   - Add `infra/sandbox-security/apparmor/sandbox-runner.apparmor`.
   - The AppArmor profile must deny writes to host-sensitive paths, deny raw network administration primitives, and document that it is a deployment profile, not a local CI enforcement proof.
   - The validator must reject missing AppArmor profile references, missing seccomp RuntimeDefault, missing `drop: ["ALL"]`, or any added Linux capabilities.
   - The validator must reject privileged, host namespace, host path, Docker socket, or writable root filesystem drift.
   - The validator must reject a plan/scenario guard that has no validator coverage, preventing checklist-only scenarios.

6. Future real pentest evidence is structurally defined but not fabricated.
   - Add `infra/sandbox-security/pentest_evidence.schema.json`.
   - Add `infra/sandbox-security/pentest_evidence.example.json` with `example_only=true`.
   - Real pentest evidence, when produced later, must live under `reports/sandbox-security/<run_id>/pentest_evidence.json`.
   - Real evidence must set `example_only=false`, include exactly one third-party-reviewed scenario from the 15-scenario set, bind to `audit_plan_sha256`, `attack_scenarios_sha256`, and `hardening_manifest_sha256`, and include `redaction_reviewed=true`.
   - Real evidence must also bind to `supply_chain_policy_sha256` and `apparmor_profile_sha256`.
   - Evidence must include `reviewed_scenario_id`, `reviewer_type`, `artifact_paths`, and `finding_summary_redacted`, with artifact paths restricted to `reports/sandbox-security/<run_id>/`.
   - The validator must reject evidence that claims `sandbox_security_pass`, `p0_escape_zero_quarterly`, or `gvisor_escape_impossible`.
   - This story must not commit real third-party pentest report text or claim a real third-party pass.
   - This story must not commit generated files under `reports/sandbox-security/**`, pytest caches, `__pycache__`, Docker build outputs, Syft/Grype output files, or real SBOM scan artifacts.

7. Validator and tests close drift across plan, scenarios, hardening, supply-chain policy, and evidence.
   - Add `scripts/validate_sandbox_security_audit.py`.
   - Add `tests/sandbox/security/test_sandbox_security_audit.py`.
   - Default validator mode must validate committed audit plan, attack scenarios, supply-chain policy, AppArmor profile, K8s hardening manifest, evidence schema, and example evidence.
   - Add optional `--evidence reports/sandbox-security/<run_id>/pentest_evidence.json` mode for future security evidence PRs.
   - Tests must include positive validation and negative cases for scenario count drift, missing supply-chain scenarios, missing runtime class, missing AppArmor, missing seccomp, missing capability drop, added capabilities, privileged/host namespace/hostPath/Docker socket drift, SBOM policy drift, evidence hash mismatch, fake pass claims, and wrong evidence directory.
   - Tests must include guard-coverage drift: if a scenario references an unknown or unvalidated guard, validation fails.

8. Runbook and CI make the security boundary operational without external dependencies.
   - Add `docs/runbooks/sandbox-security-audit.md`.
   - The runbook must describe local static validation, staging/runtime validation expectations, pentest evidence submission, redaction rules, and failure response.
   - The runbook must state that CI is static/structural and does not prove real gVisor, AppArmor, seccomp, or Kubernetes enforcement.
   - The runbook must define failure handling: any runtime escape, privileged drift, missing redaction, or supply-chain policy failure opens a P0/P1 security investigation before retry.
   - Extend `.github/workflows/ci.yml` with a `sandbox_security_audit` path filter and focused validation job.
   - CI must run validator and tests without Docker, gVisor, Kubernetes, registries, cloud credentials, host privileges, network access, or real pentest artifacts.

9. Workflow tracking and boundaries are explicit.
   - This story records three pre-implementation story review rounds and fixes after each round before implementation.
   - `_bmad-output/stories/sprint-status.yaml` moves `m3-7-sandbox-security-audit` to `ready-for-dev` only after all three story review rounds pass.
   - During implementation, move the story through `in-progress`, `code-review`, and `done` only when corresponding gates pass.
   - This story must not implement live exploit execution, real fork bombs, Docker daemon probing, host namespace probing, runtime K8s deployment, production gVisor setup, or real third-party pentest reports.
   - This story must not modify `apps/sandbox-runner` runtime behavior unless a validator/test requires reading existing constants; M3.7 is an audit/hardening contract story, not execution integration.
   - Final completion must update the Dev Agent Record, file list, validation evidence, post-implementation review findings/fixes, and sprint status.

## Tasks / Subtasks

- [x] Build audit plan and attack scenario assets. (AC: 1, 2, 3)
  - [x] Add `infra/sandbox-security/audit_plan.json`.
  - [x] Add `infra/sandbox-security/attack_scenarios.json`.
  - [x] Add `infra/sandbox-security/supply_chain_policy.json`.
  - [x] Pin exactly 15 scenarios, including the 3 CRG6 supply-chain scenarios.
- [x] Build runtime hardening assets. (AC: 4, 5)
  - [x] Add sandbox-runner K8s hardening manifest under `infra/sandbox-security/k8s/`.
  - [x] Add sandbox-runner deny-all egress NetworkPolicy fragment under `infra/sandbox-security/k8s/`.
  - [x] Add AppArmor profile under `infra/sandbox-security/apparmor/`.
  - [x] Encode runtimeClassName, seccomp RuntimeDefault, AppArmor, read-only FS, non-root, and drop-all capabilities.
- [x] Build future pentest evidence contract. (AC: 6)
  - [x] Add `pentest_evidence.schema.json`.
  - [x] Add `pentest_evidence.example.json`.
  - [x] Ensure example evidence cannot be mistaken for real third-party pentest evidence.
- [x] Add validator and security tests. (AC: 7)
  - [x] Add `scripts/validate_sandbox_security_audit.py`.
  - [x] Add `tests/sandbox/security/test_sandbox_security_audit.py`.
  - [x] Cover drift, security-context failures, supply-chain failures, evidence failures, and path separation.
- [x] Add operator runbook. (AC: 8)
  - [x] Add `docs/runbooks/sandbox-security-audit.md`.
  - [x] Document static CI boundaries, staging validation, pentest evidence, redaction, and failure response.
- [x] Wire CI. (AC: 8)
  - [x] Add `sandbox_security_audit` path filter and focused job.
  - [x] Add optional real pentest evidence validation loop.
- [x] Update workflow records and validation evidence. (AC: 9)
  - [x] Record implementation notes, file list, and change log.
  - [x] Move sprint status through `ready-for-dev`, `in-progress`, and `code-review` only after gates pass.
  - [x] Run post-implementation code review and apply fixes.

### Review Findings

- [x] [Review][Patch] Plan/scenario metadata safety boundary was not enforced — `validate_plan` and `validate_scenarios` pinned structure and guard coverage, but did not reject executable exploit payload strings, production hostnames, or credential-like text if they appeared in metadata. Fixed by adding forbidden metadata pattern validation and negative tests covering fork bomb, mount, Docker command, host traversal payload, production host, network fetch, and credential-like material.

## Dev Notes

### Source Context

- `_bmad-output/planning/epics.md:338` adds Story M3.7 Sandbox Security Audit for PMR3.
- `_bmad-output/planning/epics.md:663` maps PMR3 to Epic 0 Story M3.7.
- `_bmad-output/planning/epics.md:1197` defines M3.7 as gVisor sandbox escape / container escape / capability drop / AppArmor profile + supply-chain attack audit.
- `_bmad-output/planning/epics.md:1962` maps CRG6 to M3.7 with three supply-chain attack scenarios.
- `_bmad-output/stories/m3-1-sandbox-io-pattern.md` explicitly deferred M3.7 runtime security controls and attack scenarios.

### Previous Story Intelligence

- M3.1 created `apps/sandbox-runner` as a deterministic local P58/P62 contract and intentionally did not claim real runtime isolation.
- M3.1 policy currently blocks obvious network imports and LLM self-loop patterns before local execution.
- M3.1 tests use `PYTHONPATH=apps/sandbox-runner/src` and do not require Docker, gVisor, Kubernetes, network, database, Redis, or cloud credentials.
- M3.7 must not weaken M3.1's scope distinction: static validation can prove manifests and contracts, not live kernel/runtime isolation.
- M3.6d/e established the pattern for static security/performance contracts plus future evidence manifests without fabricating real operator evidence.

### Architecture / External Constraints

- PRD sandbox constraints: 1 vCPU, 1 GB memory, network disabled, read-only filesystem, 30s soft timeout, 90s hard kill.
- Kubernetes current security context supports `seccompProfile.type=RuntimeDefault` and `appArmorProfile` on pod/container security context.
- gVisor Kubernetes integration uses `runtimeClassName: gvisor` when the cluster/node runtime is configured for runsc.
- This repo must keep CI deterministic and offline. Static validation must not call Docker, Kubernetes, gVisor, PyPI, registries, cloud APIs, or vulnerability feeds.

### File Structure Requirements

- Use `infra/sandbox-security/` for M3.7 audit plan, scenario, policy, evidence schema/example, AppArmor, and K8s hardening assets.
- Use `scripts/validate_sandbox_security_audit.py` for standalone validation.
- Use `tests/sandbox/security/` for M3.7 security audit tests, matching the epic AC path.
- Use `docs/runbooks/sandbox-security-audit.md` for operator workflow.

### Testing / Validation Notes

Expected local commands after implementation:

```bash
uv run python scripts/validate_sandbox_security_audit.py
uv run pytest tests/sandbox/security -q
uv run ruff check scripts/validate_sandbox_security_audit.py tests/sandbox/security
uv run ruff format --check scripts/validate_sandbox_security_audit.py tests/sandbox/security
uv run pre-commit run --all-files --show-diff-on-failure
git diff --check
```

If running sandbox-runner regression is relevant:

```bash
$env:PYTHONPATH='apps/sandbox-runner/src'; uv run pytest apps/sandbox-runner/tests -q
```

### Risks / Decisions

- Data consistency risk: audit plan, attack scenarios, supply-chain policy, manifest, tests, and runbook can drift. Validator must pin counts, IDs, categories, and required guards.
- Function consistency risk: local CI might be mistaken for real gVisor/AppArmor/seccomp enforcement. Runbook and evidence schema must state static-only boundaries.
- Boundary risk: tests could accidentally execute unsafe exploit behavior. Scenario assets must be metadata-only and tests must never fork bomb, mount, open Docker socket, or probe host namespaces.
- Closure risk: third-party pentest evidence cannot be fabricated. This story commits schema/example and future report path only.
- Supply-chain risk: typosquat/base-image/SBOM checks must be deterministic and offline.

## Story Review Log

### Round 1: Data Consistency Review

Findings fixed:
- Added canonical scenario ID ordering between `audit_plan.json` and `attack_scenarios.json` so the plan cannot drift from scenario metadata.
- Added stable ID prefix requirements for the 12 escape scenarios and 3 supply-chain scenarios.
- Added evidence hash binding to supply-chain policy and AppArmor profile, not only plan/scenario/hardening manifest.
- Added evidence artifact path and reviewed scenario ID requirements so future evidence is traceable to exactly one scenario and stays under `reports/sandbox-security/<run_id>/`.

Status: PASS after fixes.

### Round 2: Function Consistency / Drift Review

Findings fixed:
- Required every scenario guard to map to a concrete validator rule or named test, preventing a passive checklist that does not enforce behavior.
- Added explicit deny-all egress NetworkPolicy coverage so the `external_network_egress` scenario is not only represented in prose.
- Added guard-coverage drift tests so unknown or unvalidated guards fail.
- Reaffirmed that CI validates static manifests/contracts and does not claim live runtime enforcement.

Status: PASS after fixes.

### Round 3: Boundary / Closure Review

Findings fixed:
- Explicitly forbade executable exploit payloads and privileged shell operations in scenario assets/tests.
- Forbade committing generated `reports/sandbox-security/**`, cache directories, Docker build outputs, scanner output files, and real SBOM/pentest artifacts in this implementation.
- Added runbook failure handling for runtime escape, privileged drift, redaction failure, and supply-chain policy failure.
- Clarified that M3.7 must not change sandbox-runner execution behavior; it creates audit/hardening contracts and static validation.
- Reaffirmed final bookkeeping requirements for Dev Agent Record, file list, validation evidence, post-implementation review fixes, and sprint status.

Status: PASS after fixes. Story is ready for development.

## Dev Agent Record

### Implementation Notes

- Added static M3.7 sandbox security audit assets under `infra/sandbox-security/`: canonical plan, 15 ordered attack scenarios, deterministic supply-chain policy, K8s hardening manifest, deny-all egress NetworkPolicy, AppArmor profile, and pentest evidence schema/example.
- Implemented `scripts/validate_sandbox_security_audit.py` as a stdlib-only offline validator. It pins scenario order/counts, guard coverage, runtime hardening posture, AppArmor snippets, supply-chain drift checks, evidence hash binding, fake pass-claim rejection, and `reports/sandbox-security/<run_id>/pentest_evidence.json` path separation.
- Added `tests/sandbox/security/test_sandbox_security_audit.py` with positive and negative coverage for scenario drift, guard drift, supply-chain typosquat/image/SBOM drift, K8s/AppArmor hardening drift, evidence hash/path/fake-pass failures, runbook assertions, and CI wiring.
- Wired `.github/workflows/ci.yml` with `sandbox_security_audit` path filtering plus focused validator/test job and optional real pentest evidence validation loop.
- Documented operator workflow and static-boundary disclaimers in `docs/runbooks/sandbox-security-audit.md`; no live exploit execution, Docker/gVisor/K8s runtime calls, network pulls, real pentest reports, generated reports, or sandbox-runner runtime behavior changes were added.
- Resolved pre-commit secret-scan false positives from existing M3.6e public example hashes and synthetic JWT negative fixture so the all-files CI lint gate is reproducible for this PR.
- Post-implementation code review found and fixed one boundary gap: plan/scenario metadata now rejects executable exploit payload strings, production hosts, and credential-like text instead of only validating required fields and guard coverage.

### File List

- `.github/workflows/ci.yml`
- `.pre-commit-config.yaml`
- `_bmad-output/stories/m3-7-sandbox-security-audit.md`
- `_bmad-output/stories/sprint-status.yaml`
- `docs/runbooks/sandbox-security-audit.md`
- `infra/sandbox-security/apparmor/sandbox-runner.apparmor`
- `infra/sandbox-security/attack_scenarios.json`
- `infra/sandbox-security/audit_plan.json`
- `infra/sandbox-security/k8s/sandbox-runner-hardening.yaml`
- `infra/sandbox-security/pentest_evidence.example.json`
- `infra/sandbox-security/pentest_evidence.schema.json`
- `infra/sandbox-security/supply_chain_policy.json`
- `scripts/validate_sandbox_security_audit.py`
- `tests/sandbox/security/test_sandbox_security_audit.py`
- `tests/test_traffic_replay_plan.py`

### Validation Evidence

- `uv run python scripts\validate_sandbox_security_audit.py` -> PASS (`sandbox security audit OK`)
- `uv run pytest tests\sandbox\security -q` -> PASS (14 passed)
- `uv run ruff check scripts\validate_sandbox_security_audit.py tests\sandbox\security` -> PASS
- `uv run ruff format --check scripts\validate_sandbox_security_audit.py tests\sandbox\security` -> PASS
- `$env:PYTHONPATH='apps/sandbox-runner/src'; uv run pytest apps\sandbox-runner\tests -q` -> PASS (9 passed)
- `uv run pytest tests\test_traffic_replay_plan.py -q` -> PASS (20 passed)
- `uv run pre-commit run --all-files --show-diff-on-failure` -> PASS
- `git diff --check` -> PASS
- `uv run pytest -q` -> FAIL due to existing monorepo collection/PYTHONPATH issues: duplicate `tests.conftest` imports across app test packages, missing `sandbox_runner` without per-job `PYTHONPATH`, missing `opticloud`, and `tests.*` collection import mismatches. M3.7 scoped tests and configured CI job pass.

## Senior Developer Review (AI)

Review date: 2026-05-26

Outcome: Approved after fix

Findings:
- Patch: Plan/scenario metadata safety boundary was not enforced by the validator. Fixed with `validate_metadata_safety()`, `test_audit_plan_rejects_exploit_hosts_and_credentials`, and `test_scenario_metadata_rejects_executable_exploit_payloads`.

Residual risk:
- Static CI still does not prove live gVisor/AppArmor/seccomp/Kubernetes enforcement; this is intentionally deferred to future runtime validation and third-party pentest evidence PRs.

### Change Log

- 2026-05-26: Initial draft created for M3.7 story context.
- 2026-05-26: Completed three pre-implementation story review rounds and moved story to ready-for-dev.
- 2026-05-26: Started implementation and moved story to in-progress.
- 2026-05-26: Implemented M3.7 static sandbox security audit contract, validator, tests, runbook, CI gate, and validation evidence; moved story to code-review.
- 2026-05-26: Completed post-implementation code review, fixed metadata payload boundary gap, and moved story to done.
