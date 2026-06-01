-- Story 7.A.1: capability-registry v1 schema.
-- Strict-minimal provider/capability schema reservation for v2 provider integration.

CREATE TABLE IF NOT EXISTS capability_providers (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           UUID NULL,
    provider_id         VARCHAR(64) NOT NULL,
    kind                VARCHAR(32) NOT NULL,
    display_name        VARCHAR(120) NOT NULL,
    provider_url        TEXT NOT NULL,
    status              VARCHAR(32) NOT NULL DEFAULT 'active',
    openapi_url         TEXT NULL,
    openapi_sha256      VARCHAR(64) NULL,
    image_digest        TEXT NULL,
    cosign_bundle       JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE capability_providers
    ADD COLUMN IF NOT EXISTS tenant_id UUID NULL,
    ADD COLUMN IF NOT EXISTS openapi_url TEXT NULL,
    ADD COLUMN IF NOT EXISTS openapi_sha256 VARCHAR(64) NULL,
    ADD COLUMN IF NOT EXISTS image_digest TEXT NULL,
    ADD COLUMN IF NOT EXISTS cosign_bundle JSONB NOT NULL DEFAULT '{}'::jsonb;

ALTER TABLE capability_providers
    DROP CONSTRAINT IF EXISTS ck_capability_providers_kind;
ALTER TABLE capability_providers
    ADD CONSTRAINT ck_capability_providers_kind
    CHECK (kind IN ('self', 'open_source', 'external', 'commercial'));

ALTER TABLE capability_providers
    DROP CONSTRAINT IF EXISTS ck_capability_providers_status;
ALTER TABLE capability_providers
    ADD CONSTRAINT ck_capability_providers_status
    CHECK (status IN ('active', 'inactive', 'deprecated'));

ALTER TABLE capability_providers
    DROP CONSTRAINT IF EXISTS ck_capability_providers_provider_id;
ALTER TABLE capability_providers
    ADD CONSTRAINT ck_capability_providers_provider_id
    CHECK (provider_id ~ '^[a-z0-9][a-z0-9-]{0,63}$');

ALTER TABLE capability_providers
    DROP CONSTRAINT IF EXISTS ck_capability_providers_openapi_sha256;
ALTER TABLE capability_providers
    ADD CONSTRAINT ck_capability_providers_openapi_sha256
    CHECK (openapi_sha256 IS NULL OR openapi_sha256 ~ '^[0-9A-Fa-f]{64}$');

ALTER TABLE capability_providers
    DROP CONSTRAINT IF EXISTS ck_capability_providers_image_digest;
ALTER TABLE capability_providers
    ADD CONSTRAINT ck_capability_providers_image_digest
    CHECK (image_digest IS NULL OR image_digest ~ 'sha256:[0-9A-Fa-f]{64}');

CREATE UNIQUE INDEX IF NOT EXISTS uq_capability_providers_global_provider_id
    ON capability_providers(provider_id)
    WHERE tenant_id IS NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_capability_providers_tenant_provider_id
    ON capability_providers(tenant_id, provider_id)
    WHERE tenant_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS capabilities (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           UUID NULL,
    k_algo              VARCHAR(64) NOT NULL,
    task_type           VARCHAR(64) NOT NULL,
    tier                VARCHAR(16) NOT NULL,
    status              VARCHAR(32) NOT NULL,
    provider_id         VARCHAR(64) NOT NULL,
    model_version       VARCHAR(64) NOT NULL,
    supported_solvers   JSONB NOT NULL DEFAULT '[]'::jsonb,
    description_zh      TEXT NOT NULL,
    description_en      TEXT NOT NULL,
    examples            JSONB NOT NULL DEFAULT '[]'::jsonb,
    metadata            JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE capabilities
    ADD COLUMN IF NOT EXISTS tenant_id UUID NULL,
    ADD COLUMN IF NOT EXISTS metadata JSONB NOT NULL DEFAULT '{}'::jsonb;

ALTER TABLE capabilities
    DROP CONSTRAINT IF EXISTS ck_capabilities_k_algo;
ALTER TABLE capabilities
    ADD CONSTRAINT ck_capabilities_k_algo
    CHECK (k_algo ~ '^[a-z0-9][a-z0-9-]{0,63}$');

ALTER TABLE capabilities
    DROP CONSTRAINT IF EXISTS ck_capabilities_tier;
ALTER TABLE capabilities
    ADD CONSTRAINT ck_capabilities_tier
    CHECK (tier ~ '^(T[1-6]|P[1-5])$');

ALTER TABLE capabilities
    DROP CONSTRAINT IF EXISTS ck_capabilities_status;
ALTER TABLE capabilities
    ADD CONSTRAINT ck_capabilities_status
    CHECK (status IN ('v1', 'v1_late', 'v2', 'audited', 'shadow'));

ALTER TABLE capabilities
    DROP CONSTRAINT IF EXISTS ck_capabilities_supported_solvers_array;
ALTER TABLE capabilities
    ADD CONSTRAINT ck_capabilities_supported_solvers_array
    CHECK (jsonb_typeof(supported_solvers) = 'array' AND jsonb_array_length(supported_solvers) >= 1);

ALTER TABLE capabilities
    DROP CONSTRAINT IF EXISTS ck_capabilities_examples_array;
ALTER TABLE capabilities
    ADD CONSTRAINT ck_capabilities_examples_array
    CHECK (jsonb_typeof(examples) = 'array');

CREATE UNIQUE INDEX IF NOT EXISTS uq_capabilities_global_k_algo
    ON capabilities(k_algo)
    WHERE tenant_id IS NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_capabilities_tenant_k_algo
    ON capabilities(tenant_id, k_algo)
    WHERE tenant_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_capabilities_task_type_tier
    ON capabilities(task_type, tier);

CREATE TABLE IF NOT EXISTS capability_tags (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    capability_id       UUID NOT NULL REFERENCES capabilities(id) ON DELETE CASCADE,
    tag                 VARCHAR(64) NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE capability_tags
    DROP CONSTRAINT IF EXISTS ck_capability_tags_tag;
ALTER TABLE capability_tags
    ADD CONSTRAINT ck_capability_tags_tag
    CHECK (tag ~ '^[a-z0-9][a-z0-9_-]{0,63}$');

CREATE UNIQUE INDEX IF NOT EXISTS uq_capability_tags_capability_tag
    ON capability_tags(capability_id, tag);

CREATE INDEX IF NOT EXISTS idx_capability_tags_tag
    ON capability_tags(tag);

CREATE TABLE IF NOT EXISTS provider_oauth_flows (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           UUID NULL,
    provider_id         VARCHAR(64) NOT NULL,
    authorization_url   TEXT NOT NULL,
    token_url           TEXT NOT NULL,
    scopes              JSONB NOT NULL DEFAULT '[]'::jsonb,
    status              VARCHAR(32) NOT NULL DEFAULT 'draft',
    client_id_ref       TEXT NOT NULL,
    client_secret_ref   TEXT NULL,
    vault_secret_ref    TEXT NULL,
    metadata            JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE provider_oauth_flows
    ADD COLUMN IF NOT EXISTS tenant_id UUID NULL,
    ADD COLUMN IF NOT EXISTS vault_secret_ref TEXT NULL,
    ADD COLUMN IF NOT EXISTS metadata JSONB NOT NULL DEFAULT '{}'::jsonb;

ALTER TABLE provider_oauth_flows
    DROP CONSTRAINT IF EXISTS ck_provider_oauth_flows_provider_id;
ALTER TABLE provider_oauth_flows
    ADD CONSTRAINT ck_provider_oauth_flows_provider_id
    CHECK (provider_id ~ '^[a-z0-9][a-z0-9-]{0,63}$');

ALTER TABLE provider_oauth_flows
    DROP CONSTRAINT IF EXISTS ck_provider_oauth_flows_scopes_array;
ALTER TABLE provider_oauth_flows
    ADD CONSTRAINT ck_provider_oauth_flows_scopes_array
    CHECK (jsonb_typeof(scopes) = 'array');

ALTER TABLE provider_oauth_flows
    DROP CONSTRAINT IF EXISTS ck_provider_oauth_flows_status;
ALTER TABLE provider_oauth_flows
    ADD CONSTRAINT ck_provider_oauth_flows_status
    CHECK (status IN ('draft', 'configured', 'disabled'));

CREATE UNIQUE INDEX IF NOT EXISTS uq_provider_oauth_flows_global_provider_id
    ON provider_oauth_flows(provider_id)
    WHERE tenant_id IS NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_provider_oauth_flows_tenant_provider_id
    ON provider_oauth_flows(tenant_id, provider_id)
    WHERE tenant_id IS NOT NULL;

-- Story 7.A.2: revenue-share v2 hook reservation.
-- Strict schema/API hook only; no payout computation or billing-service ownership.

CREATE TABLE IF NOT EXISTS revenue_share_policies (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id               UUID NULL,
    policy_id               VARCHAR(64) NOT NULL,
    provider_kind           VARCHAR(32) NOT NULL,
    platform_share_ratio    NUMERIC(7, 6) NOT NULL,
    provider_share_ratio    NUMERIC(7, 6) NOT NULL,
    status                  VARCHAR(32) NOT NULL DEFAULT 'reserved',
    effective_from          TIMESTAMPTZ NULL,
    effective_until         TIMESTAMPTZ NULL,
    metadata                JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE revenue_share_policies
    ADD COLUMN IF NOT EXISTS tenant_id UUID NULL,
    ADD COLUMN IF NOT EXISTS effective_from TIMESTAMPTZ NULL,
    ADD COLUMN IF NOT EXISTS effective_until TIMESTAMPTZ NULL,
    ADD COLUMN IF NOT EXISTS metadata JSONB NOT NULL DEFAULT '{}'::jsonb;

ALTER TABLE revenue_share_policies
    DROP CONSTRAINT IF EXISTS ck_revenue_share_policies_policy_id;
ALTER TABLE revenue_share_policies
    ADD CONSTRAINT ck_revenue_share_policies_policy_id
    CHECK (policy_id ~ '^[a-z0-9][a-z0-9-]{0,63}$');

ALTER TABLE revenue_share_policies
    DROP CONSTRAINT IF EXISTS ck_revenue_share_policies_provider_kind;
ALTER TABLE revenue_share_policies
    ADD CONSTRAINT ck_revenue_share_policies_provider_kind
    CHECK (provider_kind IN ('self', 'open_source', 'external', 'commercial'));

ALTER TABLE revenue_share_policies
    DROP CONSTRAINT IF EXISTS ck_revenue_share_policies_status;
ALTER TABLE revenue_share_policies
    ADD CONSTRAINT ck_revenue_share_policies_status
    CHECK (status IN ('reserved', 'active', 'deprecated'));

ALTER TABLE revenue_share_policies
    DROP CONSTRAINT IF EXISTS ck_revenue_share_policies_ratio_bounds;
ALTER TABLE revenue_share_policies
    ADD CONSTRAINT ck_revenue_share_policies_ratio_bounds
    CHECK (
        platform_share_ratio >= 0
        AND platform_share_ratio <= 1
        AND provider_share_ratio >= 0
        AND provider_share_ratio <= 1
    );

ALTER TABLE revenue_share_policies
    DROP CONSTRAINT IF EXISTS ck_revenue_share_policies_ratio_sum;
ALTER TABLE revenue_share_policies
    ADD CONSTRAINT ck_revenue_share_policies_ratio_sum
    CHECK (platform_share_ratio + provider_share_ratio = 1.000000);

ALTER TABLE revenue_share_policies
    DROP CONSTRAINT IF EXISTS ck_revenue_share_policies_effective_order;
ALTER TABLE revenue_share_policies
    ADD CONSTRAINT ck_revenue_share_policies_effective_order
    CHECK (
        effective_from IS NULL
        OR effective_until IS NULL
        OR effective_until > effective_from
    );

CREATE UNIQUE INDEX IF NOT EXISTS uq_revenue_share_policies_global_policy_id
    ON revenue_share_policies(policy_id)
    WHERE tenant_id IS NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_revenue_share_policies_tenant_policy_id
    ON revenue_share_policies(tenant_id, policy_id)
    WHERE tenant_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_revenue_share_policies_provider_kind
    ON revenue_share_policies(provider_kind, status);

CREATE TABLE IF NOT EXISTS revenue_share_hooks (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           UUID NULL,
    provider_id         VARCHAR(64) NOT NULL,
    k_algo              VARCHAR(64) NOT NULL,
    policy_id           VARCHAR(64) NOT NULL,
    source_service      VARCHAR(64) NOT NULL,
    source_event_id     UUID NOT NULL,
    billing_saga_id     UUID NULL,
    billing_ledger_id   UUID NULL,
    period_month        CHAR(7) NOT NULL,
    gross_amount_ref    VARCHAR(128) NULL,
    currency            CHAR(3) NOT NULL DEFAULT 'CNY',
    status              VARCHAR(32) NOT NULL DEFAULT 'reserved',
    metadata            JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE revenue_share_hooks
    ADD COLUMN IF NOT EXISTS tenant_id UUID NULL,
    ADD COLUMN IF NOT EXISTS billing_saga_id UUID NULL,
    ADD COLUMN IF NOT EXISTS billing_ledger_id UUID NULL,
    ADD COLUMN IF NOT EXISTS gross_amount_ref VARCHAR(128) NULL,
    ADD COLUMN IF NOT EXISTS metadata JSONB NOT NULL DEFAULT '{}'::jsonb;

ALTER TABLE revenue_share_hooks
    DROP CONSTRAINT IF EXISTS ck_revenue_share_hooks_provider_id;
ALTER TABLE revenue_share_hooks
    ADD CONSTRAINT ck_revenue_share_hooks_provider_id
    CHECK (provider_id ~ '^[a-z0-9][a-z0-9-]{0,63}$');

ALTER TABLE revenue_share_hooks
    DROP CONSTRAINT IF EXISTS ck_revenue_share_hooks_k_algo;
ALTER TABLE revenue_share_hooks
    ADD CONSTRAINT ck_revenue_share_hooks_k_algo
    CHECK (k_algo ~ '^[a-z0-9][a-z0-9-]{0,63}$');

ALTER TABLE revenue_share_hooks
    DROP CONSTRAINT IF EXISTS ck_revenue_share_hooks_policy_id;
ALTER TABLE revenue_share_hooks
    ADD CONSTRAINT ck_revenue_share_hooks_policy_id
    CHECK (policy_id ~ '^[a-z0-9][a-z0-9-]{0,63}$');

ALTER TABLE revenue_share_hooks
    DROP CONSTRAINT IF EXISTS ck_revenue_share_hooks_source_service;
ALTER TABLE revenue_share_hooks
    ADD CONSTRAINT ck_revenue_share_hooks_source_service
    CHECK (source_service ~ '^[a-z0-9][a-z0-9-]{0,63}$');

ALTER TABLE revenue_share_hooks
    DROP CONSTRAINT IF EXISTS ck_revenue_share_hooks_period_month;
ALTER TABLE revenue_share_hooks
    ADD CONSTRAINT ck_revenue_share_hooks_period_month
    CHECK (period_month ~ '^[0-9]{4}-(0[1-9]|1[0-2])$');

ALTER TABLE revenue_share_hooks
    DROP CONSTRAINT IF EXISTS ck_revenue_share_hooks_currency;
ALTER TABLE revenue_share_hooks
    ADD CONSTRAINT ck_revenue_share_hooks_currency
    CHECK (currency ~ '^[A-Z]{3}$');

ALTER TABLE revenue_share_hooks
    DROP CONSTRAINT IF EXISTS ck_revenue_share_hooks_status;
ALTER TABLE revenue_share_hooks
    ADD CONSTRAINT ck_revenue_share_hooks_status
    CHECK (status IN ('reserved', 'captured', 'voided'));

CREATE UNIQUE INDEX IF NOT EXISTS uq_revenue_share_hooks_source_event
    ON revenue_share_hooks(source_service, source_event_id);

CREATE INDEX IF NOT EXISTS idx_revenue_share_hooks_lookup
    ON revenue_share_hooks(tenant_id, provider_id, k_algo, period_month);

CREATE INDEX IF NOT EXISTS idx_revenue_share_hooks_policy_id
    ON revenue_share_hooks(policy_id);
