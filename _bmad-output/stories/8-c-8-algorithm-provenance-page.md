---
story_key: 8-c-8-algorithm-provenance-page
epic_num: 8
story_num: C.8
epic_name: Teaching + Provider Routing + Legal + Algorithm Library
status: done
baseline_commit: 9c81242775c7d66e6b1be49c9c822303bfb20892
priority: High
type: Algorithm Provenance detail page
created_by: bmad-create-story
created_at: 2026-06-04
sources:
  - _bmad-output/planning/epics.md (Expert Panel E10 / Story 8.C.8 brief)
  - _bmad-output/stories/2-2-algorithm-details.md
  - _bmad-output/stories/6-a-1-citation-bibtex.md
  - _bmad-output/stories/6-a-5-ip-attribution-tiers.md
  - _bmad-output/stories/8-c-4-algorithm-library-browse.md
  - _bmad-output/stories/8-c-5-algorithm-capability-card.md
  - apps/solver-orchestrator/src/solver_orchestrator/catalog.py
  - apps/solver-orchestrator/src/solver_orchestrator/schemas.py
  - apps/solver-orchestrator/src/solver_orchestrator/routes.py
  - apps/solver-orchestrator/tests/test_algorithm_details.py
  - apps/web/src/lib/api.ts
  - apps/web/src/app/algorithms/[k_algo]/page.tsx
  - apps/web/src/app/algorithms/page.tsx
---

# Story 8.C.8 - Algorithm Provenance 详情页

Status: done

## Story

**作为** 求解器学者、算法评估用户或教学用户，
**我希望** 每个公开算法 SKU 的详情页展示可审计的 Algorithm Provenance 信息，
**从而** 能在同一个页面看清求解器理论、论文引用、配置参数和适用场景，并区分公开 catalog 事实、论文引用、Provider attribution 与尚未实现的运行能力。

## Context

Expert Panel E10 只给出 brief："Algorithm Provenance 详情页 (每 SKU 含求解器理论 + 论文引用 + 配置参数 + 适用场景)"。当前系统已经有公开算法目录和 `/algorithms/[k_algo]` 详情页，详情页已展示 Provider 透明、IP Attribution、代码片段、Citation BibTeX 和 Example input JSON。

Story 6.A.1 已经把论文引用作为 `citation` 字段放入 solver catalog / API / web 详情页；Story 6.A.5 已经把 IP Attribution 作为单独字段展示。8.C.8 不应复制 BibTeX/DOI/URL，也不应把 attribution、benchmark library 或 capability-card 的职责混在一起。最小闭环是：在 catalog 中新增结构化 `provenance` 元数据，API schema 和 web TS 类型镜像该字段，并在现有 `/algorithms/[k_algo]` 页面新增 Algorithm Provenance 区块，引用 `citation` 作为论文单源。

## Scope

1. 扩展 solver catalog 中的算法 provenance 元数据。
   - 在 `apps/solver-orchestrator/src/solver_orchestrator/catalog.py` 增加 TypedDict。
   - 每个现有 catalog row 都填充 provenance，包括当前未公开的 self-developed row；公开 API 仍只返回 publishable rows。
   - Provenance 必须包含 solver theory、catalog-facing configuration parameters、applicable scenarios、limitations 和 citation source marker。
   - Configuration parameters 是公开目录/请求层可解释参数，不是可编辑的 native solver tuning knobs。
   - Provenance 不复制 `k_algo`、`task_type`、`tier`、`status`、`model_version`、`supported_solvers`、`citation` 或 `ip_attribution` 的原始值；这些字段仍由现有 Algorithm 主字段提供，UI 可在 provenance 区块旁引用它们。
2. 扩展 API schema。
   - 在 `apps/solver-orchestrator/src/solver_orchestrator/schemas.py` 增加 Pydantic schema。
   - `AlgorithmSchema.provenance` 默认为 `None` 以保留未来/旧数据兼容，但现有 catalog rows 均应非空。
3. 扩展 web API 类型。
   - 在 `apps/web/src/lib/api.ts` 增加 `AlgorithmProvenance` 类型，并把 `Algorithm.provenance` 镜像为 nullable 字段。
4. 扩展现有 `/algorithms/[k_algo]` 页面。
   - 新增 Algorithm Provenance 区块。
   - 显示求解器理论、配置参数、适用场景、局限性和论文引用摘要。
   - 论文引用摘要只从已有 `algo.citation` 渲染作者/venue/year；BibTeX、DOI 和 citation URL 仍由已有 "引用本算法" 区块负责。
   - 不为未通过 self-audit 的 self-developed algorithm 增加公开页面入口或绕过现有 404。
   - 不新增 route、不修改 `/algorithms` 列表页链接结构、不改 Console nav。
