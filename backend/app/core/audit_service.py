"""
Audit Logging Service - centralized security event tracking

Provides:
- AuditEventType enum (all event types)
- AuditLogger class (log_event method)
- @audit_event decorator (for automatic logging in routes)
"""

import json
from enum import Enum
from datetime import datetime
from functools import wraps
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from app.models.db_models import AuditLog
from loguru import logger


class AuditEventType(str, Enum):
    """All audit event types"""
    LOGIN_ATTEMPT = "LOGIN_ATTEMPT"
    LOGIN_SUCCESS = "LOGIN_SUCCESS"
    LOGIN_FAILURE = "LOGIN_FAILURE"
    PBAC_DENIAL = "PBAC_DENIAL"
    TOKEN_REFRESH = "TOKEN_REFRESH"
    LOGOUT = "LOGOUT"
    USER_CREATED = "USER_CREATED"
    USER_UPDATED = "USER_UPDATED"
    DOCUMENT_UPLOADED = "DOCUMENT_UPLOADED"


class AuditLogger:
    """Service for logging audit events"""

    def __init__(self, session: Session):
        self.session = session

    def log_event(
        self,
        event_type: str,
        user_id: Optional[int],
        username: str,
        action: str,
        resource: str,
        status: str,
        ip_address: Optional[str] = None,
        details: Optional[str] = None,
    ) -> AuditLog:
        """
        Log an audit event to database
        
        Args:
            event_type: Type of event (from AuditEventType)
            user_id: User ID (None if not authenticated)
            username: Email or LDAP DN for traceability
            action: Action performed (login, refresh, etc.)
            resource: Resource/endpoint accessed
            status: Result status (success, failure, denied)
            ip_address: Client IP address
            details: JSON string with additional context
        
        Returns:
            AuditLog: The created audit log entry
        """
        log_entry = AuditLog(
            event_type=event_type,
            user_id=user_id,
            username=username,
            action=action,
            resource=resource,
            status=status,
            ip_address=ip_address,
            details=details or "{}",
            timestamp=datetime.utcnow(),
        )
        self.session.add(log_entry)
        self.session.commit()
        
        # Also log to application logger
        logger.info(
            f"AUDIT: {event_type} | user={username} | action={action} | "
            f"resource={resource} | status={status} | ip={ip_address}"
        )
        
        return log_entry

    def get_user_events(self, user_id: int, limit: int = 100) -> list:
        """Get recent audit events for a user"""
        return (
            self.session.query(AuditLog)
            .filter_by(user_id=user_id)
            .order_by(AuditLog.timestamp.desc())
            .limit(limit)
            .all()
        )

    def get_events_by_type(self, event_type: str, limit: int = 100) -> list:
        """Get recent events of a specific type"""
        return (
            self.session.query(AuditLog)
            .filter_by(event_type=event_type)
            .order_by(AuditLog.timestamp.desc())
            .limit(limit)
            .all()
        )

    def get_failed_logins(self, username: str, hours: int = 24) -> list:
        """Get failed login attempts for a user (bruteforce detection)"""
        from datetime import timedelta

        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        return (
            self.session.query(AuditLog)
            .filter(AuditLog.username == username)
            .filter(AuditLog.event_type == "LOGIN_FAILURE")
            .filter(AuditLog.timestamp >= cutoff_time)
            .order_by(AuditLog.timestamp.desc())
            .all()
        )


# Global audit logger instance
_audit_logger: Optional[AuditLogger] = None


def get_audit_logger(session: Optional[Session] = None) -> AuditLogger:
    """Get or create global audit logger instance"""
    global _audit_logger
    if session is not None:
        _audit_logger = AuditLogger(session=session)
    if _audit_logger is None:
        raise RuntimeError("Audit logger not initialized. Call get_audit_logger(session) first.")
    return _audit_logger


def audit_event(
    event_type: str,
    resource: str,
    action: str,
):
    """
    Decorator for automatic audit logging on route handlers
    
    Usage:
        @router.post("/login")
        @audit_event(
            event_type=AuditEventType.LOGIN_ATTEMPT,
            resource="auth/login",
            action="login"
        )
        async def login(credentials: LoginRequest, request: Request, db: Session):
            # Handler code
    
    Args:
        event_type: Type of audit event
        resource: Resource being accessed
        action: Action being performed
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract request and db from kwargs (FastAPI dependency injection)
            request = kwargs.get("request")
            db = kwargs.get("db")
            
            ip_address = None
            if request:
                ip_address = request.client.host if request.client else None
            
            try:
                # Call the actual route handler
                result = await func(*args, **kwargs)
                
                # Log success (if we have DB session)
                if db:
                    logger_instance = get_audit_logger(session=db)
                    # Extract username from request/result if possible
                    username = kwargs.get("username", "unknown")
                    logger_instance.log_event(
                        event_type=event_type,
                        user_id=kwargs.get("user_id"),
                        username=username,
                        action=action,
                        resource=resource,
                        status="success",
                        ip_address=ip_address,
                        details=json.dumps({"endpoint": resource}),
                    )
                
                return result
            except Exception as e:
                # Log failure (if we have DB session)
                if db:
                    logger_instance = get_audit_logger(session=db)
                    username = kwargs.get("username", "unknown")
                    logger_instance.log_event(
                        event_type=event_type,
                        user_id=kwargs.get("user_id"),
                        username=username,
                        action=action,
                        resource=resource,
                        status="failure",
                        ip_address=ip_address,
                        details=json.dumps({"error": str(e)}),
                    )
                raise
        
        return wrapper
    return decorator
