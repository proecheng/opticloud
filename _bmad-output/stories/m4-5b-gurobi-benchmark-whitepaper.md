# Story M4.5b: Gurobi LP Benchmark Whitepaper

Status: done

owner: Marketing / Sales / Founder + Solver Owner

## Story

As a founder-led GTM owner,
I want a machine-checkable 30-LP benchmark evidence package and buyer-safe whitepaper draft comparing OptiCloud's LP workflow with a BYO-license Gurobi reference path,
so that M4.5 commercial conversations can discuss Gurobi migration with auditable methodology instead of unsupported performance claims.

## Acceptance Criteria

1. The benchmark package has a canonical manifest and does not drift from planning sources.
   - Add `tools/gurobi_benchmark/benchmark_manifest.json`.
   - Add `tools/gurobi_benchmark/benchmark_manifest.schema.json` as the schema-style reference for the manifest.
   - The manifest must identify `story_key=m4-5b-gurobi-benchmark-whitepaper`, `stage=M4.5`, `source_gap=E3`, `fixture_count=30`, and `last_updated`.
   - The manifest must list every committed M4.5b benchmark asset by repository-relative path, category, owner, status, claim status, evidence status, source references, required fields, and validation checks.
   - Manifest categories must include `fixture_suite`, `methodology`, `whitepaper`, `evidence_schema`, and `operator_runbook`.
   - Manifest asset paths must exactly match the file structure requirements in this story; no extra benchmark assets may be committed without manifest coverage.
   - Controlled status values must be explicit and shared across docs/manifest: `draft`, `internal_ready`, `evidence_required`, `operator_run_required`, `legal_review_required`, and `published`.
   - Controlled claim/evidence values must distinguish `hypothesis`, `methodology_ready`, `operator_evidence_required`, `gurobi_license_required`, and `verified`.
   - The manifest must explicitly state that no Gurobi solver output, license, token, customer data, or benchmark superiority claim is committed by this story.

2. A deterministic 30-LP fixture suite exists and is safe to run.
   - Add `tools/gurobi_benchmark/lp_fixture_suite.json` containing exactly 30 LP fixtures.
   - Every fixture must include `id`, `category`, `sense`, `objective`, `constraints.A`, `constraints.b`, `bounds.lower`, `bounds.upper`, `expected_status`, `source`, and `notes`.
   - Fixtures must be synthetic and must not include customer names, real operational data, CRM exports, contact details, file uploads, private IDs, random high-entropy tokens, or external URLs.
   - Fixtures must cover at least six categories, including small bounded LP, resource allocation, blending, transportation-style, scheduling-style, and stress-scale synthetic LP.
   - Fixture dimensions must be internally consistent: objective length equals every matrix row width and both bound-vector lengths; RHS length equals row count; all numeric values are finite.
   - Fixture `sense` values must be controlled to `minimize` or `maximize`; fixture `expected_status` values must be controlled to `optimal`, `infeasible`, `unbounded`, `timeout_expected`, or `solver_error_expected`.
   - Each fixture must include a deterministic `expected_highs` summary with status and optional objective tolerance, so the committed suite has an open-source sanity baseline without claiming Gurobi parity.
   - Fixture IDs must be stable, sorted, unique, and use the `lp-###` format from `lp-001` through `lp-030`.
   - The suite must not require Gurobi, gurobipy, a Gurobi license server, databases, Redis, network APIs, Playwright browsers, billing APIs, auth APIs, analytics vendors, or CRM tools.

3. The methodology and operator runbook make comparison evidence reproducible without overclaiming.
   - Add `docs/benchmarks/gurobi-lp-benchmark-methodology.md`.
   - Add `docs/runbooks/gurobi-lp-benchmark.md`.
   - The methodology must define solver identities, BYO Gurobi license boundary, environment capture, warm-up policy, timeout policy, metric definitions, tolerances, result schema, pass/fail interpretation, and evidence retention path.
   - Metrics must include at least solver status parity, objective delta, primal feasibility residual, runtime seconds, timeout/error rate, and unsupported-case notes.
   - The runbook must define the operator steps for producing redacted evidence under `reports/gurobi-benchmark/<run_id>/evidence_manifest.json`.
   - The runbook must forbid committing license files, tokens, machine hostnames, private customer models, contact data, raw solver logs with secrets, screenshots, or unredacted environment dumps.
   - The methodology must explain that Gurobi is a commercial reference path requiring operator-provided licensing, while OptiCloud's committed LP path uses HiGHS through existing solver-orchestrator code.
   - The runbook may describe an offline operator runner contract but must not add a production API endpoint, SaaS workflow, background job, scheduler, container image, or hosted Gurobi integration.

