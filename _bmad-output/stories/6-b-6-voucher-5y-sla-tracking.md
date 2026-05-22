# Story 6.B.6: Image 5y SLA Start Point

Status: done

## Story

As a voucher holder and academic partner,
I want the 5-year reproducibility and image archival SLA to start from `reproduction_vouchers.created_at` in UTC,
so that the contract language, recovery SOP, and user-facing docs all honor the same clock.

## Acceptance Criteria

1. `reproduction_vouchers.created_at` in UTC is the only documented start point for the 5-year SLA.
   - All user-facing references to 5-year reproducibility / image archival must anchor to the voucher row creation timestamp.
   - For an original voucher, the clock starts at that voucher's own `created_at`.
   - For a rerun child voucher, the child voucher gets its own 5-year clock from the child row's `created_at`, while the parent voucher's archival promise is not extended or reset.
   - The wording must not imply that provider handover, archive promotion, restore execution, or legal reassignment resets any existing voucher clock.
   - The docs must distinguish this archival clock from the separate 5-year rerun eligibility window already defined in Story 6.B.3.
   - UI wording may say `voucher.created_at` only when the surrounding text makes clear it refers to the durable `reproduction_vouchers.created_at` row, not a fixture or client-local timestamp.
   - Existing code paths for voucher issuance and rerun are unchanged; this story only updates documentation and operational guidance.

2. A recovery SOP exists for the archive path.
   - Create `docs/runbooks/repro-image-restore.md`.
   - The SOP documents the restore inputs, clock source, restore decision tree, validation steps, and escalation path.
   - It must reference the voucher ID, `reproduction_vouchers.created_at`, algorithm SKU, archived image identifiers, and the G7 dependency.
   - It must document the evidence output for a successful restore and the incident / exception record required when restore is unavailable.
   - It must include a quarterly drill checklist aligned with the existing runbooks practice.
   - It must make clear that the SOP is the contract reference for the archive path, not proof that the full G7 pipeline has already shipped.

3. The academic and legal-facing docs use the same clock language.
   - Update `docs/academic-provider-handbook.md` so the 5-year honor language explicitly says the clock starts at `reproduction_vouchers.created_at` (UTC).
   - Update `docs/customer-faqs/academic-onboarding-faq.md` so the 5-year reproducibility answer uses the same clock and points to the restore SOP.
   - Update `docs/academic-paper-template.zh-CN.md` and `docs/academic-joint-whitepaper-outline.zh-CN.md` so they do not describe the promise as future-only without naming the voucher clock.
   - Update `docs/legal-templates.md` so the 5-year honor clause is discoverable in the existing academic provider contract track and links to the restore SOP.
   - Update `docs/runbooks/README.md` if needed so the existing `repro-image-restore.md` entry resolves and uses the same clock wording.
   - Do not mislabel the unrelated data-export consent template as the 5-year SLA document.

4. Scope stays docs-only.
   - Do not change schema, API, UI, billing, rerun, archival job code, or any other runtime behavior.
   - Do not add a new service, endpoint, or migration.
   - Do not change the 5-year rerun window logic from Story 6.B.3.

5. Verification is documentation-level only.
   - Cross-links resolve after the new SOP file is added.
   - The updated docs use the same wording for the archival clock and do not contradict each other.
   - No broken relative paths or stale future-only phrasing remains in the touched docs.
   - `_bmad-output/stories/sprint-status.yaml` records this story as `ready-for-dev` only after all three story review rounds pass.

## Tasks / Subtasks

- [x] Create the archive restore SOP. (AC: 2)
  - [x] Add `docs/runbooks/repro-image-restore.md`.
  - [x] Include scope, trigger conditions, required inputs, restore steps, validation, and escalation.
  - [x] State clearly that the archival clock starts at `reproduction_vouchers.created_at` in UTC.
  - [x] Document successful restore evidence and unavailable-restore exception records.
  - [x] Add a quarterly drill checklist.
  - [x] Link the SOP back to the handbook, FAQ, and legal templates index.
