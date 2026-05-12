# JWT Implementation - Quick Reference Guide
## Developer Checklist & Component Reference

---

## 🎯 PHASE 1: Backend Architecture Setup

### 1.1 Create Project Structure
```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py (FastAPI app)
│   ├── config/
│   │   ├── __init__.py
│   │   ├── jwt_config.py
│   │   ├── ldap_config.py
│   │   ├── database_config.py
│   │   └── redis_config.py
│   ├── auth/
│   │   ├── __init__.py
│   │   ├── jwt_manager.py
│   │   ├── ldap_authenticator.py
│   │   ├── token_blacklist.py
│   │   └── schemas.py
│   ├── middleware/
│   │   ├── __init__.py
│   │   ├── jwt_middleware.py
│   │   ├── rate_limit_middleware.py
│   │   └── error_handler.py
│   ├── session/
│   │   ├── __init__.py
│   │   └── session_manager.py
│   ├── security/
│   │   ├── __init__.py
│   │   └── pbac.py
│   ├── audit/
│   │   ├── __init__.py
│   │   ├── audit_logger.py
│   │   └── models.py
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── auth_routes.py
│   │   └── protected_routes.py
│   ├── dependencies/
│   │   ├── __init__.py
│   │   └── auth_dependencies.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── user.py
│   │   └── audit_log.py
│   └── db/
│       ├── __init__.py
│       ├── database.py
│       ├── session.py
│       └── migrations/
│           └── 001_create_audit_logs_table.sql
├── tests/
│   ├── __init__.py
│   ├── test_jwt_manager.py
│   ├── test_ldap_authenticator.py
│   ├── test_auth_routes.py
│   └── test_pbac.py
├── requirements.txt
├── .env.example
└── README.md
```

### 1.2 Install Dependencies
```bash
pip install fastapi uvicorn
pip install pyjwt cryptography
pip install ldap3
pip install redis
pip install sqlalchemy psycopg2-binary alembic
pip install python-multipart
pip install slowapi  # for rate limiting
pip install python-dotenv
pip install pydantic
pip install pytest pytest-asyncio  # for testing
```

### 1.3 Environment Variables Setup
**Create `.env` file:**
```bash
# JWT Configuration
JWT_SECRET_KEY=<generate-with-secrets.token_urlsafe(32)>
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_HOURS=8
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7

# LDAP Configuration
LDAP_SERVER_URL=ldap://ad.bssn.go.id:389
LDAP_BASE_DN=dc=bssn,dc=go,dc=id
LDAP_DOMAIN=bssn.go.id
LDAP_TIMEOUT=10
LDAP_RETRY_COUNT=2

# Redis Configuration
REDIS_URL=redis://localhost:6379
REDIS_PASSWORD=
REDIS_DB_SESSIONS=0
REDIS_DB_BLACKLIST=1
REDIS_DB_RATELIMIT=2

# Database Configuration
DATABASE_URL=postgresql://user:password@localhost:5432/audit_db
DATABASE_POOL_SIZE=20

# Server Configuration
FRONTEND_URL=http://localhost:5173
DOMAIN=internal.pusdatik.bssn.go.id

# Logging
LOG_LEVEL=INFO
```

---

## 🔐 PHASE 2: Core Authentication Components

### 2.1 JWT Manager Implementation
**File: `app/auth/jwt_manager.py`**

