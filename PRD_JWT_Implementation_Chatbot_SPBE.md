# Product Requirements Document (PRD)
## Implementasi JSON Web Token (JWT) pada Sistem Asisten Cerdas RAG-SPBE PUSDATIK BSSN

**Versi**: 1.0  
**Tanggal**: Mei 2026  
**Status**: Ready for Implementation  
**Owner**: Development Team PUSDATIK BSSN

---

## 1. EXECUTIVE SUMMARY

Dokumen ini menetapkan spesifikasi lengkap untuk implementasi sistem autentikasi berbasis JSON Web Token (JWT) pada chatbot asisten cerdas SPBE. Sistem ini harus mengintegrasikan Active Directory BSSN, menerapkan kontrol akses berbasis peran (PBAC), dan melindungi seluruh API endpoint dari akses tidak sah sesuai standar OWASP API Security Top 10.

**Tujuan Utama:**
- Mengamankan akses chatbot hanya untuk pegawai BSSN terautentikasi
- Mengintegrasikan infrastruktur identitas existing (Active Directory BSSN)
- Menerapkan policy-based access control berbasis peran dan departemen
- Mencegah serangan umum JWT (alg:none, token manipulation, session fixation)
- Memastikan audit trail dan session invalidation yang aman

---

## 2. REQUIREMENTS OVERVIEW

### 2.1 Functional Requirements

#### FR-JWT-001: Autentikasi Active Directory
**Deskripsi**: Sistem harus melakukan autentikasi pengguna terhadap server Active Directory BSSN menggunakan protokol LDAP.

**Detail**:
- Mendukung bind LDAP dengan format domain: `username@bssn.go.id`
- Membaca atribut user dari AD: `sAMAccountName`, `memberOf`, `department`, `displayName`, `mail`, `employeeID`
- Timeout koneksi LDAP: 10 detik
- Retry logic: 2 kali percobaan sebelum gagal
- Connection pooling: min 5, max 20 connections
- Fallback: Jika AD tidak tersedia, log error dan kembalikan HTTP 503

**Acceptance Criteria:**
- [ ] Koneksi LDAP berhasil dengan AD BSSN
- [ ] Credential valid menghasilkan kode sukses
- [ ] Credential invalid menghasilkan 401
- [ ] Timeout ditangani dengan graceful error
- [ ] User attributes terbaca dengan lengkap

---

#### FR-JWT-002: Penerbitan JWT Access Token
**Deskripsi**: Setelah autentikasi AD berhasil, sistem menerbitkan JWT yang berisi informasi user dan peran.

**Detail**:
- **Algoritma Signing**: HS256 (HMAC-SHA256)
- **Secret Key**: Min 32 karakter, disimpan dalam environment variable, tidak dalam kode sumber
- **Masa Berlaku**: 8 jam (28800 detik)
- **Payload Claims**:
  ```
  {
    "sub": "username",                    // user identifier
    "username": "NIP_or_username",        // display name
    "roles": ["evaluator_spbe", ...],    // array of PBAC roles
    "dept": "KODE_UNIT_KERJA",           // department code
    "sid": "session-unique-id",          // session identifier
    "iat": 1620000000,                   // issued at
    "exp": 1620028800,                   // expiration
    "jti": "unique-token-id"             // JWT ID for blacklist
  }
  ```
- **Format Delivery**: Bearer token dalam Authorization header
- **Token Encoding**: UTF-8 base64url (standard JWT)

**Acceptance Criteria:**
- [ ] Token ditandatangani dengan HS256
- [ ] Payload berisi semua klaim yang diperlukan
- [ ] Token valid selama 8 jam
- [ ] Token invalid setelah 8 jam
- [ ] Token dapat didecode dan diverifikasi

---

#### FR-JWT-003: Penerbitan Refresh Token
**Deskripsi**: Sistem menerbitkan refresh token terpisah untuk perpanjangan sesi tanpa re-login.

**Detail**:
- **Algoritma Signing**: HS256 (sama dengan access token)
- **Masa Berlaku**: 7 hari (604800 detik)
- **Storage**: HttpOnly cookie (tidak accessible dari JavaScript)
- **Cookie Attributes**:
  - `HttpOnly: true` (proteksi dari XSS)
  - `Secure: true` (hanya HTTPS)
  - `SameSite: Strict` (proteksi dari CSRF)
  - `Path: /api/auth/refresh`
  - `Domain: internal.pusdatik.bssn.go.id` (sesuaikan dengan domain)
- **Payload**:
  ```
  {
    "sub": "username",
    "type": "refresh",
    "jti": "refresh-token-id",
    "iat": 1620000000,
    "exp": 1620604800
  }
  ```
- **Rotasi**: Refresh token baru diterbitkan setiap kali digunakan (rolling refresh)

**Acceptance Criteria:**
- [ ] Refresh token disimpan dalam HttpOnly cookie
- [ ] Refresh token berlaku 7 hari
- [ ] Refresh token dapat digunakan untuk mendapatkan access token baru
- [ ] Refresh token lama diinvalidasi setelah digunakan (rolling rotation)
- [ ] Cookie attributes sesuai spesifikasi

---

#### FR-JWT-004: Validasi Token pada Setiap Request
**Deskripsi**: Middleware JWT harus memvalidasi token pada setiap permintaan ke API endpoint yang dilindungi.

**Detail**:
- **Validasi yang dilakukan**:
  1. Token presence check: header `Authorization: Bearer <token>`
  2. Format validation: token terdiri dari 3 bagian (header.payload.signature)
  3. Signature verification: signature cocok dengan algoritma HS256
  4. Claims validation: semua klaim wajib ada (sub, roles, dept, exp, jti)
  5. Expiration check: klaim `exp` lebih besar dari current timestamp
  6. Algorithm check: hanya HS256 yang diterima (TIDAK `none`)
  7. Blacklist check: `jti` tidak ada dalam daftar token yang di-logout
  8. Scope check: peran user sesuai dengan resource yang diminta
- **Timeout validasi**: max 100ms
- **Error handling**:
  - Token tidak ada → 401 Unauthorized
  - Token invalid → 401 Unauthorized
  - Token expired → 401 Unauthorized
  - Token tidak authorized untuk resource → 403 Forbidden
  - Processing error → 500 Internal Server Error

**Acceptance Criteria:**
- [ ] Valid token diterima untuk semua request
- [ ] Invalid token ditolak dengan 401
- [ ] Expired token ditolak dengan 401
- [ ] Token dengan algoritma selain HS256 ditolak
- [ ] Token dalam blacklist ditolak
- [ ] Validasi selesai dalam < 100ms

---

#### FR-JWT-005: Kontrol Akses Berbasis Peran (PBAC)
**Deskripsi**: Sistem harus menerapkan kontrol akses berbasis peran yang dimapping dari Active Directory.

