#!/usr/bin/env bash
# Story 0.13 — E2E test data cleanup (AC6 / Round 1 R1-5 fix).
# Deletes all users where email LIKE 'e2e-%' — CASCADE removes their api_keys,
# audit_logs (set null), optimizations.

set -euo pipefail

DB_CONTAINER="${OPTICLOUD_PG_CONTAINER:-opticloud-postgres}"
DB_USER="${POSTGRES_USER:-opticloud}"
DB_NAME="${POSTGRES_DB:-opticloud_dev}"

echo "🧹 Cleaning E2E test data from ${DB_NAME}..."

docker exec -i "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" <<'SQL'
BEGIN;

-- 1. Show what we're about to delete
SELECT 'Users to delete' AS step,
       COUNT(*)         AS count
FROM users
WHERE email LIKE 'e2e-%';

-- 2. Delete (ON DELETE CASCADE handles api_keys; audit_logs.user_id is ON DELETE SET NULL)
DELETE FROM users WHERE email LIKE 'e2e-%';

-- 3. Verify
SELECT 'Remaining E2E users' AS step,
       COUNT(*)              AS count
FROM users
WHERE email LIKE 'e2e-%';

COMMIT;
SQL

echo "✅ Cleanup complete."
