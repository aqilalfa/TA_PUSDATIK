import sys
import time
from datetime import timedelta
from pathlib import Path
import pytest

# Add backend to path
sys.path.append(str(Path(__file__).parent.parent))

from app.auth.jwt_manager import jwt_manager

def test_create_and_verify_access_token():
    """Test standard access token creation and verification"""
    data = {"sub": "admin@bssn.go.id", "roles": ["admin_pusdatik"]}
    token = jwt_manager.create_access_token(data)
    
    assert token is not None
    assert isinstance(token, str)
    
    # Verify
    payload = jwt_manager.verify_token(token)
    assert payload is not None
    assert payload["sub"] == "admin@bssn.go.id"
    assert payload["roles"] == ["admin_pusdatik"]
    assert "exp" in payload
    assert "jti" in payload
    assert payload["type"] == "access"

def test_expired_token():
    """Test that an expired token is rejected"""
    data = {"sub": "test"}
    # Create token that expires immediately
    token = jwt_manager.create_access_token(data, expires_delta=timedelta(seconds=-1))
    
    # Verification should return None for expired tokens
    payload = jwt_manager.verify_token(token)
    assert payload is None
