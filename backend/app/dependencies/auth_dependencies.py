from typing import List, Callable
import json
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from loguru import logger

from app.database import get_db
from app.models.db_models import User, TokenBlacklist
from app.auth.jwt_manager import jwt_manager
from app.auth.token_revocation import token_revocation_store
from app.core.security_metrics import security_metrics

security = HTTPBearer(auto_error=False)

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """Validate token and return current user"""
    if credentials is None:
        security_metrics.increment("http.401", endpoint="auth/dependency")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    
    # Verify token
    payload = jwt_manager.verify_token(token)
    if not payload:
        security_metrics.increment("http.401", endpoint="auth/dependency")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Check if token is blacklisted
    jti = payload.get("jti")
    is_blacklisted = db.query(TokenBlacklist).filter(TokenBlacklist.jti == jti).first()
    if is_blacklisted or token_revocation_store.is_revoked(jti):
        logger.warning(f"Attempt to use blacklisted token jti={jti}")
        security_metrics.increment("http.401", endpoint="auth/dependency")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked",
        )
        
    email = payload.get("sub")
    if email is None:
        security_metrics.increment("http.401", endpoint="auth/dependency")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing subject claim",
        )
        
    user = db.query(User).filter(User.email == email).first()
    if user is None:
        security_metrics.increment("http.401", endpoint="auth/dependency")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
        
    return user

def require_roles(required_roles: List[str]) -> Callable:
    """PBAC Dependency: Check if user has required roles"""
    def role_checker(user: User = Depends(get_current_user)) -> User:
        user_roles = []
        try:
            if user.roles:
                user_roles = json.loads(user.roles)
        except json.JSONDecodeError:
            logger.error(f"Failed to parse roles for user {user.email}")
            user_roles = []
            
        # Check if user has AT LEAST ONE of the required roles
        has_role = any(role in user_roles for role in required_roles)
        if not has_role:
            logger.warning(f"PBAC Denied: User {user.email} missing roles {required_roles}")
            security_metrics.increment("http.403", endpoint="auth/roles")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Operation not permitted. Required roles: {required_roles}"
            )
            
        return user
        
    return role_checker
