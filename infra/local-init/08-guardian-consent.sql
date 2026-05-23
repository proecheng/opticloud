-- Story 1.9 — FR A10 guardian consent requests for 14-17 signup.

CREATE TABLE IF NOT EXISTS guardian_consent_requests (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    phone           VARCHAR(20) NOT NULL,
    email           VARCHAR(255) NOT NULL,
    age_years       INTEGER NOT NULL CHECK (age_years BETWEEN 14 AND 17),
    guardian_email  VARCHAR(255) NOT NULL,
    token_hash      TEXT NOT NULL,
    expires_at      TIMESTAMPTZ NOT NULL,
    confirmed_at    TIMESTAMPTZ NULL,
    user_id         UUID NULL REFERENCES users(id) ON DELETE SET NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_guardian_consent_requests_token_hash
    ON guardian_consent_requests(token_hash);
CREATE INDEX IF NOT EXISTS idx_guardian_consent_requests_pending_contacts
    ON guardian_consent_requests(phone, email, guardian_email, expires_at)
    WHERE confirmed_at IS NULL;

DROP TRIGGER IF EXISTS trigger_guardian_consent_requests_updated_at
    ON guardian_consent_requests;
CREATE TRIGGER trigger_guardian_consent_requests_updated_at
    BEFORE UPDATE ON guardian_consent_requests
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();
