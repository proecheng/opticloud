-- OptiCloud — 初始 schema (Story 0.2 + 0.6)
-- Postgres 16 + asyncpg + SQLAlchemy 2.0 async
-- C9: TDE 全环境启用（生产 pg_tde，dev 占位）
-- P1-P5: Table 复数 snake_case / column snake_case + _at 后缀 / PK = id UUID v7

-- ===== Extensions =====
CREATE EXTENSION IF NOT EXISTS pgcrypto;     -- gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";  -- uuid_generate_v4 (fallback)

-- ===== users (Story 0.6 + FR A1-A10) =====
CREATE TABLE IF NOT EXISTS users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    phone           VARCHAR(20) NOT NULL UNIQUE,
    email           VARCHAR(255) NOT NULL UNIQUE,
    edu_tier        BOOLEAN NOT NULL DEFAULT FALSE,  -- FR A4 教育版
    age_verified    BOOLEAN NOT NULL DEFAULT FALSE,  -- FR A10 <14 岁拦截
    risk_score      NUMERIC(3, 2) NOT NULL DEFAULT 0.00,  -- FR A5 风控
    is_frozen       BOOLEAN NOT NULL DEFAULT FALSE,
    merged_into_user_id UUID NULL REFERENCES users(id) ON DELETE SET NULL,
    merged_at       TIMESTAMPTZ NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at      TIMESTAMPTZ NULL  -- FR A6 PIPL soft delete (7 day hard-delete cron)
);

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS merged_into_user_id UUID NULL REFERENCES users(id) ON DELETE SET NULL;
ALTER TABLE users
    ADD COLUMN IF NOT EXISTS merged_at TIMESTAMPTZ NULL;

CREATE INDEX idx_users_phone ON users(phone) WHERE deleted_at IS NULL;
CREATE INDEX idx_users_email ON users(email) WHERE deleted_at IS NULL;
CREATE INDEX idx_users_edu_tier ON users(edu_tier) WHERE edu_tier = TRUE;
CREATE INDEX IF NOT EXISTS idx_users_merged_into
    ON users(merged_into_user_id) WHERE merged_into_user_id IS NOT NULL;

