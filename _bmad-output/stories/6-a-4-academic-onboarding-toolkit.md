# Story 6.A.4: Academic Onboarding Toolkit (学界招商工具包)

Status: done

## Story

As a Founder / Academic Relations Lead,
I want a Tier 1 academic onboarding toolkit with an execution-ready handbook, scholar FAQ, Chinese paper template, and co-branded whitepaper outline,
so that I can onboard scholar-Providers with one consistent playbook, reuse the /academic citation surface as proof, and hand collaborators cite-ready materials without inventing a new process for each conversation.

## Acceptance Criteria

1. `docs/academic-provider-handbook.md` is expanded from skeleton into an execution-ready handbook for manual Tier 1 onboarding.
   - It includes a clear onboarding flow: first contact, qualification, technical handoff, legal handoff, launch, and follow-up.
   - It states what the scholar must provide vs what OptiCloud provides.
   - It keeps Tier 1 as the v1 manual path and labels Tier 2 / Tier 3 as roadmap-only.
   - It links to `/academic`, `docs/legal-templates.md` Doc 6, and the companion toolkit docs created by this story.

2. `docs/customer-faqs/academic-onboarding-faq.md` is created as a plain-language scholar-facing FAQ.
   - It answers the common objections from the handbook: what is required, what is optional, how citations work, how IP attribution works, how student data is handled, and how the 5-year reproducibility promise is framed.
   - It reuses the same terms as the handbook and does not introduce new policy language.
   - It frames 5-year reproducibility as a roadmap / contract obligation tied to the existing handbook and legal-template language, not as a currently shipped voucher feature.

3. `docs/academic-paper-template.zh-CN.md` is created as a Chinese paper template.
   - It contains a complete outline: title, abstract, problem statement, method, experiment, result, reproducibility note, citation note, and acknowledgment.
   - It includes a dedicated BibTeX insertion block that tells scholars to paste the canonical keys from Story 6.A.1 verbatim.
   - It is usable as a starting point for a real paper or preprint without requiring repo code changes.

4. `docs/academic-joint-whitepaper-outline.zh-CN.md` is created as a co-branded whitepaper / case-study outline.
   - It covers audience, problem, approach, results, collaboration roles, approval flow, and publish-or-not decision points.
   - It is clearly framed as an outline, not a finished publication.

5. The four docs cross-link each other cleanly.
   - Handbook points to FAQ, paper template, whitepaper outline, /academic, and legal templates.
   - FAQ points back to the handbook and /academic.
   - No broken relative links or dead references are introduced.

6. The toolkit stays aligned with the existing product language.
   - It uses the current terms: Tier 1 manual onboarding, Tier 2 self-service roadmap, Tier 3 partnership roadmap, /academic landing surface, BibTeX citation surface, and 学界合作合同.
   - It does not rename the citation keys, change legal policy text, or imply the portal exists today.

7. No code, schema, API, migration, or UI implementation is added.
   - This story is docs-only.
   - All output lives under `docs/` and the existing story file / sprint tracking updates.

8. Sprint tracking and story record are updated in the same PR.
   - `_bmad-output/stories/sprint-status.yaml` moves `6-a-4-academic-onboarding-toolkit` from `ready-for-dev` / `in-progress` to `done` only after post-implementation review passes.
   - This story file records Dev Agent completion notes, file list, change log, and post-implementation code review.

## Tasks / Subtasks

- [x] Audit the current academic handbooks and legal references for canonical wording. (AC: 1, 6)
  - [x] Reuse the current Tier 1 / Tier 2 / Tier 3 framing instead of inventing new terms.
  - [x] Keep legal wording anchored to `docs/legal-templates.md` instead of drafting new policy text.
- [x] Rewrite `docs/academic-provider-handbook.md` into an execution-ready onboarding handbook. (AC: 1)
  - [x] Add a short index / quick-start at the top.
  - [x] Add a Tier 1 onboarding checklist and owner matrix.
  - [x] Add scholar supply checklist vs OptiCloud supply checklist.
  - [x] Add launch and follow-up steps tied to `/academic`.
- [x] Create `docs/customer-faqs/academic-onboarding-faq.md`. (AC: 2, 5)
  - [x] Create `docs/customer-faqs/` if it does not already exist.
  - [x] Cover the 10-15 questions that a scholar asks during the first call.
  - [x] Keep the tone direct, plain, and externally usable.
- [x] Create `docs/academic-paper-template.zh-CN.md`. (AC: 3)
  - [x] Include the citation / BibTeX insertion block.
  - [x] Include a short reproducibility note and a citation reminder tied to Story 6.A.1.
- [x] Create `docs/academic-joint-whitepaper-outline.zh-CN.md`. (AC: 4)
  - [x] Frame it as an outline for a joint publication or case study.
  - [x] Include co-author roles and publish approval checkpoints.
