# auth-service

OptiCloud Auth Service — **Story 0.6 (Sprint 0 N1 unlock node)**.

**FR coverage**: A1 (signup) + A2 (API Keys CRUD) — partial. Full A1-A10 in Epic 1 (M1).

## Quickstart

```bash
# 1. From repo root, ensure infra is up
cd ../..
docker-compose up -d postgres redis vault

# 2. Sync deps (uv workspace)
uv sync

# 3. Run service
cd apps/auth-service
uv run uvicorn auth_service.main:app --reload --port 8001

# 4. Test signup
curl -X POST http://localhost:8001/v1/auth/signup \
  -H "Content-Type: application/json" \
  -d '{"phone":"+8613800138000","email":"test@example.com","age_years":18}'

# Response (201):
# {"user_id":"...","jwt_access":"eyJ...","jwt_refresh":"eyJ...","edu_tier":false}

# 5. Test api_keys.create (use jwt_access from above)
curl -X POST http://localhost:8001/v1/auth/api_keys \
  -H "Authorization: Bearer <jwt_access>" \
  -H "Content-Type: application/json" \
  -d '{"label":"test","scope":["optimize:write"]}'

# Response (201):
# {"id":"...","api_key":"sk-...","prefix":"sk-XXX","hash_preview":"...","label":"test",...}

# 6. OpenAPI / docs
open http://localhost:8001/docs
```

## Architecture references

- **FR A1-A10** — PRD §FR.1 (10 FR)
- **D7** API Key HMAC-SHA256 with Vault pepper
- **D8** JWT Ed25519 (15min access + 7day refresh)
- **C9** Postgres TDE + Vault dev mode
- **CRG1** Performance baseline (signup P95 <800ms / api_keys.create P95 <300ms)
- **CRG4** Pepper 季度 Vault HSM 轮换 + grace 30d
- **CRG12** API Key mask + Reveal toggle in Web UI (Story 1.1b)

## TODO (Sprint 0 N1 完成度 60% → 100%)

- [ ] Alembic migrations (currently relying on infra/local-init/01-schema.sql for dev only)
- [ ] OTP 双因素验证（短信 + 邮件）— Story 1.x
- [ ] Risk scoring middleware (FR A5)
- [ ] PIPL 7 day hard-delete cron (FR A6) — Story 1.6
- [ ] API Key Bearer auth middleware（除 JWT 外）
- [ ] Performance baseline 验证 Locust 压测
- [ ] CRG4 Vault pepper integration (currently env-var dev fallback only)
