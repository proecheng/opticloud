-- Story 1.5 — risk_rules registry + risk_flags log for FR A5 (NFR-S6 风控冻结).
-- Idempotent: safe to re-run.
--
-- Convention (DO NOT re-INSERT in future migrations to change enabled):
-- When a future story enables rule R (e.g. fingerprint sensor lands in FE),
-- that migration should do `UPDATE risk_rules SET enabled=true WHERE code='...'`
-- NOT re-run an INSERT (which would no-op via ON CONFLICT).

CREATE TABLE IF NOT EXISTS risk_rules (
    code         VARCHAR(32) PRIMARY KEY,
    label_zh     VARCHAR(255) NOT NULL,
    description  TEXT NOT NULL,
    enabled      BOOLEAN NOT NULL DEFAULT false,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS risk_flags (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id      UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    rule_code    VARCHAR(32) NOT NULL REFERENCES risk_rules(code),
    source       VARCHAR(16) NOT NULL,
    metadata     JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_risk_flags_user
    ON risk_flags(user_id);

-- Seed the 5 NFR-S6 spec rules. v1 enables only ip_24_share (R3 in PRD ordering)
-- because it's the only signal source ready today; the other 4 graduate to
-- enabled=true as their source systems land (FE fingerprint, solver telemetry,
-- billing payment data, phone-reuse detection).
INSERT INTO risk_rules (code, label_zh, description, enabled) VALUES
    ('fingerprint_high',   '设备指纹相似度 ≥0.9',     'NFR-S6 #1 — needs FE fingerprint header (deferred)', false),
    ('ip_24_share',        'IP /24 同段',              'NFR-S6 #2 — counts prior auth.signup audit-log rows sharing the same /24 (v1 active)', true),
    ('calls_24h_over_20',  '24h 内调用 ≥20 次',        'NFR-S6 #3 — needs solver-orchestrator call telemetry (deferred)', false),
    ('payment_reused',     '支付方式重复使用',         'NFR-S6 #4 — needs billing-service payment-method data (deferred)', false),
    ('phone_reused',       '手机号已注册 ≥1 账号',     'NFR-S6 #5 — currently 409s at UNIQUE constraint; future signal-only variant (deferred)', false)
ON CONFLICT (code) DO NOTHING;
