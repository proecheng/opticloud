---
story_key: 5-c-5-pipl-self-service-portal
baseline_commit: f2926e46dcc55848a5c4090b01b95de2206905c4
epic_num: 5
story_num: C.5
epic_name: Billing - Refunds + PIPL Export
status: done
priority: High
type: PIPL self-service data export portal
created_by: bmad-create-story
created_at: 2026-05-30
sources:
  - _bmad-output/planning/epics.md (Story 5.C.5 / E7)
  - _bmad-output/planning/prd.md (PIPL access/copy and 7-day product SLA language)
  - _bmad-output/planning/architecture.md (Data Export Aggregator; api-gateway future owner)
  - _bmad-output/stories/5-c-3-pipl-data-export-json.md
  - _bmad-output/stories/5-c-4-pipl-data-export-csv.md
  - apps/auth-service/src/auth_service/routes.py
  - apps/auth-service/src/auth_service/schemas.py
  - apps/web/src/lib/api.ts
  - apps/web/src/app/auth/account/page.tsx
  - apps/web/src/app/console/repro/page.tsx
  - apps/web/src/app/console/chat/page.test.tsx
---

# Story 5.C.5 - PIPL Data Export Self-Service Portal

Status: done

## Story

**As** an authenticated OptiCloud user,
**I want** a Console portal where I can request JSON or CSV PIPL data exports, see live status, and download completed packages,
**so that** I can exercise my data access/copy right without operator intervention.

## Context

Story 5.C.3 added authenticated JSON export lifecycle endpoints and a worker. Story 5.C.4 extended the same lifecycle to CSV zip packages. Epic review item E7 now requires a Console self-service portal: "PIPL 数据导出 self-service portal (Console 内一键 request + 实时 status + 邮件链接)".

There is no real email provider or notification worker in the repository yet. 5.C.3/5.C.4 intentionally represent "email link" as a pointer-safe outbox event plus an authenticated download URL. Therefore this story must not fake email delivery. It closes the user-facing self-service loop by adding a Console page and web API client helpers that:

- let the current authenticated user request JSON or CSV;
- display request id, format, status, requested time, SLA deadline, completion/expiry, package hash/size, and last error;
- poll active request status after request creation;
- download completed JSON/CSV through authenticated fetch, not a naked `<a>` that drops Authorization;
- keep the 7-day language as OptiCloud's product SLA, not a direct statutory quote.

## Scope

1. Add web API client helpers for PIPL data export request/status/download.
2. Add a Console route for the self-service export portal.
3. Support JSON and CSV format selection with clear status and download actions.
4. Poll active queued/processing requests until terminal state or page unload.
5. Download JSON/CSV packages with the bearer JWT and safe generated filenames.
6. Preserve session token handling patterns used by existing account/console pages.
7. Add focused Vitest coverage for API helpers and portal behavior.
8. Update sprint/story status only after code review and gates.
9. Surface backend conflict/expiry semantics clearly: queued/processing means wait, expired means request a new export, failed means retry after remediation.
10. Treat the page as current-session state only unless/until a backend list endpoint exists; do not invent local persisted history.
11. Add a discoverable Console navigation link from existing Console surfaces without redesigning global navigation.

## Out of Scope

- Real email/SMS delivery, inbox previews, or notification-worker integration.
- New backend list endpoint for historical export requests.
- Admin export or support-agent access to another user's data.
- New api-gateway scaffolding.
- Object storage, signed unauthenticated links, or public download URLs.
- Changing JSON/CSV export package generation.
- Full account settings redesign; this is a focused Console tool surface.

## Acceptance Criteria

