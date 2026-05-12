# JWT Authentication Implementation Plan

> **For Antigravity:** REQUIRED WORKFLOW: Use `.agent/workflows/execute-plan.md` to execute this plan in single-flow mode.

**Goal:** Implement JWT Authentication and PBAC in the FastAPI app, adapting the PRD requirements to work natively within our current SQLite-based architecture without relying on external Redis or LDAP for local development.

**Architecture:** We will extend the existing SQLite `User` model to support roles and hashed passwords, acting as a fallback Local Authenticator when LDAP is unavailable. We will implement standard JWT token issuance, HTTPOnly cookie refresh tokens, and SQLite-backed token blacklisting. PBAC will be enforced via FastAPI dependency injection.

**Tech Stack:** FastAPI, SQLite (SQLAlchemy), PyJWT, passlib (bcrypt), python-multipart.

---

### Task 1: Update Application Configurations and Dependencies

**Files:**
- Modify: `requirements.txt:EOF`
- Modify: `app/config.py:EOF`

**Step 1: Write the failing test**
Run: `pytest tests/test_config.py::test_jwt_config_exists -v` (File doesn't exist yet)
Expected: FAIL

**Step 2: Write minimal implementation**
Create `tests/test_config.py` with a simple check that `settings.JWT_SECRET_KEY` exists.
In `requirements.txt`, append:
```text
PyJWT==2.8.0
passlib[bcrypt]==1.7.4
python-multipart==0.0.9
```
In `app/config.py` (inside the `Settings` class), add:
```python
    JWT_SECRET_KEY: str = "local-development-secret-key-change-in-prod-12345"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_HOURS: int = 8
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7
```

**Step 3: Run test to verify it passes**
Run: `pytest tests/test_config.py::test_jwt_config_exists -v`
Expected: PASS

**Step 4: Commit**
```bash
git add requirements.txt app/config.py tests/test_config.py
git commit -m "feat: add jwt configuration and auth dependencies"
```

---

### Task 2: Extend User Model and Add TokenBlacklist

**Files:**
- Modify: `app/models/db_models.py`
- Test: `tests/test_auth_models.py`

**Step 1: Write the failing test**
Create `tests/test_auth_models.py` to check that `User` has `hashed_password`, `roles`, and `department`. And that `TokenBlacklist` model exists.
Run: `pytest tests/test_auth_models.py -v`
Expected: FAIL

**Step 2: Write minimal implementation**
In `app/models/db_models.py`:
Modify `User`:
```python
    hashed_password = Column(String, nullable=True)
    roles = Column(String, default="[]")  # JSON string of roles
    department = Column(String, nullable=True)
```
Add `TokenBlacklist`:
```python
class TokenBlacklist(Base):
    __tablename__ = "token_blacklist"
    jti = Column(String, primary_key=True)
    expires_at = Column(DateTime, nullable=False)
```

**Step 3: Run test to verify it passes**
Run: `pytest tests/test_auth_models.py -v`
Expected: PASS

**Step 4: Commit**
```bash
git add app/models/db_models.py tests/test_auth_models.py
git commit -m "feat: extend user model and add token blacklist table"
```

---

### Task 3: Create JWT Manager

**Files:**
- Create: `app/auth/jwt_manager.py`
- Test: `tests/test_jwt_manager.py`

**Step 1: Write the failing test**
Create `tests/test_jwt_manager.py` to test `create_access_token` and `verify_token` returning valid decoded claims.
Run: `pytest tests/test_jwt_manager.py -v`
Expected: FAIL

**Step 2: Write minimal implementation**
Create `app/auth/jwt_manager.py` as defined in the Quick Reference Guide (Phase 2.1).
Implement `create_access_token`, `create_refresh_token`, and `verify_token` using `PyJWT`.

**Step 3: Run test to verify it passes**
Run: `pytest tests/test_jwt_manager.py -v`
Expected: PASS

**Step 4: Commit**
```bash
git add app/auth/jwt_manager.py tests/test_jwt_manager.py
git commit -m "feat: implement pyjwt token manager"
```

---

### Task 4: Create Local Authenticator

**Files:**
- Create: `app/auth/local_authenticator.py`
- Test: `tests/test_local_auth.py`

**Step 1: Write the failing test**
Create `tests/test_local_auth.py` to test password verification using `passlib`.
Run: `pytest tests/test_local_auth.py -v`
Expected: FAIL

**Step 2: Write minimal implementation**
Create `app/auth/local_authenticator.py`:
```python
from passlib.context import CryptContext
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)
```

**Step 3: Run test to verify it passes**
Run: `pytest tests/test_local_auth.py -v`
Expected: PASS

**Step 4: Commit**
```bash
git add app/auth/local_authenticator.py tests/test_local_auth.py
git commit -m "feat: add local password hashing utilities"
```

---

### Task 5: Create PBAC Dependencies

**Files:**
- Create: `app/dependencies/auth_dependencies.py`
- Test: `tests/test_pbac.py`

**Step 1: Write the failing test**
Create `tests/test_pbac.py` simulating a FastAPI `Depends` call verifying token blacklist and role matching.
Run: `pytest tests/test_pbac.py -v`
Expected: FAIL

**Step 2: Write minimal implementation**
Create `app/dependencies/auth_dependencies.py`:
Implement `get_current_user` (extracts Bearer token, verifies signature, checks DB blacklist) and `require_roles(roles_list)` (checks if user has required roles).

**Step 3: Run test to verify it passes**
Run: `pytest tests/test_pbac.py -v`
Expected: PASS

**Step 4: Commit**
```bash
git add app/dependencies/auth_dependencies.py tests/test_pbac.py
git commit -m "feat: implement pbac authorization dependencies"
```

---

### Task 6: Create Auth Router

**Files:**
- Create: `app/api/auth_routes.py`
- Modify: `app/main.py`
- Test: `tests/test_auth_api.py`

**Step 1: Write the failing test**
Create `tests/test_auth_api.py` testing `POST /api/auth/login` to return a JWT and a refresh cookie.
Run: `pytest tests/test_auth_api.py -v`
Expected: FAIL

**Step 2: Write minimal implementation**
Create `app/api/auth_routes.py` with `router = APIRouter()`.
Implement `@router.post("/login")` (using OAuth2PasswordRequestForm), `@router.post("/refresh")`, and `@router.post("/logout")` (adds JTI to SQLite `TokenBlacklist`).
In `app/main.py`, add `app.include_router(auth_routes.router, prefix="/api/auth", tags=["Auth"])`.

**Step 3: Run test to verify it passes**
Run: `pytest tests/test_auth_api.py -v`
Expected: PASS

**Step 4: Commit**
```bash
git add app/api/auth_routes.py app/main.py tests/test_auth_api.py
git commit -m "feat: implement authentication router and endpoints"
```
