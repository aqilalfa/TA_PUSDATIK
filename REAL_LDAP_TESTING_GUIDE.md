# Real LDAP Testing Guide

This guide explains how to enable and use real LDAP testing with the SPBE RAG system.

## Overview

Two approaches for LDAP testing:

1. **Mock LDAP Testing** (Default, No Docker Required)
   - Uses in-memory mock LDAP server
   - Fast (~1 second for 12 tests)
   - No external dependencies
   - Perfect for CI/CD pipelines

2. **Real LDAP Testing** (Optional, Docker Required)
   - Uses OpenLDAP in Docker container
   - Realistic LDAP operations
   - Good for debugging LDAP integration issues
   - Requires Docker and Docker Compose

---

## Part 1: Mock LDAP Testing (Default)

### Running Mock LDAP Tests

```bash
cd backend

# Run mock LDAP server tests
pytest tests/test_ldap_real_integration.py -v

# Run all LDAP tests (unit + integration)
pytest tests/test_ldap_provider.py tests/test_ldap_real_integration.py -v

# Run specific test class
pytest tests/test_ldap_real_integration.py::TestRealLDAPOperations -v
```

### Mock LDAP Test Users

The mock LDAP server provides these test users:

| Username | Password | Email | Groups | Roles |
|----------|----------|-------|--------|-------|
| admin | AdminPassword123! | admin@bssn.go.id | Admin_PUSDATIK, Manager_Evaluasi | admin_pusdatik, manager_evaluasi, staf_pusdatik |
| evaluator | EvaluatorPass123! | evaluator@bssn.go.id | Evaluator_SPBE, Staf_PUSDATIK | evaluator_spbe, staf_pusdatik |
| staff | StaffPass123! | staff@bssn.go.id | Staf_PUSDATIK | staf_pusdatik |

### Mock LDAP Server Structure

**Location:** `backend/tests/test_ldap_real_integration.py`

**Classes:**
- `MockLDAPServer`: In-memory LDAP directory with test users and groups
- `MockLDAPUser`: Represents a user with groups, email, department, etc.

**Features:**
- Full BSSN organization structure (4 groups)
- Realistic user attributes (displayName, mail, department, employeeID)
- Group membership validation
- Dynamic user/group management

---

## Part 2: Real LDAP Testing (Docker)

### Prerequisites

- Docker and Docker Compose installed
- Ports 389 (LDAP) and 6680 (phpLDAPadmin) available

### Step 1: Start OpenLDAP Container

```bash
cd d:\aqil\pusdatik

# Start LDAP server and phpLDAPadmin UI
docker-compose -f docker-compose.ldap.yml up -d

# Verify LDAP server is healthy
docker-compose -f docker-compose.ldap.yml ps

# Check logs
docker-compose -f docker-compose.ldap.yml logs ldap
```

### Step 2: Verify LDAP Connection

```bash
# Check if LDAP is responding
ldapwhoami -H ldap://localhost -D "cn=admin,dc=bssn,dc=go,dc=id" -w "AdminPassword123!" -v

# Or use Python
python -c "
from ldap3 import Server, Connection
server = Server('ldap://localhost:389', get_info='ALL')
conn = Connection(server, user='cn=admin,dc=bssn,dc=go,dc=id', password='AdminPassword123!', auto_bind=True)
print(f'Connected: {conn.bound}')
conn.unbind()
"
```

### Step 3: Configure Backend for Real LDAP

Update `.env` file:

```env
AUTH_PROVIDER=ldap
LDAP_ENABLED=true
LDAP_SERVER_URL=ldap://localhost:389
LDAP_BASE_DN=dc=bssn,dc=go,dc=id
LDAP_DOMAIN=bssn.go.id
LDAP_TIMEOUT=10
LDAP_RETRY_COUNT=3
```

Or set environment variables directly:

```bash
$env:LDAP_ENABLED = "true"
$env:LDAP_SERVER_URL = "ldap://localhost:389"
$env:LDAP_BASE_DN = "dc=bssn,dc=go,dc=id"
```

