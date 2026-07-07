# Plan: JWT Plan Alignment and Best Practices

## Goal

Make the current JWT authentication mechanism conform to the workspace JWT plan and practical security best practices, without replacing the existing architecture.

Primary references:

- `docs/plans/2026-05-12-jwt-implementation.md`
- `PRD_JWT_Implementation_Chatbot_SPBE.md`
- `JWT_Implementation_Quick_Reference.md`
- Current implementation:
  - `backend/app/auth/jwt_manager.py`
  - `backend/app/api/auth_routes.py`
  - `backend/app/dependencies/auth_dependencies.py`
  - `frontend/src/services/api.js`
  - `frontend/src/services/auth.js`

## Scope

### Include

- Rolling refresh token rotation.
- Refresh token blacklist/revocation.
- Consistent access-token claims between login and refresh.
- Secure refresh-cookie attributes.
- Production JWT secret validation.
- PBAC enforcement audit and application to sensitive endpoints.
- Backend tests for login, refresh, logout, blacklist, and PBAC.
- Frontend compatibility with refresh/logout behavior.
- Docker production verification.

### Exclude

- Full LDAP/Active Directory rollout.
- Redis session store migration.
- Admin force-logout UI.
- Large auth UI redesign.
- Unrelated RAG/chat behavior changes.

## Current State Summary

Already implemented:

- Access token creation with `exp`, `iat`, `jti`, `type`.
- Refresh token creation with `exp`, `iat`, `jti`, `type`.
- HS256 verification with explicit allowed algorithm.
- Login endpoint returns access token and sets refresh cookie.
- Logout blacklists current access token.
- `get_current_user` checks Bearer token and token blacklist.
- `require_roles` exists for PBAC.
- Frontend stores access token and attaches `Authorization: Bearer ...`.
- Frontend retries refresh on `401`.

Known gaps:

- Refresh endpoint does not rotate refresh token.
- Refresh token `jti` is not checked against blacklist.
- Refresh token old `jti` is not revoked after use.
- Refreshed access token claims are incomplete and inconsistent.
- Refresh cookie does not explicitly set `path=/api/auth/refresh`.
- `delete_cookie()` does not guarantee same path as `set_cookie()`.
- Production may still use default development `JWT_SECRET_KEY`.
- `require_roles` exists but is not broadly enforced on sensitive endpoints.
- There is no endpoint-level auth coverage audit.

## Target Design

### Token model

Access token claims should consistently include:

```json
{
  "sub": "admin@bssn.go.id",
  "username": "Admin PUSDATIK",
  "roles": ["admin_pusdatik"],
  "dept": "PUSDATIK",
  "sid": "uuid-session-id",
  "auth_provider": "local",
  "type": "access",
  "iat": 1770000000,
  "exp": 1770028800,
  "jti": "uuid-token-id"
}
```

Refresh token claims should include:

```json
{
  "sub": "admin@bssn.go.id",
  "sid": "uuid-session-id",
  "type": "refresh",
  "iat": 1770000000,
  "exp": 1770604800,
  "jti": "uuid-token-id"
}
```

### Refresh behavior

`POST /api/auth/refresh` should:

1. Read refresh token from HttpOnly cookie.
2. Verify signature, expiry, required claims, and `type == "refresh"`.
3. Check refresh token `jti` is not blacklisted.
4. Load user from DB.
5. Create new access token with full claims.
6. Create new refresh token with same `sid` or intentionally new `sid` if policy requires.
7. Blacklist old refresh token `jti` until its original expiry.
8. Set new refresh cookie.
9. Return new access token.
10. Log audit event.

### Cookie policy

For refresh token cookie:

```python
httponly=True
secure=settings.ENVIRONMENT.lower() == "production"
samesite="strict" if secure else "lax"
path="/api/auth/refresh"
max_age=7 * 24 * 60 * 60
```

For logout deletion, use the same path:

```python
response.delete_cookie("refresh_token", path="/api/auth/refresh")
```

### Blacklist model

Reuse existing `TokenBlacklist`:

- access token `jti` blacklisted on logout.
- refresh token `jti` blacklisted on refresh rotation.
- blacklist rows expire naturally by `expires_at`.

Optional cleanup can be added later but is not required for correctness.

### PBAC model

Keep dependency-based FastAPI protection.

Rules:

- Public endpoints: health, docs, login, refresh.
- Authenticated endpoints: chat, sessions, model selection, user profile.
- Admin-only endpoints: document upload/delete, destructive document management, audit inspection if exposed.

Dependency-based auth is acceptable only if every sensitive endpoint is explicitly covered.

## Implementation Tasks

### Task 1 — Add JWT/auth test coverage before changing behavior

Files:

- `backend/tests/test_jwt_manager.py`
- `backend/tests/test_auth_api.py`
- `backend/tests/test_pbac.py`

Add or extend tests for:

- access token contains required claims.
- refresh token contains required claims.
- `alg=none` or wrong algorithm is rejected.
- login returns access token and sets refresh cookie.
- refresh returns new access token.
- refresh rotates refresh cookie.
- old refresh token is rejected after rotation.
- logout blacklists access token.
- blacklisted token is rejected by `get_current_user`.
- invalid role gets `403`.

Acceptance criteria:

- Tests fail before implementation for missing rotation/claim behavior.
- Existing passing tests remain valid.

### Task 2 — Refactor token claim construction into shared helpers

Files:

- `backend/app/api/auth_routes.py`
- optional new helper: `backend/app/auth/token_claims.py`

Create helper functions:

- `build_access_token_data(user, roles, session_id)`
- `build_refresh_token_data(user, session_id)`

Requirements:

- Login and refresh must use the same access-token claim builder.
- `roles` must be parsed array, not JSON string.
- `sid` must persist across refresh unless explicitly changed.

Acceptance criteria:

- Login and refresh produce access tokens with matching required claim shape.

### Task 3 — Implement refresh token blacklist checking

Files:

- `backend/app/api/auth_routes.py`
- optional helper in auth dependency/service layer.

Behavior:

- Extract refresh token `jti`.
- Query `TokenBlacklist`.
- If present, return `401 Invalid refresh token`.

Acceptance criteria:

- A blacklisted refresh token cannot be used.
- Audit log records refresh failure if practical.

### Task 4 — Implement rolling refresh token rotation

Files:

- `backend/app/api/auth_routes.py`

Behavior:

- After a successful refresh, insert old refresh token `jti` into `TokenBlacklist` with its original expiry.
- Issue a new refresh token.
- Set the new refresh token cookie.
- Return new access token.

Acceptance criteria:

- First refresh succeeds.
- Reusing the old refresh cookie fails with `401`.
- New refresh cookie can refresh again.

### Task 5 — Harden refresh cookie attributes

Files:

- `backend/app/api/auth_routes.py`

Changes:

- Add `path="/api/auth/refresh"` to `set_cookie()`.
- Add the same `path` to `delete_cookie()`.
- Keep `httponly=True`.
- Keep `secure=True` in production.
- Keep `samesite="strict"` in production unless Cloudflare/browser behavior requires `lax`.

Acceptance criteria:

- Browser stores refresh cookie after login.
- Refresh request includes cookie.
- Logout clears cookie.

### Task 6 — Add production secret guardrail

Files:

- `backend/app/config.py`
- `.env.docker.example`
- docs if needed.

Behavior:

- Add `JWT_SECRET_KEY` to `.env.docker.example` with instruction to generate a random value.
- On startup, if `ENVIRONMENT=production` and `JWT_SECRET_KEY` equals the default development value, fail fast or log a critical error and refuse auth startup.

Suggested generation command:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Acceptance criteria:

- Production deployment cannot silently use default JWT secret.
- Local development remains easy.

### Task 7 — Audit and apply endpoint authentication/PBAC

Files to inspect:

- `backend/app/api/routes/chat.py`
- `backend/app/api/routes/sessions.py`
- `backend/app/api/documents.py`
- `backend/app/api/rag_documents.py`
- `backend/app/api/routes/models.py`
- `backend/app/api/routes/users.py`

