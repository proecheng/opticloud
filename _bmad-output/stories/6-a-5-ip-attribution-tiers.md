# Story 6.A.5: IP Attribution Tiers (学者 IP Attribution Tier 1/2/3 工程化)

Status: done

## Story

As a Founder / Academic Relations Lead,
I want scholar IP attribution tiers L1 / L2 / L3 encoded in the catalog, surfaced on academic pages, and reviewable in Console,
so that OptiCloud can honor academic Provider IP agreements consistently without relying on ad hoc manual wording.

## Acceptance Criteria

1. The algorithm catalog exposes a structured `ip_attribution` object for every algorithm row.
   - The object includes `tier`, `label_zh`, `display_name_zh`, `summary_zh`, `visibility`, and `contract_anchor`.
   - `tier` is constrained to `L1`, `L2`, or `L3`.
   - `visibility` is constrained to `full_visible`, `bibtex`, or `license_only`.
   - L1 means full visible attribution, L2 means standard BibTeX attribution, and L3 means license-only / open-source runner attribution.
   - Every current SKU has a non-null value; no row may silently omit attribution data.

2. `GET /v1/algorithms` and `GET /v1/algorithms/{k_algo}` return the new `ip_attribution` field.
   - Pydantic schemas validate the field shape.
   - The API response stays backward-compatible: existing `citation`, `model_version`, `supported_solvers`, and filter behavior do not change.
   - Unknown `k_algo` and tier filters keep their current behavior.

3. Successful optimization responses carry the same attribution metadata as the selected catalog row.
   - `OptimizationResponse` includes `ip_attribution` next to `citation`.
   - `/v1/optimizations/demo` includes `ip_attribution` for the LP success path.
   - If a future malformed catalog row cannot validate attribution, the response degrades to `ip_attribution: null` instead of returning 500, matching the current citation defensive pattern.

4. Frontend API types include `ip_attribution` and reuse one rendering component for tier badges.
   - Add a small `AttributionBadge` component under `apps/web/src/components/`.
   - Do not duplicate tier color / label logic separately in `/academic`, `/algorithms/[k_algo]`, and Console UI.
   - The badge must keep stable dimensions and readable text on mobile and desktop.

5. `/academic` shows attribution tier information on every citation card.
   - Each card displays the tier badge next to the algorithm tier badge.
   - L1 cards display a visible "Algorithm by ..." attribution line derived from `display_name_zh`.
   - L2 / L3 cards display concise non-claiming copy aligned with the handbook.
   - The existing BibTeX, DOI / URL, flywheel, and edu CTA behavior remains intact.

6. `/algorithms/[k_algo]` shows attribution tier information in the algorithm detail page.
   - The header or citation section displays the shared badge.
   - The page includes `display_name_zh`, `summary_zh`, and `contract_anchor` without implying that legal terms are already finalized beyond `docs/legal-templates.md`.
   - Existing citation block, snippet block, provider transparency, 404 path, and empty examples path remain unchanged.

7. A Console UI page exists for attribution review.
   - Add `/console/academic-attribution`.
   - The page lists all catalog algorithms, their attribution tier, provider, citation key / source, and contract anchor.
   - Citation key is derived from the first BibTeX line when `citation.bibtex` exists; source falls back to DOI, URL, or venue/year in that order.
   - It shows summary counts by L1 / L2 / L3 and a clear empty / error state if catalog fetch fails.
   - It is read-only; no write API, auth flow, database, or migration is added in this story.

8. Documentation stays aligned with the engineered tiers.
   - `docs/academic-provider-handbook.md` and `docs/customer-faqs/academic-onboarding-faq.md` no longer say 6.A.5 is future-only once implementation ships.
   - The docs still frame contract details as Provider Agreement / legal-template territory and do not create new legal policy.
   - Tier 2 self-service Provider portal and Tier 3 partnership roadmap remain roadmap-only.

9. Tests cover backend contract and frontend rendering.
   - Backend tests assert every catalog row has `ip_attribution`, values validate through API schemas, and representative L1 / L3 rows are correct.
   - Backend tests assert LP demo / success response includes `ip_attribution`.
   - E2E tests assert `/academic`, `/algorithms/aqgs-acopf`, and `/console/academic-attribution` render attribution data.
   - Existing solver-orchestrator tests and relevant Playwright tests pass.