### Step 4: Test Real LDAP Authentication

**Method 1: Python Script**

```python
# scripts/test_real_ldap.py
from app.auth.ldap_provider import LDAPDirectoryClient

client = LDAPDirectoryClient(
    server_url="ldap://localhost:389",
    base_dn="dc=bssn,dc=go,dc=id",
    domain="bssn.go.id"
)

result = client.authenticate("admin", "AdminPassword123!")
print(f"Authentication result: {result}")

# Expected output:
# {
#   'username': 'admin',
#   'email': 'admin@bssn.go.id',
#   'display_name': 'Administrator BSSN',
#   'department': 'IT Security',
#   'employee_id': 'EMP001',
#   'groups': ['Admin_PUSDATIK', 'Manager_Evaluasi']
# }
```

**Method 2: cURL against API**

```bash
# With real LDAP running
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@bssn.go.id",
    "password": "AdminPassword123!"
  }'

# Expected response:
# {
#   "access_token": "eyJ0eXAi...",
#   "refresh_token": "eyJ0eXAi...",
#   "expires_in": 900,
#   "user": {
#     "id": 1,
#     "email": "admin@bssn.go.id",
#     "name": "Administrator BSSN",
#     "roles": ["admin_pusdatik", "manager_evaluasi", "staf_pusdatik"],
#     "auth_provider": "ldap"
#   }
# }
```

### Step 5: Manage LDAP via Web UI

Access phpLDAPadmin at: http://localhost:6680

**Login Credentials:**
- Login DN: `cn=admin,dc=bssn,dc=go,dc=id`
- Password: `AdminPassword123!`

**You can:**
- Browse LDAP directory
- Add/edit users
- Manage group memberships
- Test authentication

### Step 6: Inspect LDAP Directory

```bash
# List all users
ldapsearch -H ldap://localhost -b "dc=bssn,dc=go,dc=id" -D "cn=admin,dc=bssn,dc=go,dc=id" -w "AdminPassword123!" objectClass=inetOrgPerson

# List all groups
ldapsearch -H ldap://localhost -b "dc=bssn,dc=go,dc=id" -D "cn=admin,dc=bssn,dc=go,dc=id" -w "AdminPassword123!" objectClass=groupOfNames

# Find user by email
ldapsearch -H ldap://localhost -b "dc=bssn,dc=go,dc=id" -D "cn=admin,dc=bssn,dc=go,dc=id" -w "AdminPassword123!" "(mail=admin@bssn.go.id)"
```

### Step 7: Stop LDAP Server

```bash
# Stop containers
docker-compose -f docker-compose.ldap.yml down

# Stop and remove volumes (clean slate)
docker-compose -f docker-compose.ldap.yml down -v
```

---

## Integration Testing Scenarios

### Scenario 1: First-Time LDAP Login (Shadow User Creation)

```python
# Test: test_ldap_user_first_login_creates_shadow_user
# What happens:
# 1. User authenticates against LDAP
# 2. LDAP returns groups: [Admin_PUSDATIK, Manager_Evaluasi]
# 3. Groups are mapped to roles: [admin_pusdatik, manager_evaluasi, staf_pusdatik]
# 4. Shadow user created in local database with:
#    - email: admin@bssn.go.id
#    - name: Administrator BSSN
#    - department: IT Security
#    - external_id: EMP001
#    - auth_provider: ldap
#    - roles: [admin_pusdatik, manager_evaluasi, staf_pusdatik]
```

### Scenario 2: Role Update on Subsequent Login

```python
# Test: test_ldap_user_subsequent_login_updates_shadow_user
# What happens:
# 1. User logs in second time
# 2. LDAP group membership has changed (e.g., removed from Manager_Evaluasi)
# 3. Shadow user is updated with new roles
# 4. Old token becomes invalid (user must refresh)
# 5. Audit log captures: TOKEN_REFRESH with updated roles
```

### Scenario 3: User with No Group Memberships