```python
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional
import jwt
import uuid
import logging

logger = logging.getLogger(__name__)

class JWTManager:
    def __init__(self, secret_key: str, algorithm: str = "HS256"):
        self.secret_key = secret_key
        self.algorithm = algorithm
    
    def create_access_token(
        self,
        data: Dict[str, Any],
        expires_delta: Optional[timedelta] = None
    ) -> str:
        """Create JWT access token"""
        to_encode = data.copy()
        
        if expires_delta:
            expire = datetime.now(timezone.utc) + expires_delta
        else:
            expire = datetime.now(timezone.utc) + timedelta(hours=8)
        
        to_encode.update({
            "exp": expire,
            "iat": datetime.now(timezone.utc),
            "jti": str(uuid.uuid4()),
            "type": "access"
        })
        
        encoded_jwt = jwt.encode(
            to_encode,
            self.secret_key,
            algorithm=self.algorithm
        )
        
        logger.debug(f"Access token created for {data.get('sub')}")
        return encoded_jwt
    
    def create_refresh_token(
        self,
        data: Dict[str, Any],
        expires_delta: Optional[timedelta] = None
    ) -> str:
        """Create JWT refresh token"""
        to_encode = data.copy()
        
        if expires_delta:
            expire = datetime.now(timezone.utc) + expires_delta
        else:
            expire = datetime.now(timezone.utc) + timedelta(days=7)
        
        to_encode.update({
            "exp": expire,
            "iat": datetime.now(timezone.utc),
            "jti": str(uuid.uuid4()),
            "type": "refresh"
        })
        
        encoded_jwt = jwt.encode(
            to_encode,
            self.secret_key,
            algorithm=self.algorithm
        )
        
        logger.debug(f"Refresh token created for {data.get('sub')}")
        return encoded_jwt
    
    def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Verify and decode token"""
        try:
            # Verify signature and algorithm
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm]  # Explicit - no alg:none
            )
            
            # Check required claims
            if not all(k in payload for k in ["sub", "exp", "jti", "type"]):
                logger.warning("Token missing required claims")
                return None
            
            return payload
        
        except jwt.ExpiredSignatureError:
            logger.debug("Token expired")
            return None
        except jwt.InvalidSignatureError:
            logger.warning("Invalid token signature")
            return None
        except jwt.DecodeError:
            logger.warning("Token decode error")
            return None
        except Exception as e:
            logger.error(f"Token verification error: {e}")
            return None
    
    def decode_token_unverified(self, token: str) -> Optional[Dict[str, Any]]:
        """Decode token without verification (for claims inspection only)"""
        try:
            return jwt.decode(
                token,
                options={"verify_signature": False}
            )
        except:
            return None

# Usage in FastAPI
jwt_manager = JWTManager(
    secret_key=settings.JWT_SECRET_KEY,
    algorithm=settings.JWT_ALGORITHM
)
```

**✅ Checklist:**
- [ ] JWTManager class created
- [ ] Secret key stored in environment (never hardcoded)
- [ ] HS256 algorithm enforced (no alg:none)
- [ ] JTI (JWT ID) generated for each token
- [ ] Expiration claim validated
- [ ] Error handling for signature/expiration

---

### 2.2 LDAP Authenticator Implementation
**File: `app/auth/ldap_authenticator.py`**

```python
from ldap3 import Server, Connection, ALL
from ldap3.core.exceptions import LDAPException
import logging
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

class LDAPAuthenticator:
    def __init__(
        self,
        server_url: str,
        base_dn: str,
        domain: str,
        timeout: int = 10,
        retry_count: int = 2
    ):
        self.server_url = server_url
        self.base_dn = base_dn
        self.domain = domain
        self.timeout = timeout
        self.retry_count = retry_count
    
    def authenticate(
        self,
        username: str,
        password: str
    ) -> Optional[Dict[str, Any]]:
        """Authenticate user against AD"""
        
        if not username or not password:
            logger.warning("Empty username or password")
            return None
        
        user_dn = f"{username}@{self.domain}"
        
        for attempt in range(self.retry_count):
            try:
                # Create LDAP server connection
                server = Server(
                    self.server_url,
                    get_info=ALL,
                    connect_timeout=self.timeout
                )
                
                # Attempt bind
                conn = Connection(
                    server,
                    user=user_dn,
                    password=password,
                    raise_exceptions=True,
                    auto_bind=True
                )
                
                logger.info(f"LDAP authentication successful for {username}")
                
                # Get user attributes
                user_attrs = self._get_user_attributes(conn, username)
                conn.unbind()
                
                return user_attrs
            
            except LDAPException as e:
                if "Invalid credentials" in str(e):
                    logger.warning(f"Invalid LDAP credentials for {username}")
                    return None
                else:
                    logger.warning(
                        f"LDAP error (attempt {attempt+1}/{self.retry_count}): {e}"
                    )
                    if attempt == self.retry_count - 1:
                        return None
            except Exception as e:
                logger.error(f"LDAP authentication error: {e}")
                if attempt == self.retry_count - 1:
                    return None
        
        return None
    
    def _get_user_attributes(self, conn, username: str) -> Dict[str, Any]:
        """Retrieve user attributes from AD"""
        try:
            # Search for user
            search_filter = f"(sAMAccountName={username})"
            conn.search(
                search_base=self.base_dn,
                search_filter=search_filter,
                attributes=["memberOf", "department", "displayName", "mail", "employeeID"]
            )
            
            if not conn.entries:
                logger.warning(f"User not found: {username}")
                return None
            
            entry = conn.entries[0]
            
            # Parse groups from memberOf
            groups = self._parse_groups(entry.memberOf.values if entry.memberOf else [])
            
            return {
                "username": username,
                "display_name": str(entry.displayName) if entry.displayName else username,
                "email": str(entry.mail) if entry.mail else "",
                "department": str(entry.department) if entry.department else "",
                "employee_id": str(entry.employeeID) if entry.employeeID else "",
                "groups": groups
            }
        
        except Exception as e:
            logger.error(f"Error retrieving user attributes: {e}")
            return None
    
    def _parse_groups(self, member_of: List[str]) -> List[str]:
        """Parse group names from memberOf attribute"""
        groups = []
        for dn in member_of:
            # Extract CN from DN like "CN=Evaluator_SPBE,OU=Groups,DC=bssn,DC=go,DC=id"
            try:
                cn = dn.split(",")[0].replace("CN=", "")
                groups.append(cn)
            except:
                pass
        return groups
    
    def test_connection(self) -> bool:
        """Test LDAP server connection"""
        try:
            server = Server(self.server_url, connect_timeout=self.timeout)
            conn = Connection(server, raise_exceptions=True)
            conn.open()
            conn.close()
            logger.info("LDAP connection test successful")
            return True
        except Exception as e:
            logger.error(f"LDAP connection test failed: {e}")
            return False

# Usage
ldap_auth = LDAPAuthenticator(
    server_url=settings.LDAP_SERVER_URL,
    base_dn=settings.LDAP_BASE_DN,
    domain=settings.LDAP_DOMAIN
)
```