**Detail**:
- **Peran Mapping** (dari AD groups ke peran sistem):
  ```
  AD Group                              → Peran Sistem
  BSSN\Evaluator_SPBE                 → evaluator_spbe
  BSSN\Admin_PUSDATIK                 → admin_pusdatik
  BSSN\Manager_Evaluasi               → manager_evaluasi
  BSSN\Staf_PUSDATIK                  → staf_pusdatik
  ```
- **Permission Model**:
  ```
  Resource: /api/chat/query
    - evaluator_spbe: READ, EXECUTE
    - staf_pusdatik: READ, EXECUTE
    - admin_pusdatik: READ, EXECUTE, DELETE_OTHER_SESSIONS
  
  Resource: /api/knowledge-base/upload
    - admin_pusdatik: CREATE, UPDATE, DELETE
    - manager_evaluasi: READ
  
  Resource: /api/audit/logs
    - admin_pusdatik: READ
    - manager_evaluasi: READ (filter by dept)
  ```
- **Enforcement Point**: Setiap endpoint API harus deklaratif mendefinisikan required roles
- **Default-Deny**: Request dengan peran tidak sesuai → 403 Forbidden

**Acceptance Criteria:**
- [ ] AD groups berhasil dimapping ke peran sistem
- [ ] User hanya dapat mengakses resource sesuai peran
- [ ] Request tanpa peran yang sesuai ditolak dengan 403
- [ ] Mapping peran dapat diupdate tanpa restart aplikasi (config-driven)

---

#### FR-JWT-006: Session Management dan Logout
**Deskripsi**: Sistem harus mengelola sesi pengguna dan memungkinkan logout yang meninvalidasi token.

**Detail**:
- **Session Tracking**:
  - Setiap login menciptakan session dengan `session_id` unik (UUID v4)
  - Session info disimpan di Redis dengan key: `session:{session_id}`
  - Session data mencakup: `user`, `roles`, `login_time`, `last_activity`, `device_info`
  - TTL session: 8 jam (sama dengan token)
- **Logout**:
  - Token `jti` (JWT ID) dimasukkan ke token blacklist
  - Blacklist disimpan di Redis dengan key: `blacklist:{jti}`
  - TTL blacklist: 8 jam (durasi maksimal token berlaku)
  - Refresh token cookie dihapus (Set-Cookie dengan `Max-Age=0`)
- **Session Invalidation**:
  - User bisa logout dari satu device
  - Admin bisa force-logout user dari semua devices
  - Logout admin pengguna lain → invalidate semua session user tersebut
- **Activity Tracking**:
  - Setiap request mengupdate `last_activity` dalam session
  - Jika inactive > 4 jam → session otomatis expire (optional)

**Acceptance Criteria:**
- [ ] Login menciptakan session unik
- [ ] Logout memasukkan token ke blacklist
- [ ] Token dalam blacklist ditolak pada request berikutnya
- [ ] Refresh token cookie dihapus saat logout
- [ ] Admin dapat force-logout user lain

---

#### FR-JWT-007: Rate Limiting per User
**Deskripsi**: Sistem harus membatasi jumlah request per pengguna untuk mencegah abuse dan DDoS.

**Detail**:
- **Rate Limit Configuration**:
  ```
  /api/chat/query: 60 requests/minute
  /api/auth/login: 5 failed attempts/minute + 10 requests/minute
  /api/auth/refresh: 20 requests/minute
  /api/knowledge-base/upload: 5 requests/minute
  /api/audit/logs: 30 requests/minute
  ```
- **Implementation**:
  - Menggunakan Redis untuk tracking request counter
  - Key: `ratelimit:{user}:{endpoint}`
  - Increment counter setiap request
  - TTL: 1 menit (reset setiap menit)
  - Jika exceed limit → response 429 Too Many Requests
  - Response header: `Retry-After: 60` (berapa detik hingga bisa request lagi)
- **Distributed Rate Limiting**:
  - Jika multiple server instances: use Redis untuk shared counter
  - Sliding window algorithm untuk akurasi lebih baik

**Acceptance Criteria:**
- [ ] Request normal diterima sampai batas limit
- [ ] Request over limit ditolak dengan 429
- [ ] Retry-After header tersedia
- [ ] Counter di-reset setiap periode
- [ ] Berbeda user tidak saling mempengaruhi limit

---

#### FR-JWT-008: Audit Logging
**Deskripsi**: Sistem harus mencatat semua aktivitas autentikasi dan otorisasi untuk keperluan audit dan troubleshooting.

**Detail**:
- **Log Events**:
  ```
  1. Authentication Attempt
     - timestamp, username, status (success/failed), reason
     - source_ip, user_agent, login_method
  
  2. Token Issued
     - timestamp, username, session_id, jti
     - roles, ttl, issued_by (system)
  
  3. Token Validated
     - timestamp, username, endpoint, status (pass/fail)
     - reason_if_failed (expired, invalid, unauthorized)
  
  4. Logout Event
     - timestamp, username, session_id, jti
     - logout_method (user_initiated, admin_forced, expired)
  
  5. Authorization Failure
     - timestamp, username, resource, required_roles, user_roles
     - action_attempted
  
  6. Rate Limit Triggered
     - timestamp, username, endpoint, attempt_count, limit
  ```
- **Storage**:
  - Primary: Database (PostgreSQL/MySQL) untuk long-term retention
  - Secondary: Structured logging (JSON format) ke log aggregation system
  - Retention: Min 90 hari untuk audit compliance
- **Accessibility**:
  - Admin dapat query audit logs via API `/api/audit/logs`
  - Filter: by username, date range, event type, status
  - Export: CSV, JSON formats
- **Security**:
  - Log tidak boleh mencatat password atau token value
  - Log entries immutable (tidak bisa diedit/dihapus setelah created)
  - Log access terbatas ke admin saja

**Acceptance Criteria:**
- [ ] Semua auth events dicatat
- [ ] Log tidak mengandung sensitive data
- [ ] Log dapat diakses dan difilter oleh admin
- [ ] Log dapat diexport untuk audit

---

### 2.2 Non-Functional Requirements

#### NFR-JWT-001: Security
- **Token Signing**: HS256 dengan secret key min 32 char
- **Transport Security**: HTTPS only (TLS 1.2+)
- **XSS Protection**: Access token di memory (Vuex), refresh token di HttpOnly cookie
- **CSRF Protection**: SameSite cookie, CSRF token untuk state-changing operations
- **Timing Attack Prevention**: Constant-time comparison untuk signature verification
- **Secret Key Rotation**: Support key rotation tanpa logout user (next refresh)

#### NFR-JWT-002: Performance
- **Token Generation**: < 50ms
- **Token Validation**: < 100ms
- **AD Authentication**: < 5s (dengan timeout dan retry)
- **Concurrent Users**: Support min 500 concurrent authenticated sessions
- **Redis Operations**: < 20ms average latency