- [x] Cross-link the toolkit docs and verify all referenced paths. (AC: 5, 6)
  - [x] Ensure the handbook links to the FAQ, paper template, whitepaper outline, /academic, and legal templates.
  - [x] Ensure the FAQ links back to the handbook and /academic.
  - [x] Ensure there are no TODO / TBD / placeholder fragments left behind.
- [x] Update story tracking and Dev Agent Record after implementation. (AC: 8)
  - [x] Set sprint-status lifecycle correctly.
  - [x] Append completion notes, file list, change log, and code review result to this story file.

## Dev Notes

### Context

- This story is the downstream packaging step after 6.A.1 citation fields, 6.A.2 /academic landing page, and 6.A.3 citation tracking.
- The goal is to turn the existing academic surface into a repeatable outbound toolkit for scholar conversations.
- The handbook already exists; the work is to make it operational, not to replace it with a new structure.

### Relevant constraints

- Keep the story docs-only. Do not add code, endpoints, migrations, or new runtime config.
- Do not invent new legal terms. Cross-link existing legal templates instead.
- Do not change citation keys or cite formats. Those are already fixed by 6.A.1 and consumed by 6.A.3.
- Do not present Tier 2 / Tier 3 as live product capabilities; they are roadmap language only.
- Do not imply Story 6.B voucher / rerun capabilities already exist. The 5-year reproducibility language must stay contract/roadmap-framed until the 6.B stories ship.

### Source anchors

- RE2-2 and the story summary: `_bmad-output/planning/epics.md:2060-2104`
- Current handbook skeleton and lifecycle content: `docs/academic-provider-handbook.md:25-45`, `docs/academic-provider-handbook.md:68-145`, `docs/academic-provider-handbook.md:188-234`
- Legal contract and timeline anchors: `docs/legal-templates.md:80-86`, `docs/legal-templates.md:152-178`
- Architecture note that the handbook lives in docs/customer-faqs and may later split out: `_bmad-output/planning/architecture.md:3036`, `_bmad-output/planning/architecture.md:3167`
- Readiness note that 6.A.4 is the M3 marketing milestone: `_bmad-output/planning/implementation-readiness-report-2026-05-17-v3.md:267`, `_bmad-output/planning/implementation-readiness-report-2026-05-17-v3.md:288`
- Kick-off runbook callout for the academic contract handoff: `docs/runbooks/sprint-0-kickoff.md:101`
- Downstream surface context from 6.A.1 and 6.A.2: `_bmad-output/stories/6-a-1-citation-bibtex.md`, `_bmad-output/stories/6-a-2-bibtex-academic-page.md`

### Project Structure Notes

- `docs/academic-provider-handbook.md` is the source of truth for the academic onboarding lifecycle.
- `docs/customer-faqs/` does not exist yet in this worktree and should be created for the FAQ asset.
- Keep the new assets under `docs/` so they are visible to the existing docs workflow and easy to cross-link from the handbook.
- Preserve the current `docs/legal-templates.md` structure; this story only references it.

### Testing / Validation Notes

- This story has no unit or integration test suite.
- Validate with:
  - `rg -n "\[.*\]\(([^)#]+)\)" docs/academic-provider-handbook.md docs/customer-faqs/academic-onboarding-faq.md docs/academic-paper-template.zh-CN.md docs/academic-joint-whitepaper-outline.zh-CN.md` followed by manual path verification for each relative link,
  - `rg -n "TODO|TBD|placeholder|待补|待定" docs/academic-provider-handbook.md docs/customer-faqs/academic-onboarding-faq.md docs/academic-paper-template.zh-CN.md docs/academic-joint-whitepaper-outline.zh-CN.md`,
  - a manual read-through for terminology consistency with `/academic`, `docs/legal-templates.md`, and `docs/academic-provider-handbook.md`.

Do not run the placeholder sweep over this story file while it is still in ready-for-dev state; the Dev Agent Record may legitimately be empty before implementation.

### Risks / Decisions

- The whitepaper artifact must stay an outline, not a fully written publication.
- The paper template should be reusable but not generic enough to lose the OptiCloud branding and citation guidance.
- The FAQ should stay concise and not duplicate the full handbook.
- If content conflicts with future v2 portal work, the handbook wins for v1 and the portal is explicitly marked roadmap-only.
- 5-year reproducibility is a legal / roadmap promise in this toolkit, not evidence of a live rerun endpoint.

## Definition of Done

- All four docs exist and are linked.
- The handbook reads like something a founder or Academic Relations Lead can use in a real scholar call.
- The paper template can be handed to a scholar without further repo editing.
- The whitepaper outline is ready for co-marketing drafting, not just internal planning.
- The repo contains no broken links or placeholder text in the new toolkit docs.
- Sprint status and this story's Dev Agent Record are updated in the implementation PR.

## Story Review Log

### Round 1: BMad Checklist Review

