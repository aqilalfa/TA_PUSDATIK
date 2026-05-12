import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add backend to path
sys.path.append(str(Path(__file__).parent.parent))

from app.config import settings
from app.database import Base
from app.models.db_models import User


def test_auth_provider_config_defaults_exist():
    assert hasattr(settings, "AUTH_PROVIDER")
    assert hasattr(settings, "LDAP_ENABLED")
    assert settings.AUTH_PROVIDER == "local"
    assert settings.LDAP_ENABLED is False


def test_factory_returns_local_provider_by_default():
    from app.auth.auth_service import get_auth_provider

    provider = get_auth_provider()
    assert provider.__class__.__name__ == "LocalAuthProvider"


class FakeDirectoryClient:
    def authenticate(self, username: str, password: str):
        if username == "john@bssn.go.id" and password == "password123":
            return {
                "username": "john@bssn.go.id",
                "display_name": "John Doe",
                "email": "john@bssn.go.id",
                "department": "PUSDATIK",
                "employee_id": "EMP-001",
                "groups": ["Evaluator_SPBE", "Staf_PUSDATIK"],
            }
        return None


def test_ldap_provider_provisions_shadow_user_and_maps_roles(tmp_path, monkeypatch):
    from app.auth.ldap_provider import LDAPAuthProvider

    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False})
    TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    db = TestSessionLocal()
    provider = LDAPAuthProvider(directory_client=FakeDirectoryClient())

    user = provider.authenticate("john@bssn.go.id", "password123", db)

    assert user is not None
    assert user.email == "john@bssn.go.id"
    assert user.name == "John Doe"
    assert user.department == "PUSDATIK"
    assert user.roles == '["evaluator_spbe", "staf_pusdatik"]'
    assert user.auth_provider == "ldap"
    assert user.external_id == "EMP-001"

    persisted = db.query(User).filter(User.email == "john@bssn.go.id").first()
    assert persisted is not None
    assert persisted.auth_provider == "ldap"
    assert persisted.external_id == "EMP-001"


def test_ldap_provider_rejects_invalid_credentials(tmp_path):
    from app.auth.ldap_provider import LDAPAuthProvider

    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False})
    TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    db = TestSessionLocal()
    provider = LDAPAuthProvider(directory_client=FakeDirectoryClient())

    user = provider.authenticate("john@bssn.go.id", "wrong-password", db)

    assert user is None
