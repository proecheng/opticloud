---
story_key: 1-2-user-login
epic_num: 1
story_num: 1.2
epic_name: Account & Identity
status: ready-for-dev
priority: 🟢 High (demo gap — round-trip incomplete without login; FR A1 partner — signup-only currently)
sizing: M-L (~5 hours; OTP table + 2 endpoints + web 2-step form + tests)
type: implementation
created_by: bmad-create-story
created_at: 2026-05-19
sources:
  - _bmad-output/planning/epics.md L1281 (Story 1.2 — POST /v1/auth/login 手机+邮箱 OTP 双因素)
  - _bmad-output/planning/prd.md (FR A1 双因素;NFR-S TLS + JWT 15min+7d)
  - apps/auth-service/src/auth_service/routes.py L58 (signup endpoint — mirrors pattern)
  - apps/auth-service/src/auth_service/security.py L112 (create_access_token + create_refresh_token already exist)
  - apps/auth-service/src/auth_service/models.py (User model exists)
  - infra/local-init/01-schema.sql (users table; OTP table goes here)
  - apps/web/src/app/auth/signup/page.tsx (signup page pattern to mirror)
dependencies:
  upstream:
    - 0-6-auth-scaffold (done) — User model + JWT mint helpers
    - 1-1a-j1-signup-api-key (done) — signup creates users
  downstream:
    - 1-3-api-keys-crud-complete — list/revoke needs login first
    - 1-5-risk-control-freeze — freeze check enforced at login
---

# Story 1.2 — User Login (OTP 2FA)

## User Story

**As** a 回访用户 who registered earlier
**I want** to log in via `POST /v1/auth/login` with my phone + email + 2 OTPs (one per factor)
**so that** I get a fresh JWT access (15min) + refresh (7d) pair without having to re-register, and the demo's session round-trip is complete (signup → logout → login).

## Why this story

Today the demo path is **signup-only**: a fresh user clicks /auth/signup, gets a JWT pair, uses it once. If they close the tab and come back, they have no way to log back in — the only option is to re-signup, which 409s on the duplicate phone/email. This breaks the "回访" UX and blocks Story 1.3 (API Keys CRUD).

This story adds the missing login endpoint **with the proper 2FA shape** (OTP per factor) so M3 can swap "log OTP to stdout" → "send real SMS+email" without changing the API contract.

## Out of scope

- **Real SMS / email gateway** integration — M3 hard-gate (NIC requires 实名 + provider account); for v1, OTPs are returned inline in the request response when `OTP_DEV_MODE_RETURN=true` (default in dev) OR logged to structured log (always)
- **Captcha / rate-limiting** at the login endpoint — Story 1.5 / 1.11 (NFR-S risk control)
- **Account-frozen lockout check** — Story 1.5 (5-rule risk control)
- **Refresh token rotation** — Story 1.x later (out of FR A1 scope per epics)
- **Password fallback** — by design no password (OTP-only, FR A1 选择)
- **Multi-session management** ("log out other devices") — Story 1.x later
- **WebAuthn / FIDO** — M3+

## Acceptance Criteria

### AC1: Schema — `user_otps` table

`infra/local-init/06-user-otps.sql` (new, idempotent):

```sql
CREATE TABLE IF NOT EXISTS user_otps (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    factor          VARCHAR(16) NOT NULL,   -- 'phone' | 'email'
    code            VARCHAR(10) NOT NULL,   -- 6-digit numeric code
    expires_at      TIMESTAMPTZ NOT NULL,
    used_at         TIMESTAMPTZ NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_user_otps_user_factor_unused
    ON user_otps(user_id, factor) WHERE used_at IS NULL;
```

- Two factors per user per login attempt (phone OTP + email OTP)
- TTL = 5 minutes (`expires_at = NOW() + INTERVAL '5 minutes'`)
- Used OTPs stay in DB for audit (7d retention; cron cleanup is M3)
- Index supports the per-user fast lookup for unused-and-unexpired OTPs

### AC2: `POST /v1/auth/otp/request` endpoint

Request body:
```json
{ "phone": "+8613800138000", "email": "user@example.com" }
```

Behavior:
1. SELECT user where phone=X AND email=Y; if not found → **404** `User Not Found` (do NOT expose whether phone or email mismatched — security best practice)
2. If found:
   - If user.is_frozen=TRUE → **403** `Account Frozen` (Story 1.5 will populate this; we already check the column)
   - Invalidate any prior unused OTPs for this user (`UPDATE user_otps SET used_at=NOW() WHERE user_id=X AND used_at IS NULL`)
   - Generate 2 fresh OTPs (one per factor): `secrets.randbelow(1_000_000)` zero-padded to 6 digits
   - INSERT two `user_otps` rows (phone + email) with TTL 5 min