5. 新增 focused tests。
   - Backend catalog/API provenance tests。
   - Web API client and detail page rendering tests。
6. 运行 post-implementation code review、local gates、GitHub sync，并且只在 CI/merge/branch cleanup/local main sync 后用单独状态同步提交标记 `done`。

## Out Of Scope

- 新 route、新 API endpoint、数据库 migration、OpenAPI/generated client、infra/CI workflow 或新服务。
- 修改 `/v1/optimizations`、`/v1/predictions`、billing、routing、fallback、repro voucher、benchmark import 或 Provider Console 行为。
- 新增真实 solver tuning API、自动调参、参数提交表单、运行参数持久化、benchmark 结果、leaderboard、SOTA 声明或论文复现实验结果。
- 复制或重新生成 citation BibTeX、DOI、URL；论文引用单源仍是 `citation` 字段。
- 在 provenance 区块内新增第二个 DOI/BibTeX/出处链接展示；这些仍只在既有 citation 区块展示。
- 修改 `packages/ui` 或引入新的 shared UI 组件；本 story 只扩展现有算法详情页。
- 修改 `/algorithms` 目录页布局、benchmark library 页面或 Console 页面；本 story 不需要新增可发现入口，因为已有算法详情页入口已经存在。
- 新 npm/Python runtime dependency。
- 把未通过 self-audit 的 self-developed algorithm 发布到公开详情页。

## Acceptance Criteria

1. `apps/solver-orchestrator/src/solver_orchestrator/catalog.py` defines typed provenance metadata for algorithms.
2. Every existing catalog row includes non-empty provenance metadata, including rows hidden by self-audit.
3. Public `GET /v1/algorithms` returns `provenance` for every publishable row.
4. Public `GET /v1/algorithms/{k_algo}` returns `provenance` for publishable rows.
5. `GET /v1/algorithms/aqgs-acopf` remains 404 while the internal catalog row may still contain provenance.
6. Provenance includes `theory_zh`, `theory_en`, `configuration_parameters`, `applicable_scenarios_zh`, `limitations_zh`, and `citation_source`.
7. `citation_source` is fixed to `catalog_citation` for current catalog rows, so paper references remain sourced from the existing `citation` field.
8. Provenance metadata does not contain duplicated `bibtex`, `doi`, citation `url`, `provider_id`, `provider_url`, `model_version.version`, `task_type`, `tier`, `status`, or `supported_solvers` values.
9. `configuration_parameters` contains at least three entries per current catalog row.
10. Each configuration parameter has `name`, `value_zh`, `description_zh`, and `source`.
11. Parameter `source` is one of `catalog_field`, `request_schema`, `runtime_policy`, or `documentation`.
12. Parameter names are unique within each algorithm row.
13. `applicable_scenarios_zh` contains at least three entries per current catalog row.
14. `limitations_zh` contains at least two entries per current catalog row.
15. No provenance text contains placeholder markers such as `TBD`, `TODO`, `coming soon`, `待补充`, `unknown`, `N/A`, or `???`.
16. Provenance copy distinguishes exposed catalog/request parameters from unsupported solver tuning or external system integrations.
17. `AlgorithmSchema` mirrors the provenance structure and keeps `provenance` nullable for backwards compatibility.
18. `apps/web/src/lib/api.ts` exposes typed `AlgorithmProvenance`, `AlgorithmProvenanceParameter`, `AlgorithmProvenanceParameterSource`, and nullable `Algorithm.provenance`.
19. `/algorithms/[k_algo]` renders a visible Algorithm Provenance section when `algo.provenance` is present.
20. The section includes solver theory in Chinese and English.
21. The section renders configuration parameters as structured rows/list items, not raw JSON.
22. The section displays parameter source labels for `catalog_field`, `request_schema`, `runtime_policy`, and `documentation`.
23. The section renders applicable scenarios and limitations as separate lists.
24. The section renders only authors/venue/year paper reference summary from `algo.citation` when present.
25. The section clearly says BibTeX/DOI/source links remain in the existing "引用本算法" block and are not duplicated in provenance.
26. If `algo.provenance` is null, the page does not crash and shows a bounded empty-state note.
27. Long parameter names, values, scenarios, limitations, citation summaries, and provider labels wrap without horizontal overflow.
28. The page still preserves existing loading, 404, non-404 error, citation block, IP attribution block, example JSON, and CTA behavior.
29. The implementation introduces no new package dependency and no package/lockfile changes.
30. No files under `apps/auth-service/**`, `apps/billing-service/**`, `apps/capability-registry/**`, migrations, generated OpenAPI, infra manifests, or CI workflows are modified.
31. Backend tests cover catalog completeness, no duplicated base/citation fields, no placeholders, public list/detail provenance, parameter source values, and self-audit hidden row remains unpublished.
32. Web tests cover API type/helper response passthrough, algorithm detail page provenance rendering/null fallback, source-label rendering, and no provenance rendering for hidden self-audit rows through the existing 404 path.
33. Provenance UI introduces no user-editable configuration controls and no run/submit action.
34. No new route, route group, nav link, broad `/algorithms` list-page rewrite, benchmark-library page change, or Console page change is introduced.
35. Local gates pass: targeted solver provenance tests, targeted web API/page tests, full web regression, solver ruff/format, web typecheck, and `git diff --check`.
36. Post-implementation code review is completed and findings are fixed or explicitly documented.
37. GitHub CI passes, PR is merged, remote branch is deleted, local `main` is synced, and only then this story and sprint status are marked `done` through a separate status-sync commit.