10. Sprint tracking and story record are updated in the same PR.
   - `_bmad-output/stories/sprint-status.yaml` moves `6-a-5-ip-attribution-tiers` through `ready-for-dev`, `in-progress`, `review`, and `done` only after the required workflow gates pass.
   - This story file records three story review rounds, implementation notes, file list, change log, and post-implementation code review.

## Tasks / Subtasks

- [x] Add structured attribution metadata to the catalog and API schema. (AC: 1, 2, 3)
  - [x] Add `IPAttribution` typed dict and field to `Algorithm` in `apps/solver-orchestrator/src/solver_orchestrator/catalog.py`.
  - [x] Populate all existing 8 catalog rows.
  - [x] Add `IPAttributionSchema`, `AlgorithmSchema.ip_attribution`, and `OptimizationResponse.ip_attribution` in `schemas.py`.
  - [x] Keep list/detail filters and existing citation response shape unchanged.
- [x] Add backend regression tests for the API contract. (AC: 1, 2, 3, 9)
  - [x] Assert `GET /v1/algorithms` includes non-null `ip_attribution` for every row.
  - [x] Assert `aqgs-acopf` is L1 with full visible attribution.
  - [x] Assert an open-source runner such as `highs-lp` is L3 license-only.
  - [x] Add these to existing catalog / citation tests (`test_algorithm_details.py` and/or `test_citation.py`) instead of creating a duplicate fixture file.
  - [x] Assert `/v1/optimizations/demo` LP success includes `ip_attribution`; colocate with the existing citation demo response test or `test_demo_optimizations.py`.
- [x] Add shared frontend attribution rendering support. (AC: 4)
  - [x] Extend `apps/web/src/lib/api.ts` with `IPAttribution`.
  - [x] Create `apps/web/src/components/AttributionBadge.tsx`.
  - [x] Keep tier color / label logic in the component, not in pages.
- [x] Update public academic surfaces. (AC: 5, 6)
  - [x] Update `/academic` citation cards.
  - [x] Update `/algorithms/[k_algo]` detail rendering.
  - [x] Preserve existing DOI / URL / BibTeX / snippet behavior.
- [x] Add read-only Console UI. (AC: 7)
  - [x] Create `apps/web/src/app/console/academic-attribution/page.tsx`.
  - [x] Fetch the catalog server-side using the same localhost normalization pattern as `/academic`.
  - [x] Add a local helper that derives citation key / source from `citation` without a new dependency.
  - [x] Render counts, table rows, and error state.
- [x] Update academic docs to remove future-only wording. (AC: 8)
  - [x] Update handbook attribution section.
  - [x] Update FAQ attribution answer.
  - [x] Replace the current "Story 6.A.5 会工程化..." wording in both docs with shipped-state language that points to the catalog/API/Console surfaces.
  - [x] Keep legal policy anchored to `docs/legal-templates.md`.
- [x] Add/adjust frontend E2E tests. (AC: 5, 6, 7, 9)
  - [x] Update `e2e/tests/academic-page.spec.ts`.
  - [x] Update `e2e/tests/algorithm-citation.spec.ts` or `algorithm-details.spec.ts`.
  - [x] Add `e2e/tests/academic-attribution-console.spec.ts`.
- [x] Update story tracking and Dev Agent Record after implementation. (AC: 10)
  - [x] Move sprint status through the lifecycle.
  - [x] Append completion notes, file list, change log, and post-implementation review result.

## Dev Notes

### Context

- Story 6.A.5 is Expert Panel E5: "学者 IP Attribution Tier 1/2/3 工程化 (L1/L2/L3) + Console UI".
- It follows the completed 6.A chain:
  - 6.A.1 created canonical `citation.bibtex` data in the solver catalog and response schemas.
  - 6.A.2 created `/academic` as the public academic landing page.
  - 6.A.3 created citation tracking and Linear payload tooling.
  - 6.A.4 created the academic onboarding toolkit and defined L1 / L2 / L3 policy wording in docs.