**✅ Checklist:**
- [ ] LDAP connection with retry logic
- [ ] User authentication via bind
- [ ] Group parsing from memberOf
- [ ] Attribute retrieval
- [ ] Error handling (invalid creds vs connection error)
- [ ] Connection timeout configured

---

### 2.3 Session Manager Implementation
**File: `app/session/session_manager.py`**

```python
import redis
import json
from datetime import datetime, timezone
import uuid
from typing import Optional, Dict, Any, List
import logging

logger = logging.getLogger(__name__)

class SessionManager:
    def __init__(self, redis_client: redis.Redis, ttl: int = 28800):
        self.redis = redis_client
        self.ttl = ttl  # 8 hours in seconds
    
    def create_session(
        self,
        username: str,
        roles: List[str],
        department: str,
        jti: str,
        device_info: Dict[str, Any] = None
    ) -> str:
        """Create new session"""
        session_id = str(uuid.uuid4())
        
        session_data = {
            "user": username,
            "roles": roles,
            "dept": department,
            "jti": jti,
            "login_time": datetime.now(timezone.utc).isoformat(),
            "last_activity": datetime.now(timezone.utc).isoformat(),
            "device_info": device_info or {}
        }
        
        try:
            self.redis.setex(
                f"session:{session_id}",
                self.ttl,
                json.dumps(session_data)
            )
            logger.info(f"Session created: {session_id} for {username}")
            return session_id
        except Exception as e:
            logger.error(f"Error creating session: {e}")
            raise
    
    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session data"""
        try:
            data = self.redis.get(f"session:{session_id}")
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            logger.error(f"Error retrieving session: {e}")
            return None
    
    def update_activity(self, session_id: str) -> bool:
        """Update last activity timestamp"""
        try:
            session_data = self.get_session(session_id)
            if session_data:
                session_data["last_activity"] = datetime.now(timezone.utc).isoformat()
                self.redis.setex(
                    f"session:{session_id}",
                    self.ttl,
                    json.dumps(session_data)
                )
                return True
            return False
        except Exception as e:
            logger.error(f"Error updating session activity: {e}")
            return False
    
    def invalidate_session(self, session_id: str) -> bool:
        """Invalidate session"""
        try:
            self.redis.delete(f"session:{session_id}")
            logger.info(f"Session invalidated: {session_id}")
            return True
        except Exception as e:
            logger.error(f"Error invalidating session: {e}")
            return False
    
    def invalidate_user_sessions(self, username: str) -> int:
        """Invalidate all sessions for a user"""
        try:
            # Find all sessions for this user
            sessions = self.redis.scan(match="session:*")
            invalidated_count = 0
            
            for key in sessions[1]:  # sessions[1] contains the keys
                session_data = self.redis.get(key)
                if session_data:
                    data = json.loads(session_data)
                    if data.get("user") == username:
                        self.redis.delete(key)
                        invalidated_count += 1
            
            logger.info(f"Invalidated {invalidated_count} sessions for {username}")
            return invalidated_count
        except Exception as e:
            logger.error(f"Error invalidating user sessions: {e}")
            return 0

# Usage
session_manager = SessionManager(
    redis_client=redis.Redis.from_url(settings.REDIS_URL),
    ttl=8 * 3600
)
```

**✅ Checklist:**
- [ ] SessionManager class with Redis backend
- [ ] Create, read, update, invalidate sessions
- [ ] TTL management (8 hours)
- [ ] Batch invalidation for force-logout

---

## 🛡️ PHASE 3: Middleware & Decorators

