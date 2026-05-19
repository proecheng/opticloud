---
story_key: 1-3-api-keys-crud-complete
epic_num: 1
story_num: 1.3
epic_name: Account & Identity
status: ready-for-dev
priority: 🟢 High (FR A2 完整; unblocked by 1.2 login)
sizing: M (~4-5 hours; 3 endpoints already exist from 0.6 — story adds expires_in_days convenience, integration tests, last_used_at tracking, and web management page)
type: implementation + test + UI
created_by: bmad-create-story
created_at: 2026-05-19
sources:
  - _bmad-output/planning/epics.md L1285 (Story 1.3 — API Key CRUD FR A2 完整)
  - _bmad-output/planning/prd.md (FR A2 multi-key + scope + label + expiration)
  - apps/auth-service/src/auth_service/routes.py L325 (existing POST/GET/DELETE — extend)
  - apps/auth-service/src/auth_service/schemas.py (APIKeyCreateRequest — extend)
  - apps/solver-orchestrator/src/solver_orchestrator/auth.py L73 (verify_api_key checks revoked_at + expires_at — add last_used_at update)
  - apps/web/src/app/auth/login/page.tsx (Tier 0 page pattern to mirror)
dependencies:
  upstream:
    - 0-6-auth-scaffold (done) — CRUD endpoints scaffolded
    - 1-1a-j1-signup-api-key (done) — first-time signup creates default key
    - 1-2-user-login (done) — JWT login flow available for management page
  downstream:
    - 1-4-edu-tier-email-whitelist (no FK — independent)
    - any future API consumer (SDK, Postman) — needs full key lifecycle
---

# Story 1.3 — API Keys CRUD complete (FR A2)

## User Story

**As** a developer with multiple environments (dev / staging / prod)
**I want** to **list / create / revoke** API keys via the Web Console, with per-key **label / description / scope / optional expiration**, and revocations to take effect **immediately** on the solver-orchestrator
**so that** I can manage keys per environment without re-creating the account, and a compromised key can be killed without changing my password.

## Why this story

The auth-service CRUD endpoints already exist from Story 0.6 (POST/GET/DELETE /v1/auth/api_keys). What's missing for "FR A2 完整":

1. **No tests** for the endpoints — current auth-service has 4 unit tests on security.py, zero on the CRUD routes
2. **No web UI** — users have no way to manage keys (the signup flow creates one, never seen again)
3. **`expires_in_days` convenience** — spec example shows "expires_in=90d"; current API only accepts absolute datetime
4. **`last_used_at` not updated** — solver checks `revoked_at`/`expires_at` but doesn't write `last_used_at` on successful auth (the column exists but is always NULL)
5. **No integration test proving "revoke 立即生效"** — the AC explicitly demands this; we should test it end-to-end (create key → use against solver → revoke → solver returns 401)

## Out of scope

- **OAuth client_credentials flow** — never; OptiCloud API uses static keys per design
- **Key rotation API** (auto-rotate every 90d) — Story 1.x later
- **Webhook notifications on key revoke** — Story 1.x later
- **Per-key rate limits** — Story 1.5 risk control
- **Scope inheritance / role hierarchy** — flat scopes per FR A2; no roles
- **GUI key generator UX** (showing curl examples, Postman import buttons) — Story 1.1b already covers this for J1; 1.3 just provides the management surface

## Acceptance Criteria

### AC1: `expires_in_days` convenience field

Extend `APIKeyCreateRequest`:
```python
class APIKeyCreateRequest(BaseModel):
    label: str
    description: str | None = None
    scope: list[str] = Field(default_factory=list)
    expires_at: datetime | None = None       # absolute (existing)
    expires_in_days: int | None = Field(default=None, ge=1, le=3650)  # NEW — convenience

    @model_validator(mode="after")
    def _resolve_expiration(self) -> "APIKeyCreateRequest":
        """If expires_in_days set, compute expires_at = NOW + days. Reject if both set."""
        if self.expires_in_days is not None and self.expires_at is not None:
            raise ValueError("set either expires_at OR expires_in_days, not both")
        if self.expires_in_days is not None:
            self.expires_at = datetime.now(UTC) + timedelta(days=self.expires_in_days)
        return self
```

Behaviour:
- Caller can send `expires_in_days=90` and the route persists `expires_at = NOW + 90 days`
- Caller can still send absolute `expires_at` (back-compat)
- Sending BOTH → 422 validation error
- Sending NEITHER → key never expires (existing behavior)

### AC2: `last_used_at` updated on successful auth (solver-orchestrator)

In `apps/solver-orchestrator/src/solver_orchestrator/auth.py:73` (the loop matching HMAC):
```python
if hmac.compare_digest(computed, key_hash):
    # 1.3 — track last_used_at (fire-and-forget UPDATE, OK if it fails)
    await session.execute(
        text("UPDATE api_keys SET last_used_at = NOW() WHERE id = :id"),
        {"id": key_id},
    )
    return user_id_val, key_id, list(scope or [])
```