Findings fixed:
- Added explicit sprint-status / Dev Agent Record acceptance criteria so implementation does not skip tracking.
- Made link and placeholder verification concrete enough to run locally.

Status: PASS after fixes.

### Round 2: Cross-Functional Review

Findings fixed:
- Clarified that the FAQ may discuss 5-year reproducibility only as existing handbook / legal-template language, not as a shipped Story 6.B voucher or rerun feature.

Status: PASS after fixes.

### Round 3: Dev-Readiness Review

Findings fixed:
- Added an explicit instruction to create `docs/customer-faqs/` because it does not exist in the current worktree.
- Scoped the placeholder sweep to deliverable docs only so the pre-implementation Dev Agent Record does not create a false failure.

Status: PASS after fixes. Story is ready for implementation.

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Implementation Plan

Executed the story as a docs-only package:

1. Audited `docs/academic-provider-handbook.md`, `docs/legal-templates.md`, Epic RE2-2, and the 6.A.1-6.A.3 story context.
2. Rewrote the handbook into a Tier 1 execution manual while preserving Tier 2 / Tier 3 as roadmap language.
3. Added the scholar-facing FAQ under `docs/customer-faqs/`.
4. Added the Chinese paper template with a BibTeX insertion block and reproducibility note.
5. Added the co-branded whitepaper outline with approval and publish / hold checkpoints.
6. Verified cross-links and placeholder terms across the deliverable docs.

### Debug Log References

- 2026-05-20 — Merged `codex/6-a-3-citation-tracking` into this branch before implementation so sprint-status order reflects 6.A.3 done before 6.A.4.
- 2026-05-20 — PowerShell shell wrapper parsed `|` in a quoted `rg` pattern as a command separator. Validation was rerun by splitting placeholder checks into separate `rg` calls.

### Completion Notes List

- AC1 satisfied: handbook now includes Tier 1 onboarding flow, first-call script, owner matrix, scholar / OptiCloud supply checklists, and /academic launch steps.
- AC2 satisfied: scholar FAQ covers 15 questions, including citation, IP attribution, student data, classroom roadmap, and 5-year reproducibility as contract / roadmap language only.
- AC3 satisfied: Chinese paper template includes title, abstract, method, experiment, result, reproducibility note, citation note, BibTeX block, and appendices.
- AC4 satisfied: joint whitepaper outline includes audience, problem, collaboration roles, result structure, attribution, approval flow, and publish / hold decision points.
- AC5 / AC6 satisfied: docs cross-link each other and keep existing Tier / citation / legal terminology.
- AC7 satisfied: docs-only change; no code, schema, API, migration, dependency, or UI surface added.
- AC8 satisfied: sprint-status is marked `done` after post-implementation review passed.

Verification:
- `rg -n TODO -- docs/academic-provider-handbook.md docs/customer-faqs/academic-onboarding-faq.md docs/academic-paper-template.zh-CN.md docs/academic-joint-whitepaper-outline.zh-CN.md` — no matches
- `rg -n TBD -- ...` — no matches
- `rg -n placeholder -- ...` — no matches
- `rg -n 待补 -- ...` — no matches
- `rg -n 待定 -- ...` — no matches
- Link references inspected with `rg -n '\\]\\(' -- ...`; all relative docs paths resolve in the current tree.
- `git diff --check` — pass after trailing-whitespace review patch

### File List

Created:
- `docs/customer-faqs/academic-onboarding-faq.md`
- `docs/academic-paper-template.zh-CN.md`
- `docs/academic-joint-whitepaper-outline.zh-CN.md`
- `_bmad-output/stories/6-a-4-academic-onboarding-toolkit.md`

Modified:
- `docs/academic-provider-handbook.md`
- `_bmad-output/stories/sprint-status.yaml`

### Change Log

- 2026-05-20 — Created Story 6.A.4 context and completed 3 story-review rounds before implementation.
- 2026-05-20 — Implemented Academic Onboarding Toolkit docs: execution-ready handbook, scholar FAQ, Chinese paper template, and joint whitepaper outline.
- 2026-05-20 — Post-implementation review completed; fixed handbook trailing whitespace and marked sprint-status done.

### Post-Implementation Code Review

Result: PASS after one docs hygiene patch.

Findings fixed:
- P3 — `docs/academic-provider-handbook.md` blockquote header used Markdown hard-break trailing spaces. `git diff --check` failed. Replaced hard-break spaces with `<br>` tags.

Verification:
- `git diff --check` — pass
- `rg -n TODO -- docs/academic-provider-handbook.md docs/customer-faqs/academic-onboarding-faq.md docs/academic-paper-template.zh-CN.md docs/academic-joint-whitepaper-outline.zh-CN.md` — no matches
- `rg -n TBD -- ...` — no matches
- `rg -n placeholder -- ...` — no matches
- `rg -n 待补 -- ...` — no matches
- `rg -n 待定 -- ...` — no matches
- Relative markdown link resolver — all links resolve