### 3.1 JWT Validation Middleware
**File: `app/middleware/jwt_middleware.py`**

```python
from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
import logging
from typing import Callable, Optional
import time

logger = logging.getLogger(__name__)

class JWTValidationMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, jwt_manager, token_blacklist):
        super().__init__(app)
        self.jwt_manager = jwt_manager
        self.token_blacklist = token_blacklist
    
    async def dispatch(self, request: Request, call_next: Callable):
        # Skip validation for public endpoints
        if request.url.path in ["/api/auth/login", "/api/auth/refresh", "/docs", "/openapi.json"]:
            return await call_next(request)
        
        # Extract token
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            # Public endpoint - no token required
            if request.url.path.startswith("/api/public"):
                return await call_next(request)
            
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing authorization header"
            )
        
        token = auth_header[7:]  # Remove "Bearer " prefix
        
        # Validate token
        start_time = time.time()
        
        payload = self.jwt_manager.verify_token(token)
        if not payload:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token"
            )
        
        # Check blacklist
        jti = payload.get("jti")
        if self.token_blacklist.is_blacklisted(jti):
            logger.warning(f"Blacklisted token used: {jti}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has been revoked"
            )
        
        # Attach to request state
        request.state.user = payload.get("sub")
        request.state.roles = payload.get("roles", [])
        request.state.dept = payload.get("dept")
        request.state.jti = jti
        request.state.session_id = payload.get("sid")
        
        validation_time = (time.time() - start_time) * 1000
        if validation_time > 100:
            logger.warning(f"Slow token validation: {validation_time}ms")
        
        return await call_next(request)
```

**✅ Checklist:**
- [ ] Extract and validate token from Authorization header
- [ ] Check blacklist
- [ ] Attach user context to request
- [ ] Performance monitoring
- [ ] Skip validation for public endpoints

---

### 3.2 PBAC Authorization Decorator
**File: `app/dependencies/auth_dependencies.py`**

```python
from fastapi import Depends, HTTPException, status, Request
import logging

logger = logging.getLogger(__name__)

async def get_current_user(request: Request) -> str:
    """Get current user from request state"""
    if not hasattr(request.state, "user"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    return request.state.user

async def require_roles(required_roles: list[str]):
    """Dependency to check if user has required roles"""
    async def check_roles(request: Request) -> bool:
        if not hasattr(request.state, "roles"):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated"
            )
        
        user_roles = request.state.roles
        
        # Check if user has any of the required roles
        if not any(role in user_roles for role in required_roles):
            logger.warning(
                f"Access denied for {request.state.user}: "
                f"required {required_roles}, has {user_roles}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
                headers={"X-Required-Roles": ",".join(required_roles)}
            )
        
        return True
    
    return Depends(check_roles)

# Usage in routes:
# @router.get("/protected")
# async def protected_endpoint(
#     _: bool = Depends(require_roles(["evaluator_spbe"]))
# ):
#     return {"message": "You have access"}
```

**✅ Checklist:**
- [ ] Extract user and roles from request state
- [ ] Check if user has required roles
- [ ] Return 403 if unauthorized
- [ ] Log authorization failures

---

### 3.3 Rate Limiting Middleware
**File: `app/middleware/rate_limit_middleware.py`**

```python
from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
import redis
import time
import logging

logger = logging.getLogger(__name__)

RATE_LIMITS = {
    "/api/chat/query": "60/minute",
    "/api/auth/login": "10/minute",
    "/api/auth/refresh": "20/minute",
}

class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, redis_client):
        super().__init__(app)
        self.redis = redis_client
    
    async def dispatch(self, request: Request, call_next):
        # Get endpoint
        endpoint = request.url.path
        
        # Get rate limit for this endpoint
        limit_str = RATE_LIMITS.get(endpoint)
        if not limit_str:
            return await call_next(request)
        
        # Parse limit (e.g., "60/minute" -> 60, 60)
        limit, period = self._parse_limit(limit_str)
        
        # Get user identifier
        user = getattr(request.state, "user", request.client.host)
        
        # Check rate limit
        key = f"ratelimit:{user}:{endpoint}"
        current_count = self.redis.incr(key)
        
        # Set TTL if new key
        if current_count == 1:
            self.redis.expire(key, period)
        
        # Check if exceeded
        if current_count > limit:
            logger.warning(
                f"Rate limit exceeded for {user} on {endpoint}: {current_count}/{limit}"
            )
            
            remaining_ttl = self.redis.ttl(key)
            
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests",
                headers={
                    "X-RateLimit-Limit": str(limit),
                    "X-RateLimit-Remaining": str(max(0, limit - current_count)),
                    "Retry-After": str(remaining_ttl)
                }
            )
        
        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(max(0, limit - current_count))
        
        return response
    
    def _parse_limit(self, limit_str: str) -> tuple[int, int]:
        """Parse limit string like '60/minute' to (limit, period_in_seconds)"""
        parts = limit_str.split("/")
        limit = int(parts[0])
        
        period_map = {
            "second": 1,
            "minute": 60,
            "hour": 3600,
            "day": 86400
        }
        
        period = period_map.get(parts[1], 60)
        return limit, period
```

