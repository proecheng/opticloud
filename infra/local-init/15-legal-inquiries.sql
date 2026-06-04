-- Story 8.C.3 — Team+ legal inquiry SLA records.
-- Idempotent: safe to re-run after 01-schema.sql and 11-billing-subscriptions.sql.

CREATE TABLE IF NOT EXISTS legal_inquiries (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    subscription_id     UUID NULL REFERENCES billing_subscriptions(id) ON DELETE SET NULL,
    plan_code           VARCHAR(32) NOT NULL,
    category            VARCHAR(32) NOT NULL,
    contact_email       VARCHAR(254) NOT NULL,
    company_name        VARCHAR(160) NULL,
    subject             VARCHAR(160) NOT NULL,
    message             TEXT NOT NULL,
    urgency             VARCHAR(16) NOT NULL DEFAULT 'normal',
    status              VARCHAR(32) NOT NULL DEFAULT 'submitted',
    ticket_key          VARCHAR(32) NOT NULL,
    submitted_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    sla_due_at          TIMESTAMPTZ NOT NULL,
    responded_at        TIMESTAMPTZ NULL,
    closed_at           TIMESTAMPTZ NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_legal_inquiries_plan_code
        CHECK (plan_code IN ('team', 'enterprise')),
    CONSTRAINT ck_legal_inquiries_category
        CHECK (
            category IN (
                'pipl',
                'gdpr',
                'graded_protection',
                'data_export',
                'dpa',
                'license',
                'security',
                'other'
            )
        ),
    CONSTRAINT ck_legal_inquiries_urgency
        CHECK (urgency IN ('normal', 'urgent')),
    CONSTRAINT ck_legal_inquiries_status
        CHECK (status IN ('submitted', 'triage_pending', 'responded', 'closed')),
    CONSTRAINT ck_legal_inquiries_contact_email
        CHECK (
            length(contact_email) BETWEEN 3 AND 254
            AND position('@' IN contact_email) > 1
        ),
    CONSTRAINT ck_legal_inquiries_company_name
        CHECK (company_name IS NULL OR length(btrim(company_name)) BETWEEN 1 AND 160),
    CONSTRAINT ck_legal_inquiries_subject
        CHECK (length(btrim(subject)) BETWEEN 3 AND 160),
    CONSTRAINT ck_legal_inquiries_message
        CHECK (length(btrim(message)) BETWEEN 10 AND 4000),
    CONSTRAINT ck_legal_inquiries_ticket_key
        CHECK (ticket_key ~ '^OPTI-LEGAL-[0-9]{8}-[A-F0-9]{6}$'),
    CONSTRAINT ck_legal_inquiries_sla_due
        CHECK (sla_due_at = submitted_at + INTERVAL '24 hours')
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_legal_inquiries_ticket_key
    ON legal_inquiries(ticket_key);

CREATE INDEX IF NOT EXISTS idx_legal_inquiries_user_submitted
    ON legal_inquiries(user_id, submitted_at);

CREATE INDEX IF NOT EXISTS idx_legal_inquiries_status_sla
    ON legal_inquiries(status, sla_due_at);

DROP TRIGGER IF EXISTS trigger_legal_inquiries_updated_at ON legal_inquiries;
CREATE TRIGGER trigger_legal_inquiries_updated_at
    BEFORE UPDATE ON legal_inquiries
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();  -- defined in 01-schema.sql

DO $$
BEGIN
    RAISE NOTICE 'OptiCloud billing schema initialized: legal_inquiries';
END $$;