- This story turns the 6.A.4 policy wording into product-visible structured data. It must not create Provider onboarding portal behavior; Tier 2 / Tier 3 portal workflows remain roadmap-only.

### Canonical Attribution Policy

Use the handbook definitions as source of truth:

| Tier | Meaning | Product treatment |
|---|---|---|
| L1 | Full Visible Attribution | Show "Algorithm by ..." on public academic surfaces. |
| L2 | Standard BibTeX | Keep BibTeX / citation visible without prominent author claim in the summary. |
| L3 | License-Only | Respect open-source license / citation while avoiding a Provider partnership claim. |

Initial catalog mapping:

- `aqgs-acopf`: L1, because it is the self-developed OptiCloud / Trust-Tech algorithm and current academic collaboration brand anchor.
- HiGHS, OR-Tools, Chronos, ARIMA, LSTM rows: L3, because current rows are open-source / literature-backed runners, not signed academic Provider partnerships.
- L2 may have zero current rows; the Console UI must still show L2 as a first-class tier with count 0. Do not invent a Provider partnership to force an L2 example.

### Technical Requirements

- Backend source of truth remains `apps/solver-orchestrator/src/solver_orchestrator/catalog.py`.
- The API response model is `AlgorithmSchema` in `apps/solver-orchestrator/src/solver_orchestrator/schemas.py`.
- Use the same defensive response pattern as `_build_success_response`: invalid optional catalog attribution should degrade to `None` in solve responses, while catalog list/detail should still fail tests because current rows are required to validate.
- Frontend public types are in `apps/web/src/lib/api.ts`.
- `/academic` is a server component and already normalizes `localhost` to `127.0.0.1`; reuse that pattern for the new Console page.
- `/algorithms/[k_algo]` is a client component and fetches via `getAlgorithm`.
- No database migration, write endpoint, auth gate, new service, or dependency is in scope.
- Do not create a new parser dependency for BibTeX keys. A small regex / string helper is acceptable because it only reads the first line of catalog-controlled BibTeX; keep it local to the Console page unless a second caller appears.
- Reuse existing pytest async client fixtures in `test_algorithm_details.py`, `test_citation.py`, or `test_demo_optimizations.py`; avoid adding another identical ASGI fixture file.

### UI Requirements

- Console page should feel like an internal operational review surface: dense table, counts, and short status copy. Do not build a marketing hero.
- Keep cards at 8px radius or less, use existing Tailwind tokens, and avoid decorative gradients/orbs.
- Use stable badge sizing so `L1`, `L2`, and `L3` do not shift layout.
- Do not use in-app text that explains how to use the UI. The copy should be business content: tier, provider, attribution, contract anchor.

### Testing / Validation Requirements

Run at minimum:

- `uv run pytest apps/solver-orchestrator/tests/test_algorithm_details.py apps/solver-orchestrator/tests/test_citation.py`
- `pnpm --filter @opticloud/web typecheck`
- `pnpm -C e2e exec playwright test academic-page.spec.ts algorithm-citation.spec.ts academic-attribution-console.spec.ts --project=chromium`
- `git diff --check`

If the full E2E command is blocked by local service startup, record the blocker and run the narrower backend/typecheck checks. Do not mark AC9 complete without either passing E2E or documenting an environment blocker.

### Source Anchors

- E5 addition: `_bmad-output/planning/epics.md:2082`, `_bmad-output/planning/epics.md:2105`
- Epic 6.A goal: `_bmad-output/planning/epics.md:480-487`, `_bmad-output/planning/epics.md:1735-1748`
- Handbook attribution policy: `docs/academic-provider-handbook.md#ip-attribution-量化标准`
- Scholar FAQ attribution wording: `docs/customer-faqs/academic-onboarding-faq.md#5-我的名字会出现在产品里吗`
- Existing catalog source: `apps/solver-orchestrator/src/solver_orchestrator/catalog.py`
- Existing API schema: `apps/solver-orchestrator/src/solver_orchestrator/schemas.py`
- Existing academic page: `apps/web/src/app/academic/page.tsx`
- Existing algorithm detail page: `apps/web/src/app/algorithms/[k_algo]/page.tsx`
- Existing academic E2E tests: `e2e/tests/academic-page.spec.ts`, `e2e/tests/algorithm-citation.spec.ts`

