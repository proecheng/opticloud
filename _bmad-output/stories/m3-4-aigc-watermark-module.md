# Story M3.4: AIGC 水印 module + 双测试集

Status: done

## Story

As an NFR-C / Security owner,
I want a single shared Python AIGC filter and watermark module with deterministic red-team and benign test suites,
so that all future user-visible NL outputs can pass through one compliance boundary and carry verifiable AIGC disclosure metadata.

## Acceptance Criteria

1. AIGC filter module has one physical implementation location.
   - Add a Python package under `packages/shared-py` for the AIGC filter/watermark module.
   - Provide import compatibility for `aigc_filter.filter(text, tier="strict"|"loose")`.
   - Re-export the module from `opticloud_shared` so existing shared-py import style stays discoverable.
   - Do not implement duplicate filters in `chat-service`, `critic-service`, web, or service-local utilities.

2. Filter result contract is deterministic and future-callable.
   - `filter(...)` returns a typed result object with at least: filtered text, `blocked`, `reason_codes`, `tier`, `trace_id`, `aria_label`, and watermark metadata.
   - The result distinguishes allowed content from blocked/replaced content without returning unsafe blocked text to callers.
   - Strict tier is at least as restrictive as loose tier.
   - Invalid tier values fail fast with a typed exception or `ValueError`.
   - No network or LLM call is required in this story; Layer 2 is represented by a deterministic local policy boundary that can be replaced behind the same API in later stories.

3. Watermark is visible, accessible, and machine-detectable.
   - Allowed outputs include a text tail marker equivalent to "本回答由 AI 生成，仅供参考".
   - Results expose `aria_label="本回答由 AI 生成，仅供参考"` for UI callers.
   - Outputs include zero-width Unicode metadata containing at least `trace_id`, module version, and provider/service marker.
   - Add a detector API that identifies module-created watermarks and extracts `trace_id`.
   - Detector recognizes 100% of module-created zero-width metadata in tests.

4. Self-loop prevention metadata is modeled.
   - Provide a constant or helper for the internal scope value `aigc-filter-self-loop`.
   - The module exposes a way to tell whether a call context is internal/self-loop bypass context.
   - This story must not add real internal tokens, service-account secrets, DeepSeek calls, or outbound HTTP.
   - Bypass metadata must be auditable in return metadata or helper output; it must not silently skip watermarking for user-visible outputs.

5. Red-team and benign test sets enforce minimum quality gates.
   - Add repo-level `tests/aigc/test_filter.py`.
   - Red-team set contains at least 200 deterministic prompts and must have block rate >= 98%.
   - Benign set contains at least 100 deterministic prompts and must have false positive rate <= 2%.
   - Tests assert strict/loose behavior, invalid tier handling, and no leakage of blocked source text.

6. Watermark tests and dashboard-ready metrics exist.
   - Add `tests/aigc/test_watermark.py`.
   - Tests cover visible marker, aria label, zero-width metadata extraction, idempotent watermarking, and tamper/missing cases.
   - Add a lightweight metrics/report command or helper that emits FP/FN rates for the deterministic test sets in JSON or Markdown form.
   - The report is a data contract for the future public quarterly dashboard; this story does not build public UI.

7. CI and workflow tracking are updated.
   - Wire a lightweight CI job for `tests/aigc`.
   - CI must run without network, external LLM credentials, database, Docker daemon, or AIGC filing secrets.
   - Update `_bmad-output/stories/sprint-status.yaml` through `ready-for-dev`, `in-progress`, `code-review`, and `done` only when corresponding gates pass.
   - Record three pre-implementation story review rounds and fixes before implementation.

## Tasks / Subtasks

- [x] Add shared AIGC filter package. (AC: 1, 2, 4)
  - [x] Add top-level `packages/shared-py/aigc_filter/` package and include it in shared-py build config.
  - [x] Implement `filter(text, tier="strict")` with a typed result object and deterministic local policy rules.
  - [x] Add strict/loose tier validation and blocked-content replacement behavior.
  - [x] Re-export/import-wire through `opticloud_shared`.
