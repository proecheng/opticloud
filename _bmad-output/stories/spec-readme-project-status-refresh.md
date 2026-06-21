---
title: 'README Project Status Refresh'
type: 'chore'
created: '2026-06-21'
status: 'done'
route: 'one-shot'
---

# README Project Status Refresh

## Intent

**Problem:** The repository README still described the project as Sprint 0 / foundation-building even though the BMAD ledger now shows v1 implementation work closed except for four explicitly blocked external process/legal/AIGC items.

**Approach:** Replace the stale README entry text with a current project status, updated repository map, practical local startup commands, validation commands, and links to the current BMAD ledger artifacts. The follow-on staging deployment verification work was completed in `spec-staging-deployment-verification.md`, so README now points to that runbook instead of leaving it as an unstarted next step.

## Suggested Review Order

1. [README.md](../../README.md) -- Check that the public repository entry now matches the current ledger and does not overclaim legal/AIGC closure.
2. [deferred-work.md](deferred-work.md) -- Confirm staging deployment verification is captured as the next separate deliverable.
3. [staging-deployment-verification.md](../../docs/runbooks/staging-deployment-verification.md) -- Confirm README's deployment reference points to the completed verification runbook.
4. [sprint-status.yaml](sprint-status.yaml) -- Cross-check story counts and blocked-item state referenced by README.