Classify endpoints:

| Endpoint type | Auth rule |
|---|---|
| `/api/health` | public |
| `/api/auth/login` | public |
| `/api/auth/refresh` | public but refresh-cookie required |
| chat/session read/write | authenticated |
| document upload/delete/sync | admin or configured role |
| document read/citation/PDF | authenticated unless intentionally public |
| model selection | admin or authenticated depending product decision |

Apply:

- `Depends(get_current_user)` for authenticated routes.
- `Depends(require_roles([...]))` for role-protected routes.

Acceptance criteria:

- Unauthenticated sensitive routes return `401`.
- Authenticated user can access allowed routes.
- User lacking role gets `403`.

### Task 8 — Frontend refresh/logout compatibility verification

Files:

- `frontend/src/services/api.js`
- `frontend/src/services/auth.js`

Check:

- Refresh request uses same origin and `withCredentials=true`.
- Retry loop cannot infinite-loop.
- Logout sends Bearer token before clearing local token.
- Login works on Cloudflare Tunnel origin.

Acceptance criteria:

- Expired access token triggers one refresh and retries original request.
- Failed refresh redirects to `/login`.
- Logout clears local token and refresh cookie server-side.

### Task 9 — Migration and DB compatibility check

Files:

- existing migrations under `backend/scripts/migrations/`
- `backend/app/main.py`

Check:

- Existing `TokenBlacklist` table exists for old DBs.
- Existing users have `auth_provider` and `external_id` columns.
- Migration runner executes all numbered migrations.

Acceptance criteria:

- Existing production SQLite DB starts without auth schema errors.
- Login works after restart/rebuild.

### Task 10 — End-to-end verification

Run backend tests:

```powershell
docker compose --env-file .env.docker -f docker-compose.prod.yml exec backend pytest tests/test_jwt_manager.py tests/test_auth_api.py tests/test_pbac.py -v
```

Run manual API smoke tests:

```powershell
# Login
Invoke-RestMethod -Method Post -Uri "http://localhost/api/auth/login" -ContentType "application/x-www-form-urlencoded" -Body "username=admin%40bssn.go.id&password=password123"

# Health
Invoke-RestMethod http://localhost/api/health
```

Manual browser tests:

- Login with `admin@bssn.go.id / password123`.
- Open chat page.
- Refresh page; auth should remain valid if access token still exists.
- Force access token expiry in test or use short expiry env to verify refresh path.
- Logout; protected routes should redirect or return unauthorized.

Cloudflare quick tunnel verification:

```powershell
docker run --rm -it cloudflare/cloudflared:latest tunnel --url http://host.docker.internal:80
```

Acceptance criteria:

- Local and tunnel login work.
- Refresh works over tunnel HTTPS.
- Logout works over tunnel HTTPS.
- Protected endpoints reject unauthenticated access.

## Risk Notes

- Setting refresh cookie `SameSite=Strict` is secure, but if Cloudflare/browser behavior causes refresh cookie not to be sent, fallback to `SameSite=Lax` may be required. Do not use `None` unless cross-site embedding is intentionally required and `Secure=True` is guaranteed.
- Rolling refresh token with SQLite is acceptable for this app scale, but high concurrency may need transaction handling to avoid race conditions.
- If multiple browser tabs refresh simultaneously, one tab may rotate the refresh token and another may fail. This is expected but should redirect cleanly.
- PBAC enforcement can break existing frontend flows if endpoints assumed public access. Apply in small batches with tests.

## Done Definition

- Automated tests cover login, refresh rotation, blacklist, logout, and PBAC.
- Login access token and refreshed access token have consistent claims.
- Refresh token rotation invalidates old refresh tokens.
- Refresh and logout cookie paths are consistent.
- Production JWT secret cannot remain default silently.
- Sensitive endpoints are either protected or explicitly documented as public.
- Docker production starts cleanly.
- Browser login/refresh/logout works through localhost and Cloudflare Tunnel.
