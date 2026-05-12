import sys
from pathlib import Path
import pytest
from fastapi import HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials

# Add backend to path
sys.path.append(str(Path(__file__).parent.parent))

from app.auth.jwt_manager import jwt_manager
from app.dependencies.auth_dependencies import get_current_user, require_roles
from app.models.db_models import User, TokenBlacklist
import json

class MockDB:
    def query(self, *args):
        return self
    def filter(self, *args):
        return self
    def first(self):
        return None  # Simulate no blacklist

# Mock user for PBAC test
class MockUser:
    def __init__(self, email, roles):
        self.email = email
        self.roles = json.dumps(roles)

def test_get_current_user_valid_token():
    """Test get_current_user with a valid token"""
    db = MockDB()
    token = jwt_manager.create_access_token({"sub": "admin@bssn.go.id", "roles": ["admin_pusdatik"]})
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    
    # We mock the db.query to return different results based on the model
    class MockUserDB:
        def __init__(self, current_model=None):
            self.current_model = current_model
            
        def query(self, model):
            return MockUserDB(current_model=model)
            
        def filter(self, *args):
            return self
            
        def first(self):
            if self.current_model == TokenBlacklist:
                return None
            return MockUser("admin@bssn.go.id", ["admin_pusdatik"])
            
    # Test requires overriding db session, so we just test the parsing
    user = get_current_user(creds, MockUserDB())
    assert user is not None
    assert user.email == "admin@bssn.go.id"

def test_require_roles():
    """Test PBAC require_roles dependency"""
    user = MockUser("admin@bssn.go.id", ["admin_pusdatik"])
    
    # This should pass without raising
    dep = require_roles(["admin_pusdatik"])
    result = dep(user)
    assert result == user
    
    # This should raise 403
    dep_fail = require_roles(["evaluator_spbe"])
    with pytest.raises(HTTPException) as excinfo:
        dep_fail(user)
    assert excinfo.value.status_code == status.HTTP_403_FORBIDDEN