1. `apps/web/src/lib/api.ts` exposes typed helpers to create data export requests with `format: "json" | "csv"`, fetch status by id, and download the completed package with Authorization preserved.
2. The request helper defaults to JSON when format is omitted, matching backend no-body compatibility.
3. Download helper returns enough metadata for the UI to save a Blob with the correct media type and deterministic filename extension (`.json` or `.zip`) without exposing the bearer token in the URL.
4. A new Console route, proposed as `/console/data-exports`, redirects unauthenticated users to `/auth/login` using the same sessionStorage token pattern as existing account pages.
5. The portal first screen is the actual export tool, not a landing page. It shows format selection, request action, status summary, and download action in a dense operational layout.
6. Users can request JSON and CSV exports independently. Repeated clicks on the same format must be disabled while a request is pending locally, and backend idempotency remains the source of truth.
7. After request creation, the page polls `GET /v1/auth/data-exports/{id}` for queued/processing status and stops polling when status is completed, failed, or expired.
8. Completed JSON and CSV exports show package hash, package size, completion time, expiry time, and a download button.
9. Queued/processing exports cannot be downloaded from the UI; failed exports show bounded `last_error`; expired exports show that a new request is needed.
10. Download actions use authenticated fetch and object URLs, revoke object URLs after use, and never store package contents or bearer tokens in localStorage/sessionStorage.
11. UI copy distinguishes PIPL access/copy rights from OptiCloud's 7-day product SLA and does not claim email delivery is live.
12. The portal remains accessible and usable on desktop and mobile without overlapping text or horizontal overflow.
13. "实时 status" is implemented as bounded client polling over the existing status endpoint, not SSE/WebSocket or a new backend channel.
14. The UI must not show a fake "email sent" state; it may say that notification delivery is future infrastructure and the authenticated download is available in Console.
15. JSON and CSV UI state is kept separate so polling/downloading one format cannot overwrite the visible status of the other.
16. A page reload may lose in-memory export ids; the UI must state that current-session requests are tracked here and backend idempotency can recover by pressing the same format request again.
17. At least one existing Console header nav links to `/console/data-exports`, so the portal is discoverable in-app.
18. Component tests mock `next/navigation` and browser download primitives explicitly; tests must not depend on a real browser download.
19. Existing account deletion and merge UI behavior is unchanged.
20. Quality gates pass:
    - focused web API client tests;
    - focused portal component tests;
    - existing web tests/typecheck;
    - relevant auth-service regression if API contracts are touched;
    - ruff/mypy only if Python files are touched;
    - `git diff --check`.

## Tasks / Subtasks

- [x] T1: Add data export API client helpers (AC: 1-3, 10)
  - [x] Add `DataExportFormat`, `DataExportStatus`, `DataExportStatusResponse`, and create/download helper types.
  - [x] Add `requestDataExport(jwt, format?)`.
  - [x] Add `getDataExportStatus(jwt, exportId)`.
  - [x] Add `downloadDataExport(jwt, status)` that uses authenticated fetch and returns Blob metadata.
  - [x] Add Vitest API helper tests covering method, body, auth header, JSON default, and CSV zip metadata.

- [x] T2: Add self-service portal page (AC: 4-12)
  - [x] Create `/console/data-exports` page.
  - [x] Read JWT from sessionStorage, redirect unauthenticated users to `/auth/login`.
  - [x] Build format segmented controls for JSON/CSV.
  - [x] Show separate JSON and CSV status/download panels without nested cards.
  - [x] Poll queued/processing status per format and stop at terminal states.
  - [x] Use authenticated download helper and revoke object URLs.
  - [x] Keep tokens and package content out of browser storage.
  - [x] Map 409/410/404 download failures to user-safe messages without exposing raw backend internals.
  - [x] Add a Console nav link from an adjacent Console page.

- [x] T3: Add focused portal tests (AC: 4-12)
  - [x] Test unauthenticated redirect.
  - [x] Test JSON/CSV request and status rendering.
  - [x] Test queued/processing disables download and triggers polling for only that format.
  - [x] Test completed download calls authenticated helper and revokes object URL.
  - [x] Test no package/token storage writes.
  - [x] Test expired and failed states render distinct next actions.
  - [x] Mock `useRouter`, `URL.createObjectURL`, `URL.revokeObjectURL`, and anchor click behavior.

- [x] T4: Run gates and complete story (AC: 13-14)
  - [x] Run focused web tests.
  - [x] Run web test suite/typecheck.
  - [x] Run relevant backend regression only if API contracts change.
  - [x] Run post-implementation code review and fix findings.
  - [x] Commit, push, open PR, wait for CI, merge, sync main.

## Dev Notes

### Existing Patterns To Reuse

- Auth token lookup: `apps/web/src/app/auth/account/page.tsx` reads `sessionStorage.getItem("jwt_access")` and redirects to `/auth/login`.
- API error normalization: `OptiCloudClientError` in `apps/web/src/lib/api.ts`.
- Console shell density: `/console/repro`, `/console/chat`, and `/console/excel`.
- Tests: component tests use happy-dom and module mocks, e.g. `console/chat/page.test.tsx`.
- Existing backend endpoints:
  - `POST /v1/auth/data-exports` with optional body `{ "format": "json" | "csv" }`.
  - `GET /v1/auth/data-exports/{export_id}`.
  - `GET /v1/auth/data-exports/{export_id}/download`.

### Download Rules

- Do not render `download_url` directly as `<a href>`, because the backend requires Authorization.
- Use `fetch` with `Authorization: Bearer <jwt>`.
- For JSON, create a Blob from `application/json`; for CSV, use the response content type (`application/zip`).
- Suggested filenames:
  - `opticloud-pipl-data-export-{id}.json`
  - `opticloud-pipl-data-export-{id}.zip`