4. The whitepaper draft is buyer-safe and evidence-gated.
   - Add `docs/benchmarks/gurobi-lp-benchmark-whitepaper.md`.
   - The whitepaper must include frontmatter with owner, status, claim status, evidence status, story key, source gap, intended audience, approvals required, and last updated.
   - The whitepaper must summarize the problem, comparison methodology, fixture composition, metrics, result-table structure, interpretation rules, and publication gate.
   - The whitepaper must be marked `evidence_required` unless a future verified evidence manifest is present and validated.
   - The whitepaper must not claim OptiCloud beats, outperforms, matches, is faster than, is cheaper than, or is production-equivalent to Gurobi without verified evidence and legal/marketing approval.
   - The whitepaper may include empty or pending result tables only if cells are explicitly marked `pending_verified_evidence`.
   - The whitepaper must not be linked as a published customer-facing claim from `/pricing` or the M4.5 GTM toolkit until the evidence status becomes verified.
   - The whitepaper must not include price-comparison claims against Gurobi license costs unless sourced to already-approved GTM copy and marked as `commercial_context`, not benchmark evidence.

5. An evidence schema exists for future real benchmark runs.
   - Add `tools/gurobi_benchmark/evidence_manifest.schema.json`.
   - Add `tools/gurobi_benchmark/evidence_manifest.example.json` as an example-only non-result template.
   - The evidence schema must require source story, run id, fixture suite id, environment summary, solver versions, run policy, aggregate metrics, per-fixture results, artifacts, redaction review, operator, and approval status.
   - Real evidence must include exactly 30 per-fixture results matching fixture IDs from the suite.
   - Per-fixture results must include OptiCloud/HiGHS and Gurobi statuses, runtime seconds, objective values or explicit not-available reasons, objective delta, feasibility residuals, and notes.
   - Aggregate metrics must be derived from per-fixture results and include fixture count, comparable count, status parity count, objective tolerance pass count, timeout count, and error count.
   - Real evidence artifact paths must stay under the same `reports/gurobi-benchmark/<run_id>/` directory, must be relative paths, and must not traverse directories or point to URLs.
   - Real evidence must include approval status values controlled to `operator_draft`, `redaction_passed`, `legal_review_required`, or `approved_for_publication`.
   - Example evidence must set `example_only=true`, must not contain real benchmark results, and must not be accepted as real evidence.
   - Real evidence validation must require `example_only=false`, `redaction_reviewed=true`, and no secret-like keys or values.

6. A standalone validator closes data consistency, function drift, boundary, and closure issues.
   - Add `scripts/validate_gurobi_benchmark.py`.
   - The validator must use only the Python standard library.
   - By default, the validator must validate manifest/schema consistency, required asset paths, required frontmatter, 30-fixture count and shape consistency, category coverage, whitepaper evidence gates, methodology/runbook required sections, evidence example structure, CI wiring, and no unsupported claims or sensitive data.
   - The validator must support `--evidence reports/gurobi-benchmark/<run_id>/evidence_manifest.json` to validate future real evidence explicitly.
   - Evidence validation must validate schema and redaction only; it must not execute solvers or recompute benchmark results in CI.
   - The validator must reject missing or extra fixtures, invalid fixture IDs, non-finite numeric values, shape mismatches, missing required metrics, inconsistent aggregate metrics, artifact path traversal, URL artifact paths, example evidence submitted as real, unsupported superiority claims, PII, secret-like keys/values, license/token references, external analytics snippets, CRM/contact exports, live marketing URLs, committed fake Gurobi results, and docs that present pending results as verified.
   - The validator must print one concise success line on pass and actionable error lines on failure.