- [x] Add watermark encoder/detector. (AC: 3, 4)
  - [x] Append visible text disclosure for user-visible outputs.
  - [x] Encode zero-width metadata with trace id, module version, and service marker.
  - [x] Add detector API for zero-width metadata extraction.
  - [x] Add self-loop scope constant/helper without adding secrets or outbound calls.
- [x] Add deterministic quality gates. (AC: 5, 6)
  - [x] Add 200+ red-team prompt set and 100+ benign prompt set.
  - [x] Add `tests/aigc/test_filter.py` for block-rate, false-positive-rate, tier, and blocked-text leakage coverage.
  - [x] Add `tests/aigc/test_watermark.py` for visible, aria, zero-width, idempotency, and tamper coverage.
  - [x] Add JSON/Markdown report helper for FP/FN dashboard data.
- [x] Wire CI and validation. (AC: 7)
  - [x] Add path filter output for AIGC filter/test changes.
  - [x] Add lightweight CI job running `tests/aigc`.
  - [x] Keep unrelated service jobs unchanged.
- [x] Update workflow records and validation evidence. (AC: 1-7)
  - [x] Move sprint status to `in-progress` during implementation, then through `code-review` to `done`.
  - [x] Update Dev Agent Record, File List, Change Log, and post-implementation code review notes.
  - [x] Run focused pytest, shared-py pytest, ruff, mypy/pre-commit where applicable, and `git diff --check`.

## Dev Notes

### Context

- Epic M3.4 closes G12 and A2 by making AIGC watermark/filter a physical single shared module. Epic 4.B and 8.B are later callers and must not reimplement the module.
- Architecture Q2 chooses shared-py AIGC filter as the single package used by chat-service and critic-service before user-visible NL output.
- Architecture P34 defines three layers: immediate local policy, later paragraph/LLM policy, and content watermarking. This story implements the deterministic local boundary and watermark API without real LLM calls.
- Architecture P62 requires self-loop prevention for future internal filter LLM calls. This story models the scope constant/helper but must not add tokens or outbound network.
- PRD marks AIGC content identification as required from M3. CAC's 2025 AIGC content marking rules distinguish visible explicit labels and hidden/metadata labels; for this text-only module, implement a visible text label plus zero-width metadata and keep file-metadata standards as a future export/download concern.

### Scope Decision

- This story ships a reusable library and deterministic tests. It does not wire Chat/Critic endpoints, SSE chunking, public dashboard UI, filing workflow, or GB metadata export handling.
- Layer 2 is intentionally a local deterministic policy stub in this story. Future M3.4b / Epic 8.B work can add contract tests and service callers without changing the public result shape.
- The metrics/report helper is dashboard-ready evidence, not the public quarterly dashboard itself.

### Architecture / External Constraints

- Use Python 3.12-compatible code and the repo's strict mypy/ruff conventions.
- Avoid new third-party dependencies; use stdlib plus existing pydantic only if it materially improves typed result stability.
- The top-level import must be `aigc_filter` because epics and architecture use that API shape. Also make `opticloud_shared.aigc_filter` discoverable for shared-py users.
- CI must stay offline and deterministic. Do not call DeepSeek/Qwen/OpenAI, do not require credentials, and do not add HTTP clients.
- Do not encode secrets in watermark metadata. `trace_id` and module/provider marker are enough for this story.

### Project Structure Notes

- Place module code under `packages/shared-py/aigc_filter/`.
- Update `packages/shared-py/pyproject.toml` build packages to include the new top-level package.
- Update `packages/shared-py/opticloud_shared/__init__.py` for discoverability.
- Place tests under repo-level `tests/aigc/` to match epic validated outcome.
- Place optional metrics helper under `scripts/` or expose a test helper if no script is needed.

### Testing / Validation Notes