- Revoke object URLs in a `finally` block or immediately after clicking the generated anchor.
- If download returns 409, refresh status and keep the download button disabled until completed.
- If download returns 410, show expired and offer a new request action.
- If download returns 404, treat it as unavailable/not owned and do not leak existence details.
- For non-OK binary download responses, parse JSON problem details when possible, otherwise fall back to a generic status-safe message.

### Polling Rules

- Poll only when the page knows an export id and status is `queued` or `processing`.
- Use a modest interval, e.g. 2 seconds.
- Clear interval on unmount, format change, terminal status, or logout/redirect.
- Do not poll if no JWT is available.
- Keep polling bounded to the current visible request id; do not create a global background watcher.
- Keep JSON and CSV timers independent so one terminal state does not stop the other format's polling.

### State Recovery Rules

- Do not persist export ids to localStorage/sessionStorage in this story.
- If the user reloads, they can press "Request JSON" or "Request CSV" again; backend idempotency returns the active not-expired request.
- Do not add a fake local history table; history needs a backend list endpoint in a later story.

### UX Constraints

- The first viewport must be the actual tool surface.
- Keep copy concise and operational. Do not add educational paragraphs about how the feature works.
- Use segmented controls for JSON/CSV format choice.
- Use ordinary buttons for request/download commands.
- Use compact status rows for request id, SLA deadline, expiry, hash, and byte size.
- Do not use decorative hero sections or nested cards.
- Add the page to nearby Console nav labels using concise text such as "数据导出" or "Exports".

### Test Harness Notes

- Mock `next/navigation` `useRouter().push`.
- Mock object URL creation and revocation.
- Mock `document.createElement("a")` click only if the implementation uses generated anchors.
- Avoid relying on actual file save behavior in happy-dom.

### Suggested Test Commands

```powershell
pnpm --dir apps/web vitest run src/lib/data-export.test.ts src/app/console/data-exports/page.test.tsx
pnpm --dir apps/web test
pnpm --dir apps/web typecheck
git diff --check
```

## Definition Of Done

- Story file has passed 3 pre-implementation adversarial review rounds and revisions.
- Implementation satisfies every Acceptance Criterion without adding out-of-scope API surfaces.
- Post-implementation code review is completed and findings are fixed or explicitly documented.
- Local quality gates and GitHub CI pass.
- Story and sprint status are updated to `done` only after review and gates.
- Branch is pushed, PR is created, merged to `main`, remote branch is deleted, and local `main` is synced.

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Debug Log References

- Baseline commit: `f2926e46dcc55848a5c4090b01b95de2206905c4`.
- Focused API/page tests passed: `pnpm vitest run src/lib/data-export.test.ts src/app/console/data-exports/page.test.tsx` (11 tests).
- Focused Console regression after review patch passed: `pnpm vitest run src/app/console/data-exports/page.test.tsx src/app/console/chat/page.test.tsx src/app/console/repro/page.test.tsx` (9 tests).
- Full web regression passed: `pnpm test` (25 files, 125 tests).
- Static gates passed: `pnpm typecheck` and `git diff --check`.
- `pnpm lint` is not a usable configured gate yet; Next prompted for first-time ESLint setup and exited without linting.
- Backend regression was not run because this story only changed the web client/UI and did not change backend API contracts.

### Completion Notes List

- Added typed PIPL data export web API helpers for request, status, and authenticated download with deterministic `.json` / `.zip` filenames.
- Added `/console/data-exports` as a dense Console tool surface using the existing `sessionStorage.getItem("jwt_access")` login pattern.
- Implemented JSON/CSV segmented selection, separate per-format state, bounded polling for queued/processing requests, completed download metadata display, failed/expired next-action states, and current-session-only recovery copy.
- Implemented authenticated Blob downloads through `downloadDataExport`, object URL creation/click/revocation, and no package/token persistence.
- Added discoverability links from existing Console chat and repro pages.
- Added focused API helper and portal component tests, including router/browser-download mocks, storage hygiene, expired/failed states, per-format isolation, and stale polling-response protection.
- Completed post-implementation code review, fixed mobile header overflow risk in Console headers, reran gates, and marked story done.

### File List

- `_bmad-output/stories/5-c-5-pipl-self-service-portal.md`
- `_bmad-output/stories/sprint-status.yaml`
- `apps/web/src/lib/api.ts`
- `apps/web/src/lib/data-export.test.ts`
- `apps/web/src/app/console/data-exports/page.tsx`
- `apps/web/src/app/console/data-exports/page.test.tsx`
- `apps/web/src/app/console/chat/page.tsx`
- `apps/web/src/app/console/repro/page.tsx`