```python
# Test: test_ldap_login_with_no_groups
# What happens:
# 1. User authenticates successfully
# 2. LDAP returns empty groups list
# 3. Shadow user created but with empty roles: []
# 4. User cannot access any protected resources (PBAC denies)
# 5. Audit log captures: PBAC_DENIAL with required_role vs user_roles
```

---

## Troubleshooting

### LDAP Connection Timeout

**Error:** `ldap3.core.exceptions.LDAPSocketOpenError: socket.gaierror`

**Solution:**
```bash
# Check if LDAP container is running
docker-compose -f docker-compose.ldap.yml ps

# Check LDAP logs
docker-compose -f docker-compose.ldap.yml logs ldap

# Restart LDAP
docker-compose -f docker-compose.ldap.yml restart ldap
```

### Authentication Failed

**Error:** `LDAPUnavailableError: Invalid Credentials`

**Solution:**
```bash
# Verify test user exists
ldapsearch -H ldap://localhost -b "dc=bssn,dc=go,dc=id" -D "cn=admin,dc=bssn,dc=go,dc=id" -w "AdminPassword123!" "(uid=admin)"

# Verify password
ldapwhoami -H ldap://localhost -D "cn=admin,ou=Users,dc=bssn,dc=go,dc=id" -w "AdminPassword123!" -v

# Check LDAP bootstrap file was loaded
docker-compose -f docker-compose.ldap.yml logs ldap | grep bootstrap
```

### Group Membership Not Returned

**Error:** `groups` field empty after authentication

**Solution:**
```bash
# Check user's memberOf attribute
ldapsearch -H ldap://localhost -b "dc=bssn,dc=go,dc=id" -D "cn=admin,dc=bssn,dc=go,dc=id" -w "AdminPassword123!" "(uid=admin)" memberOf

# Expected output shows groups like:
# memberOf: cn=Admin_PUSDATIK,ou=Groups,dc=bssn,dc=go,dc=id
# memberOf: cn=Manager_Evaluasi,ou=Groups,dc=bssn,dc=go,dc=id
```

---

## Performance Notes

### Mock LDAP (test_ldap_real_integration.py)
- **Test Suite:** 12 tests
- **Execution Time:** ~0.76 seconds
- **Memory:** ~50MB
- **Use Case:** CI/CD, rapid development, no Docker dependency

### Real LDAP (with Docker)
- **Test Suite:** 52 backend + 41 frontend
- **Execution Time:** ~3.54 seconds (backend only)
- **Memory:** ~200MB (OpenLDAP container)
- **Use Case:** Debugging LDAP issues, realistic testing

---

## Next Steps

1. **Enable Real LDAP in Development:**
   - Start Docker LDAP container
   - Update .env with LDAP_SERVER_URL
   - Run backend with AUTH_PROVIDER=ldap

2. **Test Against Real BSSN AD (When Available):**
   - Update LDAP_SERVER_URL to real AD server
   - Update LDAP_BASE_DN to BSSN forest DN
   - Update LDAP credentials in .env
   - Run full regression suite

3. **Set Up LDAP Sync (Optional):**
   - Create scheduler that refreshes roles every 24h
   - Implement group membership sync
   - Handle user deprovisioning (AD user deleted)

4. **Monitoring & Alerts:**
   - Monitor LDAP connection failures via audit logs
   - Alert on failed logins >5 in 24h
   - Track shadow user creation rate
   - Monitor role mapping accuracy

---

## Related Files

- **Mock LDAP Tests:** [backend/tests/test_ldap_real_integration.py](../backend/tests/test_ldap_real_integration.py)
- **LDAP Provider:** [backend/app/auth/ldap_provider.py](../backend/app/auth/ldap_provider.py)
- **Role Mapper:** [backend/app/auth/role_mapper.py](../backend/app/auth/role_mapper.py)
- **Docker Compose:** [docker-compose.ldap.yml](../docker-compose.ldap.yml)
- **Bootstrap LDIF:** [ldap_bootstrap.ldif](../ldap_bootstrap.ldif)

---

**Created:** Real LDAP Testing Guide
**Status:** ✅ Ready for development and testing
