import sys
from pathlib import Path

# Add backend to path
sys.path.append(str(Path(__file__).parent.parent))

from app.config import settings

def test_jwt_config_exists():
    """Verify that JWT configuration variables are present in settings"""
    assert hasattr(settings, "JWT_SECRET_KEY"), "JWT_SECRET_KEY missing"
    assert hasattr(settings, "JWT_ALGORITHM"), "JWT_ALGORITHM missing"
    assert hasattr(settings, "JWT_ACCESS_TOKEN_EXPIRE_HOURS"), "JWT_ACCESS_TOKEN_EXPIRE_HOURS missing"
    assert hasattr(settings, "JWT_REFRESH_TOKEN_EXPIRE_DAYS"), "JWT_REFRESH_TOKEN_EXPIRE_DAYS missing"
    
    assert settings.JWT_ALGORITHM == "HS256"
