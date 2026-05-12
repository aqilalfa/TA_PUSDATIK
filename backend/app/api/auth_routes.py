from datetime import datetime, timezone
from typing import Any
import uuid
import json
from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from loguru import logger

from app.config import settings
from app.database import get_db
from app.models.db_models import User, TokenBlacklist
from app.auth.role_mapper import parse_roles
from app.auth.jwt_manager import jwt_manager
from app.auth.auth_service import authenticate_user
from app.auth.ldap_provider import LDAPUnavailableError
from app.dependencies.auth_dependencies import get_current_user
from app.core.audit_service import get_audit_logger, AuditEventType

router = APIRouter()

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

    # Generate tokens
    access_token = jwt_manager.create_access_token(
        data={
            "sub": user.email,
            "username": user.name,
            "roles": roles,
            "dept": user.department or "",
            "sid": session_id,
            "auth_provider": user.auth_provider or "local",
        }
    )
    refresh_token = jwt_manager.create_refresh_token(
        data={"sub": user.email, "sid": session_id}
    )
    
    # Set HttpOnly cookie for refresh token
    cookie_secure = settings.ENVIRONMENT.lower() == "production"
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=cookie_secure,
        samesite="strict" if cookie_secure else "lax",
        max_age=7 * 24 * 60 * 60 # 7 days
    )
    
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
    
    refresh_token_cookie = request.cookies.get("refresh_token")
    if not refresh_token_cookie:
        raise HTTPException(status_code=401, detail="Refresh token missing")
        
    payload = jwt_manager.verify_token(refresh_token_cookie)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid refresh token")
        
    # Check if user still exists
    email = payload.get("sub")
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
        
    # Generate new access token
    new_access_token = jwt_manager.create_access_token(
        data={"sub": user.email, "roles": user.roles}
    )
    
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
            # Blacklist the token until it expires
            jti = payload["jti"]
            exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
            
            blacklist_entry = TokenBlacklist(jti=jti, expires_at=exp)
            db.add(blacklist_entry)
            db.commit()
            logger.info(f"Token jti={jti} blacklisted for user {current_user.email}")
            
    # Clear the refresh cookie
    response.delete_cookie("refresh_token")
    
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
