# Story M3.3a: K8s Namespace 三域 + NetworkPolicy（标准档）

Status: done

## Story

As a DevOps / Security engineer,
I want Kubernetes production namespaces split into `prod-core`, `prod-ai`, and `prod-data` with enforced one-way NetworkPolicy flow,
so that P60 namespace isolation is represented as versioned, reviewable infrastructure and reduces lateral movement / data exfiltration risk before real ACK rollout.

## Acceptance Criteria

1. Production namespace manifests exist.
   - Add standard-tier Kubernetes manifests under `infra/k8s/production/`.
   - Define exactly three production namespaces: `prod-core`, `prod-ai`, and `prod-data`.
   - Each namespace carries stable labels usable by NetworkPolicy selectors, including `opticloud.io/network-domain`.
   - Each namespace carries restricted Pod Security labels suitable for production defaults.

2. NetworkPolicy enforces bounded one-way domain flow.
   - Default deny ingress and egress exists in each of the three namespaces.
   - Same-namespace pod-to-pod traffic remains allowed inside each domain.
   - DNS egress remains allowed so service discovery can work.
   - `prod-core` may initiate traffic to `prod-ai` and `prod-data`.
   - `prod-ai` may receive from `prod-core` and may initiate traffic to `prod-data`.
   - `prod-data` may receive from `prod-core` and `prod-ai`.
   - `prod-data` must not initiate traffic to `prod-core` or `prod-ai`.
   - `prod-ai` must not initiate traffic to `prod-core`.
   - No policy may use an unbounded wildcard `namespaceSelector: {}` for application-domain traffic.

3. ACK / real-cluster validation is documented but not required in CI.
   - Document that real ACK enforcement requires a NetworkPolicy-capable CNI, with Terway as the standard-tier ACK target.
   - Include dry-run and manual validation commands for a real cluster.
   - Include the epic's validated outcome command shape: `kubectl exec -n prod-data ... curl http://service.prod-core` should fail, while `prod-core` to `prod-data` should work once representative services exist.
   - Do not require kubeconfig, ACK credentials, a live cluster, Helm, Terraform, or cloud network access in PR CI.

4. Static validation gate exists.
   - Add a local validator script that parses committed manifests and validates namespace labels, default-deny policies, allowed flows, and blocked reverse flows.
   - Add pytest coverage for valid manifests and negative cases.
   - Wire a lightweight CI job triggered by `infra/k8s/**`, the validator script, its tests, or CI root changes.

5. Scope boundaries are explicit.
   - Do not add application Deployments, Services, Ingress, Service Mesh, mTLS, ArgoCD, ACK One GitOps, Helm charts, Terraform modules, or M3.3b docker-compose blue-green deployment in this story.
   - Do not change runtime behavior of auth, billing, solver, sandbox, web, or contract tests.
   - Do not claim live ACK enforcement until manual cluster validation is performed outside PR CI.

6. Story workflow tracking is updated.
   - This story records three pre-implementation story review rounds and fixes after each round.
   - `_bmad-output/stories/sprint-status.yaml` moves `m3-3a-k8s-namespace-prod` to `ready-for-dev` only after the three story review rounds pass.
   - During implementation, move the story through `in-progress`, `code-review`, and `done` only when corresponding gates pass.

## Tasks / Subtasks

- [x] Add production K8s namespace and NetworkPolicy manifests. (AC: 1, 2, 5)
  - [x] Add `infra/k8s/production/namespaces.yaml`.
  - [x] Add `infra/k8s/production/networkpolicies.yaml`.
  - [x] Add `infra/k8s/production/README.md` with standard-tier ACK guidance and manual validation commands.
  - [x] Keep manifests limited to namespace and NetworkPolicy resources.
- [x] Add static NetworkPolicy validator. (AC: 2, 4)
  - [x] Add `scripts/validate_k8s_network_policies.py`.
  - [x] Validate required namespaces and labels.
  - [x] Validate default-deny, DNS, same-namespace, allowed forward flows, and blocked reverse flows.
  - [x] Reject wildcard application-domain selectors.
- [x] Add regression tests. (AC: 2, 4)
  - [x] Add `tests/test_k8s_network_policies.py`.
  - [x] Cover committed manifest success path.
  - [x] Cover missing namespace, missing default deny, and forbidden reverse-flow negative cases.
- [x] Wire CI. (AC: 4)
  - [x] Add a `k8s_manifests` path-filter output.
  - [x] Add a lightweight CI job that runs the validator and pytest tests.
  - [x] Keep unrelated service jobs unchanged.
- [x] Update workflow records and validation evidence. (AC: 1-6)
  - [x] Move sprint status to `in-progress` during implementation and `code-review` after implementation validation.
  - [x] Update Dev Agent Record, File List, Change Log, and post-implementation review notes.
  - [x] Run validator, pytest, ruff where applicable, and `git diff --check`.