- Updates ONLY on the matching candidate (no false-positive writes for prefix-collision misses)
- Same session — commits when the parent request commits; no separate transaction
- If the parent request fails downstream, the last_used_at update rolls back too (acceptable — semantically "last successful USE")
- No new SELECT — UPDATE by primary key is cheap (<1ms)

### AC3: Backend tests for CRUD endpoints (auth-service)

**New `apps/auth-service/tests/test_api_keys_routes.py`** — 8 cases:

1. `test_create_api_key_returns_full_key_once` — happy path: POST → 201 + `api_key` field present, 43+ chars, starts with "sk-"; GET returns the row WITHOUT the full key (only prefix)
2. `test_create_api_key_without_auth_returns_401` — POST without Bearer JWT → 401
3. `test_create_api_key_with_invalid_scope_returns_422` — `scope=["bogus:write"]` → 422 with validation error
4. `test_create_api_key_with_expires_in_days_resolves_to_absolute` — `expires_in_days=30` → response's `expires_at` is ~now+30d (within 60s tolerance)
5. `test_create_api_key_with_both_expires_args_returns_422` — both `expires_at` AND `expires_in_days` → 422 "set either... not both"
6. `test_list_api_keys_returns_only_own_keys` — User A creates 2 keys, User B creates 1; A's GET returns 2 (cross-tenant isolation)
7. `test_revoke_own_key_returns_204` — DELETE existing own key → 204; subsequent GET shows it with `revoked_at` populated
8. `test_revoke_other_users_key_returns_404` — User A tries to DELETE User B's key → 404 (NOT 403 — don't leak existence)

### AC4: Cross-service integration test — revoke 立即生效

**Extend `apps/auth-service/tests/test_api_keys_routes.py`** with 1 more:

9. `test_revoke_invalidates_solver_calls_immediately` — DB-level integration:
   - User A creates a key with `scope=["optimize:write"]`
   - Use the key directly against the solver-orchestrator's `verify_api_key()` (import + call; no HTTP server needed) → returns (user_id, key_id, scope) successfully
   - User A revokes the key via DELETE
   - Same `verify_api_key()` call → raises `HTTPException(401)`

This proves the revocation has zero cache delay — the solver re-queries DB on every call (no in-memory cache), and revoked rows are filtered by `if revoked_at is not None: continue`.

### AC5: Tests for `last_used_at` update (solver-orchestrator)

**Extend `apps/solver-orchestrator/tests/test_billing_integration.py`** with 1 case:

10. `test_solver_auth_updates_last_used_at` — call POST /v1/optimizations with a valid key; afterwards `SELECT last_used_at FROM api_keys WHERE id=X` returns a timestamp within the last few seconds (not NULL)

Or alternatively put this in a new `test_solver_auth.py` file scoped to auth concerns. Decision at impl time.

### AC6: Web `/auth/api-keys` management page

New page `apps/web/src/app/auth/api-keys/page.tsx` (requires JWT — redirect to /auth/login if no jwt_access in sessionStorage):

**Layout**:
- Header: "API Keys" + total count + "Create new key" button
- Table:
  - Columns: Label · Prefix · Scope · Created · Last used · Expires · Status (Active / Expired / Revoked) · Actions
  - Empty state: "No keys yet — create your first one"
- Create modal (existing ConfirmationModal or Tier 1 pattern):
  - Fields: Label* / Description / Scope checkboxes (8 options) / Expires-in (90 / 365 / Never)
  - Submit → POST /api_keys → modal shows **full key in copy-once-warning** UI (mimics signup 1.1b)
- Revoke action (per-row):
  - Confirm modal "Revoke key prefix sk-abc? This cannot be undone"
  - On confirm → DELETE /api_keys/{id} → row updates to "Revoked"

**Auth flow**:
- On mount: check `sessionStorage.getItem("jwt_access")`; if absent → router.push("/auth/login")
- All requests include `Authorization: Bearer ${jwt}`

### AC7: SDK helpers in `apps/web/src/lib/api.ts`

```typescript
export interface APIKeyCreateBody {
  label: string;
  description?: string;
  scope: string[];
  expires_in_days?: number;
}

export interface APIKeyListItem {
  id: string;
  prefix: string;
  label: string;
  description: string | null;
  scope: string[];
  expires_at: string | null;
  last_used_at: string | null;
  revoked_at: string | null;
  created_at: string;
}

export interface APIKeyCreateResponse extends APIKeyListItem {
  api_key: string;  // full key, returned ONCE
}

export async function listAPIKeys(jwtAccess: string): Promise<APIKeyListItem[]> { ... }
export async function createAPIKey(jwtAccess: string, body: APIKeyCreateBody): Promise<APIKeyCreateResponse> { ... }
export async function revokeAPIKey(jwtAccess: string, keyId: string): Promise<void> { ... }
```