-- ===== api_keys (Story 0.6 + FR A2) =====
-- D7: HMAC-SHA256 with Vault pepper; 仅 hash 入库，前缀 6 位可见
-- CRG4 fix: pepper 季度 Vault HSM 轮换 + grace 30d 双 pepper 验证
CREATE TABLE IF NOT EXISTS api_keys (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    key_hash        TEXT NOT NULL,                  -- HMAC-SHA256 hash
    key_prefix      VARCHAR(10) NOT NULL,           -- 前缀 6 位可见（含 sk- 前缀）
    pepper_version  INTEGER NOT NULL DEFAULT 1,     -- 多 pepper grace period 支持
    label           VARCHAR(255) NOT NULL,
    description     TEXT NULL,
    scope           TEXT[] NOT NULL DEFAULT '{}',   -- ["optimize:write", "billing:read", ...]
    expires_at      TIMESTAMPTZ NULL,
    last_used_at    TIMESTAMPTZ NULL,
    last_used_ip    INET NULL,
    last_used_geo_bucket VARCHAR(64) NULL,
    geo_risk_score  NUMERIC(3, 2) NOT NULL DEFAULT 0.00,
    geo_anomaly_at  TIMESTAMPTZ NULL,
    geo_anomaly_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    revoked_at      TIMESTAMPTZ NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE api_keys
    ADD COLUMN IF NOT EXISTS last_used_geo_bucket VARCHAR(64) NULL;
ALTER TABLE api_keys
    ADD COLUMN IF NOT EXISTS geo_risk_score NUMERIC(3, 2) NOT NULL DEFAULT 0.00;
ALTER TABLE api_keys
    ADD COLUMN IF NOT EXISTS geo_anomaly_at TIMESTAMPTZ NULL;
ALTER TABLE api_keys
    ADD COLUMN IF NOT EXISTS geo_anomaly_metadata JSONB NOT NULL DEFAULT '{}'::jsonb;

CREATE INDEX idx_api_keys_user_id ON api_keys(user_id);
CREATE INDEX idx_api_keys_key_prefix ON api_keys(key_prefix);
CREATE INDEX idx_api_keys_key_hash ON api_keys(key_hash) WHERE revoked_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_api_keys_geo_anomaly_user
    ON api_keys(user_id, geo_anomaly_at DESC)
    WHERE geo_anomaly_at IS NOT NULL;

-- ===== audit_logs (Story 0.7 + FR O3 + C3 v1 单表) =====
-- C3: v1 Audit = Postgres audit_log 表 + 异步入库；v2 末拆库
CREATE TABLE IF NOT EXISTS audit_logs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NULL REFERENCES users(id) ON DELETE SET NULL,
    actor           VARCHAR(255) NOT NULL,          -- 'user' / 'system' / 'admin'
    action          VARCHAR(255) NOT NULL,          -- 'auth.signup' / 'api_keys.create' / etc
    resource_type   VARCHAR(255) NULL,
    resource_id     UUID NULL,
    metadata        JSONB NOT NULL DEFAULT '{}'::jsonb,
    ip_address      INET NULL,
    user_agent      TEXT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_audit_logs_user_id_created_at ON audit_logs(user_id, created_at DESC);
CREATE INDEX idx_audit_logs_action_created_at ON audit_logs(action, created_at DESC);

-- ===== guardian_consent_requests (Story 1.9 + FR A10) =====
-- Pre-user consent state for 14-17 signup. Tokens are HMAC hashed; no user/JWT/credits
-- exist until confirmation succeeds.
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

-- ===== account_deletion_requests (Story 1.6 + FR A6) =====
CREATE TABLE IF NOT EXISTS account_deletion_requests (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id_snapshot    UUID NOT NULL UNIQUE,
    user_id             UUID NULL REFERENCES users(id) ON DELETE SET NULL,
    status              VARCHAR(32) NOT NULL DEFAULT 'scheduled',
    requested_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    hard_delete_at      TIMESTAMPTZ NOT NULL,
    completed_at        TIMESTAMPTZ NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_account_deletion_requests_hard_delete_at
    ON account_deletion_requests(hard_delete_at);

-- ===== data_export_requests (Story 5.C.3 + FR B10) =====
-- Self-service PIPL JSON export lifecycle. v1 stores the JSON package in DB;
-- object storage / signed email delivery are deferred to later stories.
CREATE TABLE IF NOT EXISTS data_export_requests (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id_snapshot        UUID NOT NULL,
    user_id                 UUID NULL REFERENCES users(id) ON DELETE SET NULL,
    format                  VARCHAR(16) NOT NULL DEFAULT 'json',
    status                  VARCHAR(32) NOT NULL DEFAULT 'queued',
    requested_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    sla_deadline_at         TIMESTAMPTZ NOT NULL,
    processing_started_at   TIMESTAMPTZ NULL,
    completed_at            TIMESTAMPTZ NULL,
    expires_at              TIMESTAMPTZ NULL,
    package_json            JSONB NULL,
    package_sha256          CHAR(64) NULL,
    package_bytes           INTEGER NULL,
    download_url            TEXT NULL,
    last_error              TEXT NULL,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_data_export_requests_format
        CHECK (format IN ('json')),
    CONSTRAINT ck_data_export_requests_status
        CHECK (status IN ('queued', 'processing', 'completed', 'failed', 'expired'))
);

CREATE INDEX IF NOT EXISTS idx_data_export_requests_user_requested
    ON data_export_requests(user_id_snapshot, requested_at DESC);
CREATE INDEX IF NOT EXISTS idx_data_export_requests_queued
    ON data_export_requests(requested_at)
    WHERE status = 'queued';
CREATE UNIQUE INDEX IF NOT EXISTS uq_data_export_requests_inflight_json
    ON data_export_requests(user_id_snapshot, format)
    WHERE format = 'json' AND status IN ('queued', 'processing');

-- ===== account_merge_proposals (Story 1.7 + FR A7/A8) =====
CREATE TABLE IF NOT EXISTS account_merge_proposals (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    requester_user_id   UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    primary_user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    duplicate_user_ids  UUID[] NOT NULL,
    evidence            JSONB NOT NULL DEFAULT '{}'::jsonb,
    status              VARCHAR(32) NOT NULL DEFAULT 'pending_review',
    review_mode         VARCHAR(16) NOT NULL,
    auto_score          NUMERIC(4, 2) NULL,
    review_due_at       TIMESTAMPTZ NOT NULL,
    reviewed_at         TIMESTAMPTZ NULL,
    reviewed_by         VARCHAR(255) NULL,
    decision_reason     TEXT NULL,
    accepted_at         TIMESTAMPTZ NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_account_merge_proposals_requester_created_at
    ON account_merge_proposals(requester_user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_account_merge_proposals_status_due
    ON account_merge_proposals(status, review_due_at);

-- ===== account_freeze_appeals (Story 1.12 + J7) =====
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

-- ===== outbox (P33 + P56 + C12 sidecar relayer) =====
-- M1 fire-and-forget；M2+ outbox sidecar
CREATE TABLE IF NOT EXISTS outbox (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    aggregate_type  VARCHAR(255) NOT NULL,
    aggregate_id    UUID NOT NULL,
    event_type      VARCHAR(255) NOT NULL,          -- 'auth.signup' / 'billing.charge' / etc
    event_version   INTEGER NOT NULL DEFAULT 1,     -- P63 Event Versioning
    payload         JSONB NOT NULL,
    headers         JSONB NOT NULL DEFAULT '{}'::jsonb,
    occurred_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    sent_at         TIMESTAMPTZ NULL                -- sidecar 投递成功时间
);

CREATE INDEX idx_outbox_unsent ON outbox(occurred_at) WHERE sent_at IS NULL;
CREATE INDEX idx_outbox_aggregate ON outbox(aggregate_type, aggregate_id, occurred_at DESC);

-- ===== updated_at trigger =====
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();

DROP TRIGGER IF EXISTS trigger_guardian_consent_requests_updated_at
    ON guardian_consent_requests;
CREATE TRIGGER trigger_guardian_consent_requests_updated_at
    BEFORE UPDATE ON guardian_consent_requests
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();

DROP TRIGGER IF EXISTS trigger_data_export_requests_updated_at
    ON data_export_requests;
CREATE TRIGGER trigger_data_export_requests_updated_at
    BEFORE UPDATE ON data_export_requests
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();

-- ===== 完成 =====
DO $$
BEGIN
    RAISE NOTICE 'OptiCloud schema initialized: users / api_keys / audit_logs / outbox';
END $$;
