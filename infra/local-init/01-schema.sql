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
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at      TIMESTAMPTZ NULL  -- FR A6 PIPL soft delete (7 day hard-delete cron)
);

CREATE INDEX idx_users_phone ON users(phone) WHERE deleted_at IS NULL;
CREATE INDEX idx_users_email ON users(email) WHERE deleted_at IS NULL;
CREATE INDEX idx_users_edu_tier ON users(edu_tier) WHERE edu_tier = TRUE;

-- ===== guardian_confirmations (Story 1.9 + FR A10) =====
CREATE TABLE IF NOT EXISTS guardian_confirmations (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    guardian_email      VARCHAR(255) NOT NULL,
    token_hash          TEXT NOT NULL UNIQUE,
    token_expires_at    TIMESTAMPTZ NOT NULL,
    confirmed_at        TIMESTAMPTZ NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_guardian_confirmations_token_hash
    ON guardian_confirmations(token_hash);

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
    revoked_at      TIMESTAMPTZ NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_api_keys_user_id ON api_keys(user_id);
CREATE INDEX idx_api_keys_key_prefix ON api_keys(key_prefix);
CREATE INDEX idx_api_keys_key_hash ON api_keys(key_hash) WHERE revoked_at IS NULL;

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

-- ===== 完成 =====
DO $$
BEGIN
    RAISE NOTICE 'OptiCloud schema initialized: users / api_keys / audit_logs / outbox';
END $$;
