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
        CHECK (
            event_type IN (
                'billing.budget.alerted',
                'billing.budget.paused',
                'status.incident.published'
            )
        ),
    CONSTRAINT ck_notification_preferences_webhook_url_length
        CHECK (webhook_url IS NULL OR length(webhook_url) <= 512),
    CONSTRAINT ck_notification_preferences_webhook_url_required
        CHECK (
            (webhook_enabled = TRUE AND webhook_url IS NOT NULL AND length(webhook_url) > 0)
            OR webhook_enabled = FALSE
        )
);

ALTER TABLE notification_preferences
    DROP CONSTRAINT IF EXISTS ck_notification_preferences_event_type;
ALTER TABLE notification_preferences
    ADD CONSTRAINT ck_notification_preferences_event_type
    CHECK (
        event_type IN (
            'billing.budget.alerted',
            'billing.budget.paused',
            'status.incident.published'
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

CREATE TABLE IF NOT EXISTS status_incident_notification_requests (
    id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    incident_id                 VARCHAR(96) NOT NULL,
    user_id                     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    status_url                  TEXT NOT NULL,
    title                       VARCHAR(255) NOT NULL,
    severity                    VARCHAR(16) NOT NULL,
    incident_status             VARCHAR(32) NOT NULL,
    channels                    TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    webhook_url_configured      BOOLEAN NOT NULL DEFAULT FALSE,
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_status_incident_notification_requests_incident_id
        CHECK (incident_id ~ '^inc-[A-Za-z0-9][A-Za-z0-9_.:-]{1,94}$'),
    CONSTRAINT ck_status_incident_notification_requests_severity
        CHECK (severity IN ('minor', 'major', 'critical')),
    CONSTRAINT ck_status_incident_notification_requests_status
        CHECK (incident_status IN ('investigating', 'identified', 'monitoring', 'resolved')),
    CONSTRAINT ck_status_incident_notification_requests_channels
        CHECK (channels <@ ARRAY['email', 'webhook', 'in_app']::TEXT[])
);

ALTER TABLE status_incident_notification_requests
    DROP CONSTRAINT IF EXISTS ck_status_incident_notification_requests_incident_id;
ALTER TABLE status_incident_notification_requests
    ADD CONSTRAINT ck_status_incident_notification_requests_incident_id
    CHECK (incident_id ~ '^inc-[A-Za-z0-9][A-Za-z0-9_.:-]{1,94}$');

ALTER TABLE status_incident_notification_requests
    DROP CONSTRAINT IF EXISTS ck_status_incident_notification_requests_severity;
ALTER TABLE status_incident_notification_requests
    ADD CONSTRAINT ck_status_incident_notification_requests_severity
    CHECK (severity IN ('minor', 'major', 'critical'));

ALTER TABLE status_incident_notification_requests
    DROP CONSTRAINT IF EXISTS ck_status_incident_notification_requests_status;
ALTER TABLE status_incident_notification_requests
    ADD CONSTRAINT ck_status_incident_notification_requests_status
    CHECK (incident_status IN ('investigating', 'identified', 'monitoring', 'resolved'));

ALTER TABLE status_incident_notification_requests
    DROP CONSTRAINT IF EXISTS ck_status_incident_notification_requests_channels;
ALTER TABLE status_incident_notification_requests
    ADD CONSTRAINT ck_status_incident_notification_requests_channels
    CHECK (channels <@ ARRAY['email', 'webhook', 'in_app']::TEXT[]);

CREATE UNIQUE INDEX IF NOT EXISTS idx_status_incident_notification_requests_incident_user
    ON status_incident_notification_requests(incident_id, user_id);

CREATE INDEX IF NOT EXISTS idx_status_incident_notification_requests_user_created
    ON status_incident_notification_requests(user_id, created_at);

DROP TRIGGER IF EXISTS trigger_status_incident_notification_requests_updated_at
    ON status_incident_notification_requests;
CREATE TRIGGER trigger_status_incident_notification_requests_updated_at
    BEFORE UPDATE ON status_incident_notification_requests
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();  -- defined in 01-schema.sql

DO $$
BEGIN
    RAISE NOTICE 'OptiCloud schema initialized: notification preferences';
END $$;