#### NFR-JWT-003: Availability
- **Uptime**: 99.5% availability
- **Graceful Degradation**: Jika Redis down → use in-memory cache (limited)
- **Fallback**: Jika AD down → 503 Service Unavailable (jangan gunakan cache credentials)
- **Recovery**: Automatic retry dengan exponential backoff

#### NFR-JWT-004: Scalability
- **Horizontal Scaling**: Stateless JWT (bisa multiple server instances)
- **Redis Clustering**: Support Redis cluster untuk shared session state
- **Database Connection Pool**: Configurable pool size

#### NFR-JWT-005: Compliance
- **Standards**: RFC 7519 (JWT), RFC 6234 (HMAC-SHA256)
- **Security Standards**: OWASP API Security Top 10, OWASP Top 10
- **Data Protection**: Compliance dengan regulasi keamanan data pemerintah Indonesia

---

## 3. ARCHITECTURE & COMPONENTS

### 3.1 System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                    Frontend (Vue.js 3)                          │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ Login Page    │ Chatbot Interface    │ Session Manager    │   │
│  │ (credentials) │ (chat UI)            │ (memory store)     │   │
│  └──────────────────────────────────────────────────────────┘   │
│              ↓                                ↓                   │
│         POST /auth/login              GET /api/chat/query        │
│         + (credentials)               + Authorization header     │
│                                       + (access_token)           │
└─────────────────────────────────────────────────────────────────┘
                 │                              │
                 ↓                              ↓
        ┌────────────────────┬─────────────────────────────────┐
        │                    │                                 │
        │              Backend (FastAPI)                       │
        │    ┌──────────────────────────────────────────────┐  │
        │    │ Router /auth/login                           │  │
        │    │ - Extract username, password                │  │
        │    │ - Call LDAP Authenticator                   │  │
        │    │ - Retrieve AD groups & attributes           │  │
        │    │ - Map groups to PBAC roles                  │  │
        │    │ - Generate JWT (access + refresh)           │  │
        │    │ - Store session in Redis                    │  │
        │    │ - Return token + set HttpOnly cookie        │  │
        │    └──────────────────────────────────────────────┘  │
        │                    ↓                                  │
        │    ┌──────────────────────────────────────────────┐  │
        │    │ JWT Validation Middleware                    │  │
        │    │ - Extract token from Authorization header   │  │
        │    │ - Verify signature (HS256)                  │  │
        │    │ - Check expiration                          │  │
        │    │ - Check blacklist (Redis)                   │  │
        │    │ - Extract claims (roles, dept, user)        │  │
        │    │ - Attach to request context                 │  │
        │    └──────────────────────────────────────────────┘  │
        │                    ↓                                  │
        │    ┌──────────────────────────────────────────────┐  │
        │    │ PBAC Authorization Decorator                 │  │
        │    │ - Check required_roles vs user.roles        │  │
        │    │ - Return 403 if unauthorized                │  │
        │    │ - Log authorization event                   │  │
        │    └──────────────────────────────────────────────┘  │
        │                    ↓                                  │
        │    ┌──────────────────────────────────────────────┐  │
        │    │ Rate Limit Middleware                        │  │
        │    │ - Increment counter in Redis                │  │
        │    │ - Check against limit config                │  │
        │    │ - Return 429 if exceeded                    │  │
        │    └──────────────────────────────────────────────┘  │
        │                    ↓                                  │
        │    ┌──────────────────────────────────────────────┐  │
        │    │ Protected Endpoint Handlers                  │  │
        │    │ - /api/chat/query                           │  │
        │    │ - /api/knowledge-base/upload                │  │
        │    │ - /api/auth/logout                          │  │
        │    │ - /api/audit/logs (etc)                    │  │
        │    └──────────────────────────────────────────────┘  │
        │                    ↓                                  │
        │    ┌──────────────────────────────────────────────┐  │
        │    │ Audit Logger                                 │  │
        │    │ - Log to PostgreSQL                          │  │
        │    │ - Log to structured logging (ELK/Splunk)   │  │
        │    └──────────────────────────────────────────────┘  │
        └────────────────────┬─────────────────────────────────┘
                             │
        ┌────────────────────┼─────────────────────────────────┐
        │                    │                                 │
        ↓                    ↓                                 ↓
    ┌─────────┐        ┌──────────┐                    ┌──────────────┐
    │   AD    │        │  Redis   │                    │ PostgreSQL   │
    │ (LDAP)  │        │(sessions │                    │  (audit logs)│
    │         │        │tokens)   │                    │              │
    └─────────┘        └──────────┘                    └──────────────┘
```

---

### 3.2 Component Breakdown

#### 3.2.1 Frontend Components

**Component: AuthStore (Vuex)**
```
Purpose: Manage authentication state in frontend
Responsibilities:
  - Store access token in memory (NOT localStorage)
  - Store refresh token handling via cookies (backend managed)
  - Track user info (username, roles, department)
  - Track login status and session info
  - Handle token expiration logic
Properties:
  - state.accessToken: string | null
  - state.user: { username, roles, dept, sid } | null
  - state.isAuthenticated: boolean
  - state.sessionExpiry: timestamp
Methods:
  - setAccessToken(token)
  - clearAccessToken()
  - setUser(userInfo)
  - clearUser()
  - checkTokenExpiry(): boolean
  - getAuthHeader(): string
Files:
  - frontend/src/store/modules/auth.ts
  - frontend/src/store/modules/session.ts
```

**Component: LoginView**
```
Purpose: Render login form and handle authentication flow
Responsibilities:
  - Render form fields (username, password)
  - Validate input (required fields, format)
  - Call POST /auth/login
  - Handle success: store token, redirect to dashboard
  - Handle error: display error message, log attempt
Properties:
  - form.username: string
  - form.password: string
  - loading: boolean
  - error: string | null
  - rememberMe: boolean (optional)
Methods:
  - onSubmit(): async
  - onForgotPassword(): void
  - validate(): boolean
Files:
  - frontend/src/views/LoginView.vue
  - frontend/src/components/LoginForm.vue
```

**Component: HttpClient (Axios Interceptor)**
```
Purpose: Inject JWT token into all API requests automatically
Responsibilities:
  - Intercept outgoing requests
  - Inject Authorization header with access token
  - Handle 401 responses: trigger refresh token flow
  - Handle 403 responses: redirect to unauthorized page
  - Handle 429 responses: display rate limit message
Properties:
  - Default headers config
  - Interceptor queue for retries
Methods:
  - setupInterceptors(store)
  - onRequest(config)
  - onResponse(response)
  - onError(error): Promise
  - refreshAccessToken(): Promise<token>
Files:
  - frontend/src/api/httpClient.ts
  - frontend/src/api/interceptors.ts
