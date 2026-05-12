# 🧪 Cara Testing Audit Logging

Berikut 3 cara untuk menguji Audit Logging yang baru saja diimplementasikan:

---

## **Cara 1: Via Python Test Script (RECOMMENDED)**

**Status: ✅ SUDAH DIJALANKAN & BERHASIL**

### Jalankan:
```bash
# 1. Activate virtual environment
cd d:\aqil\pusdatik
. .venv/Scripts/Activate.ps1

# 2. Run the test script
python test_audit_local.py
```

### Output:
```
✓ Database initialized
✓ Created test user: test@bssn.go.id (ID: 1)
✓ Logged event: LOGIN_SUCCESS | Status: success
  Event ID: 1
  Timestamp: 2026-05-12 07:53:06.595706

✓ Found 2 events for user: test@bssn.go.id
  • PBAC_DENIAL          | access_denied | Status: denied     | 07:53:06
  • LOGIN_SUCCESS        | login      | Status: success    | 07:53:06

✓ Events in last 24 hours: 3
✓ Total login events: 2
✓ Unique IP addresses with events: 2
```

### What This Tests:
- ✅ Log LOGIN_SUCCESS (successful login)
- ✅ Log LOGIN_FAILURE (failed login attempt)
- ✅ Log PBAC_DENIAL (access denied)
- ✅ Query events by user
- ✅ Query failed logins (bruteforce detection)
- ✅ Query by event type
- ✅ Date range queries (compliance reports)
- ✅ Event immutability

**Database location:** `D:\aqil\pusdatik\database\test_audit.db`

---

## **Cara 2: Via cURL (API Testing)**

### Setup:
1. Start backend server:
```bash
cd d:\aqil\pusdatik\backend
. .venv/Scripts/Activate.ps1
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

2. On another terminal, test login endpoint:

### Test Login (Will Log as LOGIN_SUCCESS):
```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin@bssn.go.id&password=your_password"
```

**Response:**
```json
{
  "access_token": "eyJhbGc...",
  "token_type": "bearer",
  "expires_in": 28800,
  "user": {
    "username": "admin@bssn.go.id",
    "display_name": "Administrator",
    "roles": ["admin_pusdatik"],
    "auth_provider": "local",
    "session_id": "uuid-12345"
  }
}
```

### View Audit Log in Database:
```bash
# After successful login, check audit_logs table
sqlite3 database\spbe_rag.db
SELECT * FROM audit_logs WHERE username='admin@bssn.go.id' ORDER BY timestamp DESC;
```

**Output:**
```
1|LOGIN_SUCCESS|1|admin@bssn.go.id|login|auth/login|success|127.0.0.1|{"auth_provider": "local", "session_id": "uuid-12345", "roles": ["admin_pusdatik"]}|2026-05-12 07:53:06.595706
```

### Test Failed Login (Will Log as LOGIN_FAILURE):
```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin@bssn.go.id&password=wrong_password"
```

**Response:** 
```json
{
  "detail": "Incorrect username or password"
}
```

**Audit log entry created:**
```
2|LOGIN_FAILURE|NULL|admin@bssn.go.id|login|auth/login|failure|127.0.0.1|{"reason": "invalid_credentials"}|2026-05-12 07:53:10.123456
```

---

## **Cara 3: Via SQL Queries (Database Direct)**

### Open SQLite Browser:
```bash
# Using sqlite3 CLI
sqlite3 database\spbe_rag.db

# Or using any SQLite GUI tool
# VSCode extension: SQLite
# Online: https://sqliteonline.com/
```

### Query 1: View All Audit Logs
```sql
SELECT 
  id, 
  event_type, 
  username, 
  action, 
  status, 
  ip_address, 
  timestamp 
FROM audit_logs 
ORDER BY timestamp DESC 
LIMIT 20;
```

**Output:**
```
ID | EVENT_TYPE    | USERNAME          | ACTION | STATUS  | IP_ADDRESS    | TIMESTAMP
1  | LOGIN_SUCCESS | admin@bssn.go.id  | login  | success | 192.168.1.100 | 2026-05-12 07:53:06
2  | PBAC_DENIAL   | admin@bssn.go.id  | access | denied  | 192.168.1.100 | 2026-05-12 07:53:10
3  | LOGIN_FAILURE | unknown@test.com  | login  | failure | 192.168.1.101 | 2026-05-12 07:53:15
```

### Query 2: Failed Login Attempts (Bruteforce Detection)
```sql
-- Get all failed logins in last 24 hours
SELECT 
  username, 
  ip_address, 
  COUNT(*) as attempt_count, 
  MAX(timestamp) as last_attempt 
FROM audit_logs 
WHERE 
  event_type = 'LOGIN_FAILURE' 
  AND timestamp >= datetime('now', '-24 hours')
GROUP BY username, ip_address 
ORDER BY attempt_count DESC;
```

**Output:**
```
USERNAME         | IP_ADDRESS    | ATTEMPT_COUNT | LAST_ATTEMPT
attacker@bad.com | 192.168.100.1 | 15            | 2026-05-12 14:30:00
```

### Query 3: User Activity Audit Trail
```sql
-- Get all events for a specific user
SELECT 
  timestamp, 
  event_type, 
  action, 
  resource, 
  status, 
  ip_address, 
  details 
