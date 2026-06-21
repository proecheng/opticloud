# Story M0: Blocked Items Decision Follow-Up

Status: done
Date: 2026-06-21
Type: process/status story

## Story

As the project owner and delivery team,
I want the remaining Epic 0 blocked items to have an explicit decision request and current repository status,
so that the project ledger does not misrepresent external legal, filing, or process dependencies as completed engineering work.

## Context

After PR #185 and the UX evolution ledger closure, the repository has no actionable engineering stories left in the current BMAD ledger. The only non-done concrete stories are four Epic 0 external process/legal/AIGC items:

- `0-0-sprint0-calibration-week`
- `m0-legal-1-license-deliverable`
- `m0-legal-status-tracking`
- `m0-aigc-status-tracking`

Prior evidence:

- `_bmad-output/stories/blocked-items-triage-2026-06-06.md`
- `_bmad-output/stories/blocked-items-decision-request-2026-06-06.md`
- `_bmad-output/stories/sprint-status.yaml`

## Scope

- Reconfirm the current status of the four blocked items.
- Preserve their `blocked` state until valid external evidence or owner/legal/PM waiver exists.
- Add a current follow-up record so the next project action is concrete and auditable.
- Keep `epic-0` open because the four blockers remain unresolved.

## Out of Scope

- Marking any blocked item `done` without evidence.
- Creating legal opinions, AIGC filing evidence, payment receipts, or retrospective calibration proof from repository code.
- Changing application code.
- Opening new productization work outside the current BMAD ledger.

## Acceptance Criteria

1. The repository contains a current follow-up story for the four blocked items.
2. The story references the existing triage and decision request artifacts.
3. `sprint-status.yaml` records this follow-up story as `done`.
4. The four original blocked items remain `blocked`.
5. `epic-0` remains `in-progress`.
6. The ledger still reports no actionable backlog/ready/in-progress/review engineering stories.
7. The next required external decisions are explicitly listed.

## Decision Status

### Item 1 - Sprint 0 Calibration Week

Story key: `0-0-sprint0-calibration-week`

Current decision status: pending owner / PM / Scrum Master decision.

Required decision:

- `KEEP_BLOCKED`: no retroactive calibration evidence exists.
- `UNBLOCK_WITH_EVIDENCE`: attach calibration notes, retroactive calibration artifact, or owner-approved process record.
- `WAIVE_OR_RETIRE`: attach written owner decision explaining why the item no longer blocks the project ledger.

### Item 2 - Legal License Deliverable

Story key: `m0-legal-1-license-deliverable`

Current decision status: pending Legal / Founder decision.

Required decision:

- `KEEP_BLOCKED`: legal signoff remains unavailable.
- `UNBLOCK_WITH_EVIDENCE`: attach signed EPL/ECOS/Apache 2.0 license decision or approved ADR reference.
- `WAIVE_OR_RETIRE`: attach written Founder/Legal risk acceptance or requirement removal.

### Item 3 - Legal Status Tracking

Story key: `m0-legal-status-tracking`

Current decision status: pending Legal / PM decision.

Required decision:

- `KEEP_BLOCKED`: legal weekly tracking remains external and unresolved.
- `UNBLOCK_WITH_EVIDENCE`: attach legal status tracker, weekly update record, or equivalent PM/legal artifact.
- `WAIVE_OR_RETIRE`: attach written PM/Legal decision retiring the recurring tracker.

### Item 4 - AIGC Filing Status Tracking

Story key: `m0-aigc-status-tracking`

Current decision status: pending Legal / PM decision.

Required decision:

- `KEEP_BLOCKED`: AIGC filing status remains external and unresolved.
- `UNBLOCK_WITH_EVIDENCE`: attach filing tracker, legal update record, receipt/payment evidence, or fallback decision-tree status.
- `WAIVE_OR_RETIRE`: attach written PM/Legal decision accepting the risk or removing this tracker from current scope.

## Implementation Summary

- Re-read the current blocked-item triage and decision request artifacts.
- Confirmed that the repository still lacks evidence or waiver records for the four original blocked items.
- Added this follow-up story as the current decision-status artifact.
- Updated `sprint-status.yaml` to track this follow-up as done while preserving the four original blocked statuses.

## Verification

The sprint ledger should parse to:

- Concrete stories: 202
- Done stories: 198
- Blocked stories: 4
- Non-done epic: `epic-0`

## Remaining Work

External owner/legal/PM action is still required. Once decisions are supplied, create a separate BMAD status-sync story that records the evidence or waiver and only then updates the four original blocked item statuses.

## Change Log

- 2026-06-21 - Created follow-up story for unresolved Epic 0 blocked decisions.