```

**Component: AuthGuard (Vue Router)**
```
Purpose: Protect routes that require authentication
Responsibilities:
  - Check if user is authenticated before navigation
  - Check if token expired
  - Trigger refresh if token about to expire
  - Redirect to login if not authenticated
Properties:
  - Protected routes list
Methods:
  - beforeEach(to, from, next)
  - requireAuth(roles: string[])
Files:
  - frontend/src/router/guards/authGuard.ts
  - frontend/src/router/index.ts
```

---

#### 3.2.2 Backend Components

**Component: LDAPAuthenticator**
```
Language: Python
Purpose: Authenticate users against Active Directory
Responsibilities:
  - Establish LDAP connection to AD server
  - Perform bind with user credentials
  - Retrieve user attributes (sAMAccountName, memberOf, department, etc.)
  - Parse memberOf to extract group names
  - Handle LDAP errors gracefully
  - Connection pooling and timeout handling
Configuration:
  AD_SERVER_URL: "ldap://ad.bssn.go.id:389"
  AD_BASE_DN: "dc=bssn,dc=go,dc=id"
  AD_DOMAIN: "bssn.go.id"
  AD_TIMEOUT: 10  # seconds
  AD_RETRY_COUNT: 2
  LDAP_POOL_MIN: 5
  LDAP_POOL_MAX: 20
Methods:
  - authenticate(username: str, password: str) -> dict
  - get_user_groups(username: str) -> list[str]
  - get_user_attributes(username: str) -> dict
  - test_connection() -> bool
Dependencies:
  - ldap3 (LDAP protocol)
  - python-ldap (alternative)
Files:
  - backend/app/auth/ldap_authenticator.py
  - backend/config/ldap_config.py
```

**Component: JWTManager**
```
Language: Python
Purpose: Create and manage JWT tokens
Responsibilities:
  - Generate access token (8-hour TTL)
  - Generate refresh token (7-day TTL)
  - Sign tokens with HS256 algorithm
  - Validate token structure
  - Extract claims from token
  - Support token rotation
Configuration:
  JWT_SECRET_KEY: env("JWT_SECRET_KEY")  # min 32 chars
  JWT_ALGORITHM: "HS256"
  JWT_ACCESS_TOKEN_EXPIRE_HOURS: 8
  JWT_REFRESH_TOKEN_EXPIRE_DAYS: 7
Methods:
  - create_access_token(data: dict, expires_delta: timedelta) -> str
  - create_refresh_token(data: dict) -> str
  - decode_token(token: str) -> dict
  - verify_token_signature(token: str) -> bool
  - get_token_expiry(token: str) -> datetime
Dependencies:
  - PyJWT (jwt library)
  - datetime
  - uuid
Files:
  - backend/app/auth/jwt_manager.py
  - backend/config/jwt_config.py
```

**Component: TokenValidationMiddleware**
```
Language: Python
Purpose: Validate JWT on every protected request
Responsibilities:
  - Extract token from Authorization header
  - Validate token signature
  - Check expiration
  - Check blacklist (Redis)
  - Extract claims and attach to request
  - Handle validation errors
Methods:
  - __call__(request) -> request with user context
  - extract_token(authorization_header: str) -> str
  - validate_token(token: str) -> dict | None
  - is_token_blacklisted(jti: str) -> bool
  - attach_user_context(request, token_claims)
Dependencies:
  - JWT Manager
  - Redis client
  - FastAPI middleware
Files:
  - backend/app/middleware/jwt_middleware.py
  - backend/app/dependencies/token_dependency.py
```

**Component: PBACAuthorizationDecorator**
```
Language: Python
Purpose: Enforce role-based access control on endpoints
Responsibilities:
  - Check if user roles match required roles
  - Check if user department has permission
  - Return 403 if unauthorized
  - Log authorization attempt
Methods:
  - require_roles(required_roles: list[str])  # decorator
  - require_department(required_depts: list[str])  # decorator
  - check_permission(user_roles: list[str], required_roles: list[str]) -> bool
  - log_authorization_event(user, resource, required_roles, result)
Dependencies:
  - Audit Logger
  - FastAPI dependencies
Files:
  - backend/app/dependencies/auth_dependencies.py
  - backend/app/security/pbac.py
```

**Component: RateLimitMiddleware**
```
Language: Python
Purpose: Limit requests per user per endpoint
Responsibilities:
  - Track request count per user per endpoint
  - Enforce rate limit based on configuration
  - Return 429 when limit exceeded
  - Provide Retry-After header
  - Support distributed rate limiting via Redis
Configuration:
  RATE_LIMITS:
    /api/chat/query: "60/minute"
    /api/auth/login: "10/minute"  # + 5 failed attempts/minute
    /api/auth/refresh: "20/minute"
    /api/knowledge-base/upload: "5/minute"
Methods:
  - __call__(request) -> response | 429
  - increment_counter(user: str, endpoint: str)
  - is_rate_limited(user: str, endpoint: str) -> bool
  - get_retry_after(user: str, endpoint: str) -> int
Dependencies:
  - Redis
  - FastAPI middleware
Files:
  - backend/app/middleware/rate_limit_middleware.py
  - backend/config/rate_limit_config.py
```

**Component: SessionManager**
```
Language: Python
Purpose: Manage user sessions
Responsibilities:
  - Create session on login
  - Store session info in Redis
  - Update last activity timestamp
  - Invalidate session on logout
  - Support force-logout by admin
  - Cleanup expired sessions
Configuration:
  SESSION_TTL: 8 * 3600  # 8 hours in seconds
  INACTIVITY_TIMEOUT: 4 * 3600  # Optional: auto-logout after 4 hours
Methods:
  - create_session(user: str, roles: list, jti: str) -> session_id
  - get_session(session_id: str) -> dict
  - update_activity(session_id: str)
  - invalidate_session(session_id: str)
  - invalidate_user_sessions(user: str)  # force-logout all sessions
  - list_user_sessions(user: str) -> list[dict]
  - cleanup_expired_sessions()
Data Structure in Redis:
  Key: session:{session_id}
  Value: {
    "user": "username",
    "roles": ["role1", "role2"],
    "dept": "UNIT_KERJA",
    "jti": "token-jti",
    "login_time": timestamp,
    "last_activity": timestamp,
    "device_info": {...}
  }
  TTL: 8 hours
Dependencies:
  - Redis
  - UUID
Files:
  - backend/app/session/session_manager.py
```

**Component: TokenBlacklist**
```
Language: Python
Purpose: Maintain blacklist of invalidated tokens
Responsibilities:
  - Add token JTI to blacklist on logout
  - Check if token is blacklisted
  - Automatic cleanup of expired entries
  - Support distributed blacklist via Redis
Methods:
  - add_to_blacklist(jti: str, expiry: datetime)
  - is_blacklisted(jti: str) -> bool
  - remove_from_blacklist(jti: str)  # optional, TTL handles auto-cleanup
