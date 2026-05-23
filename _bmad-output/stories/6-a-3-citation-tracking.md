---
story_key: 6-a-3-citation-tracking
epic_num: 6.A
epic_name: Reproducibility — BibTeX Academic v1 必上 (M3)
story_num: 6.A.3
status: done
priority: 🟢 High (Innovation #3 学界变现飞轮第三根支柱；6.A.1/6.A.2 已让引用可复制、可被看见，本 story 让引用可被运营团队追踪)
sizing: M (~4-5 hours; pure Python tracker + CLI + report artifacts + tests; optional external API mocked in tests; no DB migration / no frontend route)
type: implementation
created_by: bmad-create-story
created_at: 2026-05-20
sources:
  - _bmad-output/planning/epics.md L1745-L1747 (Story 6.A.3 base AC — BibTeX 输出后手动/半自动追踪 + Linear ticket)
  - _bmad-output/planning/epics.md L2022 (TT6 — Semantic Scholar API + Google Scholar weekly scrape + 每月 Dashboard 自动追踪)
  - _bmad-output/planning/epics.md L480-L485 (Epic 6.A goal — Innovation #3 学界变现飞轮基础)
  - _bmad-output/planning/architecture.md L513, L574 (D14 async/scheduled topology; current M3 scheduling can stay CLI/CronJob wrapper)
  - _bmad-output/stories/6-a-1-citation-bibtex.md (canonical citation keys + catalog data shape)
  - _bmad-output/stories/6-a-2-bibtex-academic-page.md (academic page explains 6.A.3 will create Linear cards)
  - apps/solver-orchestrator/src/solver_orchestrator/catalog.py (8 citation targets, citation keys, DOI/URL metadata)
  - apps/solver-orchestrator/src/solver_orchestrator/billing_reconciler.py (pure module + structured report pattern)
  - apps/solver-orchestrator/src/solver_orchestrator/billing_reconciler_cli.py (argparse CLI + JSON stdout + exit-code pattern)
  - apps/solver-orchestrator/src/solver_orchestrator/BILLING_RECONCILER.md (runbook pattern for future CronJob integration)
  - scripts/sbom_diff.py (existing Linear ticket placeholder/dry-run precedent)
  - Semantic Scholar official API docs — https://www.semanticscholar.org/product/api and https://api.semanticscholar.org/api-docs/
  - Semantic Scholar official tutorial — https://www.semanticscholar.org/product/api/tutorial
  - Linear official API docs — https://linear.app/developers/graphql and https://linear.app/docs/api
  - Google robots/crawling guidance — https://developers.google.com/search/docs/crawling-indexing/robots/robots_txt
dependencies:
  upstream:
    - 6-a-1-citation-bibtex (done, PR #29) — provides `citation.bibtex`, citation keys, DOI/URL fields on all 8 catalog rows
    - 6-a-2-bibtex-academic-page (done, PR #30) — public `/academic` surface that tells scholars every new citation becomes a Linear card
    - m2-2c-billing-reconciler-job / 5-a-7-reconciliation-cron (done) — module + CLI + report artifact pattern to reuse
  downstream:
    - 6-a-4-academic-onboarding-toolkit — can reuse monthly citation report as proof for scholar onboarding
    - 6-a-5-ip-attribution-tiers — can use tracked citations to assign Tier 1/2/3 scholar attribution
    - 8-c-8-algorithm-provenance-page — can link to citation-tracking report artifacts
non_goals:
  - Real scheduler wiring (K8s CronJob / systemd timer / Dramatiq) — story ships CLI/runbook; M3 deployment wires cadence
  - Direct Google Scholar HTML scraping — do not violate robots/automated-access constraints; use manual/export/import path for v1
  - Persistent DB schema for citation hits — v1 stores snapshots in JSON files; DB-backed dashboard can come later
  - Frontend dashboard route — v1 monthly dashboard is a generated Markdown/JSON artifact
  - Full Linear issue creation as required behavior — v1 must produce deterministic Linear issue payloads; optional real API call only if env vars are present and tests mock it
  - CrossRef/OpenAlex/Dimensions integrations — not needed for TT6 v1; can be added if S2 coverage is insufficient
---

# Story 6.A.3 — BibTeX 自动追踪 (Innovation #3 配套)

## User Story

**As** the 学界增长 / research ops owner,
**I want** a weekly runnable citation tracker that reads OptiCloud's canonical BibTeX keys, checks compliant citation sources, compares against the last snapshot, and emits Linear-ready cards plus a monthly dashboard artifact,
**so that** every new paper citing OptiCloud algorithms becomes an operational follow-up instead of an invisible vanity metric.

## Why This Story

6.A.1 made citations part of the product contract. 6.A.2 gave scholars a public `/academic` page where citations are easy to copy. That still leaves the flywheel unmeasured: if a scholar pastes `@software{aqgs2025opticloud,...}` into a preprint, the platform team needs a repeatable way to notice, triage, and follow up.

The base epic AC says "手动 / 半自动追踪 + Linear ticket"; TT6 raises that bar to Semantic Scholar API + Google Scholar weekly scrape + monthly dashboard. The implementation should satisfy the intent without violating current constraints:

- Semantic Scholar has an official REST/Graph API, supports paper/citation metadata, and recommends API keys + rate limiting.
- Google Scholar does not expose a supported bulk API. For v1, the "Google Scholar weekly" path must be a **compliance-safe import** from Google Scholar alerts/manual export/approved third-party export, not an HTML scraper.
- The repo already uses a pragmatic pattern for scheduled work: build a pure module + CLI + structured JSON output now; let M3 deployment wrap it in CronJob/systemd/Dramatiq later.

## Acceptance Criteria

### AC1 — Citation Target Extraction From Catalog

Create `apps/solver-orchestrator/src/solver_orchestrator/citation_tracker.py`.

It must expose:

```python
@dataclass(frozen=True)
class CitationTarget:
    k_algo: str
    citation_key: str
    title: str
    doi: str | None
    url: str | None
    source: Literal["catalog"]

def extract_citation_targets(catalog: Sequence[Algorithm] = CATALOG) -> list[CitationTarget]:
    ...
```

Rules:

- Parse `citation_key` from the canonical BibTeX entry with `@\w+{key,`.
- Parse `title` from the BibTeX `title = {...}` field; fall back to `description_en` only if title is absent.
- Include all rows where `citation is not None`.
- Preserve duplicate citation keys for different algorithms, especially `huangfu2018parallelizing` for `highs-lp` and `highs-milp`; downstream matching must retain `k_algo`, not collapse by key.
- Add tests that currently extract 8 targets and include `aqgs2025opticloud`.

### AC2 — Semantic Scholar Client, Rate-Limited and Mockable

Implement a small async Semantic Scholar client in the same module. It should use `httpx.AsyncClient` (already used by solver-orchestrator billing client; add it to runtime dependencies if needed).

Required behavior:

- Base URL: `https://api.semanticscholar.org/graph/v1`.
- For DOI-backed targets, call `/paper/DOI:{doi}/citations` with a minimal `fields` parameter for the citing paper fields:
  - `citingPaper.paperId,citingPaper.title,citingPaper.url,citingPaper.year,citingPaper.authors,citingPaper.externalIds`
- Parse Semantic Scholar citation responses from `data[].citingPaper`. Ignore individual rows where `citingPaper` is missing or has no usable title/external identity, and add a non-fatal scan note rather than failing the full run.
- Handle Semantic Scholar pagination with `offset` / `limit`; v1 default limit is 100 per target and records `truncated=true` if the response indicates more data. Do not loop unbounded in one run.
- For non-DOI targets (`aqgs-acopf`, OR-Tools software, ARIMA book), skip Semantic Scholar citation lookup and append a non-fatal scan note: `{"source":"semantic_scholar","k_algo":"...","status":"skipped_no_doi"}`. These targets are covered by the import path in AC3.
- Accept optional API key from settings/env `SEMANTIC_SCHOLAR_API_KEY`; when present send header `x-api-key`.
- Add these fields to `apps/solver-orchestrator/src/solver_orchestrator/config.py` so env handling is centralized:
  ```python
  semantic_scholar_api_key: str = Field(default="", alias="SEMANTIC_SCHOLAR_API_KEY")
  semantic_scholar_min_interval_seconds: float = Field(default=1.0, alias="SEMANTIC_SCHOLAR_MIN_INTERVAL_SECONDS")
  semantic_scholar_timeout_seconds: float = Field(default=10.0, alias="SEMANTIC_SCHOLAR_TIMEOUT_SECONDS")
  linear_api_key: str = Field(default="", alias="LINEAR_API_KEY")
  linear_team_key: str = Field(default="", alias="LINEAR_TEAM_KEY")
  ```
- Enforce a conservative delay between S2 calls. Default `semantic_scholar_min_interval_seconds = 1.0`, configurable via env, matching the official intro 1 RPS guidance.
- Each S2 request must use a bounded timeout from settings. No infinite HTTP waits.
- Treat 404 as "no indexed paper yet", not failure.
- Treat 429/5xx/network errors as source failure and include them in the report; do not crash the whole run.
- Tests must use a mock transport/client; CI must never hit the real Semantic Scholar network.
- `httpx` is already used by `solver_orchestrator.billing_client` but currently lives only in the `dev` optional dependency of `apps/solver-orchestrator/pyproject.toml`. If this module imports `httpx` at runtime, promote `httpx>=0.27` into the solver-orchestrator main dependencies and leave the dev copy removed or duplicated only if uv requires it.

### AC3 — Google Scholar Weekly Path Is Import, Not Scrape

Do not implement direct Google Scholar HTML scraping.

Implement a CSV/JSON import parser for weekly Google Scholar-derived evidence:

```python
@dataclass(frozen=True)
class ImportParseResult:
    hits: list[CitationHit]
    unmatched_imports: list[dict[str, str]]
    malformed_rows: list[dict[str, str]]

def load_google_scholar_import(
    path: Path,
    targets: Sequence[CitationTarget],
    *,
    observed_at: datetime,
) -> ImportParseResult:
    ...
```

Supported CSV columns:

- `citation_key` (required)
- `title` (required)
- `url` (optional but strongly preferred)
- `year` (optional int)
- `authors` (optional; semicolon-separated or plain string)
- `source` (optional; default `google_scholar_import`)

Supported JSON shape:

```json
[
  {
    "citation_key": "aqgs2025opticloud",
    "title": "A paper that cites AQGS-ACOPF",
    "url": "https://example.edu/preprint",
    "year": 2026,
    "authors": ["Li Wei", "Chen Ming"]
  }
]
```

Matching rules:

- Match imported hits to catalog targets by `citation_key`.
- If one citation key maps to multiple `k_algo` values, create one hit per matching target, retaining `k_algo`.
- Unknown `citation_key` rows are not dropped; put them in `unmatched_imports` with reason `unknown_citation_key`.
- Malformed rows should be reported with row number and reason; one bad row must not abort the entire import.
- Use `utf-8-sig` for CSV so exports with BOM parse cleanly.
- Normalize authors into `list[str]`: split semicolon-delimited strings; trim blanks; keep a one-element list for plain strings without semicolons.

### AC4 — Snapshot Diff and Deterministic Hit IDs

Implement snapshot comparison so weekly runs find **new** citations.

Dataclasses:

```python
@dataclass(frozen=True)
class CitationHit:
    source: Literal["semantic_scholar", "google_scholar_import"]
    k_algo: str
    citation_key: str
    external_id: str
    title: str
    url: str | None
    year: int | None
    authors: list[str]
    observed_at: datetime

@dataclass(frozen=True)
class CitationTrackingReport:
    generated_at: datetime
    targets_scanned: int
    hits_total: int
    hits_new: int
    scan_notes: list[dict[str, str]]
    source_failures: list[dict[str, str]]
    unmatched_imports: list[dict[str, str]]
    malformed_imports: list[dict[str, str]]
    new_hits: list[CitationHit]
    all_hits: list[CitationHit]
    linear_issue_payloads: list[dict[str, object]]
```

Rules:

- Hit identity must be deterministic across runs: `source + k_algo + external_id`.
- `external_id` priority: S2 `paperId`; else normalized URL; else SHA-256 of lowercase title + citation_key.
- Load previous state from `--state <path>` if present; empty state means all current hits are new.
- Write the new state only after the run completes successfully enough to produce a report.
- Deduplicate hits from S2 and Google import only when they share the same normalized URL or same S2 paperId for the same `k_algo`.
- State file shape is intentionally small and stable:
  ```json
  {
    "version": 1,
    "generated_at": "2026-05-20T00:00:00+00:00",
    "seen_hit_ids": ["semantic_scholar:highs-lp:paper-123"],
    "hits": [/* serialized CitationHit objects */]
  }
  ```
- Atomic write requirement: write `state.tmp` in the same directory, then replace the target path.

### AC5 — Linear-Ready Ticket Payloads

Build deterministic Linear issue payloads for every new hit.

Function:

```python
def build_linear_issue_payload(hit: CitationHit, target: CitationTarget) -> dict[str, object]:
    ...
```

Payload requirements:

- `title`: `[Citation] {k_algo}: {paper title truncated to 80 chars}`
- `description`: Markdown with citation key, algorithm, source, URL, year, authors, observed time, and follow-up checklist:
  - verify paper actually cites OptiCloud/BibTeX entry
  - reply/thank author if appropriate
  - consider adding to monthly academic report
  - if false positive, mark duplicate/invalid
- `labels`: include `academic`, `citation-tracking`, and `story-6-a-3`
- `metadata`: include `k_algo`, `citation_key`, `source`, `external_id`

Optional real Linear integration:

- If `LINEAR_API_KEY` and `LINEAR_TEAM_KEY` are configured and CLI is called with `--create-linear`, call Linear GraphQL `issueCreate`.
- GraphQL endpoint: `https://api.linear.app/graphql`.
- Headers: `Authorization: {LINEAR_API_KEY}` and `Content-Type: application/json`.
- Mutation input shape:
  ```graphql
  mutation IssueCreate($input: IssueCreateInput!) {
    issueCreate(input: $input) {
      success
      issue { id identifier url }
    }
  }
  ```
- `IssueCreateInput` must include `teamId` or team key resolution. For v1, use `LINEAR_TEAM_KEY` as the team identifier only if Linear accepts it in the target account; otherwise fail closed with a clear message and keep dry-run payloads. Do not guess team IDs.
- If env vars are missing, `--create-linear` must fail with a clear message and exit code 2.
- Never print `LINEAR_API_KEY` or `SEMANTIC_SCHOLAR_API_KEY` to stdout/stderr/logs, even on failure.
- Tests should mock the Linear HTTP call. No real Linear API call in CI.

### AC6 — CLI Runner and Artifacts

Create `apps/solver-orchestrator/src/solver_orchestrator/citation_tracker_cli.py`.

Expose a directly testable entry point:

```python
def main(argv: Sequence[str] | None = None) -> int:
    ...
```

Tests should call `main([...])` directly instead of spawning a subprocess unless a subprocess is specifically needed.

Usage examples:

```bash
uv run python -m solver_orchestrator.citation_tracker_cli \
  --state .cache/citation-tracking/state.json \
  --out _bmad-output/reports/citation-tracking/latest.json \
  --markdown _bmad-output/reports/citation-tracking/latest.md \
  --semantic-scholar \
  --google-scholar-import data/google-scholar-weekly.csv
```

CLI requirements:

- `--state` path, default `.cache/citation-tracking/state.json`.
- `--out` JSON report path, default `_bmad-output/reports/citation-tracking/latest.json`.
- `--markdown` optional monthly dashboard path; if provided, write a readable Markdown report.
- `--semantic-scholar` opt-in flag; default off so local runs without network are deterministic.
- `--google-scholar-import` can be passed multiple times.
- `--create-linear` optional; default is dry-run payload generation only.
- Stdout emits one JSON line with `event="citation.tracker.report"`, counts, and output paths.
- Stderr emits a short human summary.
- Exit codes:
  - `0`: report generated and any optional Linear calls succeeded
  - `1`: source failures or malformed imports occurred, but report still generated
  - `2`: invalid configuration or Linear creation failure
- Generated local artifacts under `_bmad-output/reports/citation-tracking/` and `.cache/citation-tracking/` should not be committed unless the user explicitly asks to archive a report. Add ignore rules if these paths are not already ignored.
- JSON serialization must be explicit and stable: dataclasses should serialize datetimes to ISO 8601 strings and preserve `ensure_ascii=False`; do not rely on raw `dataclasses.asdict()` for datetime-containing report/state payloads without a helper.

### AC7 — Monthly Dashboard Markdown

The `--markdown` artifact is the v1 "monthly dashboard".

It must include:

- Generated timestamp.
- Target count and scanned source summary.
- Table of new hits: `k_algo`, citation key, paper title, year, source, URL.
- Table/count of known total hits.
- Section for source failures.
- Section for unmatched Google Scholar imports.
- Section for malformed Google Scholar import rows.
- Copy-paste block containing Linear issue payload JSON for new hits.

No frontend page in this story. The artifact is intentionally file-based so it can be archived in CI artifacts, sent to email, or pasted into Linear/Notion.

### AC8 — Runbook

Create `apps/solver-orchestrator/src/solver_orchestrator/CITATION_TRACKER.md`.

Runbook must explain:

- Local dry-run command.
- Weekly run command with `--semantic-scholar` and Google Scholar import files.
- How to request/use `SEMANTIC_SCHOLAR_API_KEY`.
- Why Google Scholar is import-only in v1; no direct scraping.
- How to wire future K8s CronJob using the same CLI.
- How to use `--create-linear` and required env vars.
- Secret-handling rule: env vars only; never include keys in CLI flags, reports, Markdown, or logs.
- What each exit code means.

### AC9 — Tests

Add `apps/solver-orchestrator/tests/test_citation_tracker.py`.

Required tests:

1. `test_extract_targets_from_catalog_keeps_duplicate_keys`
2. `test_semantic_scholar_fetch_maps_citations_with_mock_transport`
3. `test_semantic_scholar_404_is_not_failure`
4. `test_semantic_scholar_429_records_source_failure`
5. `test_google_scholar_csv_import_matches_targets`
6. `test_google_scholar_import_unknown_key_goes_to_unmatched`
7. `test_snapshot_diff_marks_only_new_hits`
8. `test_dedup_same_url_same_algo_across_sources`
9. `test_linear_payload_contains_followup_checklist`
10. `test_markdown_dashboard_contains_new_hits_and_payloads`
11. `test_cli_dry_run_writes_json_and_markdown`
12. `test_cli_create_linear_requires_env`

Testing constraints:

- No real network.
- No database.
- Use `tmp_path` for state/report files.
- If CLI is tested via subprocess, set `PYTHONPATH` explicitly on Windows; otherwise call `main(argv)` directly to avoid path issues learned in 6.A.1.

### AC10 — Quality Gates and Sprint Hygiene

- `uv run --isolated --package opticloud-solver-orchestrator --extra dev pytest apps/solver-orchestrator/tests/test_citation_tracker.py`
- If `--isolated --package ... --extra dev` fails because workspace path sources are not available in an isolated env, use the equivalent non-isolated workspace command and record the reason in the Dev Agent Record.
- `uv run mypy apps/solver-orchestrator/src/solver_orchestrator apps/solver-orchestrator/tests`
- `uv run ruff check apps/solver-orchestrator/src/solver_orchestrator/citation_tracker.py apps/solver-orchestrator/src/solver_orchestrator/citation_tracker_cli.py apps/solver-orchestrator/tests/test_citation_tracker.py`
- `uv run ruff format --check apps/solver-orchestrator/src/solver_orchestrator/citation_tracker.py apps/solver-orchestrator/src/solver_orchestrator/citation_tracker_cli.py apps/solver-orchestrator/tests/test_citation_tracker.py`
- `uv tool run pre-commit run --files <changed>`
- Sprint-status transition must be bundled:
  - story creation: `6-a-3-citation-tracking: ready-for-dev`
  - implementation: `in-progress`
  - implementation complete / awaiting review: `code-review`
  - after code review fixes: `done`

## Tasks

### T1 — Tracker Core

1. [x] Add `citation_tracker.py` with dataclasses and target extraction.
2. [x] Implement BibTeX key/title parsing helpers.
3. [x] Implement hit identity, normalization, dedup, snapshot load/save.
4. [x] Implement explicit JSON serialization/deserialization helpers for `CitationHit`, `CitationTrackingReport`, and snapshot state.

### T2 — Source Ingestion

1. [x] Implement Semantic Scholar fetch path with injectable client and rate limiter.
2. [x] Implement Google Scholar CSV/JSON import parser.
3. [x] Ensure errors are captured as report data, not uncaught exceptions.
4. [x] Promote `httpx>=0.27` into `apps/solver-orchestrator/pyproject.toml` main dependencies because both the existing billing client and this tracker import it at runtime.

### T3 — Report + Linear Payloads

1. [x] Build `CitationTrackingReport`.
2. [x] Build Linear payloads.
3. [x] Add optional Linear GraphQL create function behind `--create-linear`.
4. [x] Generate Markdown dashboard.

### T4 — CLI + Runbook

1. [x] Add `citation_tracker_cli.py` with argparse and JSON stdout.
2. [x] Add `CITATION_TRACKER.md`.
3. [x] Keep scheduling examples as documentation only.
4. [x] Add `.gitignore` entries for `.cache/citation-tracking/` and `_bmad-output/reports/citation-tracking/` if absent.

### T5 — Tests and Gates

1. [x] Add the 12 tests in AC9.
2. [x] Run targeted pytest/ruff/mypy/pre-commit.
3. [x] Update sprint-status with story lifecycle states in the same PR.

## Risks and Guardrails

| Risk | Guardrail |
|---|---|
| Developer implements direct Google Scholar scraping | Explicitly forbidden. Implement import parser only; cite robots/official guidance in runbook. |
| Real API calls make CI flaky | Every network path must accept injectable client/mock transport. Tests must not hit internet. |
| S2 rate limits | Default min interval 1s; use API key header; 429 recorded as source failure. |
| Duplicate citation keys collapse `highs-lp` and `highs-milp` | Hit identity includes `k_algo`; tests lock duplicate handling. |
| State write corrupts previous snapshot | Write temp file then atomic replace. |
| Linear integration blocks local use | Default dry-run payload generation; real Linear creation only behind explicit flag and env. |
| "Dashboard" scope balloons into frontend | Dashboard is Markdown/JSON artifact only. |
| Monthly dashboard reveals bad/false-positive hits as truth | Linear checklist requires verification; report labels source and unmatched rows clearly. |
| API keys leak into reports/logs | Keys live only in `SolverSettings`; CLI must never echo env values; tests assert output does not contain configured fake keys. |
| Generated reports accidentally committed | Ignore `.cache/citation-tracking/` and `_bmad-output/reports/citation-tracking/` unless a human explicitly decides to archive a report. |

## Definition of Ready

- 6.A.1 and 6.A.2 are merged to `main`.
- Citation catalog contains `citation.bibtex`, DOI/URL, and stable citation keys.
- Existing scheduled-job pattern is module + CLI + runbook, not in-process scheduler.
- External API constraints documented: S2 official API is allowed; Google Scholar direct scraping is not.

## Definition of Done

- `citation_tracker.py`, `citation_tracker_cli.py`, `CITATION_TRACKER.md`, and `test_citation_tracker.py` are present.
- CLI can run without network and produce JSON + Markdown artifacts from a Google Scholar import fixture.
- Semantic Scholar path is implemented and covered with mocked responses.
- Linear issue payloads are deterministic; optional real creation is mocked in tests.
- All AC9 tests pass.
- Story status and sprint-status are updated according to the strict cycle.

## Three-Round Story Review Log

> The review rounds below are mandatory before implementation. Each round must produce changes or explicitly state no change required.

### Round 1 — BMad Checklist Review

**Result:** PASS after fixes.

Checklist findings applied:

- The Google Scholar import API originally returned only `list[CitationHit>` even though the AC required unmatched and malformed rows. Replaced with `ImportParseResult`.
- `semantic_status="skipped_no_doi"` was mentioned but not represented in the report. Added `scan_notes`.
- Semantic Scholar pagination/truncation was underspecified. Added bounded pagination guidance and `truncated=true` scan note.
- `httpx` runtime dependency was ambiguous. Story now requires promoting `httpx>=0.27` to solver-orchestrator main dependencies if used by the tracker.
- State file shape and atomic write behavior are now explicit.

### Round 2 — Architecture / Security / Compliance Review

**Result:** PASS after fixes.

Findings applied:

- External API credentials were mentioned only as raw env vars. Added `SolverSettings` fields for Semantic Scholar and Linear configuration.
- HTTP timeout was implicit. Added `SEMANTIC_SCHOLAR_TIMEOUT_SECONDS` and "no infinite waits" requirement.
- Linear GraphQL behavior was too vague. Added endpoint, mutation shape, dry-run/fail-closed behavior, and no-team-ID guessing rule.
- Secret leakage risk was underspecified. Added explicit no-secret-output rule and a test expectation.
- Generated report/state artifacts could be accidentally committed. Added ignore-rule guidance for `.cache/citation-tracking/` and `_bmad-output/reports/citation-tracking/`.

### Round 3 — Dev-Readiness Review

**Result:** PASS after fixes.

Findings applied:

- Semantic Scholar citations response parsing was too easy to misread. Clarified that request fields must target `citingPaper.*` and implementation must parse `data[].citingPaper`.
- CLI tests needed a stable non-subprocess path. Added `main(argv: Sequence[str] | None = None) -> int` as a required entry point.
- Dataclass JSON output contained datetime values, which `asdict()` alone cannot serialize. Added explicit serialization/deserialization helper requirements.
- `httpx` promotion and artifact ignore rules were in AC prose but not in task checklist. Added them to T2/T4 so they cannot be skipped during implementation.
- Sprint lifecycle wording used `review` while the repo sprint-status definition uses `code-review`. Aligned the story to transition `ready-for-dev -> in-progress -> code-review -> done`.
- Quality gates now spell out the full ruff format target list and allow a documented non-isolated pytest fallback if uv isolated mode cannot resolve workspace path sources.

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Debug Log References

- 2026-05-20 — Started implementation after three story-review rounds; status moved to `in-progress`.
- 2026-05-20 — RED: initial targeted pytest failed because `solver_orchestrator.citation_tracker` did not exist.
- 2026-05-20 — GREEN: implemented tracker module, CLI, config fields, runtime `httpx` dependency, runbook, ignore rules, and 12 tests.
- 2026-05-20 — Local Windows worktree path with Chinese characters prevented uv editable `.pth` from adding package roots to `sys.path`; local validation used explicit `PYTHONPATH`. CI uses `uv sync --all-packages --extra dev` on Linux ASCII paths.
- 2026-05-20 — Full solver-orchestrator regression passed with explicit local `PYTHONPATH`.

### Completion Notes List

- AC1 ✅ — extracted 8 catalog citation targets; duplicate `huangfu2018parallelizing` retained for `highs-lp` and `highs-milp`.
- AC2 ✅ — Semantic Scholar async path uses official Graph API base URL, `citingPaper.*` fields, bounded timeout, optional API key header, 1 RPS default setting, 404 scan note, and 429/5xx/network source failure capture.
- AC3 ✅ — Google Scholar path is import-only CSV/JSON; unknown and malformed rows are reported without aborting.
- AC4 ✅ — deterministic hit identity, URL/source dedup, snapshot load/save, and same-directory atomic state replace implemented.
- AC5 ✅ — Linear-ready payload generation implemented; optional GraphQL `issueCreate` is behind `--create-linear` and fails closed when env is missing.
- AC6 ✅ — CLI emits single-line JSON stdout, concise stderr summary, requested exit codes, JSON report, optional Markdown, and state file.
- AC7 ✅ — Markdown monthly dashboard includes timestamp, counts, new-hit table, failure/unmatched/malformed sections, and payload JSON block.
- AC8 ✅ — runbook documents dry-run, weekly run, Semantic Scholar key, Google Scholar import-only policy, future CronJob, Linear env vars, secret handling, and exit codes.
- AC9 ✅ — 12 focused tests added; no real network and no database.

### File List

**Created:**
- `apps/solver-orchestrator/src/solver_orchestrator/citation_tracker.py`
- `apps/solver-orchestrator/src/solver_orchestrator/citation_tracker_cli.py`
- `apps/solver-orchestrator/src/solver_orchestrator/CITATION_TRACKER.md`
- `apps/solver-orchestrator/tests/test_citation_tracker.py`

**Modified:**
- `.gitignore`
- `.pre-commit-config.yaml`
- `_bmad-output/stories/6-a-3-citation-tracking.md`
- `_bmad-output/stories/sprint-status.yaml`
- `apps/solver-orchestrator/pyproject.toml`
- `apps/solver-orchestrator/src/solver_orchestrator/config.py`
- `scripts/check_licenses.py`
- `uv.lock`

### Change Log

- 2026-05-20 — Implemented Story 6.A.3 citation tracker: catalog target extraction, Semantic Scholar mocked client path, Google Scholar import parser, snapshot diff/state, Linear-ready payloads, CLI, Markdown dashboard, runbook, runtime config/dependency updates, and 12 tests.
- 2026-05-20 — Post-implementation code review fixed four hardening issues: preserve reports before Linear create failure, fail on Linear `success=false`, record invalid Semantic Scholar JSON as source failure, and suppress duplicate "new" hits when a previous Google import later appears from Semantic Scholar with the same normalized URL. Tests expanded from 12 to 17.
- 2026-05-20 — Final sync hardening: replaced the pre-commit license hook shell script with a Windows-safe Python entrypoint so local hook runs do not depend on `/bin/bash`, and kept the license scan placeholder behavior intact.

### Verification

- `uv run --package opticloud-solver-orchestrator --extra dev pytest apps/solver-orchestrator/tests/test_citation_tracker.py -q` with explicit local `PYTHONPATH` — 17 passed.
- `uv run pytest apps/solver-orchestrator/tests/ -q` with explicit local `PYTHONPATH` — 77 passed, 5 existing FastAPI 422 deprecation warnings.
- `uv run ruff check apps/solver-orchestrator/src/solver_orchestrator/citation_tracker.py apps/solver-orchestrator/src/solver_orchestrator/citation_tracker_cli.py apps/solver-orchestrator/tests/test_citation_tracker.py` — passed.
- `uv run ruff format --check apps/solver-orchestrator/src/solver_orchestrator/citation_tracker.py apps/solver-orchestrator/src/solver_orchestrator/citation_tracker_cli.py apps/solver-orchestrator/tests/test_citation_tracker.py` — passed.
- `uv run mypy apps packages` with explicit local `PYTHONPATH` — passed.
- `git diff --check` — passed.
- `uv tool run pre-commit run --files ...` with explicit `PRE_COMMIT_HOME` — passed after replacing the license hook shell entry with a Python script.

### Post-Implementation Code Review

**Result:** PASS after four review patches.

Findings fixed:

- P2 — `--create-linear` attempted Linear issue creation before writing JSON/Markdown artifacts, so a Linear outage could discard the deterministic dry-run payloads. The CLI now writes report artifacts first and writes state only after Linear succeeds.
- P2 — Linear GraphQL HTTP 200 with `issueCreate.success=false` was treated as success. `create_linear_issues()` now validates the GraphQL body and raises `RuntimeError` when the mutation does not succeed.
- P2 — Semantic Scholar HTTP 200 with invalid JSON could crash the run instead of being recorded as a source failure. The client now reports `invalid_json` / `invalid_shape` source failures.
- P3 — Previous Google import hits could be re-reported as new when Semantic Scholar later returned the same paper under a S2 `paperId`. Snapshot diff now compares previous normalized URL signatures across sources.

Verification after review patches:

- `uv run --package opticloud-solver-orchestrator --extra dev pytest apps/solver-orchestrator/tests/test_citation_tracker.py -q` with explicit local `PYTHONPATH` — 17 passed.
- `uv run pytest apps/solver-orchestrator/tests/ -q` with explicit local `PYTHONPATH` — 77 passed.
- `uv run ruff check ...` — passed.
- `uv run ruff format --check ...` — passed.
- `uv run mypy apps packages` with explicit local `PYTHONPATH` — passed.
- `git diff --check` — passed.