### Risks / Decisions

- IP attribution is intellectual-property attribution, not network IP. Do not touch risk-control IP /24 code.
- Attribution tier is not a legal contract generator. It only displays the tier and points to the contract anchor.
- Avoid implying current open-source runners are signed scholar Providers.
- L2 can be represented as a tier definition and zero-count Console state until a real Provider row exists.
- If a catalog row has `citation=None` in the future, UI must still render `ip_attribution` without crashing.

## Definition of Done

- API returns valid `ip_attribution` for all catalog rows.
- `/academic`, `/algorithms/[k_algo]`, and `/console/academic-attribution` render attribution tiers.
- Docs no longer describe 6.A.5 as future-only.
- Backend and frontend tests cover representative L1 and L3 behavior plus the Console page.
- No schema migration, write API, or Provider portal behavior is introduced.
- Sprint status and this story's Dev Agent Record are updated in the implementation PR.

## Story Review Log

### Round 1: Requirements Completeness Review

Findings fixed:
- Constrained `visibility` to a concrete enum so backend and frontend cannot diverge.
- Added solve/demo response coverage so attribution metadata follows the selected algorithm the same way citation metadata does.
- Defined how Console derives citation key / source from existing citation data without a new parser dependency.

Status: PASS after fixes.

### Round 2: Architecture / Testability Review

Findings fixed:
- Clarified that backend attribution tests should extend existing catalog / citation test files rather than adding another duplicated ASGI fixture.
- Corrected the Playwright command to the repository's actual local pattern: `pnpm -C e2e exec playwright test ... --project=chromium`.
- Added an explicit no-new-dependency rule for BibTeX key derivation and scoped it to a local helper.

Status: PASS after fixes.

### Round 3: Acceptance / Scope Audit

Findings fixed:
- Added an explicit documentation-edit target for the two existing "Story 6.A.5 会工程化..." future-tense sentences in the handbook and FAQ.
- Corrected the testing gate reference from AC8 to AC9 after the optimization-response criterion was inserted.

Status: PASS after fixes. Story is ready for implementation.

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Implementation Plan

Implemented in task order:

1. Added RED backend assertions for catalog/list/detail/demo/success-response attribution.
2. Added `IPAttribution` catalog metadata and Pydantic schemas.
3. Mirrored attribution into LP demo and completed optimization responses.
4. Added shared `AttributionBadge` and frontend API types.
5. Rendered attribution on `/academic`, `/algorithms/[k_algo]`, and new `/console/academic-attribution`.
6. Updated academic docs from future-tense to shipped-state language.
7. Added Playwright coverage for academic cards, algorithm details, and the Console review page.

### Debug Log References

- 2026-05-20 — RED: initial backend pytest with plain `uv run` failed to import `solver_orchestrator` on Windows Chinese-character worktree path; used explicit `PYTHONPATH`, matching prior 6.A.1 / 6.A.3 local workaround.
- 2026-05-20 — `uv sync --all-packages --extra dev` was required locally before tests because `opentelemetry` was missing from the fresh venv.
- 2026-05-20 — Playwright config webServer uses bash-style `PYTHONPATH="..."`; local Windows run cannot auto-start it. Started solver/web manually and set `CI=1`, `PLAYWRIGHT_BASE_URL=http://127.0.0.1:3100`, `PLAYWRIGHT_SOLVER_URL=http://127.0.0.1:8002`.
- 2026-05-20 — Client-side `/algorithms/[k_algo]` failed under 3100 because solver CORS allowed only 3000. Added 3100 dev-origin fallback and reran E2E successfully.

### Completion Notes List

