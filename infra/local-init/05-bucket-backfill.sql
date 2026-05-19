-- Story 5.A.2 — add bucket column for FR B1 (4 buckets per user).
-- Idempotent: safe to re-run.

ALTER TABLE credit_transactions
    ADD COLUMN IF NOT EXISTS bucket VARCHAR(32) NOT NULL DEFAULT 'monthly';

-- Backfill: tag the existing lazy-seed rows from Story 5.A.1 (j1_demo_seed).
UPDATE credit_transactions
   SET bucket = 'signup'
 WHERE bucket = 'monthly'
   AND metadata ->> 'source' = 'j1_demo_seed';

-- Index for fast per-bucket balance computation (B1 query path).
CREATE INDEX IF NOT EXISTS idx_credit_tx_user_bucket
    ON credit_transactions(user_id, bucket);