### AC8: Quality gates

- `uv run ruff check apps packages` → 0 errors
- `uv run ruff format --check apps packages` → 0 changes needed
- `uv run mypy apps packages` → 0 errors
- `pnpm -C apps/web build` → 0 errors (new /auth/api-keys page)
- All Python tests pass; auth-service 12 → 21 (+9 = 8 routes + 1 cross-service)
- solver-orchestrator 12 → 13 (+1 last_used_at)

### AC9: NFR alignment

- **FR A2** ✅ AC1-AC7 — multi-key + label + scope + expiration + revocation
- **NFR-S** ✅ revoked keys cannot be used (existing solver check + new AC4 proves it)
- **NFR-O3** ✅ AuditLog rows for create + revoke (already in routes from 0.6)
- **NFR-P1**: AC2 last_used_at adds ~1ms to solver-orchestrator P95; negligible

## Tasks

### T1: Schema + `expires_in_days` (0.5h)
1. Extend `APIKeyCreateRequest` per AC1 (add field + `_resolve_expiration` validator)
2. Add `timedelta` to imports
3. mypy strict

### T2: Backend tests — CRUD + cross-tenant isolation (1.5h)
1. New `apps/auth-service/tests/test_api_keys_routes.py` per AC3 (cases 1-8)
2. Reuse `http_client` + `_ensure_jwt_keys` fixtures from `conftest.py`
3. Helper `_signup_and_get_jwt(http_client) -> tuple[user_id, jwt_access]` to seed signed-in users

### T3: Cross-service revocation integration test (1h)
1. Add case 9 per AC4 — uses solver-orchestrator's `verify_api_key` directly (import from app code)
2. Skip the HTTP layer — call the Python function with a DB session

### T4: last_used_at update on auth (0.5h)
1. Edit `apps/solver-orchestrator/src/solver_orchestrator/auth.py` per AC2
2. Add case 10 in `test_billing_integration.py` per AC5

### T5: Web /auth/api-keys page (1.5h)
1. Create new page per AC6
2. Extend `lib/api.ts` per AC7
3. Reuse existing `ConfirmationModal` for create-with-copy-once + revoke confirmation
4. Add nav link from /auth/signup success page (or homepage)
5. `pnpm build` regression

### T6: Quality gates + sprint sync + PR (0.5h)
1. Run AC8 gates
2. Update sprint-status.yaml `1-3: done`
3. Commit + push + PR
4. CI green → squash merge

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| `last_used_at` UPDATE on every request adds DB write to hot path | UPDATE-by-PK is <1ms; no index changes. Acceptable for v1. M3 may batch via Redis if traffic grows. |
| `expires_in_days` validator computes `datetime.now()` at request time — clock skew? | Acceptable; ±1s skew is invisible to users selecting "90 days". M3 with NTP discipline ok. |
| Cross-tenant isolation test relies on User A and User B both being signed up in the same test — fixture order matters | Use fresh uuids per test; signup helper handles uniqueness |
| AC4 imports solver-orchestrator's `verify_api_key` from auth-service tests — cross-package import | OK because both share the `users`/`api_keys` tables; solver's auth.py uses raw SQL (no ORM models from auth-service). Just import the function and pass an auth-service session. |
| Web /auth/api-keys page is gated by JWT, but session might expire — user lands on blank page | Redirect-to-login on 401 already pattern from /demo/charge. Add explicit check on mount. |
| Default scope on create — if user doesn't check any boxes, key is unusable (no scope) | Web defaults all 8 scopes off; backend allows empty scope (no error). User must check at least one for usefulness — UI hints "Select at least one scope". |

## Non-Functional Requirements Mapping

- **FR A2** ✅ multi-key with full lifecycle
- **NFR-S** ✅ revoke 立即生效 verified by AC4
- **NFR-O3** ✅ AuditLog (existing)
- **NFR-P1** ✅ negligible new latency

## Definition of Ready

- ✅ CRUD endpoints scaffolded from 0.6
- ✅ Auth tests infrastructure from 1.2 (conftest.py)
- ✅ Web /auth/login from 1.2 provides JWT-in-storage pattern
- ✅ ConfirmationModal Tier 1 from 0.9 (5 variants)
- ✅ All 3 review rounds applied (next step)

## Definition of Done

- All 9 ACs pass
- Test counts: auth-service 12 → 21 (+9), solver 12 → 13 (+1) → total +10
- CI green on PR (no new schema migrations)
- sprint-status.yaml: `1-3-api-keys-crud-complete: done`
- Memory updated
- Manual smoke: login → /auth/api-keys → create key with 90d expiry → copy → revoke → verify solver rejects

## Sign-off

| Role | Owner | Signed | Date |
|---|---|:-:|:-:|
| Auth Lead | TBA | ☐ | — |
| Solver Lead | TBA | ☐ | — |

> Owner committee deferred per M0 skip.
