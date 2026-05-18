# solver-orchestrator

OptiCloud Solver Orchestrator — **Story 2.1 + 3.1**.

**Implemented**:
- `GET /v1/algorithms` (FR C1, public) — 8 SKU catalog
- `GET /v1/algorithms/{k_algo}` (FR C2)
- `POST /v1/optimizations` (FR E1 + E3 + E7 + E9) — **HiGHS LP solve**
- `GET /v1/optimizations/{id}` (FR E9)

**Planned** (M1-M5): VRPTW (OR-Tools) / Schedule (CP-SAT) / Forecast (Chronos) / AQGS-ACOPF.

## Quickstart

```bash
cd D:\优化预测网站
uv sync --all-packages   # install highspy + numpy
docker exec -i opticloud-postgres psql -U opticloud -d opticloud_dev < infra/local-init/02-solver-schema.sql

# Start (port 8002)
PYTHONPATH="D:\\优化预测网站\\packages\\shared-py;D:\\优化预测网站\\apps\\solver-orchestrator\\src;D:\\优化预测网站\\packages\\python-sdk\\src" \
  .venv/Scripts/python.exe -m uvicorn solver_orchestrator.main:app --port 8002
```

## Demo

```bash
# 1. List algorithms (public, no auth)
curl http://localhost:8002/v1/algorithms

# 2. LP solve (use sk-xxx from auth-service signup)
curl -X POST http://localhost:8002/v1/optimizations \
  -H "Authorization: Bearer sk-xxx" \
  -H "Idempotency-Key: $(uuidgen)" \
  -H "Content-Type: application/json" \
  -d '{"task_type":"lp","minimize":{"c":[1,1]},"st":{"A":[[1,1]],"b":[10]}}'

# Expected response (200):
# {
#   "optimization_id":"...",
#   "status":"completed",
#   "solution":{"x":[0.0,0.0]},
#   "objective":0.0,
#   "model_version":{"provider_id":"highs","kind":"open_source","version":"1.7.0",
#                    "provider_url":"https://highs.dev/"},
#   "solve_seconds":0.001,
#   ...
# }
```

## ACs

- ✅ **FR C1**: public algorithms catalog
- ✅ **FR E1**: LP submission
- ✅ **FR E3**: sync mode (≤5s)
- ✅ **FR E7**: RFC 7807 errors[] + next_action_url + i18n hint key
- ✅ **FR E9**: status + solve_seconds + model_version with provider_url (A-S1)
- ✅ **D7 + CRG4**: Bearer API Key HMAC verification + pepper_version
- ✅ **CRG2**: HiGHS pre-warm at startup; warm-start < 200ms
- ✅ **P23**: Idempotency-Key 24h dedup
- ✅ **Q-T1**: mock-real divergence test (schema parity)
- 🟡 **scope check** (`optimize:write`) — enforced; UI/SDK return clean 403

## Architecture refs

- `solvers.py` HiGHS wrapper + prewarm (Concern #1 — Auth-First via auth.py)
- `catalog.py` static catalog (Architecture B1: M1-M2 static; M3+ capability-registry)
- `auth.py` shared HMAC pepper with auth-service (D7 + CRG4)