- Expected local commands:
  - `uv run pytest tests/aigc -q`
  - `uv run pytest packages/shared-py/tests/ -q`
  - `uv run ruff check packages/shared-py/aigc_filter tests/aigc`
  - `uv run mypy packages/shared-py`
  - `uv run pre-commit run --all-files --show-diff-on-failure`
  - `git diff --check`

### Risks / Decisions

- Data consistency risk: zero-width metadata may be appended multiple times or lose trace IDs. Detector/idempotency tests must cover this.
- Function consistency risk: callers could treat blocked results as safe text while still logging or displaying the raw prompt. Result object and tests must ensure blocked source text is not returned as output.
- Drift risk: future services may add local filters. This story should document single-package ownership and CI path for the shared package.
- Boundary risk: implementing a real LLM moderation client would introduce network, token, and self-loop complexity too early. Keep it out.
- Closure risk: red-team/benign tests can become vanity if prompts are too narrow. Use varied deterministic templates and assert the exact gate counts/rates.

### References

- `_bmad-output/planning/epics.md:1126` — Story M3.4 requirements and quality gates.
- `_bmad-output/planning/architecture.md:552` — Q2 shared-py AIGC filter single package decision.
- `_bmad-output/planning/architecture.md:961` — P34 AIGC Filter exit barrier and layers.
- `_bmad-output/planning/architecture.md:2041` — P62 self-loop prevention.
- `_bmad-output/planning/ux-design-specification.md:3406` — AIGC watermark aria-label and zero-width metadata.
- CAC: `https://www.cac.gov.cn/2025-03/14/c_1743654684782215.htm` — AIGC generated/synthetic content marking measures, effective 2025-09-01.
- CAC: `https://www.cac.gov.cn/2025-03/14/c_1743654685896173.htm` — official Q&A on explicit and implicit marking.
- `_bmad-output/stories/m3-3b-docker-compose-blue-green.md` — previous workflow pattern with story review log and validation evidence.

## Story Review Log

### Round 1: Data Consistency Review

Findings fixed:
- Added exact package/import expectations so `packages/shared-py/aigc_filter` and `aigc_filter.filter(...)` do not diverge from Python package naming constraints.
- Added concrete result fields and watermark metadata fields to avoid an under-specified API.
- Added explicit red-team/benign sample counts and rate gates from the epic.
- Added CAC explicit/implicit marking context and scoped file metadata to later export/download work.

Status: PASS after fixes.

### Round 2: Function Consistency / Drift Review

Findings fixed:
- Clarified that Layer 2 is a deterministic local boundary in this story, not a live LLM call.
- Added strict >= loose behavior and invalid tier fail-fast requirements.
- Added self-loop scope helper requirement without implementing secrets or bypassing watermarking.
- Added explicit no service-local duplicate filter boundary for Chat/Critic/Web.

Status: PASS after fixes.

### Round 3: Boundary / Closure Review

Findings fixed:
- Added CI path-filter/job requirement for `tests/aigc`.
- Added dashboard-ready metrics/report helper while explicitly excluding public dashboard UI.
- Added idempotency, tamper/missing detector, and blocked-text leakage tests.
- Added validation commands and story workflow tracking gates.

Status: PASS after fixes. Story is ready for development.

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Implementation Plan

1. Add top-level `aigc_filter` package and shared-py export wiring.
2. Implement deterministic filter result, policy tiers, self-loop metadata helper, watermark encoder, and detector.
3. Add deterministic red-team/benign quality gate tests and watermark tests.
4. Add dashboard-ready metrics/report command and CI job.
5. Run validation, perform post-implementation code review, patch findings, and move the story through workflow states.

### Debug Log References