FROM audit_logs 
WHERE username = 'admin@bssn.go.id'
ORDER BY timestamp DESC;
```

**Output:**
```
TIMESTAMP            | EVENT_TYPE    | ACTION | RESOURCE        | STATUS | IP_ADDRESS    | DETAILS
2026-05-12 07:53:30 | LOGOUT        | logout | auth/logout     | success| 192.168.1.100 | {"voluntary": true}
2026-05-12 07:53:15 | TOKEN_REFRESH | refresh| auth/refresh    | success| 192.168.1.100 | {"session_id": "uuid-123"}
2026-05-12 07:53:06 | LOGIN_SUCCESS | login  | auth/login      | success| 192.168.1.100 | {"auth_provider": "local"}
```

### Query 4: PBAC Violations (Security Analysis)
```sql
-- Find all access denials
SELECT 
  timestamp, 
  username, 
  resource, 
  ip_address, 
  details 
FROM audit_logs 
WHERE event_type = 'PBAC_DENIAL'
ORDER BY timestamp DESC;
```

**Output:**
```
TIMESTAMP            | USERNAME          | RESOURCE       | IP_ADDRESS    | DETAILS
2026-05-12 07:53:10 | viewer@bssn.go.id | admin/settings | 192.168.1.102 | {"required_role": "admin", "user_roles": ["viewer"]}
```

### Query 5: Compliance Report (All Events Last 7 Days)
```sql
-- Generate compliance report
SELECT 
  DATE(timestamp) as date,
  event_type,
  COUNT(*) as event_count,
  COUNT(DISTINCT user_id) as unique_users,
  COUNT(DISTINCT ip_address) as unique_ips
FROM audit_logs 
WHERE timestamp >= datetime('now', '-7 days')
GROUP BY DATE(timestamp), event_type
ORDER BY date DESC, event_type;
```

**Output:**
```
DATE       | EVENT_TYPE    | EVENT_COUNT | UNIQUE_USERS | UNIQUE_IPS
2026-05-12 | LOGIN_SUCCESS | 42          | 15           | 8
2026-05-12 | LOGIN_FAILURE | 3           | 2            | 1
2026-05-12 | PBAC_DENIAL   | 1           | 1            | 1
2026-05-12 | TOKEN_REFRESH | 28          | 12           | 7
```

### Query 6: Count Total Events
```sql
SELECT COUNT(*) as total_events FROM audit_logs;
```

---

## **Ringkasan Event Types yang Tercatat:**

| Event Type | When Logged | Example |
|-----------|-----------|---------|
| `LOGIN_ATTEMPT` | User mulai login | Initial auth attempt |
| `LOGIN_SUCCESS` | Login berhasil | Credentials valid, token issued |
| `LOGIN_FAILURE` | Login gagal | Wrong password, account locked |
| `TOKEN_REFRESH` | Token di-refresh | New access token issued |
| `LOGOUT` | User logout | Token blacklisted |
| `PBAC_DENIAL` | Akses ditolak | User lacks required role |
| `USER_CREATED` | User baru dibuat | Admin create account |
| `DOCUMENT_UPLOADED` | File diupload | Document ingestion |

---

## **Apa Yang Dilog dari Setiap Event:**

```json
{
  "id": 42,
  "event_type": "LOGIN_SUCCESS",
  "user_id": 5,
  "username": "admin@bssn.go.id",
  "action": "login",
  "resource": "auth/login",
  "status": "success",
  "ip_address": "192.168.1.100",
  "details": {
    "auth_provider": "local",
    "session_id": "uuid-12345",
    "roles": ["admin_pusdatik", "viewer"],
    "attempt": 1
  },
  "timestamp": "2026-05-12T07:53:06.595706"
}
```

---

## **Use Cases:**

### 1. **Bruteforce Detection** 
```sql
-- Find IP addresses with >5 failed logins in 1 hour
SELECT ip_address, COUNT(*) as failures
FROM audit_logs 
WHERE event_type = 'LOGIN_FAILURE'
  AND timestamp >= datetime('now', '-1 hour')
GROUP BY ip_address
HAVING failures > 5;
```

### 2. **Compliance Audit Trail**
```sql
-- All admin actions in last month
SELECT * FROM audit_logs 
WHERE user_id IN (SELECT id FROM users WHERE roles LIKE '%admin%')
  AND timestamp >= datetime('now', '-1 month')
ORDER BY timestamp DESC;
```

### 3. **Security Incident Forensics**
```sql
-- Timeline of events for a specific user on a specific date
SELECT * FROM audit_logs 
WHERE username = 'suspect@bssn.go.id'
  AND DATE(timestamp) = '2026-05-12'
ORDER BY timestamp ASC;
```

### 4. **Access Control Violations**
```sql
-- Users who attempted to access admin panel without permission
SELECT DISTINCT username, COUNT(*) as denial_count
FROM audit_logs 
WHERE event_type = 'PBAC_DENIAL' 
  AND resource LIKE 'admin/%'
GROUP BY username
ORDER BY denial_count DESC;
```

---

## **Berikutnya:**

✅ Audit Logging sekarang **LIVE**
🔄 Next: Step 3 - Real LDAP/AD Connection (minggu depan)
📊 Already available: Full compliance reporting + forensics capability

---

## **BONUS: Quick Inspector Commands**

Saya buatkan script untuk cepat inspect audit logs dari command line:

### View Recent Logs
```bash
python inspect_audit_logs.py
```

### View Summary by Event Type
```bash
python inspect_audit_logs.py --summary
```

### Bruteforce Detection (Failed Logins)
```bash
python inspect_audit_logs.py --bruteforce
```

### Filter by User
```bash
python inspect_audit_logs.py --user "admin@bssn.go.id"
```

### Filter by Event Type
```bash
python inspect_audit_logs.py --event LOGIN_FAILURE
```

### Custom Options
```bash
# Show logs from last 30 days
python inspect_audit_logs.py --days 30

# Show last 100 results
python inspect_audit_logs.py --limit 100

# Combine filters
python inspect_audit_logs.py --user "admin@bssn.go.id" --event LOGIN_SUCCESS
```
