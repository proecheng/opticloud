-- Story 2.1 + 3.1: solver-orchestrator tables.
-- Patterns P1-P5 (snake_case, _at suffix, UUID PK).

CREATE TABLE IF NOT EXISTS optimizations (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL,
    api_key_id          UUID NOT NULL,
    task_type           VARCHAR(50) NOT NULL,        -- 'lp', 'milp', 'vrptw', ...
    status              VARCHAR(50) NOT NULL DEFAULT 'queued',  -- queued/in_progress/completed/failed
    input_payload       JSONB NOT NULL,
    solution            JSONB NULL,
    objective           NUMERIC NULL,
    model_version       JSONB NULL,                  -- {provider_id, kind, version, provider_url}
    error               JSONB NULL,                  -- RFC 7807 errors[] payload if failed
    solve_seconds       NUMERIC NULL,
    idempotency_key     VARCHAR(255) NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at        TIMESTAMPTZ NULL
);

CREATE INDEX IF NOT EXISTS idx_optimizations_user_id_created_at
    ON optimizations(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_optimizations_status
    ON optimizations(status) WHERE status IN ('queued', 'in_progress');

-- P23 Idempotency-Key dedup (24h TTL — auto-cleanup via cron in M3)
CREATE TABLE IF NOT EXISTS idempotency_keys (
    key                 VARCHAR(255) PRIMARY KEY,
    user_id             UUID NOT NULL,
    optimization_id     UUID NOT NULL REFERENCES optimizations(id) ON DELETE CASCADE,
    request_body_hash   TEXT NOT NULL,
    expires_at          TIMESTAMPTZ NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_idempotency_keys_expires_at
    ON idempotency_keys(expires_at);

-- Story 6.B.2: permanent reproducibility vouchers.
CREATE TABLE IF NOT EXISTS reproduction_vouchers (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    voucher_id              VARCHAR(32) NOT NULL UNIQUE,
    optimization_id         UUID NOT NULL UNIQUE REFERENCES optimizations(id) ON DELETE CASCADE,
    user_id                 UUID NOT NULL,
    api_key_id              UUID NOT NULL,
    request_fingerprint     TEXT NOT NULL,
    locked_model_version    JSONB NOT NULL,
    locked_solver           VARCHAR(64) NOT NULL,
    seed_locked             BOOLEAN NOT NULL,
    seed                    INTEGER NULL,
    status                  VARCHAR(32) NOT NULL DEFAULT 'issued',
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_reproduction_vouchers_voucher_id_format
        CHECK (voucher_id ~ '^repro-[0-9]{4}-[0123456789ABCDEFGHJKMNPQRSTVWXYZ]{6}$'),
    CONSTRAINT ck_reproduction_vouchers_status
        CHECK (status IN ('issued'))
);

CREATE INDEX IF NOT EXISTS idx_reproduction_vouchers_user_id_created_at
    ON reproduction_vouchers(user_id, created_at DESC);
