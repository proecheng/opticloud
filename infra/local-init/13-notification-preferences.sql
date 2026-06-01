-- Story 5.D.6 - user notification preferences.
-- Idempotent: safe to re-run after 01-schema.sql.

CREATE TABLE IF NOT EXISTS notification_preferences (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    event_type          VARCHAR(64) NOT NULL,
    email_enabled       BOOLEAN NOT NULL DEFAULT TRUE,
    webhook_enabled     BOOLEAN NOT NULL DEFAULT FALSE,
    in_app_enabled      BOOLEAN NOT NULL DEFAULT TRUE,
    webhook_url         TEXT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_notification_preferences_event_type
        CHECK (event_type IN ('billing.budget.alerted', 'billing.budget.paused')),
    CONSTRAINT ck_notification_preferences_webhook_url_length
        CHECK (webhook_url IS NULL OR length(webhook_url) <= 512),
    CONSTRAINT ck_notification_preferences_webhook_url_required
        CHECK (
            (webhook_enabled = TRUE AND webhook_url IS NOT NULL AND length(webhook_url) > 0)
            OR webhook_enabled = FALSE
        )
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_notification_preferences_user_event
    ON notification_preferences(user_id, event_type);

CREATE INDEX IF NOT EXISTS idx_notification_preferences_event_type
    ON notification_preferences(event_type);

DROP TRIGGER IF EXISTS trigger_notification_preferences_updated_at
    ON notification_preferences;
CREATE TRIGGER trigger_notification_preferences_updated_at
    BEFORE UPDATE ON notification_preferences
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();  -- defined in 01-schema.sql

DO $$
BEGIN
    RAISE NOTICE 'OptiCloud schema initialized: notification preferences';
END $$;