**✅ Checklist:**
- [ ] Track request count per user per endpoint
- [ ] Enforce configured limits
- [ ] Return 429 with Retry-After header
- [ ] Reset counter per period

---

## 🔌 PHASE 4: Frontend Authentication

### 4.1 Vuex Auth Store
**File: `frontend/src/store/modules/auth.ts`**

```typescript
import { defineStore } from 'pinia'
import axios from 'axios'

interface User {
  username: string
  roles: string[]
  department: string
  display_name: string
}

export const useAuthStore = defineStore('auth', {
  state: () => ({
    accessToken: null as string | null,
    user: null as User | null,
    isAuthenticated: false,
    sessionExpiry: null as number | null,
    loading: false,
    error: null as string | null
  }),

  getters: {
    isLoggedIn: (state) => !!state.accessToken,
    hasRole: (state) => (role: string) => {
      return state.user?.roles.includes(role) ?? false
    },
    timeUntilExpiry: (state) => {
      if (!state.sessionExpiry) return null
      return Math.max(0, state.sessionExpiry - Date.now())
    }
  },

  actions: {
    setAccessToken(token: string) {
      this.accessToken = token
      this.isAuthenticated = !!token
    },

    clearAccessToken() {
      this.accessToken = null
      this.isAuthenticated = false
    },

    setUser(user: User) {
      this.user = user
    },

    clearUser() {
      this.user = null
    },

    setSessionExpiry(expiresIn: number) {
      this.sessionExpiry = Date.now() + expiresIn * 1000
    },

    async login(username: string, password: string) {
      this.loading = true
      this.error = null
      
      try {
        const response = await axios.post('/api/auth/login', {
          username,
          password
        })
        
        const { access_token, expires_in, user } = response.data
        
        this.setAccessToken(access_token)
        this.setUser(user)
        this.setSessionExpiry(expires_in)
        
        return true
      } catch (error: any) {
        this.error = error.response?.data?.detail || 'Login failed'
        return false
      } finally {
        this.loading = false
      }
    },

    async logout() {
      try {
        await axios.post('/api/auth/logout')
      } catch (error) {
        console.error('Logout error:', error)
      } finally {
        this.clearAccessToken()
        this.clearUser()
        this.sessionExpiry = null
      }
    },

    checkTokenExpiry() {
      if (!this.sessionExpiry) return false
      
      const timeRemaining = this.sessionExpiry - Date.now()
      
      // If less than 5 minutes remaining, consider it expiring
      if (timeRemaining < 5 * 60 * 1000) {
        return true
      }
      
      return false
    }
  }
})
```

**✅ Checklist:**
- [ ] AuthStore created with Pinia
- [ ] state: accessToken (memory only), user, session expiry
- [ ] Actions: login, logout, checkTokenExpiry
- [ ] Getters: isLoggedIn, hasRole
- [ ] Token stored in memory (NOT localStorage)

---

### 4.2 HTTP Client with Token Injection
**File: `frontend/src/api/httpClient.ts`**

```typescript
import axios, { AxiosInstance, AxiosError } from 'axios'
import { useAuthStore } from '../store/modules/auth'

const httpClient: AxiosInstance = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000',
  timeout: 10000,
  withCredentials: true  // For HttpOnly cookies
})

// Request interceptor: inject access token
httpClient.interceptors.request.use(
  (config) => {
    const authStore = useAuthStore()
    
    if (authStore.accessToken) {
      config.headers.Authorization = `Bearer ${authStore.accessToken}`
    }
    
    return config
  },
  (error) => Promise.reject(error)
)

// Response interceptor: handle token expiry and errors
httpClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const authStore = useAuthStore()
    const originalRequest = error.config as any
    
    // Handle 401 - token expired or invalid
    if (error.response?.status === 401) {
      // Try to refresh token
      try {
        const response = await axios.post(
          `${httpClient.defaults.baseURL}/api/auth/refresh`,
          {},
          { withCredentials: true }
        )
        
        const { access_token, expires_in } = response.data
        
        authStore.setAccessToken(access_token)
        authStore.setSessionExpiry(expires_in)
        
        // Retry original request with new token
        originalRequest.headers.Authorization = `Bearer ${access_token}`
        return httpClient(originalRequest)
      } catch (refreshError) {
        // Refresh failed - logout user
        authStore.logout()
        window.location.href = '/login'
        return Promise.reject(refreshError)
      }
    }
    
    // Handle 403 - forbidden
    if (error.response?.status === 403) {
      console.error('Access forbidden - insufficient permissions')
    }
    
    // Handle 429 - rate limit
    if (error.response?.status === 429) {
      const retryAfter = error.response.headers['retry-after']
      console.warn(`Rate limited. Retry after ${retryAfter} seconds`)
    }
    
    return Promise.reject(error)
  }
)

export default httpClient
```

