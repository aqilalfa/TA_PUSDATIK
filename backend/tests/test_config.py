import sys
from pathlib import Path

# Add backend to path
sys.path.append(str(Path(__file__).parent.parent))

import pytest

from app.config import DEFAULT_JWT_SECRET_KEY, Settings, settings

def test_jwt_config_exists():
    """Verify that JWT configuration variables are present in settings"""
    assert hasattr(settings, "JWT_SECRET_KEY"), "JWT_SECRET_KEY missing"
    assert hasattr(settings, "JWT_ALGORITHM"), "JWT_ALGORITHM missing"
    assert hasattr(settings, "JWT_ACCESS_TOKEN_EXPIRE_HOURS"), "JWT_ACCESS_TOKEN_EXPIRE_HOURS missing"
    assert hasattr(settings, "JWT_REFRESH_TOKEN_EXPIRE_DAYS"), "JWT_REFRESH_TOKEN_EXPIRE_DAYS missing"
    
    assert settings.JWT_ALGORITHM == "HS256"


def test_production_rejects_default_jwt_secret():
    with pytest.raises(ValueError):
        Settings(ENVIRONMENT="production", JWT_SECRET_KEY=DEFAULT_JWT_SECRET_KEY)


def test_production_accepts_strong_jwt_secret():
    cfg = Settings(ENVIRONMENT="production", JWT_SECRET_KEY="x" * 40)
    assert cfg.JWT_SECRET_KEY == "x" * 40