3. Response:
   - Always returns 200 with `{ "expires_in_seconds": 300, "factors": ["phone", "email"] }`
   - **Dev mode** (`OTP_DEV_MODE_RETURN=true` env, default in `.env.example`): response ALSO includes `{ "dev_phone_otp": "123456", "dev_email_otp": "654321" }` so test fixtures and demo can read codes without an SMS provider
   - Production (`OTP_DEV_MODE_RETURN=false`): codes are only in the structured log line `otp.requested user_id=X factor=phone` — operator must read logs (placeholder until M3 provider integration)
4. Structured log line every request regardless of mode: `auth.otp.requested user_id=X factors=["phone", "email"] ttl_s=300` — observability hook for M3 metric

Auth: **no Bearer required** — this is the pre-login flow.

### AC3: `POST /v1/auth/login` endpoint

Request body:
```json
{
  "phone": "+8613800138000",
  "email": "user@example.com",
  "phone_otp": "123456",
  "email_otp": "654321"
}
```

Behavior:
1. SELECT user where phone=X AND email=Y; if not found → **404** `User Not Found` (same as AC2 — don't leak which one mismatched)
2. If user.is_frozen=TRUE → **403** `Account Frozen`
3. For each factor (phone, email):
   - SELECT user_otps where user_id=X AND factor=F AND used_at IS NULL AND expires_at > NOW() ORDER BY created_at DESC LIMIT 1
   - If none → **401** `OTP Required` (`errors[].field_path="body.<factor>_otp"`)
   - If `row.code != provided_otp` → **401** `OTP Mismatch` + `errors[].field_path` (do not say "phone OTP wrong" vs "email OTP wrong" — combine the message to prevent enumeration)
4. **Both OTPs must verify** (it's 2FA, not 1FA-fallback). Verify BOTH (don't short-circuit) and if either fails, return single 401 with generic message `"Invalid or expired OTP"` — must NOT contain the words "phone" or "email" in the detail (R2 Q1 — prevents attackers from learning which factor matched).
5. On success:
   - UPDATE user_otps SET used_at=NOW() WHERE user_id=X AND factor IN ('phone', 'email') AND used_at IS NULL — invalidates both this and any other still-valid OTPs (prevents replay)
   - Issue JWT pair: `create_access_token(user.id)` + `create_refresh_token(user.id)` (existing helpers from security.py)
   - INSERT AuditLog row (`action="auth.login"`)
6. Response 200:
```json
{
  "user_id": "...",
  "jwt_access": "eyJ...",
  "jwt_refresh": "eyJ...",
  "edu_tier": false
}
```

Note: response shape **matches `SignupResponse` exactly** so the existing web TypeScript helpers can be reused without changes (DRY).

### AC4: Auth schema additions

In `apps/auth-service/src/auth_service/schemas.py`:
```python
class OTPRequestBody(BaseModel):
    phone: str = Field(..., description="E.164 phone")
    email: EmailStr

    @field_validator("phone")
    @classmethod
    def _validate_phone(cls, v: str) -> str:
        if not PHONE_PATTERN.match(v):
            raise ValueError("phone must be E.164")
        return v


class OTPRequestResponse(BaseModel):
    expires_in_seconds: int = 300
    factors: list[Literal["phone", "email"]]
    # Dev-mode only — present when OTP_DEV_MODE_RETURN=true
    dev_phone_otp: str | None = None
    dev_email_otp: str | None = None


class LoginRequest(OTPRequestBody):
    phone_otp: str = Field(..., min_length=6, max_length=6, pattern=r"^\d{6}$")
    email_otp: str = Field(..., min_length=6, max_length=6, pattern=r"^\d{6}$")


# LoginResponse reuses SignupResponse (same shape — DRY)
LoginResponse = SignupResponse
```

### AC5: ORM model — UserOTP

In `models.py`:
```python
class UserOTP(Base):
    __tablename__ = "user_otps"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    factor: Mapped[str] = mapped_column(String(16), nullable=False)
    code: Mapped[str] = mapped_column(String(10), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
```

### AC6: Web — `/auth/login` page

New page `apps/web/src/app/auth/login/page.tsx` with 2-step flow:

**Step 1** — `phone` + `email` inputs + "Request OTP" button
- On submit: `POST /v1/auth/otp/request`; on 200 → switch to Step 2 view, display "(dev mode) phone OTP: 123456, email OTP: 654321" hint when response includes the dev codes
- On 404 → inline error: "No account found for this phone/email"
- On 403 → inline error: "Account frozen, contact support"

**Step 2** — 2 OTP inputs + "Log In" button
- On submit: `POST /v1/auth/login` with all 4 fields
- On 200: write JWT to localStorage (matches /auth/signup pattern), redirect to `/demo/charge` (the only authenticated page so far)
- On 401: inline error: "Invalid or expired OTP, try again"
- "Resend OTP" link → resets to Step 1 view (allows requesting fresh codes)

UI uses existing Tailwind tokens + simple form components (no new Tier 1 needed). Add a nav link in `apps/web/src/app/(homepage components)` to /auth/login (alongside the existing /auth/signup link).

### AC7: SDK helpers in `apps/web/src/lib/api.ts`

```typescript
export interface OTPRequestResponse {
  expires_in_seconds: number;
  factors: ("phone" | "email")[];
  dev_phone_otp?: string;
  dev_email_otp?: string;
}

export async function requestOTP(body: { phone: string; email: string }): Promise<OTPRequestResponse> { ... }

export interface LoginRequest {
  phone: string;
  email: string;
  phone_otp: string;
  email_otp: string;
}

export async function login(body: LoginRequest): Promise<SignupResponse> { ... }
```

Auth-service URL is already wired via `AUTH_SERVICE_URL` constant.

### AC8: Backend tests (auth-service)

**Extend `apps/auth-service/tests/test_security.py`** (or new `test_login_routes.py` if cleaner — pick whichever matches conventions):

1. `test_otp_request_for_unknown_user_returns_404` — POST /otp/request with non-existent (phone, email) → 404
2. `test_otp_request_for_known_user_returns_dev_codes` — signup first; POST /otp/request → 200 with `dev_phone_otp` and `dev_email_otp` 6-digit strings
3. `test_otp_request_invalidates_prior_codes` — request OTP twice for same user; first set of codes can't be used (used_at populated)
4. `test_login_happy_path_returns_jwt_pair` — signup → request OTP → login with correct codes → 200 with `jwt_access` + `jwt_refresh` non-empty
5. `test_login_with_wrong_phone_otp_returns_401` — login with wrong phone_otp (correct email_otp) → 401, message doesn't say which factor failed
6. `test_login_with_expired_otp_returns_401` — set expires_at to past, login → 401
7. `test_login_with_already-used_otp_returns_401` — login once (succeeds); login again with same OTPs → 401 (used_at is now populated)
8. `test_login_frozen_user_returns_403` — manually set is_frozen=TRUE on the user row, then attempt login → 403

### AC9: Quality gates

- `uv run ruff check apps packages` → 0 errors
- `uv run ruff format --check apps packages` → 0 changes needed
- `uv run mypy apps packages` → 0 errors
- `pnpm -C apps/web build` → 0 errors (new /auth/login page)
- All Python regression tests pass; auth-service 4 → 12 (+8)

### AC10: CI workflow update

`.github/workflows/ci.yml` — **only the auth-service-test job** needs `06-user-otps.sql` applied (R1.1 fix — billing/outbox don't touch this table; less CI noise this way):

```yaml
- name: Apply schema
  ...
  run: |
    psql -h localhost -U opticloud -d opticloud_dev -f infra/local-init/01-schema.sql
    psql -h localhost -U opticloud -d opticloud_dev -f infra/local-init/06-user-otps.sql
```

### AC11: NFR alignment

- **FR A1** (signup + login dual-factor) ✅
- **NFR-S** (TLS + JWT 15min+7d) ✅ — re-uses existing security.py helpers
- **NFR-A1** (PIPL): no PII in JWT (only `sub=user_id`)
- **NFR-P1** (HTTP P95 < 300ms): both endpoints budget < 100ms (DB SELECT + JWT mint)
- **NFR-O3** (audit): AuditLog row on every login success

## Tasks

### T1: Schema migration (0.5h)
1. Create `infra/local-init/06-user-otps.sql` per AC1
2. Apply locally via `docker exec opticloud-postgres psql -f //docker-entrypoint-initdb.d/06-user-otps.sql`
3. Verify column structure

### T2: Models + schemas + config (0.5h)
1. Add `UserOTP` ORM model to `models.py`
2. Add `OTPRequestBody`, `OTPRequestResponse`, `LoginRequest` to `schemas.py`; alias `LoginResponse = SignupResponse`
3. Add `otp_dev_mode_return: bool = True` + `otp_ttl_seconds: int = 300` to auth-service `config.py`

### T3: OTP request endpoint (1h)
1. New helper `_lookup_user_by_phone_email(session, phone, email) -> User | None`
2. New helper `_invalidate_unused_otps(session, user_id)` — sets `used_at = NOW()`
3. New helper `_generate_otp() -> str` — `f"{secrets.randbelow(1_000_000):06d}"`
4. POST /v1/auth/otp/request route per AC2
5. Structured log via `structlog`

### T4: Login endpoint (1h)
1. POST /v1/auth/login route per AC3
2. Helper `_verify_otp(session, user_id, factor, provided_code) -> bool` — returns False on missing / expired / mismatch
3. Mint JWT pair via existing `security.create_access_token` + `create_refresh_token`
4. AuditLog row on success

### T5: Backend tests (1h)
1. New `apps/auth-service/tests/test_login_routes.py` per AC8 (8 cases)
2. Inline helper to seed user via SignupRequest then trigger OTP flow
3. Verify all 8 + existing 4 auth tests pass

### T6: Web /auth/login page (1h)
1. Create `apps/web/src/app/auth/login/page.tsx` with 2-step state machine per AC6
2. Extend `apps/web/src/lib/api.ts` with `requestOTP()` + `login()` helpers per AC7
3. Add nav link in welcome / homepage to /auth/login
4. `pnpm build` regression guard

### T7: CI workflow + quality gates + PR (0.5h)
1. Update `.github/workflows/ci.yml` AC10 (auth + billing + outbox migration application)
2. Run all AC9 quality gates
3. Update sprint-status.yaml; commit + push + PR
4. Wait CI green; merge with squash

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| **S1 user enumeration**: 404 for unknown phone+email reveals which accounts exist | **Accepted for v1 demo** — UX > security here; production M3 will switch to 200-always (silently no-op when user doesn't exist). Documented in OpenAPI description. |
| **S2 OTP brute force**: 6-digit code = 10⁶ keyspace | TTL 5min + invalidate-on-use limits the window. Rate-limiting at endpoint = Story 1.5/1.11 (NFR-S). For v1 demo no public exposure → acceptable. |
| Dev-mode returning OTPs in response body could leak to production | `OTP_DEV_MODE_RETURN` defaults to True in `.env.example` (dev), MUST be False in production env. Documented; risk owned by ops at deploy. M3 will add a strict check that refuses to start if both DEV_MODE flag and a "production-marker" env var are true. |
| 6-digit OTP brute-force (10⁶ keyspace) | TTL 5min + rate limit at endpoint (NOT implemented in v1; Story 1.5/1.11 risk control handles). For v1 demo, no public exposure → acceptable. |
| Concurrent OTP requests for same user create multiple unused rows | `_invalidate_unused_otps` runs FIRST in `/otp/request` (before INSERT). Last-write-wins on multiple concurrent requests; older codes invalidated. |
| Phone OTP and email OTP being identical reduces 2FA value | `_generate_otp()` is called twice with fresh `secrets.randbelow()`; ~10⁻⁶ chance of collision. Acceptable for v1; M3 may enforce distinct codes. |
| Web /auth/login page renders dev OTPs in plain text — looks unprofessional | Acceptable for v1 demo — explicitly labeled "(dev mode)". Production deploys with `OTP_DEV_MODE_RETURN=false`, so codes never reach the UI. |
| Migration 06-user-otps.sql conflicts with future 06-* migration | Migrations are flat-numbered; renaming if conflict at merge time. Single contributor for now — low risk. |

## Non-Functional Requirements Mapping

- **FR A1** ✅ AC2-AC3 implement dual-factor login
- **NFR-S** ✅ JWT pair via existing helpers
- **NFR-O3** ✅ AuditLog on success
- **NFR-A1** ✅ no PII in tokens

## Definition of Ready

- ✅ User model + signup exist from 0.6/1.1a
- ✅ JWT mint helpers exist from 0.6
- ✅ AuditLog model exists from 0.6
- ✅ Web /auth/signup page provides UX pattern to mirror
- ✅ All 3 review rounds applied (next step)

## Definition of Done

- All 11 ACs pass
- Test counts: auth-service 4 → 12 (+8)
- CI green on PR (with new 06-user-otps.sql applied in all postgres-dependent jobs)
- sprint-status.yaml: `1-2-user-login: done`
- Memory updated
- Manual smoke: signup → close tab → /auth/login → enter dev OTPs → land on /demo/charge with valid JWT

## Sign-off

| Role | Owner | Signed | Date |
|---|---|:-:|:-:|
| Auth Lead | TBA | ☐ | — |
| Security | TBA | ☐ | — |

> Owner committee deferred per M0 skip.