- [x] Align the academic and legal docs. (AC: 1, 3)
  - [x] Update `docs/academic-provider-handbook.md`.
  - [x] Update `docs/customer-faqs/academic-onboarding-faq.md`.
  - [x] Update `docs/academic-paper-template.zh-CN.md`.
  - [x] Update `docs/academic-joint-whitepaper-outline.zh-CN.md`.
  - [x] Update `docs/legal-templates.md` without confusing Doc 7 with the archive honor clause.
  - [x] Update `docs/runbooks/README.md` if wording or link text needs alignment.
- [x] Verify links and wording. (AC: 5)
  - [x] Check that relative links resolve after the new SOP file exists.
  - [x] Check for stale wording that still treats 5-year reproducibility as future-only.
  - [x] Run `git diff --check`.
- [x] Update story tracking and records. (AC: 1-5)
  - [x] Move sprint status to `ready-for-dev` after the three story review rounds pass, then to `in-progress` during implementation and `done` after review passes.
  - [x] Append completion notes, file list, change log, and review notes to this story file.

## Dev Notes

### Context

- Story 6.B.3 already defined the separate 5-year rerun eligibility window off the original voucher `created_at` timestamp.
- Story 6.B.5 intentionally softened the card copy to "based on voucher creation time" so this story could make the SLA start point explicit without changing behavior.
- The current handbook and FAQ still describe 5-year reproducibility / image archival as a contract or roadmap promise; this story makes the clock source explicit and points readers to the archive restore SOP.
- `docs/runbooks/README.md` already references `runbooks/repro-image-restore.md`; the file does not exist yet, so the link is currently broken.

### Scope Decision

- Treat this as a docs-and-guidance story, not a runtime feature.
- Keep the distinction between the rerun eligibility clock from Story 6.B.3 and the archive/SLA wording here.
- Use `reproduction_vouchers.created_at` as the canonical phrase in operational and legal docs; do not substitute `completed_at`, rerun time, archive transition time, provider exit time, or page fixture timestamps.
- Keep customer-facing copy readable by explaining it as "the voucher creation time recorded in the durable voucher row" when raw table names would be too internal.
- Do not invent a live archive pipeline or claim G7 is already deployed. The SOP should read as the operational contract for the eventual archive path.
- Do not create a new legal template family; update the existing template index language and keep Doc 7 separate.

### Relevant Source Anchors

- Epic requirement: `_bmad-output/planning/epics.md` around `Story 6.B.6: Image 5y SLA 起算点`
- TT4 dependency note: `_bmad-output/planning/epics.md` near `TT4`
- G7 architecture gap: `_bmad-output/planning/architecture.md` near `G7` and `Repro 5y SLA Engineering`
- Current handbook language: `docs/academic-provider-handbook.md`
- Current FAQ language: `docs/customer-faqs/academic-onboarding-faq.md`
- Current academic paper template: `docs/academic-paper-template.zh-CN.md`
- Current whitepaper outline: `docs/academic-joint-whitepaper-outline.zh-CN.md`
- Current legal template index: `docs/legal-templates.md`
- Current runbooks index: `docs/runbooks/README.md`

### Project Structure Notes

- `docs/runbooks/` is the correct home for the new SOP file.
- `docs/legal-templates.md` remains the index / ownership map; it is not the actual academic-provider agreement text.
- Keep the wording tight and consistent across the docs; this story succeeds by removing ambiguity, not by adding a new policy layer.

### Testing / Validation Notes

- Use text-only verification on deliverable docs:
  - `rg -n "reproduction_vouchers.created_at|voucher.created_at|repro-image-restore|5-year reproducibility|image archival" docs _bmad-output/stories/6-b-6-voucher-5y-sla-tracking.md -S`
  - `rg -n "Doc 7|data export consent|5y Image|5-year" docs/legal-templates.md docs/academic-provider-handbook.md docs/customer-faqs/academic-onboarding-faq.md docs/academic-paper-template.zh-CN.md docs/academic-joint-whitepaper-outline.zh-CN.md -S`
  - `git diff --check`
- Manual review should confirm the new SOP and the updated docs all use the same clock source and do not contradict Story 6.B.3.

### Risks / Decisions

