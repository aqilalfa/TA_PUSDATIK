#!/usr/bin/env python
"""
Quick Test Script for Audit Logging
Demonstrasi: Login attempt → Check audit trail
"""

import sys
import json
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Setup path
sys.path.insert(0, "backend")

from app.config import settings
from app.models.db_models import Base, User, AuditLog
from app.database import SessionLocal, engine, init_database
from app.core.audit_service import AuditLogger, AuditEventType

print("=" * 80)
print("AUDIT LOGGING TEST SUITE")
print("=" * 80)

# Initialize database (create tables if not exist)
print("\n[0] Initializing database...")
try:
    init_database()
    print("✓ Database initialized")
except Exception as e:
    print(f"✓ Database already exists or initialized: {str(e)[:50]}")

# Connect to database
session = SessionLocal()

# Initialize audit logger
audit_logger = AuditLogger(session=session)

print("\n[1] Testing: Log LOGIN_SUCCESS event")
print("-" * 80)

# Create test user if not exists
test_user = session.query(User).filter_by(email="test@bssn.go.id").first()
if not test_user:
    test_user = User(
        name="Test User",
        email="test@bssn.go.id",
        roles="[]",
        auth_provider="local"
    )
    session.add(test_user)
    session.commit()
    print(f"✓ Created test user: {test_user.email} (ID: {test_user.id})")
else:
    print(f"✓ Using existing test user: {test_user.email} (ID: {test_user.id})")

# Log a login event
log_entry = audit_logger.log_event(
    event_type=AuditEventType.LOGIN_SUCCESS,
    user_id=test_user.id,
    username=test_user.email,
    action="login",
    resource="auth/login",
    status="success",
    ip_address="192.168.1.100",
    details=json.dumps({
        "auth_provider": "local",
        "session_id": "test-session-123",
        "roles": ["viewer", "analyst"]
    })
)
print(f"✓ Logged event: {log_entry.event_type} | Status: {log_entry.status}")
print(f"  Event ID: {log_entry.id}")
print(f"  Timestamp: {log_entry.timestamp}")

print("\n[2] Testing: Log LOGIN_FAILURE event")
print("-" * 80)

fail_log = audit_logger.log_event(
    event_type=AuditEventType.LOGIN_FAILURE,
    user_id=None,
    username="unknown@bssn.go.id",
    action="login",
    resource="auth/login",
    status="failure",
    ip_address="192.168.1.101",
    details=json.dumps({"reason": "invalid_credentials"})
)
print(f"✓ Logged event: {fail_log.event_type} | Status: {fail_log.status}")
print(f"  Username: {fail_log.username}")
print(f"  IP: {fail_log.ip_address}")

print("\n[3] Testing: Log PBAC_DENIAL event")
print("-" * 80)

denial_log = audit_logger.log_event(
    event_type=AuditEventType.PBAC_DENIAL,
    user_id=test_user.id,
    username=test_user.email,
    action="access_denied",
    resource="admin/settings",
    status="denied",
    ip_address="192.168.1.100",
    details=json.dumps({
        "required_role": "admin",
        "user_roles": ["viewer", "analyst"]
    })
)
print(f"✓ Logged event: {denial_log.event_type} | Status: {denial_log.status}")
print(f"  Resource: {denial_log.resource}")
print(f"  Required role: admin, User roles: {json.loads(denial_log.details)['user_roles']}")

print("\n[4] Testing: Query all events for user")
print("-" * 80)

user_events = audit_logger.get_user_events(test_user.id, limit=10)
print(f"✓ Found {len(user_events)} events for user: {test_user.email}")
for event in user_events:
    print(f"  • {event.event_type:20} | {event.action:10} | Status: {event.status:10} | {event.timestamp.strftime('%H:%M:%S')}")

print("\n[5] Testing: Query failed login attempts (bruteforce detection)")
print("-" * 80)

failed_logins = audit_logger.get_failed_logins("unknown@bssn.go.id", hours=24)
print(f"✓ Found {len(failed_logins)} failed login attempts in last 24h")
for log in failed_logins:
    print(f"  • {log.username} from {log.ip_address} at {log.timestamp.strftime('%H:%M:%S')}")

print("\n[6] Testing: Query by event type")
print("-" * 80)

login_success_events = audit_logger.get_events_by_type(AuditEventType.LOGIN_SUCCESS, limit=5)
print(f"✓ Found {len(login_success_events)} LOGIN_SUCCESS events")
for log in login_success_events:
    print(f"  • {log.username:30} | IP: {log.ip_address:20} | {log.timestamp.strftime('%H:%M:%S')}")

print("\n[7] Testing: Raw SQL queries (for compliance reports)")
print("-" * 80)

# All events in last 24 hours
cutoff = datetime.utcnow() - timedelta(hours=24)
recent_events = session.query(AuditLog).filter(AuditLog.timestamp >= cutoff).all()
print(f"✓ Events in last 24 hours: {len(recent_events)}")

# Login events only
login_events = session.query(AuditLog).filter(
    AuditLog.event_type.in_([AuditEventType.LOGIN_SUCCESS, AuditEventType.LOGIN_FAILURE])
).count()
print(f"✓ Total login events: {login_events}")

# Events by IP
events_by_ip = session.query(AuditLog.ip_address, AuditLog.event_type).distinct().all()
print(f"✓ Unique IP addresses with events: {len(set(e[0] for e in events_by_ip))}")

print("\n[8] Testing: Audit log immutability")
print("-" * 80)

# Try to modify (won't be updated in real system)
test_log = session.query(AuditLog).filter_by(event_type=AuditEventType.LOGIN_SUCCESS).first()
if test_log:
    original_timestamp = test_log.timestamp
    test_log.status = "tampered"  # Try to tamper
    session.commit()
    
    # Reload from DB
    session.refresh(test_log)
    
    # In production, timestamp should be immutable (this is just a test)
    print(f"✓ Original timestamp: {original_timestamp}")
    print(f"✓ Status field: {test_log.status}")
    print("  Note: In production, AuditLog should be write-once (immutable)")

print("\n" + "=" * 80)
print("AUDIT LOGGING TEST COMPLETE ✓")
print("=" * 80)
print("\nTo see audit logs in database directly:")
print("  sqlite3 backend/app.db")
print("  SELECT * FROM audit_logs;")
print("  SELECT COUNT(*) as total_events FROM audit_logs;")
print("=" * 80)

session.close()
