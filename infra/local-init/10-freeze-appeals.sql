-- Story 1.12 — J7 frozen appeal tracking + recovery token.
-- Idempotent: safe to re-run on local/dev and CI schema bootstrap.

CREATE TABLE IF NOT EXISTS account_freeze_appeals (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    proposal_id         UUID NULL REFERENCES account_merge_proposals(id) ON DELETE SET NULL,
    tracking_token_hash TEXT NOT NULL UNIQUE,
    status              VARCHAR(32) NOT NULL DEFAULT 'started',
    contact_email       VARCHAR(255) NOT NULL,
    expires_at          TIMESTAMPTZ NOT NULL,
    last_viewed_at      TIMESTAMPTZ NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_account_freeze_appeals_user_created_at
    ON account_freeze_appeals(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_account_freeze_appeals_proposal
    ON account_freeze_appeals(proposal_id) WHERE proposal_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_account_freeze_appeals_expires_at
    ON account_freeze_appeals(expires_at);
