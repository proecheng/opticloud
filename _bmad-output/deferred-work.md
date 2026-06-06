# Deferred Work Log

Items surfaced by code reviews / retrospectives that are real but not blockers for the current PR. Promote to backlog items when their cost-benefit shifts.

---

## Deferred from: code review of 6-a-1-citation-bibtex (2026-05-20)

- **Cached idempotency replay returns stale citation if provider_id is renamed** — `_build_success_response` (routes.py L457-465) keys lookup against the in-process catalog; if a provider is renamed between solve and the 24h-cached replay, the citation silently drops to `null`, violating P23 same-key-same-response. Story risk table accepts this v1 posture. Promote when a provider rename actually ships (none in current catalog).
- **Clipboard `catch` branch in `CodeBlock.handleCopy` is uncovered by any test** — page.tsx L75-83 silently no-ops on `navigator.clipboard.writeText()` rejection; no user feedback in that branch. Headless Chromium requires `context.grantPermissions(['clipboard-write'])` setup. Add when M3 expands the e2e clipboard-permission harness.
- **Catalog invariant tests import full `main.py`** — `tests/test_citation.py` L13-14 drags FastAPI app + DB engine import for pure-data tests. Refactor would split sync catalog tests from async route tests. Matches existing solver-orchestrator test-file pattern; defer until a project-wide test-file restructure ticket.

---

## Deferred from: retrospective of Epic 6.C Auto-migration + Provider Exit v2 (2026-06-06)

- **Solver rerun does not yet consume capability-registry equivalent matching at runtime** — Story 6.C.1 intentionally kept a local deterministic rerun migration resolver, while Story 6.C.4 added a registry read contract. Promote when product requires solver runtime to select equivalents from live or exported registry data; decide explicitly between live registry call, exported snapshot, or continued local resolver ownership.
- **Provider exit notification is not real delivery automation** — Story 6.C.2 creates provider exit plans, per-user notification request rows, and pointer-safe outbox/status announcement events. Real email delivery, in-app inbox rendering, live status page publishing, retry, bounce handling, and delivery status dashboards remain future integration work.
- **Equivalent matching precision is metadata-derived, not telemetry-derived** — Story 6.C.4 reads safe precision fields from capability metadata. No benchmark pipeline, shadow-validation aggregation, or provider KPI telemetry writes precision back into the registry yet.

---

## Deferred from: retrospective of Epic 7.B Provider Marketplace v2 (2026-06-06)

- **Planning text still says 7.B has 13 stories** — current implementation closes P1-P8 through 7.B.1-9, with 7.B.9 consolidating the planned 7.B.9-13 Provider Console grouped scope. Update planning docs later to avoid future duplicate 7.B.10-13 creation.
- **Provider Marketplace contracts are not real external operations** — application intake, shadow validation, rollout, payout, monthly batch, and Provider Console are safe contracts/projections. Public provider auth, ownership enforcement, real provider execution, live routing mutation, and payment settlement remain future work.
- **Academic Provider Handbook / onboarding tier 1-3 remains unimplemented as a separate workstream** — planning mentioned it inside the 7.B.9-13 group, but 7.B.9 intentionally scoped to Provider Console aggregation. Promote only if product explicitly requires academic Provider onboarding beyond existing academic stories.