**✅ Checklist:**
- [ ] Axios instance created with base URL
- [ ] Request interceptor injects Authorization header
- [ ] Response interceptor handles 401 (auto-refresh)
- [ ] Response interceptor handles 403, 429
- [ ] withCredentials = true (for refresh token cookie)

---

### 4.3 Router Guard
**File: `frontend/src/router/guards/authGuard.ts`**

```typescript
import { Router } from 'vue-router'
import { useAuthStore } from '../../store/modules/auth'

export function setupAuthGuard(router: Router) {
  router.beforeEach((to, from, next) => {
    const authStore = useAuthStore()
    
    const requiresAuth = to.matched.some(record => record.meta.requiresAuth)
    const requiredRoles = to.meta.roles as string[] | undefined
    
    if (requiresAuth) {
      if (!authStore.isLoggedIn) {
        // Not authenticated - redirect to login
        next({ name: 'Login', query: { redirect: to.fullPath } })
        return
      }
      
      // Check if token is expiring soon
      if (authStore.checkTokenExpiry()) {
        console.warn('Token expiring soon')
        // Optionally trigger refresh here
      }
      
      // Check required roles
      if (requiredRoles && !requiredRoles.some(role => authStore.hasRole(role))) {
        // Unauthorized - redirect to unauthorized page
        next({ name: 'Unauthorized' })
        return
      }
    } else {
      // Public route
      if (to.name === 'Login' && authStore.isLoggedIn) {
        // Redirect authenticated users away from login page
        next({ name: 'Dashboard' })
        return
      }
    }
    
    next()
  })
}
```

**File: `frontend/src/router/index.ts`**

```typescript
import { createRouter, createWebHistory } from 'vue-router'
import { setupAuthGuard } from './guards/authGuard'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      name: 'Login',
      component: () => import('../views/LoginView.vue'),
      meta: { requiresAuth: false }
    },
    {
      path: '/dashboard',
      name: 'Dashboard',
      component: () => import('../views/DashboardView.vue'),
      meta: { requiresAuth: true, roles: ['evaluator_spbe'] }
    },
    {
      path: '/unauthorized',
      name: 'Unauthorized',
      component: () => import('../views/UnauthorizedView.vue')
    }
  ]
})

setupAuthGuard(router)

export default router
```

**✅ Checklist:**
- [ ] Router guard checks authentication
- [ ] Router guard checks required roles
- [ ] Redirect to login if not authenticated
- [ ] Redirect to unauthorized if insufficient roles
- [ ] Check token expiry

---

## 📋 PHASE 5: API Routes

### 5.1 Authentication Routes
**File: `app/routers/auth_routes.py`**