Data Structure in Redis:
  Key: blacklist:{jti}
  Value: true
  TTL: same as token expiry time
Dependencies:
  - Redis
  - JWT Manager (for getting token expiry)
Files:
  - backend/app/auth/token_blacklist.py
```

**Component: AuditLogger**
```
Language: Python
Purpose: Log all authentication and authorization events
Responsibilities:
  - Log authentication attempts
  - Log token lifecycle events (issued, validated, invalidated)
  - Log authorization successes and failures
  - Log rate limit events
  - Store in PostgreSQL and structured logging system
Data Model:
  Table: audit_logs
  Columns:
    - id (UUID primary key)
    - timestamp (datetime)
    - event_type (enum: AUTH_ATTEMPT, TOKEN_ISSUED, TOKEN_VALIDATED, LOGOUT, AUTHZ_FAILURE, RATE_LIMIT)
    - username (string, nullable)
    - resource (string, nullable) - /api/endpoint
    - status (enum: SUCCESS, FAILED)
    - reason (string) - detailed reason if failed
    - source_ip (string)
    - user_agent (string)
    - roles (string array)
    - department (string)
    - session_id (string, nullable)
    - additional_data (JSON) - flexible field for extra info
Methods:
  - log_auth_attempt(username: str, status: str, reason: str, ip: str, user_agent: str)
  - log_token_event(event_type: str, username: str, jti: str, roles: list, status: str)
  - log_authorization_event(username: str, resource: str, required_roles: list, user_roles: list, status: str)
  - log_rate_limit_event(username: str, endpoint: str, attempt_count: int, limit: int)
  - query_logs(filters: dict) -> list[dict]
  - export_logs(format: str, filters: dict) -> bytes  # CSV, JSON
Dependencies:
  - SQLAlchemy (ORM)
  - PostgreSQL
  - Structured logging (Python logging module)
Files:
  - backend/app/audit/audit_logger.py
  - backend/app/models/audit_log.py
  - backend/app/db/migrations/001_create_audit_logs_table.sql
```

**Component: AuthenticationRouter (FastAPI)**
```
Language: Python
Purpose: Expose authentication endpoints
Endpoints:

1. POST /api/auth/login
   Request:
     {
       "username": "string",
       "password": "string"
     }
   Response (200):
     {
       "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
       "token_type": "bearer",
       "expires_in": 28800,
       "user": {
         "username": "username",
         "roles": ["evaluator_spbe"],
         "department": "PUSDATIK",
         "display_name": "Nama Lengkap"
       }
     }
   Response (401):
     {
       "detail": "Invalid credentials or user not authorized"
     }
   Side Effects:
     - Set HttpOnly cookie with refresh_token
     - Create session in Redis
     - Log authentication attempt
     - Check rate limit (5/minute for failed attempts)

2. POST /api/auth/refresh
   Request: (no body, uses HttpOnly cookie)
   Response (200):
     {
       "access_token": "new-token...",
       "token_type": "bearer",
       "expires_in": 28800
     }
   Response (401):
     {
       "detail": "Refresh token expired or invalid"
     }
   Side Effects:
     - Issue new access token
     - Rotate refresh token (new cookie)
     - Update session last_activity
     - Log token refresh event

3. POST /api/auth/logout
   Request: (empty body)
   Response (200):
     {
       "detail": "Logout successful"
     }
   Side Effects:
     - Add token JTI to blacklist
     - Invalidate session
     - Clear refresh token cookie
     - Log logout event
   Requires: Authentication

4. POST /api/auth/validate
   Request: (no body, uses Authorization header)
   Response (200):
     {
       "valid": true,
       "user": {...},
       "expires_in": 3600
     }
   Response (401):
     {
       "valid": false
     }
   Side Effects:
     - None (read-only)
   Requires: Authentication

5. POST /api/auth/force-logout (admin only)
   Request:
     {
       "username": "string"  // target user
     }
   Response (200):
     {
       "detail": "User logged out from all sessions"
     }
   Side Effects:
     - Invalidate all sessions of target user
     - Log force-logout event
   Requires: admin_pusdatik role

Files:
  - backend/app/routers/auth_routes.py
  - backend/app/schemas/auth_schemas.py
```

---

#### 3.2.3 Data Storage Components

**Component: Redis**
```
Purpose: Store session data and token blacklist
Configuration:
  Host: [config from environment]
  Port: 6379 (default)
  Database: 0 (sessions), 1 (blacklist), 2 (rate_limit)
  Password: [config from environment]
  SSL: true (if in production)
  Max Connections: 50
Data Keys:
  1. session:{session_id}
     - TTL: 8 hours
     - Type: Hash
     - Data: user, roles, dept, login_time, last_activity, device_info
  
  2. blacklist:{jti}
     - TTL: token expiry time (8 hours max)
     - Type: String
     - Data: true
  
  3. ratelimit:{username}:{endpoint}
     - TTL: 1 minute (sliding window)
     - Type: Sorted Set (or simple string with ttl)
     - Data: request count

Dependencies:
  - redis-py (Python client)
  - Connection pooling
```

**Component: PostgreSQL Database**
```
Purpose: Store audit logs
Table: audit_logs
Columns:
  - id (UUID, PRIMARY KEY)
  - timestamp (TIMESTAMP, NOT NULL, INDEX)
  - event_type (VARCHAR(50), NOT NULL, INDEX)
  - username (VARCHAR(255), INDEX)
  - resource (VARCHAR(255), INDEX)
  - status (VARCHAR(20), NOT NULL)  # SUCCESS, FAILED
  - reason (TEXT)
  - source_ip (VARCHAR(45))
  - user_agent (VARCHAR(500))
  - roles (TEXT[])  # array type
  - department (VARCHAR(100))
  - session_id (VARCHAR(100))
  - additional_data (JSONB)
  - created_at (TIMESTAMP, DEFAULT NOW())

Indexes:
  - (timestamp DESC) for efficient time-range queries
  - (username, timestamp) for user activity history
  - (event_type, timestamp) for event type filtering
  - (status, timestamp) for success/failure analysis

Retention Policy:
  - Keep records for min 90 days
  - Archive to cold storage after 1 year
  - Never delete (for compliance)

Dependencies:
  - sqlalchemy (ORM)
  - alembic (migrations)
```

---

## 4. API ENDPOINT SPECIFICATIONS

### 4.1 Authentication Endpoints

#### Endpoint: POST /api/auth/login
```
Purpose: Authenticate user and issue tokens
Scope: Public (no auth required)
Rate Limit: 10 requests/minute + 5 failed attempts/minute

Request:
  Content-Type: application/json
  Body:
    {
      "username": "string (required)",  // NIP or username
      "password": "string (required)"   // plaintext, transmitted via HTTPS
    }

