"""
TDD Tests for Real LDAP/AD Integration
Tests: LDAP bind, shadow user provisioning, group→role mapping, retry logic
"""

import pytest
from unittest.mock import MagicMock, patch, call
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from app.models.db_models import Base, User
from app.auth.ldap_provider import (
    LDAPAuthProvider,
    LDAPDirectoryClient,
    LDAPUnavailableError,
)
from app.auth.role_mapper import map_directory_groups_to_roles
from app.config import settings


@pytest.fixture
def test_db():
    """Create in-memory SQLite database for testing"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()
    engine.dispose()


class TestLDAPDirectoryClient:
    """Test LDAP directory client connectivity"""

    def test_ldap_client_initialized_with_config(self):
        """Verify LDAPDirectoryClient reads from settings"""
        client = LDAPDirectoryClient()
        assert client.server_url == settings.LDAP_SERVER_URL
        assert client.base_dn == settings.LDAP_BASE_DN
        assert client.domain == settings.LDAP_DOMAIN
        assert client.timeout == settings.LDAP_TIMEOUT
        assert client.retry_count == settings.LDAP_RETRY_COUNT

    def test_ldap_client_custom_initialization(self):
        """Verify LDAPDirectoryClient accepts custom parameters"""
        client = LDAPDirectoryClient(
            server_url="ldap://custom.test:389",
            base_dn="dc=custom,dc=test",
            domain="custom.test",
            timeout=5,
            retry_count=1,
        )
        assert client.server_url == "ldap://custom.test:389"
        assert client.base_dn == "dc=custom,dc=test"
        assert client.domain == "custom.test"
        assert client.timeout == 5
        assert client.retry_count == 1

    @patch("ldap3.Connection")
    @patch("ldap3.Server")
    def test_ldap_authenticate_success(self, mock_server_class, mock_connection_class):
        """Test successful LDAP authentication and user data extraction"""
        # Mock LDAP response - configure str() conversion for attributes
        mock_entry = MagicMock()
        
        # Configure attributes to return correct strings when converted
        mock_displayName = MagicMock()
        mock_displayName.values = ["Aqil Administrator"]
        mock_displayName.__str__ = MagicMock(return_value="Aqil Administrator")
        mock_entry.displayName = mock_displayName
        
        mock_mail = MagicMock()
        mock_mail.values = ["admin@bssn.go.id"]
        mock_mail.__str__ = MagicMock(return_value="admin@bssn.go.id")
        mock_entry.mail = mock_mail
        
        mock_department = MagicMock()
        mock_department.values = ["IT Department"]
        mock_department.__str__ = MagicMock(return_value="IT Department")
        mock_entry.department = mock_department
        
        mock_employeeID = MagicMock()
        mock_employeeID.values = ["123456"]
        mock_employeeID.__str__ = MagicMock(return_value="123456")
        mock_entry.employeeID = mock_employeeID
        
        mock_entry.memberOf = MagicMock()
        mock_entry.memberOf.values = [
            "CN=Admin_PUSDATIK,CN=Groups,DC=bssn,DC=go,DC=id",
            "CN=Manager_Evaluasi,CN=Groups,DC=bssn,DC=go,DC=id",
        ]

        mock_connection = MagicMock()
        mock_connection.entries = [mock_entry]
        mock_connection_class.return_value = mock_connection

        mock_server = MagicMock()
        mock_server_class.return_value = mock_server

        client = LDAPDirectoryClient(domain="bssn.go.id")
        result = client.authenticate("aqil", "password123")

        # Verify Server and Connection were called
        mock_server_class.assert_called_once()
        mock_connection_class.assert_called_once()
        mock_connection.search.assert_called_once()
        mock_connection.unbind.assert_called_once()

        # Verify returned data
        assert result is not None
        assert result["username"] == "aqil"
        assert result["email"] == "admin@bssn.go.id"
        assert result["display_name"] == "Aqil Administrator"
        assert result["department"] == "IT Department"
        assert result["employee_id"] == "123456"
        assert "Admin_PUSDATIK" in result["groups"]
        assert "Manager_Evaluasi" in result["groups"]

    @patch("ldap3.Connection")
    @patch("ldap3.Server")
    def test_ldap_authenticate_invalid_credentials(self, mock_server_class, mock_connection_class):
        """Test LDAP authentication with invalid credentials"""
        mock_connection = MagicMock()
        mock_connection.entries = []  # No entries = user not found
        mock_connection_class.return_value = mock_connection

        mock_server = MagicMock()
        mock_server_class.return_value = mock_server

        client = LDAPDirectoryClient()
        result = client.authenticate("aqil", "wrong_password")

        assert result is None

    @patch("ldap3.Connection")
    @patch("ldap3.Server")
    def test_ldap_retry_on_failure(self, mock_server_class, mock_connection_class):
        """Test LDAP client retries on connection failure"""
        mock_connection_class.side_effect = [
            Exception("Connection timeout"),
            Exception("Connection timeout"),
            MagicMock(entries=[]),  # Third attempt succeeds but returns no user
        ]

        client = LDAPDirectoryClient(retry_count=3)
        result = client.authenticate("aqil", "password123")

        # Should have tried 3 times before giving up
        assert mock_connection_class.call_count == 3
        assert result is None

    def test_ldap_unavailable_error_raised(self):
        """Test LDAPUnavailableError is raised when ldap3 not available"""
        with patch("builtins.__import__", side_effect=ImportError("ldap3 not found")):
            # Force import error to trigger LDAPUnavailableError
            client = LDAPDirectoryClient()
            with pytest.raises(LDAPUnavailableError):
                client.authenticate("aqil", "password")


class TestLDAPRoleMapping:
    """Test LDAP group to PBAC role mapping"""

    def test_map_admin_group_to_roles(self):
        """Verify Admin_PUSDATIK group maps to correct roles"""
        groups = ["Admin_PUSDATIK"]
        roles = map_directory_groups_to_roles(groups)
        assert "admin_pusdatik" in roles
        assert "staf_pusdatik" in roles

    def test_map_evaluator_group_to_roles(self):
        """Verify Evaluator_SPBE group maps to correct role"""
        groups = ["Evaluator_SPBE"]
        roles = map_directory_groups_to_roles(groups)
        assert "evaluator_spbe" in roles

    def test_map_manager_group_to_roles(self):
        """Verify Manager_Evaluasi group maps to correct roles"""
        groups = ["Manager_Evaluasi"]
        roles = map_directory_groups_to_roles(groups)
        assert "manager_evaluasi" in roles
        assert "staf_pusdatik" in roles

    def test_map_multiple_groups_to_roles(self):
        """Verify multiple groups map to combined roles"""
        groups = ["Admin_PUSDATIK", "Evaluator_SPBE", "Manager_Evaluasi"]
        roles = map_directory_groups_to_roles(groups)
        
        # Verify all roles present (should be deduplicated)
        assert "admin_pusdatik" in roles
        assert "evaluator_spbe" in roles
        assert "manager_evaluasi" in roles
        assert "staf_pusdatik" in roles
        
        # staf_pusdatik should only appear once
        assert roles.count("staf_pusdatik") == 1

    def test_map_unknown_group_ignored(self):
        """Verify unknown groups are ignored"""
        groups = ["UnknownGroup_XYZ", "Admin_PUSDATIK"]
        roles = map_directory_groups_to_roles(groups)
        
        # Unknown group should be ignored
        assert len(roles) == 2
        assert "admin_pusdatik" in roles
        assert "staf_pusdatik" in roles

    def test_custom_role_mapping(self):
        """Verify custom role mapping can be provided"""
        custom_mapping = {
            "CustomGroup": ["custom_role"],
            "AnotherGroup": ["another_role", "base_role"],
        }
        groups = ["CustomGroup", "AnotherGroup"]
        roles = map_directory_groups_to_roles(groups, role_mapping=custom_mapping)
        
        assert "custom_role" in roles
        assert "another_role" in roles
        assert "base_role" in roles


class TestLDAPAuthProvider:
    """Test LDAP authentication provider with shadow user provisioning"""

    @patch.object(LDAPDirectoryClient, "authenticate")
    def test_ldap_provider_authenticates_user(self, mock_auth, test_db: Session):
        """Verify LDAP provider calls directory client"""
        mock_auth.return_value = {
            "username": "aqil",
            "email": "aqil@bssn.go.id",
            "display_name": "Aqil Admin",
            "department": "IT",
            "employee_id": "12345",
            "groups": ["Admin_PUSDATIK"],
        }

        provider = LDAPAuthProvider(
            directory_client=MagicMock(authenticate=mock_auth)
        )
        user = provider.authenticate("aqil", "password123", test_db)

        assert user is not None
        assert user.email == "aqil@bssn.go.id"
        assert user.auth_provider == "ldap"

    @patch.object(LDAPDirectoryClient, "authenticate")
    def test_ldap_provider_provisions_shadow_user(self, mock_auth, test_db: Session):
        """Verify LDAP provider creates shadow user on first login"""
        mock_auth.return_value = {
            "username": "aqil",
            "email": "aqil@bssn.go.id",
            "display_name": "Aqil Administrator",
            "department": "IT Department",
            "employee_id": "EMP123",
            "groups": ["Admin_PUSDATIK"],
        }

        provider = LDAPAuthProvider(
            directory_client=MagicMock(authenticate=mock_auth)
        )
        user = provider.authenticate("aqil", "password123", test_db)

        # Verify shadow user was created
        assert user is not None
        assert user.email == "aqil@bssn.go.id"
        assert user.name == "Aqil Administrator"
        assert user.department == "IT Department"
        assert user.external_id == "EMP123"
        assert user.auth_provider == "ldap"

        # Verify role was assigned
        assert "admin_pusdatik" in user.roles

        # Verify user exists in database
        db_user = test_db.query(User).filter_by(email="aqil@bssn.go.id").first()
        assert db_user is not None
        assert db_user.id == user.id

    @patch.object(LDAPDirectoryClient, "authenticate")
    def test_ldap_provider_updates_existing_user(self, mock_auth, test_db: Session):
        """Verify LDAP provider updates shadow user on subsequent logins"""
        # Create initial user
        initial_user = User(
            name="Old Name",
            email="aqil@bssn.go.id",
            department="Old Department",
            auth_provider="ldap",
            external_id="EMP123",
        )
        test_db.add(initial_user)
        test_db.commit()

        # Simulate LDAP response with updated info
        mock_auth.return_value = {
            "username": "aqil",
            "email": "aqil@bssn.go.id",
            "display_name": "Aqil Updated Name",
            "department": "New IT Department",
            "employee_id": "EMP123",
            "groups": ["Manager_Evaluasi"],
        }

        provider = LDAPAuthProvider(
            directory_client=MagicMock(authenticate=mock_auth)
        )
        user = provider.authenticate("aqil", "password123", test_db)

        # Verify user was updated
        assert user.name == "Aqil Updated Name"
        assert user.department == "New IT Department"
        
        # Verify role was updated
        assert "manager_evaluasi" in user.roles
        assert "staf_pusdatik" in user.roles

    @patch.object(LDAPDirectoryClient, "authenticate")
    def test_ldap_provider_handles_invalid_credentials(self, mock_auth, test_db: Session):
        """Verify LDAP provider handles invalid credentials"""
        mock_auth.return_value = None

        provider = LDAPAuthProvider(
            directory_client=MagicMock(authenticate=mock_auth)
        )
        user = provider.authenticate("aqil", "wrong_password", test_db)

        assert user is None

    @patch.object(LDAPDirectoryClient, "authenticate")
    def test_ldap_provider_handles_unavailable_backend(self, mock_auth, test_db: Session):
        """Verify LDAP provider propagates backend unavailable error"""
        mock_auth.side_effect = LDAPUnavailableError("LDAP server unreachable")

        provider = LDAPAuthProvider(
            directory_client=MagicMock(authenticate=mock_auth)
        )

        with pytest.raises(LDAPUnavailableError):
            provider.authenticate("aqil", "password123", test_db)

    @patch.object(LDAPDirectoryClient, "authenticate")
    def test_ldap_provider_multiple_groups(self, mock_auth, test_db: Session):
        """Verify shadow user gets all mapped roles from multiple LDAP groups"""
        mock_auth.return_value = {
            "username": "aqil",
            "email": "aqil@bssn.go.id",
            "display_name": "Aqil Multi-Role",
            "department": "IT",
            "employee_id": "EMP123",
            "groups": ["Admin_PUSDATIK", "Evaluator_SPBE"],
        }

        provider = LDAPAuthProvider(
            directory_client=MagicMock(authenticate=mock_auth)
        )
        user = provider.authenticate("aqil", "password123", test_db)

        # Verify all roles assigned
        assert "admin_pusdatik" in user.roles
        assert "staf_pusdatik" in user.roles
        assert "evaluator_spbe" in user.roles


class TestLDAPIntegration:
    """Integration tests for LDAP authentication flow"""

    @patch.object(LDAPDirectoryClient, "authenticate")
    def test_end_to_end_ldap_login_flow(self, mock_auth, test_db: Session):
        """Test complete LDAP login flow: authenticate → provision → token"""
        # Setup mock LDAP response
        mock_auth.return_value = {
            "username": "aqil",
            "email": "aqil@bssn.go.id",
            "display_name": "Aqil Administrator",
            "department": "IT Security",
            "employee_id": "SEC001",
            "groups": ["Admin_PUSDATIK", "Manager_Evaluasi"],
        }

        # Create provider
        provider = LDAPAuthProvider(
            directory_client=MagicMock(authenticate=mock_auth)
        )

        # Authenticate
        user = provider.authenticate("aqil", "secure_password123", test_db)

        # Verify result
        assert user is not None
        assert user.email == "aqil@bssn.go.id"
        assert user.auth_provider == "ldap"
        assert "admin_pusdatik" in user.roles
        assert "manager_evaluasi" in user.roles

        # Verify shadow user persisted
        db_user = test_db.query(User).filter_by(email="aqil@bssn.go.id").first()
        assert db_user is not None
        assert db_user.external_id == "SEC001"

        # Second login should find existing user
        user2 = provider.authenticate("aqil", "secure_password123", test_db)
        assert user2.id == user.id

    @patch.object(LDAPDirectoryClient, "authenticate")
    def test_ldap_login_with_no_groups(self, mock_auth, test_db: Session):
        """Test LDAP login for user with no group memberships"""
        mock_auth.return_value = {
            "username": "viewer",
            "email": "viewer@bssn.go.id",
            "display_name": "Basic Viewer",
            "department": "",
            "employee_id": None,
            "groups": [],  # No groups
        }

        provider = LDAPAuthProvider(
            directory_client=MagicMock(authenticate=mock_auth)
        )
        user = provider.authenticate("viewer", "password", test_db)

        # Verify user created even without roles
        assert user is not None
        assert user.email == "viewer@bssn.go.id"
        # Roles should be empty list
        assert user.roles == "[]"
