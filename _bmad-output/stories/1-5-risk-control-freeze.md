---
story_key: 1-5-risk-control-freeze
epic_num: 1
epic_name: Account & Identity Management
story_num: 1.5
status: ready-for-dev
priority: 🟠 High (FR A5 — NFR-S6 风控工程化; Epic 1 first new story since 1.4; ~3-4h)
sizing: M (~3-4 hours; backend-only — migration + evaluator + signup integration + 3 admin endpoints + tests)
type: implementation
created_by: bmad-create-story
created_at: 2026-05-19
sources:
  - _bmad-output/planning/epics.md L1307-1311 (Story 1.5 spec — "5 条规则任 2 项触发自动冻结")
  - _bmad-output/planning/prd.md L1631-1638 (NFR-S6 风控冻结条件 5 rules + "任 2 项触发")
  - _bmad-output/planning/prd.md L595-605 (Journey 7 老张 风控冻结申诉 — defines the user-facing arc this story enables)
  - _bmad-output/planning/implementation-readiness-report-2026-05-17-v2.md L236 (NFR-S6 binding)
  - _bmad-output/planning/implementation-readiness-report-2026-05-17-v2.md L324 (Hard Rules: 风控冻结条件)
  - apps/auth-service/src/auth_service/models.py L40-52 (User.is_frozen + User.risk_score columns ALREADY EXIST in schema — story adds the wiring around them)
  - apps/auth-service/src/auth_service/routes.py L77-139 (signup endpoint — primary signal injection point)
  - apps/auth-service/src/auth_service/routes.py L174-313 (otp/request + login — already 403 when is_frozen=true; ready for our trigger to flip the bit)
  - apps/auth-service/src/auth_service/config.py L47-48 (risk_freeze_threshold setting placeholder)
  - infra/local-init/01-schema.sql (users.is_frozen column present)
  - infra/local-init/06-user-otps.sql (recent migration shape to mirror)
dependencies:
  upstream:
    - 1-1a-j1-signup-api-key (done) — signup endpoint + audit_logs (provides the IP-history signal source for R1)
    - 1-2-user-login (done) — login + OTP request both already check `is_frozen` and 403; once we flip the bit, those routes deny access for free
    - 1-3-api-keys-crud-complete (done) — establishes the JWT auth pattern admin endpoints follow
  downstream:
    - 1-7-account-merge-proposal (FR A7) — uses risk_flags as evidence for merge-vs-block decisions
    - 1-11-geo-anomaly-risk-scoring (NFR-S4) — adds the geo-anomaly risk-score input that may later promote to a 6th rule
    - 1-12-j7-fraud-freeze-vertical-slice — depends on 1.5 + 1.7; closes J7 with the full appeal arc
    - Future stories that promote R2-R5 to enabled=true as their signal sources land (fingerprint = FE, 24h-calls = solver-orchestrator telemetry, payment = billing 5.A.6)
---

# Story 1.5 — Risk-Control Auto-Freeze (FR A5)

## User Story

