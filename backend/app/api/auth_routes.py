from datetime import datetime, timezone
from typing import Any
import uuid
import json
from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from loguru import logger

from app.config import settings
from app.database import get_db
from app.models.db_models import User, TokenBlacklist
from app.auth.role_mapper import parse_roles
from app.auth.jwt_manager import jwt_manager
from app.auth.auth_service import authenticate_user
from app.auth.ldap_provider import LDAPUnavailableError
from app.auth.login_rate_limiter import login_failed_rate_limiter
from app.auth.token_revocation import token_revocation_store
from app.dependencies.auth_dependencies import get_current_user
from app.core.audit_service import get_audit_logger, AuditEventType
from app.core.security_metrics import security_metrics

router = APIRouter()

REFRESH_COOKIE_NAME = "refresh_token"
REFRESH_COOKIE_PATH = "/api/auth/refresh"


def _cookie_secure() -> bool:
    return settings.ENVIRONMENT.lower() == "production"


def _set_refresh_cookie(response: Response, refresh_token: str) -> None:
    secure = _cookie_secure()
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=refresh_token,
        httponly=True,
        secure=secure,
        samesite="strict" if secure else "lax",
        max_age=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        path=REFRESH_COOKIE_PATH,
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(REFRESH_COOKIE_NAME, path=REFRESH_COOKIE_PATH)


def _build_access_token_data(user: User, roles: list[str], session_id: str) -> dict[str, Any]:
    return {
        "sub": user.email,
        "username": user.name,
        "roles": roles,
        "dept": user.department or "",
        "sid": session_id,
        "auth_provider": user.auth_provider or "local",
    }


def _build_refresh_token_data(user: User, session_id: str) -> dict[str, Any]:
    return {
        "sub": user.email,
        "sid": session_id,
    }


def _is_token_blacklisted(db: Session, jti: str | None) -> bool:
    if not jti:
        return True
    return (
        token_revocation_store.is_revoked(jti)
        or db.query(TokenBlacklist).filter(TokenBlacklist.jti == jti).first() is not None
    )


def _blacklist_token(db: Session, jti: str | None, exp: int | None) -> None:
    if not jti or not exp:
        return

    blacklist_entry = TokenBlacklist(
        jti=jti,
        expires_at=datetime.fromtimestamp(exp, tz=timezone.utc),
    )
    db.add(blacklist_entry)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
    token_revocation_store.revoke(jti, exp)


def _login_rate_limit_key(request: Request, username: str) -> str:
    client_ip = request.client.host if request.client else "unknown"
    return f"{client_ip}:{username.strip().lower()}"


def _raise_login_rate_limited(audit_logger, username: str, client_ip: str, retry_after: int) -> None:
    audit_logger.log_event(
        event_type=AuditEventType.LOGIN_FAILURE,
        user_id=None,
        username=username,
        action="login",
        resource="auth/login",
        status="failure",
        ip_address=client_ip,
        details=json.dumps({"reason": "rate_limited", "retry_after": retry_after}),
    )
    security_metrics.increment("http.429", endpoint="auth/login")
    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail="Too many failed login attempts. Please try again later.",
        headers={"Retry-After": str(retry_after)},
    )