7. Tests and CI protect the benchmark package from future drift.
   - Add `tests/test_gurobi_benchmark.py`.
   - Tests must start as failing tests before implementation assets exist.
   - Tests must cover committed benchmark validation, exact 30-fixture count, fixture shape/category coverage, manifest asset coverage, CI path-filter coverage, whitepaper claim-boundary rejection, evidence example rejection as real evidence, real-evidence validation path, aggregate metric mismatch rejection, artifact path traversal rejection, and fixture ID drift.
   - Extend `.github/workflows/ci.yml` with a focused `gurobi_benchmark` path filter and validation job.
   - The path filter must include `docs/benchmarks/**`, `docs/runbooks/gurobi-lp-benchmark.md`, `tools/gurobi_benchmark/**`, `scripts/validate_gurobi_benchmark.py`, `tests/test_gurobi_benchmark.py`, and `reports/gurobi-benchmark/**`.
   - CI must run `uv run python scripts/validate_gurobi_benchmark.py` and `uv run pytest tests/test_gurobi_benchmark.py`.
   - CI must validate future evidence manifests only if `reports/gurobi-benchmark/**/evidence_manifest.json` is committed.
   - CI must not call Gurobi, gurobipy, license servers, network APIs, databases, Redis, Playwright browsers, billing APIs, auth APIs, analytics vendors, or CRM tools.

8. The prior M4.5 GTM boundary remains intact.
   - `scripts/validate_gtm_toolkit.py` and `tests/test_gtm_toolkit.py` must still pass.
   - M4.5b assets must not be added under `docs/gtm/` or `docs/customer-faqs/` unless the M4.5 validator is intentionally updated to distinguish completed M4.5b assets from M4.5 scope drift.
   - `docs/enterprise-gtm-toolkit.md` must not be changed to imply the benchmark is published or verified.
   - Pricing page copy must not be changed to introduce benchmark or Gurobi superiority claims.

9. Workflow tracking and closure are explicit.
   - This story records three pre-implementation story review rounds and the fixes made after each round.
   - `_bmad-output/stories/sprint-status.yaml` moves `m4-5b-gurobi-benchmark-whitepaper` to `ready-for-dev` only after all three story review rounds pass.
   - During implementation, move the story through `in-progress`, `code-review`, and `done` only when corresponding gates pass.
   - The final validation gate must include the new validator, new focused pytest, existing GTM validator/tests, ruff check/format for Python files, pre-commit, `git diff --check`, and GitHub CI checks.
   - Final completion must update the Dev Agent Record, file list, validation evidence, post-implementation code review findings/fixes, change log, and sprint status.
   - The story may be marked `done` with the whitepaper still `evidence_required` only if the committed deliverable is explicitly a methodology-ready, evidence-gated package and all validators/tests/CI pass.

## Tasks / Subtasks

- [x] Create canonical M4.5b benchmark manifest and evidence contract. (AC: 1, 5)
  - [x] Add manifest and schema-style reference under `tools/gurobi_benchmark/`.
  - [x] Add evidence manifest schema and example-only evidence template.
- [x] Build deterministic 30-LP fixture suite. (AC: 2)
  - [x] Add exactly 30 synthetic LP fixtures in one suite file.
  - [x] Cover required categories and shape constraints without customer data or secrets.
- [x] Write methodology, runbook, and whitepaper draft. (AC: 3, 4, 8)
  - [x] Add benchmark methodology under `docs/benchmarks/`.
  - [x] Add operator runbook under `docs/runbooks/`.
  - [x] Add buyer-safe whitepaper draft with evidence gates.
- [x] Add validator, tests, and CI wiring. (AC: 6, 7, 8)
  - [x] Add standard-library validator with optional evidence mode.
  - [x] Add focused pytest coverage for positive and negative cases.
  - [x] Add CI path filter and focused validation job.
- [x] Update workflow records and validation evidence. (AC: 9)
  - [x] Move sprint status through BMAD gates.
  - [x] Update Dev Agent Record, File List, Change Log, review notes, and validation commands.

## Dev Notes

### Source Context

