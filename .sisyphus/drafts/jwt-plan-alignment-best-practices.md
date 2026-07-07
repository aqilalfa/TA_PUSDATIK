# Draft: JWT Plan Alignment and Best Practices

## Requirements (confirmed)
- User meminta plan untuk membuat mekanisme JWT sesuai dengan plan JWT yang sudah ada di workspace dan best practice.
- User mengizinkan penggunaan skill/specialist bila dibutuhkan.
- Output yang diminta adalah planning, bukan implementasi langsung.

## Technical Decisions
- Plan akan berpatokan pada `docs/plans/2026-05-12-jwt-implementation.md`, `PRD_JWT_Implementation_Chatbot_SPBE.md`, dan implementasi aktual di `backend/app/auth/jwt_manager.py`, `backend/app/api/auth_routes.py`, `backend/app/dependencies/auth_dependencies.py`, serta frontend auth services.
- Fokus perbaikan: rolling refresh token, blacklist refresh token, cookie attributes/path, claim consistency, production JWT secret, PBAC enforcement, tests, migration/deployment verification.
- Redis dari PRD tidak akan diwajibkan karena plan workspace menyesuaikan arsitektur SQLite lokal; SQLite-backed blacklist/session tetap dipakai kecuali user meminta Redis.

## Research Findings
- Current JWT foundation exists: access token, refresh token, `jti`, `exp`, `iat`, `type`, HS256 verification, logout blacklist, frontend Bearer interceptor, refresh-on-401 flow.
- Gaps found:
  - `/api/auth/refresh` does not rotate refresh token.
  - Refresh token `jti` is not checked against blacklist.
  - Refresh cookie lacks explicit `path=/api/auth/refresh` and delete-cookie path consistency.
  - Refreshed access token has incomplete/inconsistent claims (`roles` string rather than parsed array, missing `username`, `dept`, `sid`, `auth_provider`).
  - Production `JWT_SECRET_KEY` may still rely on default dev value if not overridden.
  - `require_roles` exists but endpoint enforcement appears limited; protected endpoint audit needed.
  - No global JWT middleware; dependency-based auth is acceptable only if every sensitive endpoint declares dependencies.

## Open Questions
- None blocking. Defaults will be applied in the plan:
  - Keep SQLite-backed token blacklist and audit log.
  - Use dependency-based endpoint protection rather than global middleware, but audit and add dependencies to sensitive routes.
  - Treat Cloudflare/production deployment as HTTPS and set secure cookies for production.

## Scope Boundaries
- INCLUDE: Backend JWT hardening, auth routes, auth dependencies, frontend refresh/logout compatibility, tests, docs/checklist, production env validation.
- INCLUDE: Verify login, refresh, logout, blacklisted token rejection, role authorization, and Cloudflare/local production behavior.
- EXCLUDE: Full LDAP infrastructure rollout, Redis session store migration, force-logout admin UI, unrelated RAG feature changes.

## Test Strategy Decision
- **Infrastructure exists**: YES (backend pytest, frontend vitest available).
- **Automated tests**: Tests-after / regression tests for existing implementation hardening; include unit + API integration tests.
- **Agent-Executed QA**: ALWAYS — curl login/refresh/logout/protected endpoint checks, DB blacklist inspection, browser/manual QA where needed.
