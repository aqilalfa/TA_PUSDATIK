import sys
from pathlib import Path
import pytest
from sqlalchemy import Column

# Add backend to path
sys.path.append(str(Path(__file__).parent.parent))

from app.models.db_models import User

def test_user_auth_fields_exist():
    """Verify that User model has authentication and PBAC fields"""
    # Using python's hasattr to check if the SQLAlchemy model has the column descriptors
    assert hasattr(User, "hashed_password"), "User missing hashed_password"
    assert hasattr(User, "roles"), "User missing roles"
    assert hasattr(User, "department"), "User missing department"

def test_token_blacklist_model_exists():
    """Verify that TokenBlacklist model exists"""
    try:
        from app.models.db_models import TokenBlacklist
        assert hasattr(TokenBlacklist, "jti"), "TokenBlacklist missing jti"
        assert hasattr(TokenBlacklist, "expires_at"), "TokenBlacklist missing expires_at"
    except ImportError:
        pytest.fail("TokenBlacklist model not found in app.models.db_models")
