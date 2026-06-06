# Epic 6.C Retrospective - Auto-migration + Provider Exit v2

Date: 2026-06-06
Project: 通用优化与预测服务网站
Epic: Epic 6.C - Auto-migration + Provider Exit v2
Status: complete

## Summary

Epic 6.C closed with four completed stories:

- 6.C.1 Auto-migrate to Equivalent Provider
- 6.C.2 >=30d Provider Exit Pre-Notification
- 6.C.3 Capability Vocabulary Design
- 6.C.4 Equivalent Matching Algorithm

All four stories followed the enforced lifecycle: story creation, exactly three pre-implementation adversarial review rounds, revision after each round, implementation, post-implementation code review, local gates, GitHub PR CI, merge, remote branch deletion, local `main` sync, and a separate post-merge status-sync commit.

## Outcome

Epic 6.C now has a complete v2 control-plane foundation for Provider exit and equivalent matching:

- `solver-orchestrator` reruns can perform deterministic local Provider migration preflight before durable writes.
- Provider exit plans can generate voucher-holder notification requests and public-safe status announcement outbox events with >=30d enforcement.
- `capability-registry` maintains canonical capability vocab terms and aliases, and capability registration now stores active canonical tags only.
- `capability-registry` exposes read-only equivalent matching over canonical tags, task type, solver support, active provider state, eligible capability status, precision metadata, and semantic-version distance.

The implementation intentionally preserves service boundaries. Solver rerun migration remains local and deterministic; registry equivalent matching is available as a read contract but is not wired into solver runtime in this epic.

## What Worked

The strongest system improvement was separating the R4/R7 problem into four narrow contracts instead of trying to ship one broad Provider migration feature. That kept each story testable and prevented false completion.

The three-round adversarial review process paid off in every story. It caught durable-write ordering, tenant/global fallback, free-form tag bypass, cache invalidation, metadata privacy, response leakage, and status-sync ordering before or immediately after implementation.

The post-implementation reviews found real boundary issues:

- 6.C.1: default capability tags were initially too strict for absent-source-provider migrations.
- 6.C.2: voucher expiry needed per-voucher 5-year evaluation, including leap-day behavior.
- 6.C.3: alias responses needed audit fields and blank `task_type` filter normalization.
- 6.C.4: untagged source capabilities needed rejection, and `include_source=true` needed direct API regression coverage.

The GitHub closure discipline prevented status drift. Story and sprint status moved to `done` only after CI passed, PRs merged, remote branches were deleted, and local `main` was synced.

## Issues Found

The epic deliberately has two equivalent-provider mechanisms with different responsibilities:

- 6.C.1 local solver rerun preflight protects voucher reruns without a cross-service dependency.
- 6.C.4 registry equivalent matching provides a broader read-only ranking contract.

That split is correct for this epic, but it creates an explicit future integration decision: solver runtime can keep local snapshots, consume registry exports, or call the registry in a later story. This is not a hidden gap; it is a deferred architecture choice.

Provider exit notification is a control-plane and outbox contract, not real delivery automation. Email, in-app inbox, status page live publishing, retries, and delivery status remain outside this epic.

Error i18n audit drift appeared in multiple stories when new `HTTPException` literals or remediation keys were added. The gate caught it, but future capability/solver route stories should expect this maintenance step.

Sprint aggregate status was stale after the four story-level closures: `epic-6-c` still showed `in-progress` even though all child stories were done.

## Repeated Review Themes

- Boundary issues: do not imply real provider runtime integration, real notification delivery, live status publishing, or ML/manual matching when only contracts are implemented.
- Drift issues: tenant/global fallback, status enums, cache keys, error-i18n pins, OpenAPI specs, and response schemas must stay synchronized with implementation.
- Data consistency: durable writes must happen after all eligibility checks; invalid vocab tags and no-equivalent failures must be atomic; notification recipients must be deduplicated by user.
- Dependency consistency: avoid runtime cross-service calls between solver-orchestrator and capability-registry unless a later story explicitly owns that dependency.
- Privacy: no voucher IDs, source payloads, raw metadata, provider secrets, billing IDs, API keys, user emails, webhook URLs, or raw datasets in matching or notification outputs.
- Closure: keep the separate post-merge status-sync commit for every story.

## Residual Risks

Epic 6.C does not prove real-world Provider exit operations end to end. The following remain intentionally out of scope:

- Real email provider delivery.
- Real in-app notification inbox rendering.
- Live public status page publishing from provider exit announcement events.
- Delivery retry, bounce, acknowledgement, and audit dashboards.
- Runtime consumption of capability-registry equivalent matching by solver rerun.
- Precision telemetry ingestion or benchmark-derived precision calculation.
- Provider-facing manual review queues or ML matching.

These are represented as future work rather than hidden completion claims.

## Follow-Through From Previous Retro

The previous retrospective found no Epic 8 retro, but it established the process expectation to select the next actionable story from sprint status and preserve the full lifecycle. Epic 6.C applied that process across PRs #178, #179, #180, and #181.

The Epic 9 lessons were also applied:

- Static or control-plane contracts did not claim real external delivery.
- CI and validation gates were treated as required closure evidence.
- New i18n/OpenAPI/audit drift was fixed before merge.
- Final `done` status updates were separate post-merge commits.

## Action Items

- Owner: BMAD status maintainer. Mark `epic-6-c` as `done` now that all four child stories and this retrospective are complete.
- Owner: Planning maintainer. Reconcile the next Provider backlog before creating new 7.B stories, because sprint status tracks 7.B.1-7.B.9 as done while planning text still references 7.B.9-13 as a grouped scope.
- Owner: Architecture/dev. When a future story requires solver runtime to use registry equivalent matching, decide explicitly between live registry call, exported snapshot, or continued local resolver ownership.
- Owner: QA/dev. Continue requiring direct regression coverage for every boolean/query switch and every privacy boundary added to Provider/Repro flows.

## Recommended Next Step

After this retrospective and `epic-6-c` status update are committed, inspect Epic 7.B planning/status drift before opening another story. If 7.B.9 is accepted as the consolidated closure for 7.B.9-13, continue scanning sprint status for the next genuinely incomplete non-blocked story. If it is not accepted, create the next 7.B story only after writing a precise story file and running the required three pre-implementation adversarial review rounds.