## Change Log

- 2026-05-30 - Story created with self-service portal scope, authenticated download guardrails, and no fake email delivery.
- 2026-05-30 - Implemented PIPL Console data export portal, focused tests, post-review mobile header fix, and local gates; status set to done.

## Pre-Implementation Adversarial Review

### Round 1 - Boundary, Authentication, Download Semantics, And False-Completion Risk

Findings:

1. "实时 status" could be over-implemented as SSE/WebSocket despite the existing backend only exposing polling.
2. The epic phrase "邮件链接" could lead the UI to claim email delivery exists; it does not.
3. The story did not require explicit UX for backend 409 queued/processing download conflicts.
4. Expired 410 and cross-tenant 404 behavior were not mapped to safe user-facing states.
5. A naive `<a href={download_url}>` would drop Authorization and fail or leak URL assumptions.
6. Blob/object URL revocation was required but not test-tied enough to prevent leaks.
7. The UI could accidentally store downloaded package content in browser storage for convenience.
8. Polling needed to be scoped to the visible request id, not a hidden background watcher.
9. Failed exports need a retry/remediation state, not a generic red error only.
10. Story tests did not yet require expired and failed terminal-state rendering.

Revision after Round 1:

- Clarified polling as the only "live" status mechanism.
- Forbid fake email-sent copy and naked download links.
- Added 409/410/404 download semantics and terminal-state UI requirements.
- Added tests for expired/failed states and object URL/storage hygiene.

### Round 2 - Drift, State Consistency, Format Isolation, And Recovery

Findings:

1. The story did not specify whether JSON and CSV statuses share one selected panel or have independent state.
2. A CSV poll result could overwrite JSON status if state is keyed too loosely.
3. A single interval could stop polling both formats when only one format reaches a terminal state.
4. Reload behavior was vague and might push implementation toward unsafe persisted export ids.
5. Without a backend list endpoint, a local history table would be fake history and could mislead users.
6. `download_url` should be displayed as metadata at most, not used as persisted source of truth.
7. Backend idempotency can recover active requests after reload by pressing the same format again; the story should say that.
8. Tests did not yet require per-format polling isolation.
9. The UI could accidentally imply it lists all historical exports, which it cannot.
10. Separate JSON/CSV panels are clearer than one selected-format-only panel for compliance operations.

Revision after Round 2:

- Required separate JSON and CSV status/download state.
- Added independent polling/timer rules per format.
- Added current-session-only recovery rules and forbade fake local history.
- Added test coverage for per-format polling isolation.

### Round 3 - Dependency Closure, Testability, Navigation, And CI Fit

Findings:

1. The story did not make the new page discoverable from any existing Console navigation.
2. happy-dom will not perform real file downloads; tests need explicit browser primitive mocks.
3. `next/navigation` is used by auth/account pages and must be mocked in page tests.
4. Download helper must parse problem JSON for non-OK responses when possible, but binary failures may not be JSON.
5. Adding only a direct URL route would technically work but fail the self-service discoverability intent.
6. The story did not require typecheck after adding new client types.
7. If the portal test stores JWT in localStorage instead of sessionStorage, it would drift from account page patterns.
8. The implementation could accidentally alter account deletion page while adding links; the story needs to keep that unchanged.
9. CI path filters should run web checks, so focused web tests and typecheck are the core gates.
10. Anchor-click download code must be deterministic and isolated enough to test without browser side effects.

Revision after Round 3:

- Added Console nav discoverability requirement.
- Added explicit test harness mocks for router and object URL/download primitives.
- Added binary error parsing guidance and typecheck/gate emphasis.
- Reconfirmed sessionStorage-only token pattern and no account settings redesign.

## Senior Developer Review (AI)

Findings:

- [x] [Review][Patch] Adding a new `数据导出` link to existing Console headers increased the chance of horizontal overflow on narrow mobile widths. Patched the data-export, chat, and repro Console headers to allow the brand/nav row and nav links to wrap with stable gaps.

Additional review notes:

- Auth/download semantics are compliant with the story: no naked download URL is rendered; downloads go through authenticated fetch and object URLs are revoked.
- JSON and CSV request state is isolated by format, and stale polling responses are ignored unless both the requested id and returned id match the active row.
- The UI does not persist export ids, package contents, or bearer tokens beyond the existing login session token.
- No fake email-delivered state or backend history/list endpoint was introduced.

Decision: Approved after patch.
