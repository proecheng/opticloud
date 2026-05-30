-- Story 5.B.1 — billing subscriptions + monthly refill state.
-- Idempotent: safe to re-run.

CREATE TABLE IF NOT EXISTS billing_subscriptions (
    id                           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id                      UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    plan_code                    VARCHAR(32) NOT NULL,
    status                       VARCHAR(32) NOT NULL DEFAULT 'active',
    current_period_start         TIMESTAMPTZ NOT NULL,
    current_period_end           TIMESTAMPTZ NOT NULL,
    last_refilled_period_start   TIMESTAMPTZ NULL,
    metadata                     JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at                   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at                   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_billing_subscriptions_plan_code
        CHECK (plan_code IN ('free', 'starter', 'pro', 'team', 'enterprise')),
    CONSTRAINT ck_billing_subscriptions_status
        CHECK (status IN ('active', 'canceled', 'expired')),
    CONSTRAINT ck_billing_subscriptions_period_order
        CHECK (current_period_end > current_period_start)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_billing_subscriptions_one_active_per_user
    ON billing_subscriptions(user_id)
    WHERE status = 'active';

CREATE INDEX IF NOT EXISTS idx_billing_subscriptions_due
    ON billing_subscriptions(status, current_period_end);

DROP TRIGGER IF EXISTS trigger_billing_subscriptions_updated_at ON billing_subscriptions;
CREATE TRIGGER trigger_billing_subscriptions_updated_at
    BEFORE UPDATE ON billing_subscriptions
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();  -- defined in 01-schema.sql

DO $$
BEGIN
    RAISE NOTICE 'OptiCloud billing schema initialized: billing_subscriptions';
END $$;