- 2026-05-26 — Created Story M3.4 after PR #59 merged, all open historical PRs were closed, and `HEAD` matched `origin/main`.
- 2026-05-26 — Completed three pre-implementation story review rounds before implementation; sprint status moved to ready-for-dev.
- 2026-05-26 — Started implementation; sprint status moved to in-progress.
- 2026-05-26 — Added top-level `aigc_filter` module with deterministic policy tiers, typed result contract, self-loop helper, and watermark encoder/detector.
- 2026-05-26 — Added 200 red-team prompts, 100 benign prompts, focused filter/watermark tests, metrics report helper, and CI validation job.
- 2026-05-26 — Validation passed: `uv run pytest tests/aigc -q` (12 passed).
- 2026-05-26 — Validation passed: `uv run pytest packages/shared-py/tests/ -q` (32 passed).
- 2026-05-26 — Validation passed: `uv run ruff check packages/shared-py/aigc_filter tests/aigc scripts/report_aigc_filter_metrics.py`.
- 2026-05-26 — Validation passed: `uv run mypy packages/shared-py`.
- 2026-05-26 — Validation passed: `uv run pre-commit run check-yaml --files .github/workflows/ci.yml`.
- 2026-05-26 — Validation passed: `git diff --check`.
- 2026-05-26 — Post-implementation code review found and fixed two issues: unsafe already-watermarked blocked text retention, and duplicate prompt datasets in metrics script.
- 2026-05-26 — Validation passed after review patches: `uv run pytest tests/aigc -q` (13 passed).
- 2026-05-26 — Validation passed: `uv run pre-commit run --all-files --show-diff-on-failure`.

### Completion Notes List

- Added shared-py top-level `aigc_filter` package with `filter(...)`, typed result dataclasses, strict/loose deterministic local policy rules, invalid-tier validation, blocked-text replacement, and explicit self-loop scope helper.
- Added visible AIGC disclosure marker, stable aria label, zero-width JSON metadata encoding, watermark detector, idempotent watermarking behavior, and 100% detector coverage for module-created outputs.
- Added deterministic `tests/aigc` quality gates with 200 red-team prompts and 100 benign prompts; current report shows red-team block rate 1.0 and benign false-positive rate 0.0.
- Added `scripts/report_aigc_filter_metrics.py` and a lightweight CI validation job that runs offline with `PYTHONPATH=packages/shared-py`.

### Post-Implementation Code Review (AI)

Outcome: PASS after fixes.

Findings fixed:
- Already-watermarked unsafe input could preserve original unsafe text while marking the result blocked. Fixed by replacing blocked output with the safe blocked message even when the input already contains module watermark metadata, while preserving the existing trace id.
- The metrics report script duplicated the red-team/benign prompt data, creating dataset drift risk. Fixed by importing the canonical prompt sets from `tests/aigc/datasets.py` after adding the repo root to `sys.path`.

Residual risk:
- The filter policy is intentionally deterministic and local for M3.4. It is not a substitute for the later Layer 2 LLM moderation client or service-level exit-barrier integration.

### File List

- `_bmad-output/stories/m3-4-aigc-watermark-module.md`
- `_bmad-output/stories/sprint-status.yaml`
- `.github/workflows/ci.yml`
- `packages/shared-py/aigc_filter/__init__.py`
- `packages/shared-py/opticloud_shared/__init__.py`
- `packages/shared-py/pyproject.toml`
- `scripts/report_aigc_filter_metrics.py`
- `tests/aigc/__init__.py`
- `tests/aigc/conftest.py`
- `tests/aigc/datasets.py`
- `tests/aigc/test_filter.py`
- `tests/aigc/test_watermark.py`

### Change Log

- 2026-05-26 — Created Story M3.4 and completed three story review rounds before implementation.
- 2026-05-26 — Started implementation and moved story to in-progress.
- 2026-05-26 — Added AIGC filter/watermark module, deterministic quality gates, metrics report helper, and CI validation job.
- 2026-05-26 — Completed post-implementation code review and patched unsafe already-watermarked blocked output plus metrics dataset drift.
- 2026-05-26 — Marked story done after AIGC tests, shared-py tests, ruff, mypy, YAML check, pre-commit, and diff-check passed.
