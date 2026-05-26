-- OptiCloud — Cost attribution schema (Story M2.3)
-- G3 minimum viable per-tenant / per-service cost telemetry.
-- No FK on tenant_id: M2 uses users.id as tenant surrogate; later org/team tenancy can migrate.

CREATE TABLE IF NOT EXISTS cost_attribution (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL,
    service         VARCHAR(64) NOT NULL,
    cost_unit       VARCHAR(32) NOT NULL,
    value           NUMERIC(18, 6) NOT NULL CHECK (value >= 0),
    source_id       UUID NULL,
    metadata        JSONB NOT NULL DEFAULT '{}'::jsonb,
    recorded_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_cost_attribution_cost_unit
        CHECK (cost_unit IN ('llm_token', 'gpu_second', 'solver_second'))
);

CREATE INDEX IF NOT EXISTS idx_cost_attr_tenant_service_unit_recorded
    ON cost_attribution(tenant_id, service, cost_unit, recorded_at DESC);

CREATE INDEX IF NOT EXISTS idx_cost_attr_source_id
    ON cost_attribution(source_id)
    WHERE source_id IS NOT NULL;

DO $$
BEGIN
    RAISE NOTICE 'OptiCloud cost_attribution schema initialized';
END $$;
