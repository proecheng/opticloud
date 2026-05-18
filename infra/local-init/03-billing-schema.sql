-- OptiCloud — Billing schema (Story 5.A.0a)
-- Saga orchestrator + Credit ledger + Idempotency keys
-- Depends on 01-schema.sql (users, outbox)
-- ADR-0001 alignment: payload_ref = pointers only; amounts in credit_transactions

-- ===== saga_instances (ADR-0001 §State persistence) =====
-- Tracks current state per Saga. payload_ref contains POINTERS (optimization_id etc.),
-- NEVER monetary amounts (NFR-S1 + PIPL).
CREATE TABLE IF NOT EXISTS saga_instances (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    saga_type           VARCHAR(64) NOT NULL,        -- 'solve_charge' / 'topup' / 'refund' / ...
    current_state       VARCHAR(32) NOT NULL,        -- opticloud_shared.saga.State enum value
    user_id             UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    idempotency_key     VARCHAR(255) NULL,
    amount              NUMERIC(12, 4) NULL,         -- declared charge amount (CNY); ledger entries derive sign
    retries             INTEGER NOT NULL DEFAULT 0,
    last_error          TEXT NULL,
    payload_ref         JSONB NOT NULL DEFAULT '{}'::jsonb,  -- POINTERS only (NO amounts, NO PII)
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_saga_instances_user_state ON saga_instances(user_id, current_state);
CREATE UNIQUE INDEX idx_saga_instances_idem
    ON saga_instances(idempotency_key)
    WHERE idempotency_key IS NOT NULL;

-- ===== credit_transactions (NFR-R4 source of truth) =====
-- Double-entry ledger: charge = negative balance change; refund/topup = positive.
-- Reconciliation: SUM(amount WHERE user_id=X) = current Credits balance.
CREATE TABLE IF NOT EXISTS credit_transactions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    saga_id         UUID NULL REFERENCES saga_instances(id) ON DELETE SET NULL,
    amount          NUMERIC(12, 4) NOT NULL,         -- signed: charge = negative, refund/topup = positive
    kind            VARCHAR(32) NOT NULL,            -- 'charge' / 'refund' / 'topup' / 'adjustment'
    currency        VARCHAR(3) NOT NULL DEFAULT 'CNY',
    metadata        JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_credit_tx_user_kind_created
    ON credit_transactions(user_id, kind, created_at DESC);
CREATE INDEX idx_credit_tx_saga
    ON credit_transactions(saga_id)
    WHERE saga_id IS NOT NULL;

-- ===== billing_idempotency_keys (P23 — billing scope) =====
-- Separate from solver's `idempotency_keys` (which is scoped to optimization_id FK).
-- Billing keys point at saga_instances; same P23 contract, different aggregate.
-- Body never persisted, only SHA-256 hash (S2).
CREATE TABLE IF NOT EXISTS billing_idempotency_keys (
    key                 VARCHAR(255) PRIMARY KEY,
    user_id             UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    request_body_hash   CHAR(64) NOT NULL,           -- SHA-256 hex
    response_body       JSONB NULL,
    saga_id             UUID NULL REFERENCES saga_instances(id) ON DELETE SET NULL,
    expires_at          TIMESTAMPTZ NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_billing_idempotency_keys_expires ON billing_idempotency_keys(expires_at);

-- ===== updated_at trigger for saga_instances =====
DROP TRIGGER IF EXISTS trigger_saga_instances_updated_at ON saga_instances;
CREATE TRIGGER trigger_saga_instances_updated_at
    BEFORE UPDATE ON saga_instances
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();  -- defined in 01-schema.sql

-- ===== done =====
DO $$
BEGIN
    RAISE NOTICE 'OptiCloud billing schema initialized: saga_instances / credit_transactions / idempotency_keys';
END $$;
