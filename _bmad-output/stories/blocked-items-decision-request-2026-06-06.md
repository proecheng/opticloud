# Blocked Items Decision Request

Date: 2026-06-06
Project: 通用优化与预测服务网站
Audience: Project Owner, Legal, PM
Status: pending external decision

## Purpose

The repository has no actionable engineering stories left. Four Epic 0 items remain blocked because they require external process, legal, or filing evidence.

This document requests an explicit decision for each item so BMAD status can proceed without misrepresenting external work as completed.

## Current Evidence

Current sprint status:

- Concrete stories: 196
- Done: 192
- Blocked: 4
- Actionable backlog/ready/in-progress/code-review stories: 0
- Open epic: `epic-0` only

Prior triage:

- `_bmad-output/stories/blocked-items-triage-2026-06-06.md`

## Requested Decisions

For each item below, choose exactly one decision:

- `KEEP_BLOCKED`: external dependency remains unresolved.
- `UNBLOCK_WITH_EVIDENCE`: evidence is available and should be attached/referenced.
- `WAIVE_OR_RETIRE`: owner explicitly accepts that the item should no longer block the project ledger.

## Item 1 - Sprint 0 Calibration Week

Story key: `0-0-sprint0-calibration-week`

Current status: `blocked`

Owner needed: Project Owner / PM / Scrum Master

Decision needed:

- Keep blocked because no retroactive calibration evidence exists.
- Provide evidence that calibration was completed.
- Waive or retire the calibration item and allow a BMAD status story to record the waiver.

Evidence required for `UNBLOCK_WITH_EVIDENCE`:

- Calibration notes, retroactive calibration artifact, or owner-approved process record.

Evidence required for `WAIVE_OR_RETIRE`:

- Written owner decision stating why the item is no longer required.

## Item 2 - Legal License Deliverable

Story key: `m0-legal-1-license-deliverable`

Current status: `blocked`

Owner needed: Legal / Founder

Decision needed:

- Keep blocked until legal signoff is available.
- Provide signed EPL/ECOS/Apache 2.0 license decision deliverable.
- Waive or retire the legal-signoff gate.

Evidence required for `UNBLOCK_WITH_EVIDENCE`:

- Signed legal decision or approved ADR reference for EPL, ECOS, Apache 2.0, and relevant SaaS usage constraints.

Evidence required for `WAIVE_OR_RETIRE`:

- Written Founder/Legal decision accepting the risk or removing the requirement.

## Item 3 - Legal Status Tracking

Story key: `m0-legal-status-tracking`

Current status: `blocked`

Owner needed: Legal / PM

Decision needed:

- Keep blocked because legal weekly tracking remains external.
- Provide current tracking evidence.
- Retire the tracking item as no longer required.

Evidence required for `UNBLOCK_WITH_EVIDENCE`:

- Current legal status tracker, weekly update record, or equivalent PM/legal status artifact.

Evidence required for `WAIVE_OR_RETIRE`:

- Written PM/Legal decision that this recurring tracker is no longer required.

## Item 4 - AIGC Filing Status Tracking

Story key: `m0-aigc-status-tracking`

Current status: `blocked`

Owner needed: Legal / PM

Decision needed:

- Keep blocked because AIGC filing status remains external.
- Provide filing status, weekly tracking, and payment/receipt evidence if applicable.
- Retire or waive the filing tracker as no longer required for this ledger.

Evidence required for `UNBLOCK_WITH_EVIDENCE`:

- AIGC filing tracker, legal update record, receipt/payment evidence, or fallback decision tree status.

Evidence required for `WAIVE_OR_RETIRE`:

- Written PM/Legal decision accepting the filing-status risk or removing the tracker from current scope.

## Implementation Rule After Decision

Do not edit blocked statuses directly from this request document.

If owner/legal/PM returns decisions, create a dedicated BMAD process/status story and run the full required lifecycle:

1. Create story.
2. Run exactly three pre-implementation adversarial review rounds.
3. Revise after each review round.
4. Implement only the approved status/documentation change.
5. Run post-implementation review.
6. Push branch, create PR, wait for CI, merge, delete remote branch, and sync local `main`.
7. Mark final status in a separate post-merge status-sync commit.
