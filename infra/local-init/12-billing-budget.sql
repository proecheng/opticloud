-- Story 5.D.5 — monthly budget alert + automatic pause.
-- Idempotent: safe to re-run.

CREATE TABLE IF NOT EXISTS billing_budget_controls (
    id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id                  UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    monthly_budget_amount    NUMERIC(12, 2) NOT NULL,
    alert_threshold_ratio    NUMERIC(5, 4) NOT NULL DEFAULT 0.8000,
    enabled                  BOOLEAN NOT NULL DEFAULT TRUE,
    status                   VARCHAR(32) NOT NULL DEFAULT 'active',
    paused_at                TIMESTAMPTZ NULL,
    pause_period_start       TIMESTAMPTZ NULL,
    created_at               TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at               TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_billing_budget_controls_amount
        CHECK (monthly_budget_amount >= 1.00 AND monthly_budget_amount <= 9999999.99),
    CONSTRAINT ck_billing_budget_controls_alert_ratio
        CHECK (alert_threshold_ratio > 0 AND alert_threshold_ratio < 1),
    CONSTRAINT ck_billing_budget_controls_status
        CHECK (status IN ('active', 'paused')),
    CONSTRAINT ck_billing_budget_controls_pause_fields
        CHECK (
            (status = 'paused' AND paused_at IS NOT NULL AND pause_period_start IS NOT NULL)
            OR (status = 'active')
        )
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_billing_budget_controls_one_per_user
    ON billing_budget_controls(user_id);

CREATE INDEX IF NOT EXISTS idx_billing_budget_controls_status
    ON billing_budget_controls(status, pause_period_start)
    WHERE enabled = TRUE;

CREATE TABLE IF NOT EXISTS billing_budget_events (
    id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id                  UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    budget_control_id        UUID NOT NULL REFERENCES billing_budget_controls(id) ON DELETE CASCADE,
    period_start             TIMESTAMPTZ NOT NULL,
    period_end               TIMESTAMPTZ NOT NULL,
    event_type               VARCHAR(64) NOT NULL,
    payload                  JSONB NOT NULL DEFAULT '{}'::jsonb,
    occurred_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_billing_budget_events_type
        CHECK (
            event_type IN (
                'billing.budget.configured',
                'billing.budget.disabled',
                'billing.budget.alerted',
                'billing.budget.paused'
            )
        ),
    CONSTRAINT ck_billing_budget_events_period_order
        CHECK (period_end > period_start)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_billing_budget_events_unique_threshold_period_type
    ON billing_budget_events(user_id, period_start, event_type)
    WHERE event_type IN ('billing.budget.alerted', 'billing.budget.paused');

CREATE INDEX IF NOT EXISTS idx_billing_budget_events_user_occurred
    ON billing_budget_events(user_id, occurred_at DESC);

DROP TRIGGER IF EXISTS trigger_billing_budget_controls_updated_at ON billing_budget_controls;
CREATE TRIGGER trigger_billing_budget_controls_updated_at
    BEFORE UPDATE ON billing_budget_controls
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();  -- defined in 01-schema.sql

DO $$
BEGIN
    RAISE NOTICE 'OptiCloud billing schema initialized: billing budget controls/events';
END $$;