### Review Findings

- [x] [Review][Patch] Validator allowed out-of-scope Kubernetes resource kinds [scripts/validate_k8s_network_policies.py] — fixed by rejecting resources other than `Namespace` and `NetworkPolicy`, with a Deployment negative test.
- [x] [Review][Patch] Validator did not enforce the manifest namespace set for non-production-labeled namespaces [scripts/validate_k8s_network_policies.py] — fixed by requiring the committed Namespace set to be exactly `prod-core`, `prod-ai`, and `prod-data`.
- [x] [Review][Patch] Validator allowed NetworkPolicies outside the required production namespaces [scripts/validate_k8s_network_policies.py] — fixed by rejecting policies whose `metadata.namespace` is not one of the three required namespaces.

## Dev Notes

### Context

- Epic M3.3a is the standard-tier Kubernetes path; M3.3b is the separate simplified docker-compose blue-green path and must not be mixed into this story.
- Architecture D21 chooses Alibaba Cloud ACK managed Kubernetes + ACK One GitOps for standard tier, while D21 simplified tier remains single ECS + docker-compose.
- Architecture PI3 explicitly split the former K8s namespace story into M3.3a standard-tier K8s and M3.3b simplified docker-compose.
- Architecture P60 is the namespace isolation target for preventing lateral movement and data exfiltration.
- The repository currently has no `infra/k8s/` tree; this story establishes the first static K8s manifest area and validation pattern.
- Story M3.2 added a path-filtered CI job pattern that this story can mirror.

### Scope Decision

- This story creates reviewable static Kubernetes manifests and a deterministic local/CI validator.
- It does not attempt live ACK validation in PR CI because that requires cloud credentials, kubeconfig, a NetworkPolicy-capable CNI, and representative services/pods.
- Real enforcement validation is documented as an operator/manual step after cluster availability.
- Keep policy validation semantic and explicit rather than relying on string matching.

### Architecture / External Constraints

- Use Kubernetes `networking.k8s.io/v1` `NetworkPolicy`; NetworkPolicy behavior depends on the cluster's network plugin implementing it.
- Kubernetes NetworkPolicy is namespace-scoped and selected pods are isolated for the policy types selected by matching policies.
- Default behavior without policies is allow-all; therefore each production domain needs default-deny ingress and egress.
- ACK standard-tier target should use a NetworkPolicy-capable CNI. Alibaba Cloud ACK documentation states Terway supports NetworkPolicy for policy-based network control; Flannel is not the standard target for this story.
- Do not require latest Kubernetes APIs beyond stable `v1` Namespace and NetworkPolicy resources.

### Project Structure Notes

- Place manifests under `infra/k8s/production/`.
- Place the validator under `scripts/` to match existing infra validation scripts.
- Place tests under repo-level `tests/` like `tests/test_image_archival_plan.py`.
- Update `.github/workflows/ci.yml` only for path filter and new job.

### Testing / Validation Notes

- Expected local commands:
  - `uv run python scripts/validate_k8s_network_policies.py infra/k8s/production`
  - `uv run pytest tests/test_k8s_network_policies.py -q`
  - `uv run ruff check tests/test_k8s_network_policies.py`
  - `git diff --check`
- Optional real-cluster checks belong in README, not CI:
  - `kubectl apply --server-side --dry-run=server -f infra/k8s/production/`
  - `kubectl exec -n prod-data ... -- curl http://service.prod-core`
  - `kubectl exec -n prod-core ... -- curl http://service.prod-data`

### Risks / Decisions

- Main data consistency risk: namespace labels and NetworkPolicy selectors drifting apart. The validator must verify both sides.
- Main function drift risk: implementing a permissive policy that looks structured but allows reverse flows. The validator must assert blocked `prod-data -> prod-core` and `prod-ai -> prod-core`.
- Main boundary risk: silently adding Helm/Terraform/Deployments and expanding beyond namespace isolation. The story forbids those additions.
- Main closure risk: shipping YAML without CI. Add a dedicated static validator job.
- ACK risk: static manifests cannot prove runtime enforcement; README must state that live enforcement requires a compatible ACK CNI and manual validation.

### References

- `_bmad-output/planning/epics.md` — Story M3.3a K8s Namespace 三域 + NetworkPolicy.
- `_bmad-output/planning/architecture.md` — D21, P60, PI3.
- `_bmad-output/stories/m3-2-contract-test-framework.md` — previous path-filtered CI and post-review process pattern.
- Kubernetes NetworkPolicy docs: https://kubernetes.io/docs/concepts/services-networking/network-policies/
- Alibaba Cloud ACK NetworkPolicy docs: https://www.alibabacloud.com/help/en/ack/ack-managed-and-ack-dedicated/user-guide/use-network-policies