**As** the OptiCloud platform (and the support team behind it),
**I want** 5 risk-detection rules registered against every user, **autoamtically freeze** any account that accumulates ≥2 triggered rules (default freeze = no login, no OTP request), and give support a clean admin surface to manually add risk-flags (covering the rule slots whose signals haven't shipped yet) + un-freeze users after appeal review,
**so that** the NFR-S6 hard rule ("任 2 项触发自动冻结") is engineered into the platform on day one rather than being aspirational — and the J7 appeal arc has a backend to talk to when Story 1.12 wires it up.

## Why this story

The platform's day-1 fraud posture per PRD §2.3:
> 风控冻结条件（任 2 项成立）：设备指纹相似度 ≥ 0.9 / IP /24 同段 / 24h 内调用 ≥ 20 次 / 支付方式重复使用 / 手机号已注册 ≥ 1 账号

The user-table scaffolding is already in place (`User.is_frozen`, `User.risk_score`); both the login and OTP-request endpoints ALREADY 403 when `is_frozen=true` (lines 184-188 + 276-280 of routes.py). What's missing:

1. **The flag log itself** — a `risk_flags` table recording every rule trigger with metadata (which rule, when, why), so support can audit
2. **The evaluator** — a pure function that counts a user's enabled-rule triggers and freezes when ≥2
3. **A wiring at signup** — call the evaluator after each successful signup (auto-detect R1 = IP/24 share)
4. **An admin surface** — `POST /v1/admin/risk-flags` (add a flag), `POST /v1/admin/users/{id}/unfreeze` (clear is_frozen), `GET /v1/admin/risk-flags?user_id=...` (audit). v1 uses a shared-secret header (`X-Admin-Secret`); admin RBAC is M2+.

**Why v1 ships with only R1 enabled (rest defined-but-disabled)**: 4 of the 5 spec rules need signals from systems that haven't shipped yet:
- R2 fingerprint similarity → FE fingerprint header (no FE story slated)
- R3 IP-/24 share → ✅ implementable now via `audit_logs.ip_address` history
- R4 24h call ≥20 → solver-orchestrator telemetry stream (Story 3.x territory)
- R5 payment_reused → billing-service payment-method data (Story 5.A.6)
- R6 phone-already-registered → currently 409s at the UNIQUE constraint; signal exists but is destructive to log against an existing user without consent (privacy posture)

So v1's realistic auto-detect is R3 alone. To still hit the spec's "≥2 triggers freezes" semantics, **admin manual flags count toward the threshold** — the support team can promote a single auto-detected R3 to a freeze by adding a second manual flag after review. As R2/R4/R5/R6 signals land in future stories, they flip `risk_rules.enabled = true` and the system becomes more automatic without further freeze-logic changes.

**Why now (vs deferring)**: Epic 1 hasn't moved since 1.4 (PR #15, 2026-05-19). This is its first new story; lands the FR A5 hard rule data model so subsequent Epic 1 stories (1.7 account-merge / 1.11 geo-anomaly / 1.12 J7 appeal) can build on it. Per memory `feedback_actionable_work`: actionable v1 with a clear v1.5 graduation path is better than holding for all 5 signal sources.

## Out of scope

- **R2/R3/R4/R5/R6 enable** — defined but `enabled=false` in v1 seed; future stories flip them as their signal sources land
- **Admin RBAC / admin users table** — v1 uses shared-secret header (`X-Admin-Secret`, env-loaded); real admin user model is M2+
- **Appeal workflow / J7 UI** — Story 1.12 owns; this story only exposes the data model + manual-flag + unfreeze endpoints needed by it
- **Email/SMS notifications to frozen users** — M3 when notification infra ships; v1 logs to `audit_logs` only
- **Frontend admin console** — backend-only this story; admin uses curl / Postman against the shared-secret endpoints (matches the J1 pattern from 1.1b)
- **risk_score column update** — the existing `users.risk_score` column stays unchanged (set by Story 1.11 geo-anomaly); 1.5 only flips `is_frozen` boolean
- **Rate limiting on admin endpoints** — v1 trusts the shared-secret holder; M3 adds throttling
- **Audit-immutable log of admin actions** — every admin call writes an `audit_logs` row with `actor="admin"`; tamper-evident chains are a separate compliance epic
- **Auto-unfreeze after N days** — v1 freezes are sticky until admin acts; no time-based auto-clear

## Acceptance Criteria

### AC1: New migration `07-risk-control.sql`

Idempotent (same pattern as `06-user-otps.sql`):

```sql
-- Story 1.5 — risk_rules registry + risk_flags log for FR A5 (NFR-S6).
-- Idempotent: safe to re-run.

CREATE TABLE IF NOT EXISTS risk_rules (
    code         VARCHAR(32) PRIMARY KEY,         -- e.g. 'ip_24_share'
    label_zh     VARCHAR(255) NOT NULL,
    description  TEXT NOT NULL,
    enabled      BOOLEAN NOT NULL DEFAULT false,  -- v1 starts with only R3 enabled
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS risk_flags (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id        UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    rule_code      VARCHAR(32) NOT NULL REFERENCES risk_rules(code),
    source         VARCHAR(16) NOT NULL,          -- 'auto' | 'admin'
    metadata       JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_risk_flags_user
    ON risk_flags(user_id);

-- Seed the 5 spec rules + v1 enable=true for R3 only.
INSERT INTO risk_rules (code, label_zh, description, enabled) VALUES
    ('fingerprint_high', '设备指纹相似度 ≥0.9', 'NFR-S6 #1 — needs FE fingerprint header', false),
    ('phone_reused', '手机号已注册 ≥1 账号', 'NFR-S6 #5 — currently 409s at UNIQUE; future variant', false),
    ('ip_24_share', 'IP /24 同段', 'NFR-S6 #2 — counts prior auth.signup audit-log entries sharing the same /24', true),
    ('calls_24h_over_20', '24h 内调用 ≥20 次', 'NFR-S6 #3 — needs solver-orchestrator telemetry', false),
    ('payment_reused', '支付方式重复使用', 'NFR-S6 #4 — needs billing-service payment-method data', false)
ON CONFLICT (code) DO NOTHING;
```

Wiring into CI: add this file to `solver-orchestrator-test` + `auth-service-test` jobs' `psql -f` blocks (CI uses the same fresh schema per run).

### AC2: ORM models

In `apps/auth-service/src/auth_service/models.py`:

```python
class RiskRule(Base):
    """FR A5 — registry of 5 risk-detection rules; v1 seeds enabled only for R3."""

    __tablename__ = "risk_rules"

    code: Mapped[str] = mapped_column(String(32), primary_key=True)
    label_zh: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class RiskFlag(Base):
    """FR A5 — per-event log of rule triggers; ≥2 enabled triggers freezes user."""

    __tablename__ = "risk_flags"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    rule_code: Mapped[str] = mapped_column(
        String(32), ForeignKey("risk_rules.code"), nullable=False
    )
    source: Mapped[str] = mapped_column(String(16), nullable=False)  # 'auto' | 'admin'
    flag_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
```

The `metadata` column uses Python attribute `flag_metadata` (mirrors `AuditLog.audit_metadata` to avoid SQLA reserved-name conflict).

### AC3: Risk evaluator module

New `apps/auth-service/src/auth_service/risk.py`:

```python
"""Story 1.5 — FR A5 risk-detection evaluator.

Pure-ish module: takes a Session + user_id, applies enabled rules, writes
RiskFlag rows for triggers, and flips User.is_frozen when total enabled
triggers across user history ≥ FREEZE_THRESHOLD.

Auto-detection at signup currently fires only R3 (ip_24_share); R1/R2/R4/R5
are defined-but-disabled in v1 (signals not yet available). Admin manual
flags count toward the threshold via the same evaluator path.
"""

FREEZE_THRESHOLD = 2  # NFR-S6 "任 2 项触发"

R3_CODE = "ip_24_share"
R3_MIN_PRIOR_USERS = 3  # ≥3 prior distinct users share the /24 → trigger

async def evaluate_ip_24_share(
    session: AsyncSession, user_id: uuid.UUID, signup_ip: str | None
) -> RiskFlag | None:
    """Returns a RiskFlag (NOT yet added to session) if R3 trips for this signup IP.
    R3 trips when ≥ R3_MIN_PRIOR_USERS prior signups share the same IPv4 /24."""

async def evaluate_signup(
    session: AsyncSession, user_id: uuid.UUID, signup_ip: str | None
) -> list[str]:
    """Apply all ENABLED auto-rules at signup time. Returns list of triggered rule_codes.
    Does NOT add flags or freeze — caller does that via `apply_flags_and_maybe_freeze`."""

async def apply_flags_and_maybe_freeze(
    session: AsyncSession,
    user_id: uuid.UUID,
    new_flags: list[tuple[str, str, dict]],  # (rule_code, source, metadata)
) -> bool:
    """Persist new_flags + count user's ALL distinct ENABLED rule_codes (existing + new).
    If ≥ FREEZE_THRESHOLD distinct enabled rules tripped, flip users.is_frozen=true and
    write an audit_logs row. Returns True iff user was frozen by this call."""
```

Key invariants:
- "Distinct rule_codes" — same rule triggering 10 times still counts as 1 toward threshold (prevents flood-flagging from artificially freezing)
- Only ENABLED rules count (admin flags for disabled rules are still recorded but don't count toward freeze — supports the v1.5 graduation path)
- Freeze action is idempotent (re-evaluating doesn't unfreeze; only admin unfreeze endpoint clears)
- All freeze + flag events write to `audit_logs` with `actor="system"` for auto / `"admin"` for manual

### AC4: Signup wiring

In `routes.py` `signup`:

After the AuditLog `auth.signup` add but BEFORE `return SignupResponse(...)`, add:

```python
# FR A5 — risk evaluation. Pull caller IP from request.client.host (best-effort;
# proxies may be behind X-Forwarded-For — M3 will normalize).
signup_ip = request.client.host if request.client else None
triggered = await risk.evaluate_signup(session, user.id, signup_ip)
new_flags = [(code, "auto", {"signup_ip": signup_ip}) for code in triggered]
if new_flags:
    await risk.apply_flags_and_maybe_freeze(session, user.id, new_flags)
```

The `signup` function gains a `request: Request` parameter (FastAPI dependency).

**Critically**: even if R3 trips on this signup, with only R3 enabled and 1 distinct rule, the user is NOT frozen on first signup. Freeze requires a 2nd distinct enabled rule trigger — which today only comes from admin flagging.

### AC5: Admin endpoints — shared-secret auth

New `apps/auth-service/src/auth_service/admin_routes.py` mounted at `/v1/admin`:

```python
from fastapi import APIRouter, Depends, Header, HTTPException, status
from auth_service.config import settings

admin_router = APIRouter(prefix="/v1/admin", tags=["admin"])

def require_admin_secret(x_admin_secret: str | None = Header(default=None)) -> None:
    """Constant-time compare against settings.admin_secret (Story 5.A.4 pattern).
    Returns None on success; raises 401 on fail. Empty/missing secret → 401."""
    if not settings.admin_secret:
        raise HTTPException(403, "admin endpoints disabled (ADMIN_SECRET not configured)")
    if x_admin_secret is None or not secrets.compare_digest(x_admin_secret, settings.admin_secret):
        raise HTTPException(401, "missing or invalid X-Admin-Secret")
```

Endpoints (all `Depends(require_admin_secret)`):

#### POST /v1/admin/risk-flags
Body: `{user_id: UUID, rule_code: str, metadata?: dict}`
- Looks up RiskRule by code; 404 if unknown
- Inserts RiskFlag with source="admin"
- Calls `apply_flags_and_maybe_freeze` (may freeze if this brings count to ≥2)
- Returns `{flag_id, user_frozen: bool, distinct_enabled_triggers: int}`
- Audit log: `actor="admin", action="risk.flag.add"`

#### POST /v1/admin/users/{user_id}/unfreeze
Body: `{reason: str}` (optional but recommended for audit)
- Looks up User; 404 if unknown
- Sets `is_frozen=false`
- Audit log: `actor="admin", action="user.unfreeze", metadata={reason}`
- Does NOT delete existing risk_flags (audit trail preserved)
- Returns `{user_id, is_frozen: false}`
- v1 idempotent: unfreezing an already-unfrozen user returns 200 cleanly

#### GET /v1/admin/risk-flags?user_id={uuid}
- Returns all RiskFlag rows for the user, ordered by `created_at DESC`
- Shape: `[{id, rule_code, source, metadata, created_at}, ...]`
- 404 if user not found

#### GET /v1/admin/risk-rules
- Returns all RiskRule rows; convenience for ops to see what's enabled
- No body shape — straight list of `{code, label_zh, description, enabled, created_at}`

### AC6: Config

`apps/auth-service/src/auth_service/config.py`:

```python
# ----- Story 1.5 — admin shared-secret (FR A5 admin endpoints) -----
admin_secret: str = Field(
    default="",
    alias="ADMIN_SECRET",
    description="Shared secret for X-Admin-Secret header on /v1/admin/* endpoints. "
                "Empty (default) → admin endpoints return 403. v1 only; M2+ uses real RBAC.",
)
```

Keep the existing `risk_freeze_threshold: float = 0.9` placeholder line — leave it untouched; v1 uses the discrete COUNT threshold (`risk.FREEZE_THRESHOLD = 2`), not a fractional score. Add a comment that the float-based score is reserved for Story 1.11 (geo-anomaly risk-scoring).

### AC7: Tests

New `apps/auth-service/tests/test_risk_freeze.py` — 10 cases:

1. `test_seed_risk_rules_loaded` — fixture verifies migration loaded all 5 rules; only `ip_24_share.enabled` is True
2. `test_signup_alone_does_not_freeze` — single signup → 1 R3 flag (if applicable) → still NOT frozen (count < 2)
3. `test_signup_then_admin_flag_freezes` — signup + admin POST risk-flag (different rule) → user frozen + login 403 + audit_log "system.freeze"
4. `test_admin_flag_unknown_rule_returns_404`
5. `test_admin_flag_missing_secret_returns_401`
6. `test_admin_flag_disabled_rule_does_not_count_toward_freeze` — admin flags `phone_reused` (disabled) → recorded in `risk_flags` but does NOT contribute to count → user still NOT frozen even at 2 flags (1 enabled + 1 disabled)
7. `test_admin_unfreeze_clears_is_frozen` — frozen user + POST unfreeze → is_frozen=false + login succeeds + audit_log "admin.user.unfreeze"
8. `test_admin_unfreeze_preserves_risk_flags` — unfreeze does NOT delete `risk_flags` rows
9. `test_admin_list_flags_returns_history` — GET risk-flags?user_id=X returns all rows for that user, DESC ordered
10. `test_r3_ip24_share_triggers_when_3_priors_same_24` — seed 3 prior users with same /24 IP via audit_logs → 4th signup → R3 fires (returned in `triggered`); single rule still doesn't freeze alone (count=1)

auth-service: **27 → 37** (+10).

### AC8: Quality gates (per `feedback_full_quality_gates`)

- `uv run ruff check .` + `ruff format --check .`
- `uv run mypy apps packages`
- `pnpm -C apps/web typecheck` (no FE work; verify untouched)
- `pnpm -C apps/web build`
- Backend pytest via CI (DR5 local block unchanged)
- CI must include `07-risk-control.sql` in the `psql -f` migration cascade for both `auth-service-test` and `solver-orchestrator-test` jobs (shared schema fixture)

### AC9: NFR alignment

- **FR A5** ✅ — primary deliverable
- **NFR-S6** ✅ — the "任 2 项触发" semantics ship; v1 honors with R3 + admin path
- **NFR-S2** (audit) ✅ — every flag + freeze + unfreeze writes an `audit_logs` row
- **NFR-S4** (API Key异常地理) — orthogonal; Story 1.11 will reuse the same risk_flags table for geo-anomaly evidence
- No new external dependencies (just a shared-secret env var)
- No FE work; no bundle delta

## Tasks

### T1 — DB migration + CI wiring (0.3h)
1. Create `infra/local-init/07-risk-control.sql` per AC1
2. Update `.github/workflows/ci.yml`: add `psql -f infra/local-init/07-risk-control.sql` to `auth-service-test` + `solver-orchestrator-test` jobs

### T2 — ORM models (0.2h)
1. Add `RiskRule` + `RiskFlag` classes to `auth_service/models.py` per AC2

### T3 — Risk evaluator + tests (0.7h)
1. Create `auth_service/risk.py` per AC3 (`FREEZE_THRESHOLD`, `evaluate_ip_24_share`, `evaluate_signup`, `apply_flags_and_maybe_freeze`)
2. Pure-function ip_24_share uses ipaddress.ip_network to compute /24 from `signup_ip`; queries `audit_logs` for prior `auth.signup` IPs

### T4 — Signup wiring (0.3h)
1. Add `request: Request` to `signup` handler signature
2. Insert risk-eval call after AuditLog + before return per AC4

### T5 — Admin endpoints + config (0.6h)
1. Add `admin_secret: str` to `config.py` per AC6
2. Create `auth_service/admin_routes.py` with `require_admin_secret` + 4 endpoints per AC5
3. Mount `admin_router` in `main.py`

### T6 — Tests (0.7h)
1. Create `apps/auth-service/tests/test_risk_freeze.py` with 10 cases per AC7
2. Reuse `apps/auth-service/tests/conftest.py` ASGI fixture pattern from `test_otp_login.py`

### T7 — Quality gates + sprint-status bundled + PR (0.5h)

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Single auto-rule (R3) means v1 freeze NEVER fires without admin intervention — the spec promised "auto" | Documented in story scope. ≥2 of {enabled rules} is the spec; with only R3 enabled, admin manual flag is the second slot. Each future story (1.11 geo-anomaly, 3.x telemetry, 5.A.6 payment) flips one more rule → fully automatic as signals land. The data model + threshold logic ships now so those stories add 1 line each. |
| Admin shared-secret stored in env is weaker than RBAC; if leaked, any user can freeze any account | M3 hard-cap on admin endpoints + real RBAC. v1: secret is in `ADMIN_SECRET` env var, not committed; constant-time compare prevents timing attacks; `audit_logs` row per call gives forensic trail. Documented as DR-1.5. |
| Empty `ADMIN_SECRET` env (dev / CI default) — endpoints 403 — could be silently broken in prod if forgotten | The `require_admin_secret` returns 403 with explicit "admin endpoints disabled (ADMIN_SECRET not configured)" message. Tests explicitly verify the empty-secret 403 path so it can't regress silently. |
| Race: two near-simultaneous admin flag POSTs both see count=1 and neither freezes | `apply_flags_and_maybe_freeze` runs inside the request's transaction; the SELECT + UPDATE happen serially in one session. PostgreSQL default isolation (Read Committed) means each sees the other's INSERTs only post-commit. With 2 concurrent admin POSTs from different ops users, neither sees the other's INSERT in time → both compute count=1 → neither freezes. **Acceptable v1** — support team uses a single console; race window is sub-100ms. M3 will add `SELECT FOR UPDATE` on `users.is_frozen` (or move to advisory locks). Documented as DR-1.5-2. |
| `request.client.host` returns proxy IP not real-user IP behind ALB | M3 will parse `X-Forwarded-For` properly. v1: in local dev `client.host` is the real caller; in prod (behind a proxy) R3 evaluation degrades gracefully (the proxy IP is shared across ALL signups → R3 fires after 3 signups → admin flag still required for freeze). Acceptable v1 surface; documented as DR-1.5-3. |
| The same `audit_logs.ip_address` row history is also touched by Story 1.11 geo-anomaly | Reading is concurrent-safe; both stories only read. 1.11 will add an `audit_logs` row of its own at decision time; doesn't conflict. |
| Admin flag with `metadata` containing PII (e.g. support ticket text) | Documented in API description: `metadata` is JSONB free-form; PII discipline is the admin's responsibility. M3 can add a JSONB scrubber if needed. |
| Migration `INSERT INTO risk_rules ... ON CONFLICT DO NOTHING` doesn't update `enabled` flag if rule already exists with `enabled=false` | Intentional. Future stories enabling R1/R2/R4/R5 will add an `UPDATE risk_rules SET enabled=true WHERE code='...'` in their migration, NOT re-INSERT. Document the convention in 07-risk-control.sql header comment. |
| `is_frozen` already in users table — we don't need a migration for it BUT future stories may want richer freeze state (reason, frozen_at, expires_at) | Out-of-scope. v1 boolean is sufficient for "blocks login". Story 1.7 (account merge) may want a `frozen_at` timestamp; if so, add via an ADD COLUMN migration then. |
| Failure during freeze (e.g., DB connection drop between INSERT risk_flag + UPDATE users.is_frozen) leaves partial state | Both writes are in the SAME session; commit is atomic. Caller commits via `session.commit()`. Documented in `apply_flags_and_maybe_freeze` JSDoc. |
| `audit_logs.audit_metadata` JSONB field already used for many things; adding "freeze_reason" + "triggered_rules" risks namespace collision | Use distinct top-level keys: `{"event_kind": "freeze", "triggered_rules": [...], "actor_source": "system"}`. No collision with existing keys. |
| Tests need to manipulate `audit_logs.ip_address` directly to seed R3 prior-history scenarios | Use raw SQL in test setup (same pattern as Story 1.4 edu-tier raw-SQL seed). Document in test docstring. |

## Definition of Ready

- ✅ `User.is_frozen` column exists in schema (Sprint 0)
- ✅ `audit_logs` table + IP column exist
- ✅ `auth_service/security.py` shared-secret pattern is established (Story 5.A.4 X-Internal-Service-Auth)
- ✅ login + otp/request already 403 when is_frozen=true (Story 1.2)
- ✅ Pydantic Settings env-var pattern (config.py)

## Definition of Done

- 9 ACs pass
- New migration `07-risk-control.sql` lands + CI applies it in 2 jobs
- 2 new ORM models + 1 evaluator module + 4 admin endpoints
- auth-service tests 27 → 37 (+10 in `test_risk_freeze.py`)
- Manual smoke: signup with proxy-set IP that shares /24 with 3 prior users → R3 logged → admin POST risk-flag with rule=phone_reused (or any other) → 200 + `user_frozen: true` → login attempt → 403; admin unfreeze → login succeeds
- CI all green
- Sprint-status update **bundled into this PR's commit** (lesson from 2.5/PR#26)

## Sign-off

| Role | Owner | Signed | Date |
|---|---|:-:|:-:|
| Auth Lead | TBA | ☐ | — |
| Compliance Lead | TBA | ☐ | — |

> Owner committee deferred per M0 skip.

---

## Round 1: BMad Checklist Review

| # | Item | Status | Note |
|---|---|:-:|---|
| 1 | User story has As/I want/so that | ✅ | Platform persona + support persona |
| 2 | ACs testable & BDD-shaped | ✅ | Each AC has concrete schema or test |
| 3 | Scope explicit (in/out) | ✅ | RBAC / notifications / FE console all explicitly out |
| 4 | Dependencies declared | ✅ | upstream 1.1a/1.2/1.3; downstream 1.7/1.11/1.12 |
| 5 | Sizing estimate | ✅ | M (~3-4h); tasks sum to ~3.3h |
| 6 | Risks identified with mitigations | ✅ | 12 risks (including 4 documented as DR-1.5 tech-debt) |
| 7 | Quality gates listed | ✅ | AC8 |
| 8 | Test plan | ✅ | 10 backend tests covering 5 paths × happy/error |
| 9 | Backwards compat | ✅ | Adds tables only; existing users.is_frozen behavior unchanged |
| 10 | Sources cited | ✅ | 10 source files w/ line numbers |

Round 1: **PASS**

---

## Round 2: 5-Perspective Review

### 🏗️ Architect

- ✅ Two tables (`risk_rules` registry + `risk_flags` event log) is the right shape — enables both data-model freezing AND audit replay
- ✅ The `enabled` flag pattern lets future stories flip rules without touching freeze logic — clean v1.5 graduation
- ✅ Same-session transactional commit ensures flag + freeze are atomic
- ⚠️ Admin endpoint cluster (`/v1/admin/*`) is the first admin surface in the platform. Consider whether it should live in a separate `admin-service` from day one. **Decision: NO** for v1 — auth-service is the right home because the data model is colocated and the freeze action mutates auth-domain state. Splitting would require a cross-service write path (more failure modes). M3 can extract if admin RBAC + dashboard grow. Documented as DR-1.5-4.
- ✅ Shared-secret approach mirrors `X-Internal-Service-Auth` from Story 5.A.4 — consistent

### 👨‍💻 Dev

- ✅ Mostly mechanical work; the only novel piece is `evaluate_ip_24_share` using `ipaddress.ip_network(f"{ip}/24", strict=False)`
- ⚠️ `audit_logs.ip_address` is type `INET` — SQL query needs `host(ip_address)` or `text(...)` casting to compare /24 with the new signup IP. **Decision**: do the /24 calculation in Python (Pull all signup IPs from past 30 days, group by /24, count); avoids INET-specific SQL. Sub-1ms for v1 user counts.
- ⚠️ The `Request` injection into signup adds a FastAPI dependency. Existing `signup` doesn't have one; check that test fixtures still work. **Verified**: httpx AsyncClient with ASGITransport synthesizes a client.host; tests need explicit IP injection via mock or scope-override. Add a fixture helper.
- ✅ Reuses Story 1.4's raw-SQL pattern for test setup → no boilerplate

### 🧪 QA

- ✅ 10 tests cover: seed integrity, single-flag-no-freeze, freeze-on-2nd-flag, unfreeze, 401/404 paths, disabled-rule-no-count, audit-trail-preserved
- ⚠️ Add an 11th case: "test_freezing_already_frozen_user_is_noop" — idempotency when flag #3 fires on an already-frozen user. **Decision: SKIP** — `apply_flags_and_maybe_freeze` is idempotent by definition (UPDATE users SET is_frozen=true is harmless if already true). The flag still records (good — audit trail). Adding a test would document idempotency but not catch regression. Drop.
- ⚠️ Consider a race-condition test for two simultaneous admin flags. **Decision: SKIP** — documented as DR-1.5-2; out-of-scope for v1 (single-ops-console assumption). Adding a flaky concurrency test isn't worth it.

### 🔐 Security

- ✅ Constant-time compare on `X-Admin-Secret` (`secrets.compare_digest`) prevents timing attacks
- ✅ Empty-secret → 403 (fail-closed); explicit error message helps ops debugging
- ✅ Admin endpoints log to `audit_logs` for forensics
- ✅ `risk_flags.metadata` is free-form JSONB but doc warns admins not to put PII
- ⚠️ Frozen user can still hit signup endpoint (since signup doesn't auth) — but signup tries to INSERT a duplicate phone, hits 409. **Not a vuln, but document**: freeze persists per phone+email; re-registration is naturally blocked by UNIQUE constraint.
- ✅ Signup IP is sourced server-side via `request.client.host` — user can't spoof it (proxy normalization comes M3)

### 🛠️ SRE

- ✅ Migration is idempotent (CREATE TABLE IF NOT EXISTS + INSERT ON CONFLICT DO NOTHING)
- ✅ CI wiring adds 1 line to 2 jobs — low risk
- ✅ No new external dependencies; no new services
- ⚠️ Admin endpoints need to be added to the load-balancer's allowed paths in prod. **Out of scope** — v1 is local dev / CI only; M3 deploy story will add this
- ✅ No new metrics or alerts (`audit_logs` already covers); future Grafana dashboards can query risk_flags

Round 2: **PASS** with 1 documented architectural decision (admin-service split deferred = DR-1.5-4). No AC changes needed.

---

## Round 3: Dev-Readiness

- ✅ All file paths absolute (`infra/local-init/07-risk-control.sql`, `apps/auth-service/src/auth_service/risk.py`, etc.)
- ✅ Schema fully specified (SQL + Python types)
- ✅ Test names enumerated (10 cases)
- ✅ Reference patterns documented: `06-user-otps.sql` for migration shape; Story 5.A.4 `X-Internal-Service-Auth` for the shared-secret pattern; Story 1.4 raw-SQL for test seed
- ✅ Sizing realistic — ~3.3h per Tasks summation; 3.E.6 came in at ~3h with similar scope (new module + integration + admin-like endpoints)
- ✅ Sprint-status bundling lesson applied (T7)
- ✅ Branch name: `feature/1-5-risk-control-freeze`
- ✅ CI watch: direct `gh pr checks N --watch` + run_in_background, wait ~15s after PR open before launching

Round 3: **PASS — READY FOR DEV**

---

## Implementation Notes

- For T3 IP /24 evaluation: query past 30 days of `audit_logs` rows with `action='auth.signup' AND ip_address IS NOT NULL`, fetch as text via `host(ip_address)::text`, then in Python: `ip_network(f"{ip}/24", strict=False)`. Count distinct user_ids in same /24. If ≥3 prior distinct, R3 trips.
- Empty/null `signup_ip` (test environment, localhost) → R3 skipped silently (returns None). Don't error.
- For T5 admin endpoints: use the same `_log = structlog.get_logger(...)` pattern from routes.py. Log every admin action with key fields (user_id, rule_code, source, decision).
- Mount `admin_router` AFTER `router` in `main.py` (alphabetical / logical order).
- The `risk_freeze_threshold: float = 0.9` setting in config.py is from Sprint 0; leave it but add a comment line above saying "Reserved for Story 1.11 (geo-anomaly risk-scoring); 1.5 uses the discrete COUNT threshold (`risk.FREEZE_THRESHOLD = 2`)."
- Tests must create users via raw INSERT (not via /signup) when they want to control the IP — the /signup endpoint pulls IP from `request.client.host` and we don't want test setup to spoof a header.
- Audit log for system-driven freeze: `actor="system"`, `action="user.freeze"`, `metadata={"triggered_rules": [...], "rule_count": N}`. For admin-driven: `actor="admin"`, `action="user.freeze"` (when flag pushes to 2+) and `action="user.unfreeze"`.

Completion note: "Ultimate context engine analysis complete — FR A5 freeze data model + R3 auto-detect + admin manual-flag path + unfreeze + 10 tests; v1 ships with R3 alone enabled so the v1.5 graduation path (4 more rules) is a 1-line UPDATE statement each."