- `_bmad-output/planning/epics.md:2080` adds Story M4.5b as quality comparison whitepaper versus Gurobi 30 LP benchmark from source E3.
- `_bmad-output/planning/epics.md:2102` places Story M4.5b in Epic 0 / stage M4.5.
- `_bmad-output/planning/implementation-readiness-report-2026-05-17-v3.md:268` identifies Story M4.5/M4.5b GTM Toolkit + quality comparison Whitepaper as M4.5 important work.
- `_bmad-output/planning/architecture.md:3146` maps Gurobi migration / dual-run comparison to G19.
- `_bmad-output/planning/prd.md:786` states commercial solvers such as Gurobi are only user-provided license paths and are not directly adopted by the platform.
- `_bmad-output/planning/prd.md:797` lists LP/MILP/QP default solvers as HiGHS plus OSQP, with Gurobi only as user-provided license in future/extension paths.
- `docs/enterprise-gtm-toolkit.md` currently marks the 30 LP benchmark whitepaper as M4.5b out of M4.5 scope, so this story must avoid mutating M4.5 GTM assets into unsupported published claims.

### Previous Story Intelligence

- M4.5 established the static-asset + standard-library validator + CI-gate pattern and explicitly rejected benchmark claims inside GTM assets.
- `scripts/validate_gtm_toolkit.py` scans M4.5 manifest assets and rejects M4.5b benchmark scope drift; M4.5b assets should live outside `docs/gtm/` and `docs/customer-faqs/` unless the validator is deliberately updated.
- M3.6e, M3.7, M3.8, and M3.9 established the evidence-contract pattern: committed static plans/examples, optional real evidence under `reports/**`, redaction checks, no live external calls in CI, and explicit no-secret boundaries.
- M3.8 and M3.9 had secret-scan false positives on public hashes. M4.5b should avoid committing SHA-256 digest strings unless they are necessary and added to `.secrets.baseline` or hook excludes.
- Existing `apps/solver-orchestrator/src/solver_orchestrator/solvers.py` uses `highspy` for LP solves and supports `A*x <= b`, lower/upper bounds, minimize/maximize, and timeout options. This story should not modify runtime solver behavior unless required by validation.
- Existing repo has no `gurobipy` dependency. This story must not add it as a dependency or make CI depend on a Gurobi license.

### Architecture / External Constraints

- Use Python 3.12-compatible standard-library validation code for `scripts/validate_gurobi_benchmark.py`.
- Do not add new dependencies.
- Do not add `gurobipy`, Gurobi license configuration, license server calls, or commercial solver runtime integration.
- Do not modify billing, auth, databases, Redis, solver runtime behavior, pricing page copy, CRM, analytics, legal templates, or customer data flows.
- Keep benchmark docs under `docs/benchmarks/`, runbook under `docs/runbooks/`, benchmark contract assets under `tools/gurobi_benchmark/`, validator under `scripts/`, and tests under `tests/`.
- Real operator evidence, if ever committed, must live under `reports/gurobi-benchmark/<run_id>/evidence_manifest.json` and pass explicit evidence validation.
- Do not commit raw solver logs, screenshots, binary whitepapers, PDFs, CRM exports, customer models, private datasets, Gurobi license files, hostnames, usernames, emails, phone numbers, tokens, or API keys.

### File Structure Requirements

- `tools/gurobi_benchmark/benchmark_manifest.json`
- `tools/gurobi_benchmark/benchmark_manifest.schema.json`
- `tools/gurobi_benchmark/lp_fixture_suite.json`
- `tools/gurobi_benchmark/evidence_manifest.schema.json`
- `tools/gurobi_benchmark/evidence_manifest.example.json`
- `docs/benchmarks/gurobi-lp-benchmark-methodology.md`
- `docs/benchmarks/gurobi-lp-benchmark-whitepaper.md`
- `docs/runbooks/gurobi-lp-benchmark.md`
- `scripts/validate_gurobi_benchmark.py`
- `tests/test_gurobi_benchmark.py`
- Update `.github/workflows/ci.yml`
- Update `_bmad-output/stories/sprint-status.yaml`

### Testing / Validation Notes

Expected local commands after implementation:

```bash
uv run python scripts/validate_gurobi_benchmark.py
uv run pytest tests/test_gurobi_benchmark.py -q
uv run python scripts/validate_gtm_toolkit.py
uv run pytest tests/test_gtm_toolkit.py -q
uv run ruff check scripts/validate_gurobi_benchmark.py tests/test_gurobi_benchmark.py
uv run ruff format --check scripts/validate_gurobi_benchmark.py tests/test_gurobi_benchmark.py
uv run pre-commit run --all-files --show-diff-on-failure
git diff --check
```

### Risks / Decisions

- Data consistency risk: the fixture suite, manifest, whitepaper, methodology, evidence schema, and CI filters can drift. The validator must pin counts, paths, fields, and category coverage.
- Function consistency risk: a whitepaper without machine-checkable evidence can become pure marketing. The validator/tests/CI job are required closure.
- Drift risk: this story can accidentally update M4.5 GTM assets in a way that breaks `validate_gtm_toolkit.py` or implies benchmark results are now verified. Keep benchmark assets in separate paths and rerun M4.5 checks.
- Boundary risk: comparison language can imply Gurobi superiority or OptiCloud superiority without evidence. The whitepaper must remain evidence-gated.
- License risk: adding Gurobi runtime integration or `gurobipy` dependency would violate the BYO license boundary and CI constraints.
- Privacy risk: fixture examples can accidentally resemble customer models or contact data. Use synthetic generic fixtures only.
- Secret-scan risk: committed hashes, license-like strings, or tokens can trigger detect-secrets. Avoid high-entropy examples.
- Closure risk: CI path filters can miss future benchmark edits. The CI filter list must mirror every committed benchmark path.

## Story Review Log

### Round 1: Data Consistency Review

Findings fixed:
- Added exact manifest path coverage so committed benchmark assets cannot drift outside the canonical manifest.
- Added controlled fixture `sense` and `expected_status` values so runner/validator/result docs use the same state vocabulary.
- Added committed `expected_highs` summaries to separate open-source fixture sanity checks from future Gurobi parity evidence.
- Added aggregate metric derivation requirements so future evidence cannot report aggregate numbers inconsistent with per-fixture rows.

Status: PASS after fixes.

### Round 2: Function Consistency / Drift Review

Findings fixed:
- Added an explicit no-production-integration boundary so this story cannot drift into hosted Gurobi execution, new APIs, schedulers, containers, or background jobs.
- Clarified that future evidence validation checks schema/redaction only and must not execute solvers inside CI.
- Added price-comparison boundary so benchmark whitepaper content does not turn into unsupported Gurobi cost marketing.
- Reaffirmed the split between committed HiGHS fixture sanity data, future BYO-license Gurobi evidence, and externally publishable claims.

Status: PASS after fixes.

### Round 3: Boundary / Closure Review

Findings fixed:
- Added artifact-path confinement for future real evidence so reports cannot reference URLs or traverse outside the run directory.
- Added controlled approval statuses for future evidence publication flow.
- Expanded validator/test requirements to reject inconsistent aggregate metrics and unsafe artifact paths.
- Clarified completion semantics: this story can close the methodology-ready package while the whitepaper remains `evidence_required`; closing the story must not imply verified benchmark results.

Status: PASS after fixes. Story is ready for development.

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Implementation Notes

- Added canonical M4.5b benchmark manifest and schema-style reference under `tools/gurobi_benchmark/`.
- Added exactly 30 synthetic LP fixtures with stable `lp-001` through `lp-030` IDs and required category coverage.
- Added evidence manifest schema and example-only evidence template for future BYO-license Gurobi operator runs.
- Added methodology, operator runbook, and evidence-gated whitepaper draft under `docs/benchmarks/` and `docs/runbooks/`.
- Added standard-library validator with default package validation and explicit `--evidence` mode for future real evidence.
- Added focused pytest coverage for manifest, fixture, CI, whitepaper claim boundary, evidence validation, aggregate mismatch, artifact traversal, and fixture ID drift.
- Wired focused `gurobi-benchmark-validation` CI job and path filter.
- Confirmed prior M4.5 GTM validator/tests still pass.
- Post-implementation review tightened real-evidence validation so placeholder `not_run` rows cannot pass as real benchmark evidence.
- Post-implementation review added focused HiGHS sanity tests for the committed `expected_highs` baseline and corrected fixture objective baselines to actual HiGHS results.

