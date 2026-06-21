# Story M0: Blocked Items Owner Decision Record

Status: done
Date: 2026-06-21
Type: owner/legal/PM decision record

## Story

As the owner/legal/PM decision maker,
I want the four remaining Epic 0 blocked items to have an explicit recorded decision,
so that the project ledger reflects the current external-dependency position without pretending those dependencies are resolved.

## Decision Source

The project owner/legal/PM responded in the project thread on 2026-06-21:

- `0-0-sprint0-calibration-week`: "不懂，KEEP_BLOCKED"
- `m0-legal-1-license-deliverable`: "不懂，KEEP_BLOCKED"
- `m0-legal-status-tracking`: "KEEP_BLOCKED"
- `m0-aigc-status-tracking`: "KEEP_BLOCKED"

## Recorded Decisions

### 1. Sprint 0 Calibration Week

Story key: `0-0-sprint0-calibration-week`

Decision: `KEEP_BLOCKED`

Reason recorded: Owner does not have enough context or evidence to unblock or waive this item. No retroactive calibration evidence has been supplied.

Status action: keep original story `blocked`.

### 2. Legal License Deliverable

Story key: `m0-legal-1-license-deliverable`

Decision: `KEEP_BLOCKED`

Reason recorded: Owner/legal/PM does not have enough context or evidence to unblock or waive this item. No signed license decision or approved ADR has been supplied.

Status action: keep original story `blocked`.

### 3. Legal Status Tracking

Story key: `m0-legal-status-tracking`

Decision: `KEEP_BLOCKED`

Reason recorded: Legal status tracking remains unresolved and no current legal tracker or weekly update evidence has been supplied.

Status action: keep original story `blocked`.

### 4. AIGC Filing Status Tracking

Story key: `m0-aigc-status-tracking`

Decision: `KEEP_BLOCKED`

Reason recorded: AIGC filing tracking remains unresolved and no filing tracker, payment/receipt evidence, or fallback decision-tree status has been supplied.

Status action: keep original story `blocked`.

## Acceptance Criteria

1. The four owner/legal/PM decisions are recorded exactly as `KEEP_BLOCKED`.
2. The original four blocked stories remain `blocked`.
3. `epic-0` remains `in-progress`.
4. `sprint-status.yaml` records this decision record story as `done`.
5. The ledger still has no actionable backlog/ready/in-progress/review engineering stories.

## Implementation Summary

- Added this owner decision record.
- Updated `sprint-status.yaml` to track this decision record as completed.
- Preserved the original blocked statuses and open `epic-0`.

## Verification

The sprint ledger should parse to:

- Concrete stories: 203
- Done stories: 199
- Blocked stories: 4
- Non-done epic: `epic-0`

## Remaining Work

The four external items remain blocked. To change any of them later, owner/legal/PM must provide either:

- `UNBLOCK_WITH_EVIDENCE` with evidence, or
- `WAIVE_OR_RETIRE` with written risk acceptance or retirement rationale.

## Change Log

- 2026-06-21 - Recorded owner/legal/PM decision to keep all four Epic 0 blockers blocked.
