# Deferred Work Log

Items surfaced by code reviews / retrospectives that are real but not blockers for the current PR. Promote to backlog items when their cost-benefit shifts.

---

## Deferred from: code review of 6-a-1-citation-bibtex (2026-05-20)

- **Cached idempotency replay returns stale citation if provider_id is renamed** — `_build_success_response` (routes.py L457-465) keys lookup against the in-process catalog; if a provider is renamed between solve and the 24h-cached replay, the citation silently drops to `null`, violating P23 same-key-same-response. Story risk table accepts this v1 posture. Promote when a provider rename actually ships (none in current catalog).
- **Clipboard `catch` branch in `CodeBlock.handleCopy` is uncovered by any test** — page.tsx L75-83 silently no-ops on `navigator.clipboard.writeText()` rejection; no user feedback in that branch. Headless Chromium requires `context.grantPermissions(['clipboard-write'])` setup. Add when M3 expands the e2e clipboard-permission harness.
- **Catalog invariant tests import full `main.py`** — `tests/test_citation.py` L13-14 drags FastAPI app + DB engine import for pure-data tests. Refactor would split sync catalog tests from async route tests. Matches existing solver-orchestrator test-file pattern; defer until a project-wide test-file restructure ticket.
