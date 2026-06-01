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

-- Story 7.B.1: Provider Apply v2 intake contract.
-- Intake-only application/evaluation records; no provider catalog mutation or worker execution.

CREATE TABLE IF NOT EXISTS provider_applications (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id               UUID NULL,
    application_id          VARCHAR(64) NOT NULL,
    requested_provider_id   VARCHAR(64) NOT NULL,
    provider_kind           VARCHAR(32) NOT NULL,
    display_name            VARCHAR(120) NOT NULL,
    organization_name       VARCHAR(160) NOT NULL,
    contact_email           VARCHAR(254) NOT NULL,
    homepage_url            TEXT NULL,
    openapi_url             TEXT NOT NULL,
    openapi_sha256          VARCHAR(64) NOT NULL,
    image_digest            TEXT NOT NULL,
    cosign_bundle           JSONB NOT NULL DEFAULT '{}'::jsonb,
    evaluation_profile      JSONB NOT NULL DEFAULT '{}'::jsonb,
    status                  VARCHAR(32) NOT NULL DEFAULT 'draft',
    submitted_at            TIMESTAMPTZ NULL,
    metadata                JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE provider_applications
    ADD COLUMN IF NOT EXISTS tenant_id UUID NULL,
    ADD COLUMN IF NOT EXISTS homepage_url TEXT NULL,
    ADD COLUMN IF NOT EXISTS submitted_at TIMESTAMPTZ NULL,
    ADD COLUMN IF NOT EXISTS metadata JSONB NOT NULL DEFAULT '{}'::jsonb;

ALTER TABLE provider_applications
    DROP CONSTRAINT IF EXISTS ck_provider_applications_application_id;
ALTER TABLE provider_applications
    ADD CONSTRAINT ck_provider_applications_application_id
    CHECK (application_id ~ '^[a-z0-9][a-z0-9-]{0,63}$');

ALTER TABLE provider_applications
    DROP CONSTRAINT IF EXISTS ck_provider_applications_requested_provider_id;
ALTER TABLE provider_applications
    ADD CONSTRAINT ck_provider_applications_requested_provider_id
    CHECK (requested_provider_id ~ '^[a-z0-9][a-z0-9-]{0,63}$');

ALTER TABLE provider_applications
    DROP CONSTRAINT IF EXISTS ck_provider_applications_provider_kind;
ALTER TABLE provider_applications
    ADD CONSTRAINT ck_provider_applications_provider_kind
    CHECK (provider_kind IN ('external', 'commercial'));

ALTER TABLE provider_applications
    DROP CONSTRAINT IF EXISTS ck_provider_applications_status;
ALTER TABLE provider_applications
    ADD CONSTRAINT ck_provider_applications_status
    CHECK (status IN ('draft', 'submitted'));

ALTER TABLE provider_applications
    DROP CONSTRAINT IF EXISTS ck_provider_applications_contact_email;
ALTER TABLE provider_applications
    ADD CONSTRAINT ck_provider_applications_contact_email
    CHECK (contact_email ~ '^[^@\s]+@[^@\s]+\.[^@\s]+$');

ALTER TABLE provider_applications
    DROP CONSTRAINT IF EXISTS ck_provider_applications_homepage_url;
ALTER TABLE provider_applications
    ADD CONSTRAINT ck_provider_applications_homepage_url
    CHECK (homepage_url IS NULL OR homepage_url ~ '^https?://');

ALTER TABLE provider_applications
    DROP CONSTRAINT IF EXISTS ck_provider_applications_openapi_url;
ALTER TABLE provider_applications
    ADD CONSTRAINT ck_provider_applications_openapi_url
    CHECK (openapi_url ~ '^https?://');

ALTER TABLE provider_applications
    DROP CONSTRAINT IF EXISTS ck_provider_applications_openapi_sha256;
ALTER TABLE provider_applications
    ADD CONSTRAINT ck_provider_applications_openapi_sha256
    CHECK (openapi_sha256 ~ '^[0-9A-Fa-f]{64}$');

ALTER TABLE provider_applications
    DROP CONSTRAINT IF EXISTS ck_provider_applications_image_digest;
ALTER TABLE provider_applications
    ADD CONSTRAINT ck_provider_applications_image_digest
    CHECK (image_digest ~ 'sha256:[0-9A-Fa-f]{64}');

ALTER TABLE provider_applications
    DROP CONSTRAINT IF EXISTS ck_provider_applications_cosign_bundle_object;
ALTER TABLE provider_applications
    ADD CONSTRAINT ck_provider_applications_cosign_bundle_object
    CHECK (jsonb_typeof(cosign_bundle) = 'object');

ALTER TABLE provider_applications
    DROP CONSTRAINT IF EXISTS ck_provider_applications_evaluation_profile_object;
ALTER TABLE provider_applications
    ADD CONSTRAINT ck_provider_applications_evaluation_profile_object
    CHECK (jsonb_typeof(evaluation_profile) = 'object');

ALTER TABLE provider_applications
    DROP CONSTRAINT IF EXISTS ck_provider_applications_metadata_object;
ALTER TABLE provider_applications
    ADD CONSTRAINT ck_provider_applications_metadata_object
    CHECK (jsonb_typeof(metadata) = 'object');

CREATE UNIQUE INDEX IF NOT EXISTS uq_provider_applications_global_application_id
    ON provider_applications(application_id)
    WHERE tenant_id IS NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_provider_applications_tenant_application_id
    ON provider_applications(tenant_id, application_id)
    WHERE tenant_id IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_provider_applications_global_requested_provider_id
    ON provider_applications(requested_provider_id)
    WHERE tenant_id IS NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_provider_applications_tenant_requested_provider_id
    ON provider_applications(tenant_id, requested_provider_id)
    WHERE tenant_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_provider_applications_status
    ON provider_applications(status, requested_provider_id);

CREATE TABLE IF NOT EXISTS provider_application_evaluation_requests (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id               UUID NULL,
    application_row_id      UUID NOT NULL REFERENCES provider_applications(id) ON DELETE CASCADE,
    application_id          VARCHAR(64) NOT NULL,
    evaluation_id           VARCHAR(64) NOT NULL,
    requested_provider_id   VARCHAR(64) NOT NULL,
    benchmark_suite         VARCHAR(64) NOT NULL,
    sample_count            INTEGER NOT NULL,
    timeout_seconds         INTEGER NOT NULL,
    status                  VARCHAR(32) NOT NULL DEFAULT 'requested',
    dataset_refs            JSONB NOT NULL DEFAULT '[]'::jsonb,
    report_ref              TEXT NULL,
    metadata                JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE provider_application_evaluation_requests
    ADD COLUMN IF NOT EXISTS tenant_id UUID NULL,
    ADD COLUMN IF NOT EXISTS report_ref TEXT NULL,
    ADD COLUMN IF NOT EXISTS metadata JSONB NOT NULL DEFAULT '{}'::jsonb;

ALTER TABLE provider_application_evaluation_requests
    DROP CONSTRAINT IF EXISTS ck_provider_application_evaluations_application_id;
ALTER TABLE provider_application_evaluation_requests
    ADD CONSTRAINT ck_provider_application_evaluations_application_id
    CHECK (application_id ~ '^[a-z0-9][a-z0-9-]{0,63}$');

ALTER TABLE provider_application_evaluation_requests
    DROP CONSTRAINT IF EXISTS ck_provider_application_evaluations_evaluation_id;
ALTER TABLE provider_application_evaluation_requests
    ADD CONSTRAINT ck_provider_application_evaluations_evaluation_id
    CHECK (evaluation_id ~ '^[a-z0-9][a-z0-9-]{0,63}$');

ALTER TABLE provider_application_evaluation_requests
    DROP CONSTRAINT IF EXISTS ck_provider_application_evaluations_requested_provider_id;
ALTER TABLE provider_application_evaluation_requests
    ADD CONSTRAINT ck_provider_application_evaluations_requested_provider_id
    CHECK (requested_provider_id ~ '^[a-z0-9][a-z0-9-]{0,63}$');

ALTER TABLE provider_application_evaluation_requests
    DROP CONSTRAINT IF EXISTS ck_provider_application_evaluations_benchmark_suite;
ALTER TABLE provider_application_evaluation_requests
    ADD CONSTRAINT ck_provider_application_evaluations_benchmark_suite
    CHECK (benchmark_suite ~ '^[a-z0-9][a-z0-9_-]{0,63}$');

ALTER TABLE provider_application_evaluation_requests
    DROP CONSTRAINT IF EXISTS ck_provider_application_evaluations_sample_count;
ALTER TABLE provider_application_evaluation_requests
    ADD CONSTRAINT ck_provider_application_evaluations_sample_count
    CHECK (sample_count BETWEEN 1 AND 500);

ALTER TABLE provider_application_evaluation_requests
    DROP CONSTRAINT IF EXISTS ck_provider_application_evaluations_timeout_seconds;
ALTER TABLE provider_application_evaluation_requests
    ADD CONSTRAINT ck_provider_application_evaluations_timeout_seconds
    CHECK (timeout_seconds BETWEEN 1 AND 60);

ALTER TABLE provider_application_evaluation_requests
    DROP CONSTRAINT IF EXISTS ck_provider_application_evaluations_status;
ALTER TABLE provider_application_evaluation_requests
    ADD CONSTRAINT ck_provider_application_evaluations_status
    CHECK (status IN ('requested', 'queued', 'cancelled'));

ALTER TABLE provider_application_evaluation_requests
    DROP CONSTRAINT IF EXISTS ck_provider_application_evaluations_dataset_refs;
ALTER TABLE provider_application_evaluation_requests
    ADD CONSTRAINT ck_provider_application_evaluations_dataset_refs
    CHECK (
        jsonb_typeof(dataset_refs) = 'array'
        AND jsonb_array_length(dataset_refs) >= 1
    );

ALTER TABLE provider_application_evaluation_requests
    DROP CONSTRAINT IF EXISTS ck_provider_application_evaluations_report_ref;
ALTER TABLE provider_application_evaluation_requests
    ADD CONSTRAINT ck_provider_application_evaluations_report_ref
    CHECK (report_ref IS NULL OR report_ref ~ '^(s3|oss|fixture|benchmark|repro)://');

ALTER TABLE provider_application_evaluation_requests
    DROP CONSTRAINT IF EXISTS ck_provider_application_evaluations_metadata_object;
ALTER TABLE provider_application_evaluation_requests
    ADD CONSTRAINT ck_provider_application_evaluations_metadata_object
    CHECK (jsonb_typeof(metadata) = 'object');

CREATE UNIQUE INDEX IF NOT EXISTS uq_provider_application_evaluations_global_eval_id
    ON provider_application_evaluation_requests(application_row_id, evaluation_id)
    WHERE tenant_id IS NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_provider_application_evaluations_tenant_eval_id
    ON provider_application_evaluation_requests(tenant_id, application_row_id, evaluation_id)
    WHERE tenant_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_provider_application_evaluations_application
    ON provider_application_evaluation_requests(application_row_id, status);

-- Story 7.B.2: Provider shadow validation contract and promotion gate.
-- Contract/evidence records only; no provider execution, worker queue, or traffic rollout.

CREATE TABLE IF NOT EXISTS provider_shadow_validation_runs (
    id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id                   UUID NULL,
    application_row_id          UUID NOT NULL REFERENCES provider_applications(id) ON DELETE CASCADE,
    evaluation_row_id           UUID NOT NULL REFERENCES provider_application_evaluation_requests(id) ON DELETE CASCADE,
    application_id              VARCHAR(64) NOT NULL,
    evaluation_id               VARCHAR(64) NOT NULL,
    run_id                      VARCHAR(64) NOT NULL,
    requested_provider_id       VARCHAR(64) NOT NULL,
    benchmark_suite             VARCHAR(64) NOT NULL,
    evaluation_sample_count     INTEGER NOT NULL,
    baseline_provider_id        VARCHAR(64) NOT NULL,
    status                      VARCHAR(32) NOT NULL DEFAULT 'draft',
    started_at                  TIMESTAMPTZ NULL,
    ended_at                    TIMESTAMPTZ NULL,
    summary                     JSONB NOT NULL DEFAULT '{}'::jsonb,
    evidence_refs               JSONB NOT NULL DEFAULT '[]'::jsonb,
    metadata                    JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE provider_shadow_validation_runs
    ADD COLUMN IF NOT EXISTS tenant_id UUID NULL,
    ADD COLUMN IF NOT EXISTS evaluation_sample_count INTEGER NOT NULL DEFAULT 500,
    ADD COLUMN IF NOT EXISTS summary JSONB NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS evidence_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS metadata JSONB NOT NULL DEFAULT '{}'::jsonb;

ALTER TABLE provider_shadow_validation_runs
    DROP CONSTRAINT IF EXISTS ck_provider_shadow_runs_application_id;
ALTER TABLE provider_shadow_validation_runs
    ADD CONSTRAINT ck_provider_shadow_runs_application_id
    CHECK (application_id ~ '^[a-z0-9][a-z0-9-]{0,63}$');

ALTER TABLE provider_shadow_validation_runs
    DROP CONSTRAINT IF EXISTS ck_provider_shadow_runs_evaluation_id;
ALTER TABLE provider_shadow_validation_runs
    ADD CONSTRAINT ck_provider_shadow_runs_evaluation_id
    CHECK (evaluation_id ~ '^[a-z0-9][a-z0-9-]{0,63}$');

ALTER TABLE provider_shadow_validation_runs
    DROP CONSTRAINT IF EXISTS ck_provider_shadow_runs_run_id;
ALTER TABLE provider_shadow_validation_runs
    ADD CONSTRAINT ck_provider_shadow_runs_run_id
    CHECK (run_id ~ '^[a-z0-9][a-z0-9-]{0,63}$');

ALTER TABLE provider_shadow_validation_runs
    DROP CONSTRAINT IF EXISTS ck_provider_shadow_runs_requested_provider_id;
ALTER TABLE provider_shadow_validation_runs
    ADD CONSTRAINT ck_provider_shadow_runs_requested_provider_id
    CHECK (requested_provider_id ~ '^[a-z0-9][a-z0-9-]{0,63}$');

ALTER TABLE provider_shadow_validation_runs
    DROP CONSTRAINT IF EXISTS ck_provider_shadow_runs_baseline_provider_id;
ALTER TABLE provider_shadow_validation_runs
    ADD CONSTRAINT ck_provider_shadow_runs_baseline_provider_id
    CHECK (baseline_provider_id ~ '^[a-z0-9][a-z0-9-]{0,63}$');

ALTER TABLE provider_shadow_validation_runs
    DROP CONSTRAINT IF EXISTS ck_provider_shadow_runs_benchmark_suite;
ALTER TABLE provider_shadow_validation_runs
    ADD CONSTRAINT ck_provider_shadow_runs_benchmark_suite
    CHECK (benchmark_suite ~ '^[a-z0-9][a-z0-9_-]{0,63}$');

ALTER TABLE provider_shadow_validation_runs
    DROP CONSTRAINT IF EXISTS ck_provider_shadow_runs_evaluation_sample_count;
ALTER TABLE provider_shadow_validation_runs
    ADD CONSTRAINT ck_provider_shadow_runs_evaluation_sample_count
    CHECK (evaluation_sample_count BETWEEN 1 AND 500);

ALTER TABLE provider_shadow_validation_runs
    DROP CONSTRAINT IF EXISTS ck_provider_shadow_runs_status;
ALTER TABLE provider_shadow_validation_runs
    ADD CONSTRAINT ck_provider_shadow_runs_status
    CHECK (status IN ('draft', 'running', 'passed', 'failed', 'cancelled'));

ALTER TABLE provider_shadow_validation_runs
    DROP CONSTRAINT IF EXISTS ck_provider_shadow_runs_summary_object;
ALTER TABLE provider_shadow_validation_runs
    ADD CONSTRAINT ck_provider_shadow_runs_summary_object
    CHECK (jsonb_typeof(summary) = 'object');

ALTER TABLE provider_shadow_validation_runs
    DROP CONSTRAINT IF EXISTS ck_provider_shadow_runs_evidence_refs_array;
ALTER TABLE provider_shadow_validation_runs
    ADD CONSTRAINT ck_provider_shadow_runs_evidence_refs_array
    CHECK (jsonb_typeof(evidence_refs) = 'array');

ALTER TABLE provider_shadow_validation_runs
    DROP CONSTRAINT IF EXISTS ck_provider_shadow_runs_metadata_object;
ALTER TABLE provider_shadow_validation_runs
    ADD CONSTRAINT ck_provider_shadow_runs_metadata_object
    CHECK (jsonb_typeof(metadata) = 'object');

CREATE UNIQUE INDEX IF NOT EXISTS uq_provider_shadow_runs_global_run_id
    ON provider_shadow_validation_runs(evaluation_row_id, run_id)
    WHERE tenant_id IS NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_provider_shadow_runs_tenant_run_id
    ON provider_shadow_validation_runs(tenant_id, evaluation_row_id, run_id)
    WHERE tenant_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_provider_shadow_runs_evaluation
    ON provider_shadow_validation_runs(evaluation_row_id, status);

CREATE TABLE IF NOT EXISTS provider_shadow_validation_samples (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id               UUID NULL,
    run_row_id              UUID NOT NULL REFERENCES provider_shadow_validation_runs(id) ON DELETE CASCADE,
    sample_id               VARCHAR(64) NOT NULL,
    coverage_class          VARCHAR(32) NOT NULL,
    dataset_ref             TEXT NOT NULL,
    case_ref                TEXT NOT NULL,
    observed_at             TIMESTAMPTZ NOT NULL,
    provider_status_code    INTEGER NOT NULL,
    provider_latency_ms     INTEGER NOT NULL,
    baseline_latency_ms     INTEGER NOT NULL,
    deviation_ratio         NUMERIC(9, 6) NOT NULL,
    timed_out               BOOLEAN NOT NULL DEFAULT false,
    metadata                JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE provider_shadow_validation_samples
    ADD COLUMN IF NOT EXISTS tenant_id UUID NULL,
    ADD COLUMN IF NOT EXISTS metadata JSONB NOT NULL DEFAULT '{}'::jsonb;

ALTER TABLE provider_shadow_validation_samples
    DROP CONSTRAINT IF EXISTS ck_provider_shadow_samples_sample_id;
ALTER TABLE provider_shadow_validation_samples
    ADD CONSTRAINT ck_provider_shadow_samples_sample_id
    CHECK (sample_id ~ '^[a-z0-9][a-z0-9-]{0,63}$');

ALTER TABLE provider_shadow_validation_samples
    DROP CONSTRAINT IF EXISTS ck_provider_shadow_samples_coverage_class;
ALTER TABLE provider_shadow_validation_samples
    ADD CONSTRAINT ck_provider_shadow_samples_coverage_class
    CHECK (coverage_class IN ('platform_standard', 'provider_supplied', 'adversarial', 'desensitized_real'));

ALTER TABLE provider_shadow_validation_samples
    DROP CONSTRAINT IF EXISTS ck_provider_shadow_samples_dataset_ref;
ALTER TABLE provider_shadow_validation_samples
    ADD CONSTRAINT ck_provider_shadow_samples_dataset_ref
    CHECK (dataset_ref ~ '^(s3|oss|fixture|benchmark|repro)://');

ALTER TABLE provider_shadow_validation_samples
    DROP CONSTRAINT IF EXISTS ck_provider_shadow_samples_case_ref;
ALTER TABLE provider_shadow_validation_samples
    ADD CONSTRAINT ck_provider_shadow_samples_case_ref
    CHECK (case_ref ~ '^(s3|oss|fixture|benchmark|repro)://');

ALTER TABLE provider_shadow_validation_samples
    DROP CONSTRAINT IF EXISTS ck_provider_shadow_samples_status_code;
ALTER TABLE provider_shadow_validation_samples
    ADD CONSTRAINT ck_provider_shadow_samples_status_code
    CHECK (provider_status_code BETWEEN 100 AND 599);

ALTER TABLE provider_shadow_validation_samples
    DROP CONSTRAINT IF EXISTS ck_provider_shadow_samples_provider_latency;
ALTER TABLE provider_shadow_validation_samples
    ADD CONSTRAINT ck_provider_shadow_samples_provider_latency
    CHECK (provider_latency_ms > 0);

ALTER TABLE provider_shadow_validation_samples
    DROP CONSTRAINT IF EXISTS ck_provider_shadow_samples_baseline_latency;
ALTER TABLE provider_shadow_validation_samples
    ADD CONSTRAINT ck_provider_shadow_samples_baseline_latency
    CHECK (baseline_latency_ms > 0);

ALTER TABLE provider_shadow_validation_samples
    DROP CONSTRAINT IF EXISTS ck_provider_shadow_samples_deviation_ratio;
ALTER TABLE provider_shadow_validation_samples
    ADD CONSTRAINT ck_provider_shadow_samples_deviation_ratio
    CHECK (deviation_ratio >= 0 AND deviation_ratio <= 999.999999);

ALTER TABLE provider_shadow_validation_samples
    DROP CONSTRAINT IF EXISTS ck_provider_shadow_samples_metadata_object;
ALTER TABLE provider_shadow_validation_samples
    ADD CONSTRAINT ck_provider_shadow_samples_metadata_object
    CHECK (jsonb_typeof(metadata) = 'object');

CREATE UNIQUE INDEX IF NOT EXISTS uq_provider_shadow_samples_global_sample_id
    ON provider_shadow_validation_samples(run_row_id, sample_id)
    WHERE tenant_id IS NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_provider_shadow_samples_tenant_sample_id
    ON provider_shadow_validation_samples(tenant_id, run_row_id, sample_id)
    WHERE tenant_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_provider_shadow_samples_run
    ON provider_shadow_validation_samples(run_row_id, coverage_class);

-- Story 7.B.3: Provider gradient rollout contract and staged promotion gate.
-- Contract/evidence records only; no live traffic routing, feature flag mutation, or solver routing.

CREATE TABLE IF NOT EXISTS provider_gradient_rollouts (
    id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id                   UUID NULL,
    application_row_id          UUID NOT NULL REFERENCES provider_applications(id) ON DELETE CASCADE,
    evaluation_row_id           UUID NOT NULL REFERENCES provider_application_evaluation_requests(id) ON DELETE CASCADE,
    shadow_run_row_id           UUID NOT NULL REFERENCES provider_shadow_validation_runs(id) ON DELETE CASCADE,
    application_id              VARCHAR(64) NOT NULL,
    evaluation_id               VARCHAR(64) NOT NULL,
    run_id                      VARCHAR(64) NOT NULL,
    rollout_id                  VARCHAR(64) NOT NULL,
    requested_provider_id       VARCHAR(64) NOT NULL,
    baseline_provider_id        VARCHAR(64) NOT NULL,
    benchmark_suite             VARCHAR(64) NOT NULL,
    status                      VARCHAR(32) NOT NULL DEFAULT 'draft',
    current_stage_percent       INTEGER NOT NULL DEFAULT 0,
    stage_history               JSONB NOT NULL DEFAULT '[]'::jsonb,
    shadow_summary_snapshot     JSONB NOT NULL DEFAULT '{}'::jsonb,
    started_at                  TIMESTAMPTZ NULL,
    completed_at                TIMESTAMPTZ NULL,
    paused_at                   TIMESTAMPTZ NULL,
    cancelled_at                TIMESTAMPTZ NULL,
    evidence_refs               JSONB NOT NULL DEFAULT '[]'::jsonb,
    metadata                    JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE provider_gradient_rollouts
    ADD COLUMN IF NOT EXISTS tenant_id UUID NULL,
    ADD COLUMN IF NOT EXISTS stage_history JSONB NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS shadow_summary_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS evidence_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS metadata JSONB NOT NULL DEFAULT '{}'::jsonb;

ALTER TABLE provider_gradient_rollouts
    DROP CONSTRAINT IF EXISTS ck_provider_gradient_rollouts_application_id;
ALTER TABLE provider_gradient_rollouts
    ADD CONSTRAINT ck_provider_gradient_rollouts_application_id
    CHECK (application_id ~ '^[a-z0-9][a-z0-9-]{0,63}$');

ALTER TABLE provider_gradient_rollouts
    DROP CONSTRAINT IF EXISTS ck_provider_gradient_rollouts_evaluation_id;
ALTER TABLE provider_gradient_rollouts
    ADD CONSTRAINT ck_provider_gradient_rollouts_evaluation_id
    CHECK (evaluation_id ~ '^[a-z0-9][a-z0-9-]{0,63}$');

ALTER TABLE provider_gradient_rollouts
    DROP CONSTRAINT IF EXISTS ck_provider_gradient_rollouts_run_id;
ALTER TABLE provider_gradient_rollouts
    ADD CONSTRAINT ck_provider_gradient_rollouts_run_id
    CHECK (run_id ~ '^[a-z0-9][a-z0-9-]{0,63}$');

ALTER TABLE provider_gradient_rollouts
    DROP CONSTRAINT IF EXISTS ck_provider_gradient_rollouts_rollout_id;
ALTER TABLE provider_gradient_rollouts
    ADD CONSTRAINT ck_provider_gradient_rollouts_rollout_id
    CHECK (rollout_id ~ '^[a-z0-9][a-z0-9-]{0,63}$');

ALTER TABLE provider_gradient_rollouts
    DROP CONSTRAINT IF EXISTS ck_provider_gradient_rollouts_requested_provider_id;
ALTER TABLE provider_gradient_rollouts
    ADD CONSTRAINT ck_provider_gradient_rollouts_requested_provider_id
    CHECK (requested_provider_id ~ '^[a-z0-9][a-z0-9-]{0,63}$');

ALTER TABLE provider_gradient_rollouts
    DROP CONSTRAINT IF EXISTS ck_provider_gradient_rollouts_baseline_provider_id;
ALTER TABLE provider_gradient_rollouts
    ADD CONSTRAINT ck_provider_gradient_rollouts_baseline_provider_id
    CHECK (baseline_provider_id ~ '^[a-z0-9][a-z0-9-]{0,63}$');

ALTER TABLE provider_gradient_rollouts
    DROP CONSTRAINT IF EXISTS ck_provider_gradient_rollouts_benchmark_suite;
ALTER TABLE provider_gradient_rollouts
    ADD CONSTRAINT ck_provider_gradient_rollouts_benchmark_suite
    CHECK (benchmark_suite ~ '^[a-z0-9][a-z0-9_-]{0,63}$');

ALTER TABLE provider_gradient_rollouts
    DROP CONSTRAINT IF EXISTS ck_provider_gradient_rollouts_status;
ALTER TABLE provider_gradient_rollouts
    ADD CONSTRAINT ck_provider_gradient_rollouts_status
    CHECK (status IN ('draft', 'active', 'paused', 'completed', 'cancelled'));

ALTER TABLE provider_gradient_rollouts
    DROP CONSTRAINT IF EXISTS ck_provider_gradient_rollouts_stage;
ALTER TABLE provider_gradient_rollouts
    ADD CONSTRAINT ck_provider_gradient_rollouts_stage
    CHECK (current_stage_percent IN (0, 5, 50, 100));

ALTER TABLE provider_gradient_rollouts
    DROP CONSTRAINT IF EXISTS ck_provider_gradient_rollouts_stage_history_array;
ALTER TABLE provider_gradient_rollouts
    ADD CONSTRAINT ck_provider_gradient_rollouts_stage_history_array
    CHECK (jsonb_typeof(stage_history) = 'array');

ALTER TABLE provider_gradient_rollouts
    DROP CONSTRAINT IF EXISTS ck_provider_gradient_rollouts_shadow_summary_object;
ALTER TABLE provider_gradient_rollouts
    ADD CONSTRAINT ck_provider_gradient_rollouts_shadow_summary_object
    CHECK (jsonb_typeof(shadow_summary_snapshot) = 'object');

ALTER TABLE provider_gradient_rollouts
    DROP CONSTRAINT IF EXISTS ck_provider_gradient_rollouts_evidence_refs_array;
ALTER TABLE provider_gradient_rollouts
    ADD CONSTRAINT ck_provider_gradient_rollouts_evidence_refs_array
    CHECK (jsonb_typeof(evidence_refs) = 'array');

ALTER TABLE provider_gradient_rollouts
    DROP CONSTRAINT IF EXISTS ck_provider_gradient_rollouts_metadata_object;
ALTER TABLE provider_gradient_rollouts
    ADD CONSTRAINT ck_provider_gradient_rollouts_metadata_object
    CHECK (jsonb_typeof(metadata) = 'object');

CREATE UNIQUE INDEX IF NOT EXISTS uq_provider_gradient_rollouts_global_rollout_id
    ON provider_gradient_rollouts(shadow_run_row_id, rollout_id)
    WHERE tenant_id IS NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_provider_gradient_rollouts_tenant_rollout_id
    ON provider_gradient_rollouts(tenant_id, shadow_run_row_id, rollout_id)
    WHERE tenant_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_provider_gradient_rollouts_shadow_run
    ON provider_gradient_rollouts(shadow_run_row_id, status, current_stage_percent);
