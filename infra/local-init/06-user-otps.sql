-- Story 1.2 — user_otps table for 2FA login (FR A1).
-- Two factors per login attempt (phone + email); TTL 5min; invalidated on use.
-- Idempotent: safe to re-run.

CREATE TABLE IF NOT EXISTS user_otps (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    factor      VARCHAR(16) NOT NULL,           -- 'phone' | 'email'
    code        VARCHAR(10) NOT NULL,           -- 6-digit numeric
    expires_at  TIMESTAMPTZ NOT NULL,
    used_at     TIMESTAMPTZ NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_user_otps_user_factor_unused
    ON user_otps(user_id, factor) WHERE used_at IS NULL;
