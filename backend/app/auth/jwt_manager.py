from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional
import jwt
import uuid
import logging

from app.config import settings

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
        
        if expires_delta is not None:
            expire = datetime.now(timezone.utc) + expires_delta
        else:
            expire = datetime.now(timezone.utc) + timedelta(hours=settings.JWT_ACCESS_TOKEN_EXPIRE_HOURS)
        
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
        
        if expires_delta is not None:
            expire = datetime.now(timezone.utc) + expires_delta
        else:
            expire = datetime.now(timezone.utc) + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)
        
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

# Singleton instance
jwt_manager = JWTManager(
    secret_key=settings.JWT_SECRET_KEY,
    algorithm=settings.JWT_ALGORITHM
)