## Tasks / Subtasks

- [x] T1: Add catalog and schema provenance contract (AC: 1-18, 29-31)
  - [x] Define TypedDict and Pydantic schemas.
  - [x] Fill every current catalog row with structured provenance.
  - [x] Add backend tests for completeness, no duplication/placeholders, and public API behavior.
  - [x] Add TS API types and a focused `getAlgorithm()` passthrough test.

- [x] T2: Render Algorithm Provenance on detail page (AC: 19-28, 32-33)
  - [x] Add an Algorithm Provenance section to `/algorithms/[k_algo]`.
  - [x] Render theory, parameters, scenarios, limitations and citation summary without raw JSON.
  - [x] Keep existing citation/BibTeX section as the canonical copy surface.
  - [x] Add page tests for present and null provenance paths.

- [ ] T3: Review, gates, and GitHub sync (AC: 35-37)
  - [x] Run local quality gates and fix failures.
  - [x] Run post-implementation code review and fix/document findings.
  - [x] Commit, push, create PR, wait for CI, merge, delete remote branch, and sync local `main`.
  - [x] Mark story and sprint status `done` only after merge/sync through a separate status-sync commit.

## Dev Notes

### Existing Facts

- `/v1/algorithms` and `/v1/algorithms/{k_algo}` both serialize `AlgorithmSchema` directly from `catalog.py`.
- `publishable_catalog_items()` excludes unaudited self-developed algorithms from public list responses.
- `/algorithms/[k_algo]` already renders citation and IP attribution; provenance should be additive and should not remove those sections.
- Existing web page tests can opt into happy-dom with `// @vitest-environment happy-dom`.

### Implementation Guardrails

- Keep provenance static in `catalog.py`; do not create a DB-backed table or service.
- Use `citation_source: "catalog_citation"` rather than duplicating citation fields inside provenance.
- Do not copy base Algorithm field values into provenance metadata. When the page needs provider/task/tier/status/supported solver context, render from the existing top-level `Algorithm` object.
- Use compact, factual copy. Avoid claims that the platform exposes all native solver knobs.
- For parameters, use a fixed `source` label to distinguish `catalog_field`, `request_schema`, `runtime_policy`, and `documentation`. Do not render numeric inputs as editable controls.
- For VRPTW/CP-SAT/forecast rows, distinguish modeling concepts from current request/API support.
- Render lists with semantic `dl`, `ul`, `li`, headings and wrapping utilities.
- Do not add a dependency or broad UI abstraction.
- Keep `/algorithms` list-page behavior unchanged. Existing detail links already make the provenance section discoverable.
- Do not add Playwright/E2E solely for this additive detail-page section; focused happy-dom page tests plus full web regression are sufficient unless implementation changes navigation or routing.

### Suggested Commands