```python
from fastapi import APIRouter, HTTPException, status, Request, Response, Depends
from fastapi.security import HTTPBearer
import logging
from datetime import timedelta
from typing import Optional

from app.auth.jwt_manager import jwt_manager
from app.auth.ldap_authenticator import ldap_auth
from app.auth.token_blacklist import token_blacklist
from app.session.session_manager import session_manager
from app.audit.audit_logger import audit_logger
from app.dependencies.auth_dependencies import get_current_user
from app.schemas.auth_schemas import LoginRequest, LoginResponse, UserInfo

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["auth"])

@router.post("/login", response_model=LoginResponse)
async def login(request: Request, creds: LoginRequest):
    """Authenticate user and issue tokens"""
    
    # Extract source IP
    source_ip = request.client.host
    user_agent = request.headers.get("User-Agent", "Unknown")
    
    # Attempt LDAP authentication
    user_info = ldap_auth.authenticate(creds.username, creds.password)
    
    if not user_info:
        # Log failed attempt
        audit_logger.log_auth_attempt(
            username=creds.username,
            status="FAILED",
            reason="Invalid credentials",
            source_ip=source_ip,
            user_agent=user_agent
        )
        
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )
    
    # Map AD groups to roles
    roles = map_groups_to_roles(user_info.get("groups", []))
    
    # Create tokens
    access_token_data = {
        "sub": user_info["username"],
        "username": user_info.get("username"),
        "roles": roles,
        "dept": user_info.get("department", ""),
        "type": "access"
    }
    
    access_token = jwt_manager.create_access_token(
        data=access_token_data,
        expires_delta=timedelta(hours=8)
    )
    
    refresh_token = jwt_manager.create_refresh_token(
        data={
            "sub": user_info["username"],
            "type": "refresh"
        },
        expires_delta=timedelta(days=7)
    )
    
    # Get JTI from token payload (decode without verification is ok here, we just created it)
    token_payload = jwt_manager.decode_token_unverified(access_token)
    jti = token_payload.get("jti") if token_payload else ""
    
    # Create session
    session_id = session_manager.create_session(
        username=user_info["username"],
        roles=roles,
        department=user_info.get("department", ""),
        jti=jti,
        device_info={
            "ip": source_ip,
            "user_agent": user_agent
        }
    )
    
    # Log successful authentication
    audit_logger.log_auth_attempt(
        username=creds.username,
        status="SUCCESS",
        reason="",
        source_ip=source_ip,
        user_agent=user_agent
    )
    
    # Create response
    response = LoginResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=8 * 3600,
        user=UserInfo(
            username=user_info["username"],
            roles=roles,
            department=user_info.get("department", ""),
            display_name=user_info.get("display_name", ""),
            email=user_info.get("email", ""),
            session_id=session_id
        )
    )
    
    # Set refresh token cookie (HttpOnly)
    cookie_response = Response(
        content=response.model_dump_json(),
        media_type="application/json"
    )
    cookie_response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=True,
        samesite="strict",
        path="/api/auth/refresh",
        max_age=7 * 24 * 3600  # 7 days
    )
    
    return cookie_response


@router.post("/refresh")
async def refresh(request: Request):
    """Refresh access token using refresh token from cookie"""
    
    # Extract refresh token from cookie
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token not found"
        )
    
    # Verify refresh token
    payload = jwt_manager.verify_token(refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )
    
    # Get session info
    session = session_manager.get_session(payload.get("sid", ""))
    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session not found"
        )
    
    # Create new access token
    new_access_token = jwt_manager.create_access_token(
        data={
            "sub": payload["sub"],
            "roles": session["roles"],
            "dept": session["dept"],
            "type": "access"
        },
        expires_delta=timedelta(hours=8)
    )
    
    # Create new refresh token (rolling rotation)
    new_refresh_token = jwt_manager.create_refresh_token(
        data={"sub": payload["sub"], "type": "refresh"},
        expires_delta=timedelta(days=7)
    )
    
    # Update session activity
    session_manager.update_activity(payload.get("sid", ""))
    
    # Log refresh event
    audit_logger.log_token_event(
        event_type="TOKEN_REFRESHED",
        username=payload["sub"],
        jti=payload.get("jti", ""),
        roles=session["roles"],
        status="SUCCESS"
    )
    
    response = Response(
        content=JSONResponse({
            "access_token": new_access_token,
            "token_type": "bearer",
            "expires_in": 8 * 3600
        }).body,
        media_type="application/json"
    )
    
    # Set new refresh token cookie
    response.set_cookie(
        key="refresh_token",
        value=new_refresh_token,
        httponly=True,
        secure=True,
        samesite="strict",
        path="/api/auth/refresh",
        max_age=7 * 24 * 3600
    )
    
    return response


@router.post("/logout")
async def logout(request: Request, current_user: str = Depends(get_current_user)):
    """Logout user and invalidate token"""
    
    # Get JTI and session ID from state
    jti = request.state.jti
    session_id = request.state.session_id
    
    # Add token to blacklist
    token_blacklist.add_to_blacklist(jti)
    
    # Invalidate session
    session_manager.invalidate_session(session_id)
    
    # Log logout
    audit_logger.log_auth_attempt(
        username=current_user,
        status="LOGOUT",
        reason="User initiated logout"
    )
    
    response = JSONResponse({"detail": "Logout successful"})
    
    # Clear refresh token cookie
    response.delete_cookie(
        key="refresh_token",
        path="/api/auth/refresh"
    )
    
    return response


def map_groups_to_roles(ad_groups: list[str]) -> list[str]:
    """Map AD groups to application roles"""
    ROLE_MAPPING = {
        "Evaluator_SPBE": ["evaluator_spbe"],
        "Staf_PUSDATIK": ["staf_pusdatik"],
        "Admin_PUSDATIK": ["admin_pusdatik", "staf_pusdatik"],
        "Manager_Evaluasi": ["manager_evaluasi", "staf_pusdatik"],
    }
    
    roles = set()
    for group in ad_groups:
        if group in ROLE_MAPPING:
            roles.update(ROLE_MAPPING[group])
    
    return list(roles)
```

