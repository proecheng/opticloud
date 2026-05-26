-- Story 1.12 — J7 fraud/risk freeze appeal vertical slice.
-- Idempotent: safe to re-run.

CREATE TABLE IF NOT EXISTS risk_appeals (
    id                         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id                    UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    status                     VARCHAR(32) NOT NULL DEFAULT 'pending',
    reason                     TEXT NOT NULL,
    evidence                   JSONB NOT NULL DEFAULT '{}'::jsonb,
    team_size                  INTEGER NOT NULL,
    review_mode                VARCHAR(32) NOT NULL,
    decision                   VARCHAR(32) NULL,
    decision_reason            TEXT NULL,
    tracking_token_hash        TEXT NOT NULL UNIQUE,
    tracking_token_expires_at  TIMESTAMPTZ NOT NULL,
    merge_offer                JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at                 TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at                 TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    decided_at                 TIMESTAMPTZ NULL,
    CONSTRAINT ck_risk_appeals_status
        CHECK (status IN ('pending', 'approved', 'rejected', 'merge_offered', 'merge_accepted')),
    CONSTRAINT ck_risk_appeals_review_mode
        CHECK (review_mode IN ('auto_score', 'manual_48h')),
    CONSTRAINT ck_risk_appeals_decision
        CHECK (
            decision IS NULL
            OR decision IN ('approved', 'maintained', 'rejected', 'merge_accepted')
        ),
    CONSTRAINT ck_risk_appeals_team_size
        CHECK (team_size >= 1)
);

CREATE INDEX IF NOT EXISTS idx_risk_appeals_user_status
    ON risk_appeals(user_id, status);

CREATE UNIQUE INDEX IF NOT EXISTS idx_risk_appeals_user_active
    ON risk_appeals(user_id)
    WHERE status IN ('pending', 'merge_offered');

CREATE INDEX IF NOT EXISTS idx_risk_appeals_pending_review
    ON risk_appeals(created_at)
    WHERE status = 'pending';

CREATE UNIQUE INDEX IF NOT EXISTS idx_risk_appeals_tracking_token_hash
    ON risk_appeals(tracking_token_hash);
