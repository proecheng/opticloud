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
    user_id             UUID NOT NULL,
    key                 VARCHAR(255) NOT NULL,
    optimization_id     UUID NOT NULL REFERENCES optimizations(id) ON DELETE CASCADE,
    request_body_hash   TEXT NOT NULL,
    expires_at          TIMESTAMPTZ NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, key)
);

CREATE INDEX IF NOT EXISTS idx_idempotency_keys_expires_at
    ON idempotency_keys(expires_at);

-- Story 3.13: async optimization batch grouping and whole-batch idempotency.
CREATE TABLE IF NOT EXISTS optimization_batches (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL,
    api_key_id          UUID NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_optimization_batches_user_id_created_at
    ON optimization_batches(user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS optimization_batch_items (
    batch_id            UUID NOT NULL REFERENCES optimization_batches(id) ON DELETE CASCADE,
    item_index          INTEGER NOT NULL,
    optimization_id     UUID NOT NULL UNIQUE REFERENCES optimizations(id) ON DELETE CASCADE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (batch_id, item_index)
);

CREATE INDEX IF NOT EXISTS idx_optimization_batch_items_batch_id_item_index
    ON optimization_batch_items(batch_id, item_index);

CREATE TABLE IF NOT EXISTS optimization_batch_idempotency_keys (
    user_id             UUID NOT NULL,
    key                 VARCHAR(255) NOT NULL,
    batch_id            UUID NOT NULL REFERENCES optimization_batches(id) ON DELETE CASCADE,
    request_body_hash   TEXT NOT NULL,
    expires_at          TIMESTAMPTZ NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, key)
);

CREATE INDEX IF NOT EXISTS idx_optimization_batch_idempotency_keys_expires_at
    ON optimization_batch_idempotency_keys(expires_at);

-- Story 6.B.3: scope solver idempotency by user + key rather than global key.
ALTER TABLE idempotency_keys
    DROP CONSTRAINT IF EXISTS idempotency_keys_pkey;
ALTER TABLE idempotency_keys
    ALTER COLUMN user_id SET NOT NULL;
ALTER TABLE idempotency_keys
    ALTER COLUMN key SET NOT NULL;
ALTER TABLE idempotency_keys
    ADD PRIMARY KEY (user_id, key);

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
    anonymous               BOOLEAN NOT NULL DEFAULT FALSE,
    status                  VARCHAR(32) NOT NULL DEFAULT 'issued',
    parent_voucher_id       UUID NULL,
    rerun_depth             INTEGER NOT NULL DEFAULT 0,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_reproduction_vouchers_parent_voucher_id
        FOREIGN KEY (parent_voucher_id) REFERENCES reproduction_vouchers(id),
    CONSTRAINT ck_reproduction_vouchers_voucher_id_format
        CHECK (voucher_id ~ '^repro-[0-9]{4}-[0123456789ABCDEFGHJKMNPQRSTVWXYZ]{6}$'),
    CONSTRAINT ck_reproduction_vouchers_status
        CHECK (status IN ('issued', 'revoked')),
    CONSTRAINT ck_reproduction_vouchers_rerun_depth
        CHECK (rerun_depth >= 0)
);

CREATE INDEX IF NOT EXISTS idx_reproduction_vouchers_user_id_created_at
    ON reproduction_vouchers(user_id, created_at DESC);

-- Story 6.B.3: idempotent upgrade for dev databases created before rerun lineage.
ALTER TABLE reproduction_vouchers
    ADD COLUMN IF NOT EXISTS parent_voucher_id UUID NULL;
ALTER TABLE reproduction_vouchers
    ADD COLUMN IF NOT EXISTS rerun_depth INTEGER NOT NULL DEFAULT 0;
ALTER TABLE reproduction_vouchers
    ADD COLUMN IF NOT EXISTS anonymous BOOLEAN NOT NULL DEFAULT FALSE;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint c
        JOIN pg_attribute a
            ON a.attrelid = c.conrelid
            AND a.attnum = ANY(c.conkey)
        WHERE c.conrelid = 'reproduction_vouchers'::regclass
            AND c.contype = 'f'
            AND a.attname = 'parent_voucher_id'
    ) THEN
        ALTER TABLE reproduction_vouchers
            ADD CONSTRAINT fk_reproduction_vouchers_parent_voucher_id
            FOREIGN KEY (parent_voucher_id) REFERENCES reproduction_vouchers(id);
    END IF;
END
$$;

ALTER TABLE reproduction_vouchers
    DROP CONSTRAINT IF EXISTS ck_reproduction_vouchers_status;