## Story Review Log

### Round 1: Data Consistency Review

Findings fixed:
- Added exact namespace names and required `opticloud.io/network-domain` labels so manifests and selectors have a single stable key.
- Added default-deny ingress and egress requirements for all three namespaces instead of relying on partial allow rules.
- Added DNS egress as a required exception so service discovery is not accidentally blocked.
- Added explicit distinction between static PR validation and later live ACK validation.

Status: PASS after fixes.

### Round 2: Function Consistency / Drift Review

Findings fixed:
- Clarified allowed flows so `prod-core -> prod-data` is allowed per epic validated outcome, not only adjacent `prod-core -> prod-ai -> prod-data`.
- Added forbidden reverse-flow checks for `prod-data -> prod-core`, `prod-data -> prod-ai`, and `prod-ai -> prod-core`.
- Excluded M3.3b docker-compose blue-green, Helm, Terraform, ArgoCD, service mesh, and runtime Deployments from this story.
- Required semantic validation of YAML manifests instead of ad hoc string checks.

Status: PASS after fixes.

### Round 3: Boundary / Closure Review

Findings fixed:
- Added CI path-filter and validator job requirements so the YAML gate is not documentation-only.
- Added negative tests for missing namespace, missing default deny, and forbidden reverse flow.
- Added ACK CNI compatibility note so the story does not overclaim live enforcement from static manifests.
- Confirmed no application runtime behavior changes are needed.

Status: PASS after fixes. Story is ready for development.

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Implementation Plan

1. Add static `infra/k8s/production` namespace and NetworkPolicy manifests.
2. Add a semantic Python validator for namespace labels, default-deny, allowed flows, and forbidden reverse flows.
3. Add pytest coverage for valid and invalid policy sets.
4. Wire CI path filter and a lightweight K8s manifest validation job.
5. Run validation, perform post-implementation code review, patch findings, and move the story through workflow states.

### Debug Log References

- 2026-05-26 — Created Story M3.3a after PR #56 checks passed and from M3.2 stacked branch.
- 2026-05-26 — Completed three pre-implementation story review rounds before implementation; sprint status moved to ready-for-dev.
- 2026-05-26 — Started implementation; sprint status moved to in-progress.
- 2026-05-26 — Added production namespace and NetworkPolicy manifests under `infra/k8s/production`.
- 2026-05-26 — Added semantic static validator for required namespaces, labels, default-deny, DNS, same-namespace, allowed flows, blocked reverse flows, and wildcard selectors.
- 2026-05-26 — Added 6 pytest regression cases and a path-filtered `k8s-manifest-validation` CI job.
- 2026-05-26 — Implementation validation passed: validator OK, `pytest tests/test_k8s_network_policies.py -q` (6 passed), ruff, `git diff --check`, and explicit no-index whitespace checks for new M3.3a files.
- 2026-05-26 — Post-implementation code review found and fixed three validator boundary gaps: unsupported resource kinds, extra namespaces, and NetworkPolicies outside required namespaces.
- 2026-05-26 — Post-review validation passed: validator OK, `pytest tests/test_k8s_network_policies.py -q` (9 passed), ruff, and `git diff --check`.

### Completion Notes List

- Added first standard-tier K8s production manifest area at `infra/k8s/production`.
- Defined `prod-core`, `prod-ai`, and `prod-data` namespaces with stable domain labels and restricted Pod Security labels.
- Added default-deny, same-namespace, DNS, and explicit one-way application-domain NetworkPolicies.
- Added static semantic validation and regression tests for policy drift and boundary violations.
- Added CI path filter and job for M3.3a K8s manifest validation.
- Post-implementation code review completed; all patch findings were fixed and revalidated.

### File List

- `.github/workflows/ci.yml`
- `_bmad-output/stories/m3-3a-k8s-namespace-prod.md`
- `_bmad-output/stories/sprint-status.yaml`
- `infra/k8s/production/README.md`
- `infra/k8s/production/namespaces.yaml`
- `infra/k8s/production/networkpolicies.yaml`
- `scripts/validate_k8s_network_policies.py`
- `tests/test_k8s_network_policies.py`

### Change Log

- 2026-05-26 — Created Story M3.3a and completed three story review rounds before implementation.
- 2026-05-26 — Started implementation and moved story to in-progress.
- 2026-05-26 — Implemented production K8s namespace/NetworkPolicy manifests, static validator, regression tests, and CI job.
- 2026-05-26 — Completed implementation validation and moved story to code-review.
- 2026-05-26 — Addressed post-implementation code review findings and moved story to done.