Response (200 OK):
  {
    "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ...",
    "token_type": "bearer",
    "expires_in": 28800,  # seconds
    "user": {
      "username": "username",
      "roles": ["evaluator_spbe", "staf_pusdatik"],
      "department": "PUSDATIK",
      "display_name": "Nama Lengkap Pegawai",
      "email": "user@bssn.go.id",
      "session_id": "550e8400-e29b-41d4-a716-446655440000"
    }
  }
  
  Headers:
    Set-Cookie: refresh_token=<jwt>; HttpOnly; Secure; SameSite=Strict; Path=/api/auth/refresh; Max-Age=604800

Response (401 Unauthorized):
  {
    "detail": "Invalid credentials",
    "error_code": "INVALID_CREDENTIALS"
  }

Response (401 Unauthorized):
  {
    "detail": "User not authorized to access this system",
    "error_code": "USER_NOT_AUTHORIZED"
  }

Response (429 Too Many Requests):
  {
    "detail": "Too many login attempts. Please try again later.",
    "retry_after": 60
  }

Response (503 Service Unavailable):
  {
    "detail": "Active Directory service temporarily unavailable",
    "error_code": "AD_UNAVAILABLE"
  }

Error Handling:
  - Invalid username/password → 401 with reason
  - User locked in AD → 401 with specific message
  - AD connection timeout → 503 (not 401)
  - Rate limit exceeded → 429
  - Unexpected error → 500 with generic message (log details internally)

Implementation Logic:
  1. Validate input (both fields required, format check)
  2. Check rate limit on username (5 failed/min)
  3. Call LDAPAuthenticator.authenticate(username, password)
  4. If failed → log attempt, increment failed counter, return 401
  5. If success → retrieve user groups from AD
  6. Map AD groups to PBAC roles
  7. Create JWT access token with claims
  8. Create JWT refresh token
  9. Create session in Redis
  10. Return access token + set refresh token cookie
  11. Log successful authentication
```

#### Endpoint: POST /api/auth/refresh
```
Purpose: Refresh expired or expiring access token
Scope: Public (uses refresh token from cookie)
Rate Limit: 20 requests/minute

Request:
  Cookie: refresh_token=<jwt>
  Body: (empty)

Response (200 OK):
  {
    "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
    "token_type": "bearer",
    "expires_in": 28800
  }
  
  Headers:
    Set-Cookie: refresh_token=<new-jwt>; HttpOnly; Secure; SameSite=Strict; Path=/api/auth/refresh; Max-Age=604800

Response (401 Unauthorized):
  {
    "detail": "Refresh token invalid or expired",
    "error_code": "INVALID_REFRESH_TOKEN"
  }

Response (429 Too Many Requests):
  {
    "detail": "Too many refresh attempts",
    "retry_after": 60
  }

Implementation Logic:
  1. Extract refresh_token from HttpOnly cookie
  2. If missing → 401
  3. Validate refresh token signature
  4. If invalid/expired → 401, clear cookie
  5. If valid → extract username from token
  6. Retrieve session from Redis
  7. Generate new access token with same claims
  8. Generate new refresh token (rolling rotation)
  9. Update session in Redis
  10. Return new access token + new refresh token cookie
  11. Old refresh token automatically invalidated when new one issued
```

#### Endpoint: POST /api/auth/logout
```
Purpose: Logout user and invalidate tokens
Scope: Protected (requires valid access token)
Rate Limit: 10 requests/minute

Request:
  Authorization: Bearer <access_token>
  Body: (empty)

Response (200 OK):
  {
    "detail": "Logout successful",
    "message": "You have been logged out"
  }
  
  Headers:
    Set-Cookie: refresh_token=; HttpOnly; Secure; SameSite=Strict; Path=/api/auth/refresh; Max-Age=0

Response (401 Unauthorized):
  {
    "detail": "Invalid or expired token"
  }

Implementation Logic:
  1. Validate access token
  2. Extract jti and session_id from token
  3. Add jti to blacklist with TTL = token expiry time
  4. Invalidate session in Redis
  5. Clear refresh token cookie (Max-Age=0)
  6. Log logout event
  7. Return success
```

#### Endpoint: POST /api/auth/validate
```
Purpose: Validate current token without using protected resource
Scope: Public (uses Authorization header, validates it)
Rate Limit: 30 requests/minute

Request:
  Authorization: Bearer <access_token>
  Body: (empty)

Response (200 OK):
  {
    "valid": true,
    "user": {
      "username": "username",
      "roles": ["evaluator_spbe"],
      "department": "PUSDATIK"
    },
    "expires_in": 3600,  # seconds until expiration
    "expired_at": "2026-05-12T15:00:00Z"
  }

Response (401 Unauthorized):
  {
    "valid": false,
    "reason": "Token expired"  // or "Invalid signature", "Blacklisted", etc.
  }

Implementation Logic:
  1. Try to extract and validate token
  2. If valid → return user info + expires_in
  3. If invalid → return false + reason
  4. No side effects (read-only)
```

#### Endpoint: POST /api/auth/force-logout (ADMIN ONLY)
```
Purpose: Admin force-logout a user from all sessions
Scope: Protected (requires admin_pusdatik role)
Rate Limit: 5 requests/minute

Request:
  Authorization: Bearer <access_token>
  Content-Type: application/json
  Body:
    {
      "username": "string (required)",  // target user
      "reason": "string (optional)"     // reason for force logout
    }

Response (200 OK):
  {
    "detail": "User logged out from all sessions",
    "sessions_invalidated": 2,
    "timestamp": "2026-05-12T12:00:00Z"
  }

Response (401 Unauthorized):
  {
    "detail": "Invalid or expired token"
  }

Response (403 Forbidden):
  {
    "detail": "You do not have permission to force logout users",
    "required_role": "admin_pusdatik"
  }

Response (404 Not Found):
  {
    "detail": "User not found"
  }

Implementation Logic:
  1. Validate access token
  2. Check if user has admin_pusdatik role (if not → 403)
  3. Get all sessions for target username
  4. For each session: invalidate in Redis + add token JTI to blacklist
  5. Log force-logout event with reason
  6. Return count of invalidated sessions
```

---

### 4.2 Protected Endpoint Example

#### Endpoint: GET /api/chat/query
```
Purpose: Query chatbot with RAG
Scope: Protected (requires valid access token)
Auth Required Roles: [evaluator_spbe, staf_pusdatik, admin_pusdatik]
Rate Limit: 60 requests/minute

Request:
  Authorization: Bearer <access_token>
  Content-Type: application/json
  Body:
    {
      "query": "Apa itu indikator SPBE?",
      "session_id": "550e8400-e29b-41d4-a716-446655440000"
    }

Response (200 OK):
  {
    "answer": "Indikator SPBE adalah...",
    "citations": [
      {
        "pasal": "Pasal 2",
        "peraturan": "Perpres No. 95 Tahun 2018",
        "excerpt": "..."
      }
    ],
    "session_id": "550e8400-e29b-41d4-a716-446655440000"
  }