### File List

Created:
- `_bmad-output/stories/m4-5b-gurobi-benchmark-whitepaper.md`
- `docs/benchmarks/gurobi-lp-benchmark-methodology.md`
- `docs/benchmarks/gurobi-lp-benchmark-whitepaper.md`
- `docs/runbooks/gurobi-lp-benchmark.md`
- `scripts/validate_gurobi_benchmark.py`
- `tests/test_gurobi_benchmark.py`
- `tools/gurobi_benchmark/benchmark_manifest.json`
- `tools/gurobi_benchmark/benchmark_manifest.schema.json`
- `tools/gurobi_benchmark/evidence_manifest.example.json`
- `tools/gurobi_benchmark/evidence_manifest.schema.json`
- `tools/gurobi_benchmark/lp_fixture_suite.json`

Modified:
- `.github/workflows/ci.yml`
- `_bmad-output/stories/sprint-status.yaml`

### Validation Evidence

- `uv run pytest tests/test_gurobi_benchmark.py -q` -> RED before implementation: 9 failed because validator, manifest, fixture suite, evidence assets, and CI path filter did not exist.
- `uv run python scripts/validate_gurobi_benchmark.py` -> PASS (`gurobi benchmark package OK`).
- `uv run pytest tests/test_gurobi_benchmark.py -q` -> PASS (`9 passed`).
- `uv run python scripts/validate_gtm_toolkit.py` -> PASS (`gtm toolkit OK`).
- `uv run pytest tests/test_gtm_toolkit.py -q` -> PASS (`7 passed`).
- `uv run python scripts/validate_gurobi_benchmark.py` -> PASS after code review fixes.
- `uv run pytest tests/test_gurobi_benchmark.py -q` -> PASS (`12 passed`) after code review fixes.
- `uv run python scripts/validate_gtm_toolkit.py` -> PASS after code review fixes.
- `uv run pytest tests/test_gtm_toolkit.py -q` -> PASS (`7 passed`) after code review fixes.
- `uv run ruff check scripts/validate_gurobi_benchmark.py tests/test_gurobi_benchmark.py` -> PASS after formatting.
- `uv run ruff format --check scripts/validate_gurobi_benchmark.py tests/test_gurobi_benchmark.py` -> PASS.
- `uv run pre-commit run --all-files --show-diff-on-failure` -> PASS.
- `git diff --check` -> PASS.

## Senior Developer Review (AI)

Review date: 2026-05-27

Outcome: Approved after fixes

Findings fixed:
- Real evidence validation allowed 30 `not_run` placeholder rows to pass if `example_only=false` and redaction flags were set, which could let an operator draft masquerade as benchmark evidence. Added real-evidence rejection for placeholder statuses and missing runtimes, plus regression coverage.
- The committed `expected_highs` fixture sanity baseline was only shape-checked, so incorrect objectives could drift silently. Added focused pytest coverage that compares all 30 expected HiGHS objectives against the existing solver-orchestrator HiGHS path, then corrected the fixture objective baselines.
- Story task list retained a duplicate unchecked task line after status updates. Removed the stale unchecked line so completion tracking is closed.

Residual risk:
- This story validates a methodology-ready, evidence-gated benchmark package. It does not produce verified Gurobi results, public performance claims, legal approval, or production Gurobi integration.

### Change Log

- 2026-05-27: Initial draft created for M4.5b story context.
- 2026-05-27: Completed Round 1 story review for data consistency and revised manifest, fixture status, HiGHS baseline, and aggregate evidence requirements.
- 2026-05-27: Completed Round 2 story review for function consistency and drift; tightened Gurobi integration, CI execution, and cost-comparison boundaries.
- 2026-05-27: Completed Round 3 story review for boundary and closure; added evidence artifact confinement, approval statuses, aggregate checks, and completion semantics.
- 2026-05-27: Implemented M4.5b benchmark package, evidence-gated docs, validator, tests, and CI job; moved story to code review.
- 2026-05-27: Completed post-implementation code review, fixed real-evidence placeholder acceptance and HiGHS baseline drift coverage, and prepared final validation.
- 2026-05-27: Recorded final local validation evidence and moved story status to done.