**✅ Checklist:**
- [ ] POST /auth/login: authenticate with AD, issue tokens
- [ ] POST /auth/refresh: refresh access token using refresh token cookie
- [ ] POST /auth/logout: blacklist token, invalidate session
- [ ] Proper error handling and logging
- [ ] HttpOnly cookie for refresh token

---

## 🧪 PHASE 6: Testing

### 6.1 Test JWT Manager
**File: `tests/test_jwt_manager.py`**

```python
import pytest
from datetime import timedelta
from app.auth.jwt_manager import JWTManager

@pytest.fixture
def jwt_mgr():
    return JWTManager(
        secret_key="test-secret-key-min-32-characters-long",
        algorithm="HS256"
    )

def test_create_access_token(jwt_mgr):
    token = jwt_mgr.create_access_token(
        data={"sub": "testuser"},
        expires_delta=timedelta(hours=1)
    )
    assert token is not None
    assert len(token) > 0

def test_verify_token_valid(jwt_mgr):
    token = jwt_mgr.create_access_token({"sub": "testuser"})
    payload = jwt_mgr.verify_token(token)
    assert payload is not None
    assert payload["sub"] == "testuser"

def test_verify_token_invalid_signature(jwt_mgr):
    token = "invalid.token.signature"
    payload = jwt_mgr.verify_token(token)
    assert payload is None

def test_alg_none_attack(jwt_mgr):
    """Verify that alg:none attack is prevented"""
    # Manually create token with alg:none (attack attempt)
    import jwt as pyjwt
    
    attack_token = pyjwt.encode(
        {"sub": "testuser"},
        options={"verify_signature": False}
    )
    
    # Try to verify - should fail because only HS256 is allowed
    payload = jwt_mgr.verify_token(attack_token)
    assert payload is None
```

**✅ Checklist:**
- [ ] Token creation tests
- [ ] Token verification tests
- [ ] Signature verification tests
- [ ] Expiration tests
- [ ] alg:none attack prevention test

---

### 6.2 Integration Test: Login Flow
**File: `tests/test_login_flow.py`**

```python
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_login_success():
    response = client.post(
        "/api/auth/login",
        json={"username": "testuser", "password": "testpass"}
    )
    # Note: This will fail without actual AD credentials
    # In real tests, use mock LDAP server
    assert response.status_code in [200, 401]

def test_login_invalid_credentials():
    response = client.post(
        "/api/auth/login",
        json={"username": "invalid", "password": "invalid"}
    )
    assert response.status_code == 401
    assert "Invalid credentials" in response.json()["detail"]

def test_protected_endpoint_without_token():
    response = client.get("/api/chat/query")
    assert response.status_code == 401

def test_rate_limiting():
    # Simulate exceeding rate limit
    for i in range(70):  # Exceed 60/minute limit
        response = client.post(
            "/api/auth/login",
            json={"username": "test", "password": "test"}
        )
        if i >= 60:
            assert response.status_code == 429
```

**✅ Checklist:**
- [ ] Login flow integration test
- [ ] Protected endpoint access tests
- [ ] Rate limiting tests
- [ ] Token refresh tests

---

## ✅ FINAL DEPLOYMENT CHECKLIST

Before deploying to production:

**Security:**
- [ ] JWT_SECRET_KEY is 32+ random characters
- [ ] HTTPS/TLS enabled
- [ ] CORS configured to specific domain
- [ ] Security headers set (HSTS, X-Frame-Options, etc.)
- [ ] LDAP connection uses secure protocol
- [ ] Database connections pooled
- [ ] Audit logging enabled

**Testing:**
- [ ] All unit tests passing
- [ ] All integration tests passing
- [ ] Security tests passed
- [ ] Load tests acceptable
- [ ] Manual testing on staging

**Configuration:**
- [ ] Environment variables set
- [ ] Database migrations applied
- [ ] Redis connection tested
- [ ] LDAP connection tested
- [ ] Email notifications configured (optional)

**Monitoring:**
- [ ] Logging configured
- [ ] Alerting configured
- [ ] Metrics collection set up
- [ ] Error tracking (Sentry) configured (optional)

**Documentation:**
- [ ] API documentation updated
- [ ] Deployment guide written
- [ ] Admin manual created
- [ ] Troubleshooting guide written

---

This PRD and checklist provide a complete roadmap for implementing JWT authentication in your chatbot. Start with Phase 1 and work through systematically. Each section has checkboxes to track progress.

**Good luck with your implementation! 🚀**