Response (401 Unauthorized):
  {
    "detail": "Invalid or expired token"
  }

Response (403 Forbidden):
  {
    "detail": "Your role does not have access to this resource",
    "required_roles": ["evaluator_spbe", "staf_pusdatik", "admin_pusdatik"],
    "your_roles": ["viewer"]
  }

Response (429 Too Many Requests):
  {
    "detail": "Rate limit exceeded",
    "retry_after": 15,
    "limit": "60 requests per minute"
  }

Implementation:
  1. Middleware validates JWT
  2. Middleware checks roles (PBAC decorator)
  3. Rate limit middleware checks limit
  4. If all pass → execute handler
  5. Handler processes query with RAG pipeline
  6. Log API call in audit logs
```

---

## 5. INTEGRATION CHECKLIST

### 5.1 Backend Setup

- [ ] **Redis Setup**
  - [ ] Install Redis server
  - [ ] Configure connection pool (min 5, max 20)
  - [ ] Set up separate databases (0: sessions, 1: blacklist, 2: ratelimit)
  - [ ] Test connection

- [ ] **PostgreSQL Setup**
  - [ ] Create audit_logs table
  - [ ] Create indexes on timestamp, username, event_type
  - [ ] Set up connection pool
  - [ ] Configure retention policy (90+ days)

- [ ] **LDAP Configuration**
  - [ ] Get AD server URL, port, base DN from PUSDATIK IT
  - [ ] Configure LDAP_CONFIG in code
  - [ ] Test LDAP connection with test credentials
  - [ ] Verify attribute mapping (memberOf, department, etc.)

- [ ] **Environment Variables**
  ```
  JWT_SECRET_KEY=<min 32 random chars>
  JWT_ALGORITHM=HS256
  JWT_ACCESS_TOKEN_EXPIRE_HOURS=8
  JWT_REFRESH_TOKEN_EXPIRE_DAYS=7
  
  LDAP_SERVER_URL=ldap://ad.bssn.go.id:389
  LDAP_BASE_DN=dc=bssn,dc=go,dc=id
  LDAP_DOMAIN=bssn.go.id
  LDAP_TIMEOUT=10
  LDAP_RETRY_COUNT=2
  
  REDIS_URL=redis://localhost:6379
  REDIS_PASSWORD=<if configured>
  
  DATABASE_URL=postgresql://user:password@localhost/audit_db
  
  FRONTEND_DOMAIN=http://localhost:5173  # for CORS
  ```

- [ ] **Middleware Registration**
  - [ ] Register JWT validation middleware
  - [ ] Register PBAC authorization decorator
  - [ ] Register rate limit middleware
  - [ ] Register audit logging
  - [ ] Set middleware order: JWT → PBAC → RateLimit

- [ ] **Routes Registration**
  - [ ] Register /api/auth/* routes
  - [ ] Register @require_roles decorator on protected routes
  - [ ] Test all routes with Postman/curl

- [ ] **Logging Configuration**
  - [ ] Configure Python logging (file, console, ELK)
  - [ ] Set up structured JSON logging
  - [ ] Configure log rotation (daily, 30 days retention)

---

### 5.2 Frontend Setup

- [ ] **Vuex Store Configuration**
  - [ ] Create AuthStore module
  - [ ] Initialize state (accessToken, user, isAuthenticated)
  - [ ] Implement mutations and actions

- [ ] **HTTP Client Setup**
  - [ ] Configure Axios with interceptors
  - [ ] Implement request interceptor (inject token)
  - [ ] Implement response interceptor (handle 401, 403, 429)
  - [ ] Implement auto-refresh logic on 401

- [ ] **Login Page**
  - [ ] Create LoginView component
  - [ ] Add form validation
  - [ ] Implement login error handling
  - [ ] Add loading state during request

- [ ] **Auth Guard**
  - [ ] Create router guard for protected routes
  - [ ] Check authentication status
  - [ ] Check token expiration
  - [ ] Redirect to login if needed

- [ ] **Protected Routes**
  - [ ] Add meta: { requiresAuth: true } to routes
  - [ ] Test navigation to protected routes

- [ ] **Session Management**
  - [ ] Display remaining session time
  - [ ] Show warning before token expiry
  - [ ] Implement auto-refresh before expiry

- [ ] **Logout**
  - [ ] Add logout button
  - [ ] Call /api/auth/logout on click
  - [ ] Clear AuthStore
  - [ ] Clear HttpOnly cookie (backend handles)
  - [ ] Redirect to login

- [ ] **Error Handling**
  - [ ] Display 401 message: "Session expired, please login again"
  - [ ] Display 403 message: "You don't have permission"
  - [ ] Display 429 message: "Too many requests, please wait"
  - [ ] Display 503 message: "Service temporarily unavailable"

---

### 5.3 Security Hardening

- [ ] **HTTPS/TLS**
  - [ ] Enable HTTPS on all endpoints
  - [ ] Use TLS 1.2+ (disable TLS 1.0, 1.1)
  - [ ] Install valid SSL certificate (not self-signed in production)

- [ ] **CORS Configuration**
  - [ ] Allow only frontend domain (not *)
  - [ ] Allow credentials (for cookies)
  - [ ] Restrict allowed methods (GET, POST, OPTIONS)
  - [ ] Restrict allowed headers

- [ ] **Headers Security**
  - [ ] Add X-Frame-Options: DENY (prevent clickjacking)
  - [ ] Add X-Content-Type-Options: nosniff
  - [ ] Add X-XSS-Protection: 1; mode=block
  - [ ] Add Strict-Transport-Security (for HTTPS)
  - [ ] Remove Server header (don't expose framework)

- [ ] **Token Security**
  - [ ] Verify access token NOT in cookies (only refresh token)
  - [ ] Verify refresh token in HttpOnly cookie
  - [ ] Verify JWT_SECRET_KEY never logged
  - [ ] Implement key rotation strategy

- [ ] **Input Validation**
  - [ ] Validate username format (alphanumeric, no special chars)
  - [ ] Validate password length (8+ chars)
  - [ ] Sanitize all inputs to prevent LDAP injection
  - [ ] Validate JWT claims format

- [ ] **Rate Limiting**
  - [ ] Enable rate limiting on all endpoints
  - [ ] Test rate limit behavior
  - [ ] Verify 429 response + Retry-After header

- [ ] **Audit Logging**
  - [ ] Verify all auth events logged
  - [ ] Verify logs don't contain passwords/tokens
  - [ ] Test log query API
  - [ ] Verify log retention policy

- [ ] **Testing**
  - [ ] JWT signature validation test
  - [ ] Token expiration test
  - [ ] Blacklist test
  - [ ] alg:none attack test
  - [ ] Token manipulation test
  - [ ] Role-based access test

---

## 6. IMPLEMENTATION TIMELINE

| Phase | Tasks | Duration | Owner |
|-------|-------|----------|-------|
| **Phase 1: Setup** | Redis, PostgreSQL, LDAP config | 2 weeks | Backend Team |
| **Phase 2: Backend Core** | JWTManager, LDAPAuthenticator, SessionManager | 3 weeks | Backend Team |
| **Phase 3: Backend Integration** | Middleware, decorators, routers | 2 weeks | Backend Team |
| **Phase 4: Frontend Auth** | AuthStore, LoginView, HttpClient, guards | 2 weeks | Frontend Team |
| **Phase 5: Testing** | Unit tests, integration tests, security tests | 2 weeks | QA Team |
| **Phase 6: Deployment** | Staging deployment, production deployment | 1 week | DevOps Team |
| **Phase 7: Documentation** | API docs, deployment guide, admin manual | 1 week | Tech Writer |
| **Total** | | **13 weeks** | |

---

## 7. TESTING STRATEGY

### 7.1 Unit Tests

**Backend**:
```python
# test_jwt_manager.py
- test_create_access_token_valid
- test_create_access_token_with_custom_expiry
- test_decode_token_valid
- test_decode_token_expired
- test_decode_token_invalid_signature
- test_decode_token_invalid_algorithm

