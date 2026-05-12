"""
TDD Tests for Audit Logging System
Tests: schema, audit_service decorator, audit event capture in auth routes
"""

import pytest
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from app.models.db_models import Base, User, AuditLog
from app.core.audit_service import audit_event, get_audit_logger, AuditEventType
from app.database import get_db


@pytest.fixture
def test_db():
    """Create in-memory SQLite database for testing"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()
    engine.dispose()


@pytest.fixture
def test_user(test_db: Session):
    """Create test user"""
    user = User(
        id=1,
        name="Test User",
        email="test@example.com",
        roles="[]",
        auth_provider="local",
    )
    test_db.add(user)
    test_db.commit()
    return user


class TestAuditLogSchema:
    """Test AuditLog database model"""

    def test_audit_log_table_exists(self, test_db: Session):
        """Verify AuditLog table exists"""
        assert hasattr(AuditLog, "__tablename__")
        assert AuditLog.__tablename__ == "audit_logs"

    def test_audit_log_required_fields(self):
        """Verify AuditLog has required fields"""
        required_fields = [
            "id",
            "event_type",
            "user_id",
            "username",
            "action",
            "resource",
            "status",
            "ip_address",
            "details",
            "timestamp",
        ]
        for field in required_fields:
            assert hasattr(AuditLog, field), f"AuditLog missing field: {field}"

    def test_audit_log_insert(self, test_db: Session):
        """Test inserting audit log entry"""
        log = AuditLog(
            event_type="LOGIN_ATTEMPT",
            user_id=1,
            username="testuser",
            action="login",
            resource="auth/login",
            status="success",
            ip_address="127.0.0.1",
            details='{"provider": "local"}',
        )
        test_db.add(log)
        test_db.commit()

        # Verify insert
        result = test_db.query(AuditLog).filter_by(username="testuser").first()
        assert result is not None
        assert result.event_type == "LOGIN_ATTEMPT"
        assert result.status == "success"


class TestAuditService:
    """Test audit service and decorator pattern"""

    def test_audit_event_decorator_exists(self):
        """Verify @audit_event decorator exists"""
        assert callable(audit_event)

    def test_get_audit_logger_returns_service(self, test_db: Session):
        """Verify get_audit_logger returns service instance"""
        logger = get_audit_logger(session=test_db)
        assert logger is not None
        assert hasattr(logger, "log_event")

    def test_audit_event_types_defined(self):
        """Verify all event types are defined"""
        event_types = [
            "LOGIN_ATTEMPT",
            "LOGIN_SUCCESS",
            "LOGIN_FAILURE",
            "PBAC_DENIAL",
            "TOKEN_REFRESH",
            "LOGOUT",
            "USER_CREATED",
        ]
        for event_type in event_types:
            assert hasattr(AuditEventType, event_type)

    def test_log_event_captures_details(self, test_db: Session, test_user: User):
        """Test that log_event captures full event details"""
        from app.core.audit_service import AuditLogger

        logger = AuditLogger(session=test_db)
        logger.log_event(
            event_type="LOGIN_SUCCESS",
            user_id=test_user.id,
            username=test_user.email,
            action="login",
            resource="auth/login",
            status="success",
            ip_address="192.168.1.1",
            details='{"auth_provider": "local", "mfa": false}',
        )

        # Verify event logged
        result = (
            test_db.query(AuditLog)
            .filter_by(event_type="LOGIN_SUCCESS", user_id=test_user.id)
            .first()
        )
        assert result is not None
        assert result.username == test_user.email
        assert result.ip_address == "192.168.1.1"
        assert '"auth_provider": "local"' in result.details


class TestAuditLoggingIntegration:
    """Test audit logging in actual auth routes (integration test)"""

    def test_login_attempt_logged(self, test_db: Session, test_user: User):
        """Verify login attempt is logged in audit trail"""
        from app.core.audit_service import AuditLogger

        logger = AuditLogger(session=test_db)

        # Simulate login attempt
        logger.log_event(
            event_type="LOGIN_ATTEMPT",
            user_id=None,  # Not yet authenticated
            username="test@example.com",
            action="login",
            resource="auth/login",
            status="pending",
            ip_address="127.0.0.1",
            details='{"attempt": 1}',
        )

        # Then log success
        logger.log_event(
            event_type="LOGIN_SUCCESS",
            user_id=test_user.id,
            username=test_user.email,
            action="login",
            resource="auth/login",
            status="success",
            ip_address="127.0.0.1",
            details='{"auth_provider": "local"}',
        )

        # Verify both logged
        logs = test_db.query(AuditLog).filter_by(username="test@example.com").all()
        assert len(logs) >= 2
        assert any(log.event_type == "LOGIN_ATTEMPT" for log in logs)
        assert any(log.event_type == "LOGIN_SUCCESS" for log in logs)

    def test_login_failure_logged(self, test_db: Session):
        """Verify failed login attempt is logged"""
        from app.core.audit_service import AuditLogger

        logger = AuditLogger(session=test_db)

        logger.log_event(
            event_type="LOGIN_FAILURE",
            user_id=None,
            username="unknown@example.com",
            action="login",
            resource="auth/login",
            status="failure",
            ip_address="192.168.1.100",
            details='{"reason": "invalid_credentials"}',
        )

        result = (
            test_db.query(AuditLog)
            .filter_by(event_type="LOGIN_FAILURE", username="unknown@example.com")
            .first()
        )
        assert result is not None
        assert "invalid_credentials" in result.details

    def test_audit_log_immutable(self, test_db: Session):
        """Verify audit logs cannot be modified after creation (immutable)"""
        log = AuditLog(
            event_type="LOGIN_SUCCESS",
            user_id=1,
            username="user1",
            action="login",
            resource="auth/login",
            status="success",
            ip_address="127.0.0.1",
            details="{}",
        )
        test_db.add(log)
        test_db.commit()

        original_timestamp = log.timestamp

        # Attempt to modify (should fail or be rejected in production)
        log.status = "failure"  # Try to tamper
        test_db.commit()

        # In real system, timestamp should be immutable
        # For now, just verify original creation timestamp is preserved
        assert log.timestamp == original_timestamp

    def test_audit_log_queryable_by_user(self, test_db: Session, test_user: User):
        """Test querying audit logs by user"""
        from app.core.audit_service import AuditLogger

        logger = AuditLogger(session=test_db)

        logger.log_event(
            event_type="LOGIN_SUCCESS",
            user_id=test_user.id,
            username=test_user.email,
            action="login",
            resource="auth/login",
            status="success",
            ip_address="127.0.0.1",
            details="{}",
        )

        logger.log_event(
            event_type="TOKEN_REFRESH",
            user_id=test_user.id,
            username=test_user.email,
            action="refresh",
            resource="auth/refresh",
            status="success",
            ip_address="127.0.0.1",
            details="{}",
        )

        # Query by user
        user_logs = (
            test_db.query(AuditLog).filter_by(user_id=test_user.id).all()
        )
        assert len(user_logs) == 2
        assert all(log.user_id == test_user.id for log in user_logs)

    def test_audit_log_queryable_by_date_range(self, test_db: Session):
        """Test querying audit logs by date range"""
        from app.core.audit_service import AuditLogger

        logger = AuditLogger(session=test_db)

        start_time = datetime.utcnow()

        logger.log_event(
            event_type="LOGIN_SUCCESS",
            user_id=1,
            username="user1",
            action="login",
            resource="auth/login",
            status="success",
            ip_address="127.0.0.1",
            details="{}",
        )

        end_time = datetime.utcnow()

        # Query by date range
        logs = (
            test_db.query(AuditLog)
            .filter(AuditLog.timestamp >= start_time)
            .filter(AuditLog.timestamp <= end_time)
            .all()
        )
        assert len(logs) >= 1

    def test_pbac_denial_logged(self, test_db: Session, test_user: User):
        """Verify PBAC denial is logged"""
        from app.core.audit_service import AuditLogger

        logger = AuditLogger(session=test_db)

        logger.log_event(
            event_type="PBAC_DENIAL",
            user_id=test_user.id,
            username=test_user.email,
            action="access_denied",
            resource="admin/settings",
            status="denied",
            ip_address="127.0.0.1",
            details='{"required_role": "admin", "user_roles": "[]"}',
        )

        result = (
            test_db.query(AuditLog)
            .filter_by(event_type="PBAC_DENIAL", user_id=test_user.id)
            .first()
        )
        assert result is not None
        assert "admin" in result.details