- AC1 / AC2 satisfied: all 8 catalog rows expose non-null `ip_attribution`; list/detail APIs validate through `AlgorithmSchema`.
- AC3 satisfied: LP demo and completed optimization responses now include `ip_attribution`; unknown provider degrades to `null` like citation.
- AC4 satisfied: frontend types include `IPAttribution`, and `AttributionBadge` centralizes badge rendering.
- AC5 / AC6 satisfied: `/academic` and `/algorithms/[k_algo]` render L1/L3 attribution while preserving BibTeX, DOI/URL, snippets, and existing page states.
- AC7 satisfied: `/console/academic-attribution` shows L1/L2/L3 counts, all rows, provider, citation key/source, and contract anchor.
- AC8 satisfied: handbook and FAQ now describe attribution tier as shipped into catalog/API/Console surfaces while keeping legal terms anchored to Provider Agreement.
- AC9 satisfied: backend, typecheck, lint, and targeted E2E validation pass.
- AC10 satisfied: sprint-status moved to `done` after post-implementation code review.

Verification:
- `uv run pytest apps/solver-orchestrator/tests/test_algorithm_details.py apps/solver-orchestrator/tests/test_citation.py -q` with explicit local `PYTHONPATH` — 24 passed, 1 existing FastAPI deprecation warning.
- `uv run pytest apps/solver-orchestrator/tests/ -q` with explicit local `PYTHONPATH` — 80 passed, 5 existing FastAPI deprecation warnings.
- `pnpm --filter @opticloud/web typecheck` — pass.
- `pnpm -C e2e exec playwright test academic-page.spec.ts algorithm-citation.spec.ts academic-attribution-console.spec.ts --project=chromium` with manual local services / `CI=1` — 9 passed.
- `uv run ruff check apps/solver-orchestrator/src/solver_orchestrator/catalog.py apps/solver-orchestrator/src/solver_orchestrator/schemas.py apps/solver-orchestrator/src/solver_orchestrator/routes.py apps/solver-orchestrator/tests/test_algorithm_details.py apps/solver-orchestrator/tests/test_citation.py` — pass.
- `git diff --check` — pass.

### Post-Implementation Code Review

Review date: 2026-05-20

Scope reviewed:
- Catalog/schema/response propagation for `ip_attribution`.
- Shared frontend badge rendering and `/academic`, `/algorithms/[k_algo]`, `/console/academic-attribution` surfaces.
- Backend pytest coverage, Playwright E2E coverage, and documentation wording updates.

Findings:
- No decision-needed findings.
- No patch findings.
- No deferred findings.
- Dismissed: one non-blocking implementation note on fixed dev CORS port `3100`; accepted as a local E2E/dev fallback and recorded in Debug Log References.

Result: PASS. Implementation is approved for merge after validation and GitHub sync.

### File List

Created:
- `_bmad-output/stories/6-a-5-ip-attribution-tiers.md`
- `apps/web/src/components/AttributionBadge.tsx`
- `apps/web/src/app/console/academic-attribution/page.tsx`
- `e2e/tests/academic-attribution-console.spec.ts`

Modified:
- `_bmad-output/stories/sprint-status.yaml`
- `apps/solver-orchestrator/src/solver_orchestrator/catalog.py`
- `apps/solver-orchestrator/src/solver_orchestrator/main.py`
- `apps/solver-orchestrator/src/solver_orchestrator/routes.py`
- `apps/solver-orchestrator/src/solver_orchestrator/schemas.py`
- `apps/solver-orchestrator/tests/test_algorithm_details.py`
- `apps/solver-orchestrator/tests/test_citation.py`
- `apps/web/src/app/academic/page.tsx`
- `apps/web/src/app/algorithms/[k_algo]/page.tsx`
- `apps/web/src/lib/api.ts`
- `docs/academic-provider-handbook.md`
- `docs/customer-faqs/academic-onboarding-faq.md`
- `e2e/tests/academic-page.spec.ts`
- `e2e/tests/algorithm-citation.spec.ts`

### Change Log

- 2026-05-20 — Created Story 6.A.5 context and completed three story-review rounds before implementation.
- 2026-05-20 — Implemented IP Attribution L1/L2/L3 catalog metadata, API schemas, success-response propagation, public/Console UI, docs alignment, and tests.
- 2026-05-20 — Completed post-implementation code review; no blocking findings; story moved to done.
