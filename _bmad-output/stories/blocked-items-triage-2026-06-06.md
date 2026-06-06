# Blocked Items Triage - Epic 0 External Process Items

Date: 2026-06-06
Project: 通用优化与预测服务网站
Status: complete

## Summary

Sprint status has no actionable engineering stories left. The only non-done concrete items are four Epic 0 process/legal/AIGC tracking items:

- `0-0-sprint0-calibration-week`
- `m0-legal-1-license-deliverable`
- `m0-legal-status-tracking`
- `m0-aigc-status-tracking`

These remain `blocked`. They cannot be completed from repository code alone and should not be marked `done` without external evidence.

## Current State

Programmatic sprint-status scan on 2026-06-06 found:

- Concrete stories: 196 total
- Done stories: 192
- Blocked stories: 4
- Actionable backlog/ready/in-progress/code-review stories: 0
- Epics: 21 total
- Done epics: 20
- Open epics: `epic-0` only

Epic 0 stays `in-progress` solely because these four blocked external/process items remain open.

## Item Decisions

### 0-0-sprint0-calibration-week

Decision: keep `blocked`.

Reason:

- Source `RE2-1` adds Story 0.0 Sprint 0 Calibration Week as a team cadence/calibration process.
- The implementation work has already progressed far beyond Sprint 0, and there is no repo-owned artifact that can retroactively prove the original team calibration week occurred.
- Completing it now would require an explicit process waiver or a documented retroactive calibration decision from the project owner.

Unblock condition:

- Project owner decides one of:
  - provide external evidence that the calibration was completed,
  - replace it with a retrospective/process calibration artifact,
  - formally waive it and mark as not-applicable through a dedicated BMAD status change.

### m0-legal-1-license-deliverable

Decision: keep `blocked`.

Reason:

- Source `E9` / `G17` / `C21` requires EPL + ECOS + Apache 2.0 legal signoff.
- `docs/legal-templates.md` explicitly says the license decision ADR is pending legal signoff.
- Implementation readiness v3 records this as "用户先前已声明不操心", with owner `法务 + Founder`.
- Repository code cannot produce the legal opinion or external signature.

Unblock condition:

- Legal/Founder supplies the signed license decision deliverable or explicitly waives the blocked item.

### m0-legal-status-tracking

Decision: keep `blocked`.

Reason:

- Source `RE2-8` requires legal signoff and intermediary-fee weekly tracking.
- This is an ongoing legal/process tracking cadence, not an engineering deliverable.
- No current repository artifact can prove the external weekly legal status process is active or complete.

Unblock condition:

- Legal/PM provides current tracking evidence, or the project owner formally retires this tracking item as no longer required.

### m0-aigc-status-tracking

Decision: keep `blocked`.

Reason:

- Source `CM3` requires AIGC filing weekly tracking, intermediary-fee payment verification, and fallback decision tree tracking.
- Engineering mitigation stories for AIGC filtering/watermarking have been completed elsewhere, but the filing status itself remains an external legal/PM process.
- No current repository artifact proves filing status updates, payment receipts, or weekly legal follow-up.

Unblock condition:

- Legal/PM supplies AIGC filing tracking evidence, or the project owner formally waives/retires the tracking item.

## Deferred Follow-Up

No engineering implementation should be started from these items until one of the unblock conditions above is met.

If the project owner wants to close the project ledger without waiting on external parties, the correct next story is not a code story. It should be a BMAD process/status story that explicitly asks whether these four blocked items are to remain blocked, be waived, or be replaced by retrospective documentation.

## Recommendation

Keep all four items `blocked` and keep `epic-0` `in-progress`.

The next operational action is external: obtain owner/legal/PM decisions for the four blocked items. The repository is otherwise at the end of the current actionable backlog.