```powershell
uv run --directory apps/solver-orchestrator pytest tests/test_algorithm_provenance.py tests/test_algorithm_details.py -q
uv run --directory apps/solver-orchestrator ruff check src tests/test_algorithm_provenance.py tests/test_algorithm_details.py
uv run --directory apps/solver-orchestrator ruff format --check src tests/test_algorithm_provenance.py tests/test_algorithm_details.py
pnpm --filter @opticloud/web test -- src/lib/api-algorithm-provenance.test.ts "src/app/algorithms/[k_algo]/page.test.tsx"
pnpm --filter @opticloud/web test
pnpm --filter @opticloud/web typecheck
git diff --check
```

## Definition Of Done

- Story file has passed exactly 3 pre-implementation adversarial review rounds and revisions.
- Every current algorithm catalog row has structured provenance metadata.
- Public algorithm list/detail APIs expose provenance for publishable rows.
- `/algorithms/[k_algo]` shows a bounded, non-duplicative Algorithm Provenance section.
- Citation remains single-sourced from the existing `citation` field.
- No backend side-effect path, dependency, package lockfile, migration, generated artifact, infra or CI drift is introduced.
- Post-implementation code review is completed and findings are fixed or explicitly documented.
- Local quality gates and GitHub CI pass.
- Story and sprint status are updated to `done` only after review, gates, CI, merge, branch cleanup, local `main` sync, and separate status-sync closure.

## Story Review Log

### Round 1: Boundary And False-Completion Review

Findings fixed:

- Initial story said configuration parameters without enough qualification, which could be implemented as native solver tuning controls or a parameter submission form. Revised scope, ACs and guardrails to define catalog/request-facing parameters only and to prohibit editable controls/run actions.
- Initial page requirement said paper reference summary from citation but did not explicitly prevent duplicating DOI/BibTeX/source links in the provenance block. Revised scope, out-of-scope and ACs so provenance renders authors/venue/year only; DOI/BibTeX/source links remain in the existing citation section.
- Initial hidden self-developed row requirement could be misread as making `aqgs-acopf` visible because provenance exists internally. Revised scope and web ACs to preserve the existing self-audit 404 path and avoid adding any public entry point for hidden rows.

Status: PASS after fixes.

### Round 2: Data Consistency And Drift Review

Findings fixed:

- Initial story allowed provenance to copy base Algorithm values such as `task_type`, provider id/version, tier, status or supported solvers. That would create drift-prone duplicate sources. Revised scope, ACs and Dev Notes to keep those values single-sourced from existing Algorithm fields and to test that provenance does not duplicate them.
- Initial parameter contract only required `name`, `value_zh` and `description_zh`, which did not encode whether a value came from catalog metadata, request schema, runtime policy or docs. Added required `source` with fixed literals and UI source-label rendering.
- Initial placeholder guard missed common placeholders such as `N/A` and `???`. Expanded the blocked marker set and test expectations.

Status: PASS after fixes.

### Round 3: Dependency, Test Closure, And Discoverability Review

Findings fixed:

- Initial story left room for a new route or list-page/nav work even though the existing detail-page links already provide discovery. Revised scope, out-of-scope, ACs and guardrails to prohibit new routes, nav changes, benchmark-page changes, Console changes and broad `/algorithms` list-page rewrites.
- Initial local gate list only included focused web tests. Because this touches a shared public detail page, revised ACs and commands to include full web regression after focused tests.
- Initial suggested PowerShell command used an unquoted path containing `[k_algo]`, which is easy to mis-handle as a pattern. Revised the command to quote the path.

Status: PASS after fixes. Story is ready for development.

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Debug Log References

