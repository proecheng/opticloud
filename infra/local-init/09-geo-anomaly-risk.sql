-- Story 1.11 — API Key geo-anomaly risk score and user warning evidence.
-- Idempotent: safe to re-run.

ALTER TABLE api_keys
    ADD COLUMN IF NOT EXISTS last_used_geo_bucket VARCHAR(64) NULL;

ALTER TABLE api_keys
    ADD COLUMN IF NOT EXISTS geo_risk_score NUMERIC(3, 2) NOT NULL DEFAULT 0.00;

ALTER TABLE api_keys
    ADD COLUMN IF NOT EXISTS geo_anomaly_at TIMESTAMPTZ NULL;

ALTER TABLE api_keys
    ADD COLUMN IF NOT EXISTS geo_anomaly_metadata JSONB NOT NULL DEFAULT '{}'::jsonb;

CREATE INDEX IF NOT EXISTS idx_api_keys_geo_anomaly_user
    ON api_keys(user_id, geo_anomaly_at DESC)
    WHERE geo_anomaly_at IS NOT NULL;

INSERT INTO risk_rules (code, label_zh, description, enabled) VALUES
    (
        'geo_anomaly',
        'API Key 异常地理使用',
        'Story 1.11 — API Key known geo bucket changes unexpectedly; v1 scores and warns only',
        false
    )
ON CONFLICT (code) DO NOTHING;