# test_ldap_authenticator.py
- test_authenticate_valid_credentials
- test_authenticate_invalid_credentials
- test_authenticate_ad_timeout
- test_get_user_groups

# test_rate_limit.py
- test_rate_limit_within_threshold
- test_rate_limit_exceeded
- test_rate_limit_reset_per_minute
```

**Frontend**:
```javascript
// tests/unit/store/auth.spec.ts
- test_setAccessToken
- test_clearAccessToken
- test_setUser
- test_checkTokenExpiry

// tests/unit/api/httpClient.spec.ts
- test_inject_token_in_request
- test_handle_401_response
- test_refresh_token_on_401
- test_handle_429_response
```

### 7.2 Integration Tests

```
- test_complete_login_flow
- test_complete_logout_flow
- test_token_refresh_flow
- test_force_logout_by_admin
- test_protected_endpoint_access
- test_role_based_access_control
- test_rate_limiting_across_endpoints
- test_audit_logging_events
```

### 7.3 Security Tests

```
- test_alg_none_attack_prevented
- test_token_manipulation_detected
- test_signature_verification_required
- test_expired_token_rejected
- test_blacklisted_token_rejected
- test_unauthorized_role_access_denied
- test_rate_limit_protection
- test_ad_credentials_not_cached
- test_password_not_logged
```

### 7.4 Load Tests

```
- test_concurrent_logins (500 users)
- test_concurrent_api_requests (5000 req/sec)
- test_redis_connection_pool_limits
- test_database_connection_pool_limits
- test_response_time_under_load
```

---

## 8. DEPLOYMENT CHECKLIST

**Pre-Deployment**:
- [ ] All tests passing (unit, integration, security, load)
- [ ] Code review approved
- [ ] Security audit completed
- [ ] LDAP connectivity tested on production network
- [ ] Redis and PostgreSQL accessible from application server
- [ ] SSL certificates installed
- [ ] Environment variables configured
- [ ] Database migrations applied
- [ ] Backups taken of production data

**Deployment**:
- [ ] Deploy backend code
- [ ] Deploy frontend code
- [ ] Verify all endpoints responding
- [ ] Verify authentication flow working
- [ ] Check audit logs
- [ ] Monitor error rates

**Post-Deployment**:
- [ ] Perform smoke tests
- [ ] Monitor Redis memory usage
- [ ] Monitor database performance
- [ ] Monitor error logs
- [ ] Get user feedback
- [ ] Document any issues

---

## 9. MONITORING & ALERTING

**Metrics to Monitor**:
- [ ] Authentication success rate (target: > 99%)
- [ ] Token validation latency (target: < 100ms)
- [ ] Failed login attempts (detect brute force)
- [ ] Rate limit hits (detect abuse)
- [ ] Token refresh rate (detect unusual patterns)
- [ ] Session count (detect resource exhaustion)
- [ ] Redis memory usage (prevent out-of-memory)
- [ ] PostgreSQL query performance

**Alerts to Configure**:
- [ ] High rate of failed logins (> 10/min for single user)
- [ ] High rate of 401 responses (> 50/min)
- [ ] High rate of 429 responses (> 100/min)
- [ ] Redis connection pool exhaustion
- [ ] Database connection pool exhaustion
- [ ] LDAP connection failures
- [ ] Token validation errors
- [ ] Audit log insertion failures

---

## 10. SECURITY CONSIDERATIONS

### 10.1 Threats & Mitigations

| Threat | Mitigation |
|--------|-----------|
| Credential Brute Force | Rate limiting (5 failed/min), Account lockout after N attempts |
| Token Theft | HttpOnly cookie for refresh token, HTTPS only, short TTL |
| Token Forgery | HS256 signature verification, secret key stored securely |
| Replay Attack | Token JTI + timestamp validation, blacklist on logout |
| Session Fixation | Session regeneration on login, secure session ID (UUID) |
| XSS | Access token in memory (not localStorage), HttpOnly cookie for refresh |
| CSRF | SameSite cookie, CSRF token for state-changing operations |
| LDAP Injection | Input sanitization, prepared queries/binds |
| Man-in-the-Middle | HTTPS/TLS 1.2+, HSTS header |

### 10.2 Compliance

- **OWASP API Security Top 10**: Addresses API2:2023, API4:2023, API1:2023
- **Data Protection**: Audit logs retained per regulatory requirements
- **Audit Trail**: All authentication events logged for compliance

---

## 11. APPENDIX

### A. Example JWT Payload

```json
{
  "sub": "username",
  "username": "12345678",
  "roles": ["evaluator_spbe", "staf_pusdatik"],
  "dept": "PUSDATIK",
  "sid": "550e8400-e29b-41d4-a716-446655440000",
  "iat": 1620000000,
  "exp": 1620028800,
  "jti": "abc123def456"
}
```

### B. Example Role Mapping

```python
ROLE_MAPPING = {
    "BSSN\\Evaluator_SPBE": ["evaluator_spbe"],
    "BSSN\\Staf_PUSDATIK": ["staf_pusdatik"],
    "BSSN\\Admin_PUSDATIK": ["admin_pusdatik", "staf_pusdatik"],
    "BSSN\\Manager_Evaluasi": ["manager_evaluasi", "staf_pusdatik"],
}
```

### C. Example API Error Response

```json
{
  "detail": "Invalid or expired token",
  "error_code": "INVALID_TOKEN",
  "timestamp": "2026-05-12T12:00:00Z",
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "help_url": "https://docs.pusdatik.bssn/errors/invalid_token"
}
```

---

**Document Version**: 1.0  
**Last Updated**: May 2026  
**Next Review**: August 2026