ALTER TABLE reproduction_vouchers
    ADD CONSTRAINT ck_reproduction_vouchers_status
    CHECK (status IN ('issued', 'revoked'));

ALTER TABLE reproduction_vouchers
    DROP CONSTRAINT IF EXISTS ck_reproduction_vouchers_rerun_depth;
ALTER TABLE reproduction_vouchers
    ADD CONSTRAINT ck_reproduction_vouchers_rerun_depth
    CHECK (rerun_depth >= 0);

CREATE INDEX IF NOT EXISTS idx_reproduction_vouchers_parent_voucher_id
    ON reproduction_vouchers(parent_voucher_id);

-- Story 3.2: prediction submissions.
CREATE TABLE IF NOT EXISTS predictions (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL,
    api_key_id          UUID NOT NULL,
    family              VARCHAR(64) NOT NULL,
    status              VARCHAR(50) NOT NULL DEFAULT 'queued',
    input_payload       JSONB NOT NULL,
    prediction          JSONB NULL,
    drift_score         NUMERIC NULL,
    model_version       JSONB NULL,
    error               JSONB NULL,
    predict_seconds     NUMERIC NULL,
    idempotency_key     VARCHAR(255) NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at        TIMESTAMPTZ NULL
);

CREATE INDEX IF NOT EXISTS idx_predictions_user_id_created_at
    ON predictions(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_predictions_status
    ON predictions(status) WHERE status IN ('queued', 'in_progress');

CREATE TABLE IF NOT EXISTS prediction_idempotency_keys (
    user_id             UUID NOT NULL,
    key                 VARCHAR(255) NOT NULL,
    prediction_id       UUID NOT NULL REFERENCES predictions(id) ON DELETE CASCADE,
    request_body_hash   TEXT NOT NULL,
    expires_at          TIMESTAMPTZ NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, key)
);

CREATE INDEX IF NOT EXISTS idx_prediction_idempotency_keys_expires_at
    ON prediction_idempotency_keys(expires_at);

-- Story 5.D.3: owner-scoped saved execution request templates.
CREATE TABLE IF NOT EXISTS job_templates (
    id                      UUID PRIMARY KEY,
    user_id                 UUID NOT NULL,
    name                    VARCHAR(120) NOT NULL,
    description             TEXT NULL,
    source_kind             VARCHAR(32) NOT NULL,
    source_id               UUID NOT NULL,
    task_type               VARCHAR(64) NOT NULL,
    payload_schema_version  VARCHAR(64) NOT NULL,
    payload_json            JSONB NOT NULL,
    payload_sha256          TEXT NOT NULL,
    version                 INTEGER NOT NULL DEFAULT 1,
    root_template_id        UUID NOT NULL,
    parent_template_id      UUID NULL,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at              TIMESTAMPTZ NULL
);

ALTER TABLE job_templates
    ADD COLUMN IF NOT EXISTS payload_schema_version VARCHAR(64) NOT NULL
    DEFAULT 'prediction_request_v1';
ALTER TABLE job_templates
    ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'ck_job_templates_source_kind'
    ) THEN
        ALTER TABLE job_templates
            ADD CONSTRAINT ck_job_templates_source_kind
            CHECK (source_kind IN ('optimization', 'prediction'));
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'ck_job_templates_payload_schema_version'
    ) THEN
        ALTER TABLE job_templates
            ADD CONSTRAINT ck_job_templates_payload_schema_version
            CHECK (
                payload_schema_version IN (
                    'optimization_request_v1',
                    'prediction_request_v1'
                )
            );
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'ck_job_templates_version_positive'
    ) THEN
        ALTER TABLE job_templates
            ADD CONSTRAINT ck_job_templates_version_positive
            CHECK (version >= 1);
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'fk_job_templates_root_template_id'
    ) THEN
        ALTER TABLE job_templates
            ADD CONSTRAINT fk_job_templates_root_template_id
            FOREIGN KEY (root_template_id) REFERENCES job_templates(id);
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'fk_job_templates_parent_template_id'
    ) THEN
        ALTER TABLE job_templates
            ADD CONSTRAINT fk_job_templates_parent_template_id
            FOREIGN KEY (parent_template_id) REFERENCES job_templates(id);
    END IF;
END
$$;

CREATE UNIQUE INDEX IF NOT EXISTS uq_job_templates_active_source_name
    ON job_templates(user_id, source_kind, source_id, name)
    WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_job_templates_user_created_at
    ON job_templates(user_id, created_at DESC)
    WHERE deleted_at IS NULL;