@router.post("/login")
def login_for_access_token(
    response: Response,
    request: Request,
    db: Session = Depends(get_db),
    form_data: OAuth2PasswordRequestForm = Depends()
) -> Any:
    """
    OAuth2 compatible token login, get an access token for future requests.
    Also sets an HttpOnly cookie with the refresh token.
    """
    # Get client IP for audit logging
    client_ip = request.client.host if request.client else "unknown"
    audit_logger = get_audit_logger(session=db)
    
    # Log login attempt
    audit_logger.log_event(
        event_type=AuditEventType.LOGIN_ATTEMPT,
        user_id=None,  # Not yet authenticated
        username=form_data.username,
        action="login",
        resource="auth/login",
        status="pending",
        ip_address=client_ip,
        details=json.dumps({"attempt": "initial"}),
    )

    rate_limit_key = _login_rate_limit_key(request, form_data.username)
    retry_after = login_failed_rate_limiter.get_retry_after(rate_limit_key)
    if retry_after is not None:
        _raise_login_rate_limited(audit_logger, form_data.username, client_ip, retry_after)
    
    try:
        user = authenticate_user(form_data.username, form_data.password, db)
    except LDAPUnavailableError as exc:
        logger.exception(f"Authentication backend unavailable for {form_data.username}: {exc}")
        
        # Log backend failure
        audit_logger.log_event(
            event_type=AuditEventType.LOGIN_FAILURE,
            user_id=None,
            username=form_data.username,
            action="login",
            resource="auth/login",
            status="failure",
            ip_address=client_ip,
            details=json.dumps({"reason": "auth_backend_unavailable", "error": str(exc)}),
        )
        
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service temporarily unavailable",
        )

    if not user:
        logger.warning(f"Failed login attempt for username: {form_data.username} (wrong password)")
        login_failed_rate_limiter.record_failure(rate_limit_key)
        security_metrics.increment("auth.failed_login", username=form_data.username, ip=client_ip)
        security_metrics.increment("http.401", endpoint="auth/login")
        
        # Log failed login
        audit_logger.log_event(
            event_type=AuditEventType.LOGIN_FAILURE,
            user_id=None,
            username=form_data.username,
            action="login",
            resource="auth/login",
            status="failure",
            ip_address=client_ip,
            details=json.dumps({"reason": "invalid_credentials"}),
        )
        
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    session_id = str(uuid.uuid4())
    roles = parse_roles(user.roles)
    login_failed_rate_limiter.reset(rate_limit_key)

    # Generate tokens
    access_token = jwt_manager.create_access_token(
        data=_build_access_token_data(user, roles, session_id)
    )
    refresh_token = jwt_manager.create_refresh_token(
        data=_build_refresh_token_data(user, session_id)
    )
    
    _set_refresh_cookie(response, refresh_token)
    
    logger.info(f"User {user.email} logged in successfully")
    
    # Log successful login
    audit_logger.log_event(
        event_type=AuditEventType.LOGIN_SUCCESS,
        user_id=user.id,
        username=user.email,
        action="login",
        resource="auth/login",
        status="success",
        ip_address=client_ip,
        details=json.dumps({
            "auth_provider": user.auth_provider or "local",
            "session_id": session_id,
            "roles": roles,
        }),
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer"
        ,"expires_in": settings.JWT_ACCESS_TOKEN_EXPIRE_HOURS * 3600,
        "user": {
            "username": user.email,
            "display_name": user.name,
            "roles": roles,
            "department": user.department,
            "auth_provider": user.auth_provider or "local",
            "session_id": session_id,
        }
    }

@router.post("/refresh")
def refresh_token(request: Request, response: Response, db: Session = Depends(get_db)) -> Any:
    """Refresh access token using the refresh token cookie"""
    client_ip = request.client.host if request.client else "unknown"
    audit_logger = get_audit_logger(session=db)
    
    refresh_token_cookie = request.cookies.get(REFRESH_COOKIE_NAME)
    if not refresh_token_cookie:
        raise HTTPException(status_code=401, detail="Refresh token missing")
        
    payload = jwt_manager.verify_token(refresh_token_cookie)
    if not payload or payload.get("type") != "refresh":
        security_metrics.increment("http.401", endpoint="auth/refresh")
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    if _is_token_blacklisted(db, payload.get("jti")):
        security_metrics.increment("http.401", endpoint="auth/refresh")
        raise HTTPException(status_code=401, detail="Invalid refresh token")
        
    # Check if user still exists
    email = payload.get("sub")
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    session_id = payload.get("sid") or str(uuid.uuid4())
    roles = parse_roles(user.roles)
        
    # Generate new access token
    new_access_token = jwt_manager.create_access_token(
        data=_build_access_token_data(user, roles, session_id)
    )
    new_refresh_token = jwt_manager.create_refresh_token(
        data=_build_refresh_token_data(user, session_id)
    )
    _blacklist_token(db, payload.get("jti"), payload.get("exp"))
    _set_refresh_cookie(response, new_refresh_token)
    
    # Log token refresh
    audit_logger.log_event(
        event_type=AuditEventType.TOKEN_REFRESH,
        user_id=user.id,
        username=user.email,
        action="refresh",
        resource="auth/refresh",
        status="success",
        ip_address=client_ip,
        details=json.dumps({"session_id": payload.get("sid")}),
    )
    
    return {
        "access_token": new_access_token,
        "token_type": "bearer"
    }

@router.post("/logout")
def logout(
    response: Response,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Any:
    """Logout by blacklisting the current access token and clearing refresh cookie"""
    client_ip = request.client.host if request.client else "unknown"
    audit_logger = get_audit_logger(session=db)
    
    # Extract token
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
        payload = jwt_manager.verify_token(token)
        if payload and "jti" in payload:
            _blacklist_token(db, payload.get("jti"), payload.get("exp"))
            security_metrics.increment("auth.token_revoked", username=current_user.email)
            logger.info(f"Token jti={payload.get('jti')} blacklisted for user {current_user.email}")
             
    # Clear the refresh cookie
    _clear_refresh_cookie(response)
    
    # Log logout
    audit_logger.log_event(
        event_type=AuditEventType.LOGOUT,
        user_id=current_user.id,
        username=current_user.email,
        action="logout",
        resource="auth/logout",
        status="success",
        ip_address=client_ip,
        details=json.dumps({"voluntary": True}),
    )
    
    return {"detail": "Successfully logged out"}