- Baseline branch: `codex/8-c-8-algorithm-provenance-page`.
- Story creation analyzed Expert Panel E10, prior Story 2.2 detail page boundaries, Story 6.A.1 citation single-source, Story 6.A.5 IP attribution, Story 8.C.4/8.C.5 benchmark library and CapabilityCard boundaries, current solver catalog/schema/routes, current web API types, and current algorithm detail page.
- 2026-06-04 - Story moved to in-progress after exactly three pre-implementation adversarial review rounds.
- 2026-06-04 - Implemented static algorithm provenance TypedDicts and Pydantic schemas.
- 2026-06-04 - Added structured provenance metadata for all current catalog rows, including internally hidden `aqgs-acopf`.
- 2026-06-04 - Extended web API types with nullable Algorithm Provenance contract.
- 2026-06-04 - Added Algorithm Provenance section to existing `/algorithms/[k_algo]` detail page without adding routes or nav changes.
- 2026-06-04 - Added backend provenance tests and web API/page tests.
- 2026-06-04 - Focused solver tests passed: `uv run --directory apps/solver-orchestrator pytest tests/test_algorithm_provenance.py tests/test_algorithm_details.py -q` -> 19 passed.
- 2026-06-04 - Focused web tests passed: `pnpm --filter @opticloud/web test -- src/lib/api-algorithm-provenance.test.ts "src/app/algorithms/[k_algo]/page.test.tsx"` -> 4 passed.
- 2026-06-04 - Full web regression passed: `pnpm --filter @opticloud/web test` -> 251 passed.
- 2026-06-04 - Web typecheck passed: `pnpm --filter @opticloud/web typecheck`.
- 2026-06-04 - Solver ruff check and format check passed after formatting `catalog.py`.
- 2026-06-04 - Whitespace gate passed: `git diff --check`.
- 2026-06-04 - Diff scope checked: no package/lockfile, generated OpenAPI, migrations, auth-service, billing-service, capability-registry, infra, CI, Console, benchmark page, or broad `/algorithms` list-page changes.
- 2026-06-04 - Post-implementation code review found one patch finding: page tests did not cover the `catalog_field` source-label rendering required by AC 22.
- 2026-06-04 - Review fix applied: expanded page test fixture and assertions to cover the `Catalog` source label; focused web test, typecheck and `git diff --check` passed.
- 2026-06-04 - PR #168 passed GitHub CI: changes, lint, ts-typecheck, e2e, matrix-detect, mypy, solver-orchestrator-test, build-and-sbom (auth-service), error-i18n-validation, and gtm-toolkit-validation passed; unrelated service jobs were skipped by matrix.
- 2026-06-04 - PR #168 squash-merged to `main` at merge commit `d007cf12b15c9a01e2a774f3e9555ff88a4b455b`; remote feature branch deleted; local `main` synced to `origin/main`.
- 2026-06-04 - Story and sprint status marked `done` via separate status-sync commit after merge/sync closure.

### Completion Notes List

- Initial story draft created.
- Round 1 pre-implementation review completed and story revised.
- Round 2 pre-implementation review completed and story revised.
- Round 3 pre-implementation review completed and story revised.
- Story is ready for development.
- Story moved to in-progress after exactly three pre-implementation adversarial review rounds.
- Algorithm Provenance catalog/schema/API/page implementation completed.
- Focused backend and frontend tests pass.
- Full web regression, web typecheck, solver ruff/format and diff check pass locally.
- Post-implementation code review completed; missing `catalog_field` source-label coverage was fixed and verified.
- GitHub CI passed; PR #168 merged; remote branch deleted; local `main` synced.
- Story closed as `done` after merge/sync in this separate status-sync.

### File List

- _bmad-output/stories/8-c-8-algorithm-provenance-page.md
- _bmad-output/stories/sprint-status.yaml
- apps/solver-orchestrator/src/solver_orchestrator/catalog.py
- apps/solver-orchestrator/src/solver_orchestrator/schemas.py
- apps/solver-orchestrator/tests/test_algorithm_provenance.py
- apps/web/src/lib/api.ts
- apps/web/src/lib/api-algorithm-provenance.test.ts
- apps/web/src/app/algorithms/[k_algo]/page.tsx
- apps/web/src/app/algorithms/[k_algo]/page.test.tsx

## Change Log

- 2026-06-04 - Initial story draft created for Algorithm Provenance detail page.
- 2026-06-04 - Round 1 pre-implementation review revised parameter-control, citation-duplication, and hidden self-audit boundaries.
- 2026-06-04 - Round 2 pre-implementation review revised provenance/base-field single-source, parameter source literals, and placeholder guards.
- 2026-06-04 - Round 3 pre-implementation review revised route/nav dependency boundaries, full web regression gate, and quoted PowerShell test path.
- 2026-06-04 - Story status moved to in-progress after pre-implementation review closure.
- 2026-06-04 - Implemented Algorithm Provenance catalog/schema/API/page surface and focused tests; local gates pass.
- 2026-06-04 - Completed post-implementation code review, fixed missing `catalog_field` source-label coverage, and verified focused gates.
- 2026-06-04 - PR #168 passed CI, merged to `main`, branch cleanup and local sync completed; story status moved to `done`.

## Post-Implementation Code Review

### Findings

- [x] [Review][Patch] Page tests covered `request_schema`, `runtime_policy`, and `documentation` source labels but not `catalog_field`, despite AC 22 requiring all four labels to render. Fixed by adding a catalog-field parameter to the page test fixture and asserting the `Catalog` label.

### Outcome

Changes requested internally; finding fixed and focused gates rerun.