- The biggest risk is leaving the archive clock implicit, which would let future stories or handbook edits drift back to vague "5-year promise" wording.
- The second risk is confusing the archive clock with the rerun eligibility clock from Story 6.B.3; they are related but not the same contract statement.
- Another risk is pointing readers to Doc 7 by mistake when the 5-year honor language belongs on the academic provider contract track; keep the legal template index precise.

## Story Review Log

### Round 1: Requirements Completeness Review

Findings fixed:
- Added original-voucher vs rerun-child clock semantics so child vouchers get their own clock without resetting parent promises.
- Added restore evidence, unavailable-restore exception records, and quarterly drill checklist requirements for the SOP.
- Added `docs/runbooks/README.md` as an explicit update target because it already points to the missing SOP.

Status: PASS after fixes.

### Round 2: Architecture / Testability Review

Findings fixed:
- Replaced the ambiguous `voucher.created_at` source with the durable database field `reproduction_vouchers.created_at` for operational and legal wording.
- Added a guard that UI/customer copy may simplify the wording only if it still points back to the durable voucher row.
- Narrowed validation commands to deliverable docs plus this story so historical planning files do not create false positives.

Status: PASS after fixes.

### Round 3: Acceptance / Scope Audit

Findings fixed:
- Corrected the implementation plan and workflow wording to use `reproduction_vouchers.created_at`, not the earlier shorthand.
- Added an explicit sprint-status gate: `ready-for-dev` is only set after the three story review rounds pass.

Status: PASS after fixes. Story is ready for development.

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Implementation Plan

1. Draft the archive restore SOP and link it from the runbooks index.
2. Align the handbook, FAQ, academic templates, and legal template index on the same `reproduction_vouchers.created_at` clock source.
3. Verify all touched docs are internally consistent and that no broken links remain.
4. Update the story record and sprint status after the docs pass review.

### Debug Log References

- 2026-05-22 — Started Story 6.B.6 from Epic 6.B and resolved the scope as docs-only after checking the existing 6.B.3 rerun window, 6.B.5 card copy, and the current legal-template index.

### Completion Notes List

- Created `docs/runbooks/repro-image-restore.md` as the operational contract draft for image archive restore.
- Aligned the handbook, FAQ, paper template, whitepaper outline, legal template index, and runbooks index on `reproduction_vouchers.created_at` UTC as the 5-year clock source.
- Clarified that rerun child vouchers use their own `created_at` while parent voucher clocks are not extended or reset.
- Preserved docs-only scope: no code, schema, API, UI, migration, billing, rerun, or archive job behavior changed.
- Verification passed: no stale future-only phrasing in touched docs, no broken relative links from touched docs, and `git diff --check` passed.

### File List

Created:
- `_bmad-output/stories/6-b-6-voucher-5y-sla-tracking.md`
- `docs/runbooks/repro-image-restore.md`

Modified:
- `_bmad-output/stories/sprint-status.yaml`
- `docs/academic-provider-handbook.md`
- `docs/customer-faqs/academic-onboarding-faq.md`
- `docs/academic-paper-template.zh-CN.md`
- `docs/academic-joint-whitepaper-outline.zh-CN.md`
- `docs/legal-templates.md`
- `docs/runbooks/README.md`

### Change Log

- 2026-05-22 — Created Story 6.B.6 and completed three story review rounds before implementation.
- 2026-05-22 — Added Repro Image Restore SOP and aligned academic/legal docs on `reproduction_vouchers.created_at` UTC as the 5-year SLA start point.
- 2026-05-22 — Verified docs links, stale future-only phrasing, and `git diff --check`; moved story to code review.
- 2026-05-22 — Code review patched two path-only SOP references into resolvable Markdown links; validation re-run passed.

### Post-Implementation Code Review

Result: PASS after one documentation-link patch.

Findings fixed:
- Low — Two SOP references used path-like inline code instead of Markdown links, weakening the story's cross-link requirement. Updated `docs/legal-templates.md` and `docs/runbooks/README.md` to use resolvable relative links.

Verification after review patch:
- Relative link scan across touched docs — no broken links reported.
- Stale future-only wording scan — no matches.
- `git diff --check` — pass.
