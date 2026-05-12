"""
Real LDAP Testing with Mock LDAP Server
Provides fixtures and integration tests for real LDAP operations
"""

import pytest
import os
from pathlib import Path
from dataclasses import dataclass
from typing import Generator
from unittest.mock import MagicMock, patch
import threading
import time

from ldap3 import Server, Connection, ALL, MOCK_SYNC
from ldap3.utils.dn import escape_rdn


@dataclass
class MockLDAPUser:
    """Mock LDAP user for testing"""
    username: str
    password: str
    email: str
    display_name: str
    department: str
    employee_id: str
    groups: list[str]  # Group DNs
    
    @property
    def dn(self):
        """Return user's distinguished name"""
        return f"CN={self.username},CN=Users,DC=bssn,DC=go,DC=id"
    
    @property
    def user_dn(self):
        """Return principal name (username@domain)"""
        return f"{self.username}@bssn.go.id"


class MockLDAPServer:
    """
    Mock LDAP server for testing LDAP operations.
    Provides realistic LDAP directory structure without requiring real AD.
    """
    
    def __init__(self, server_url: str = "ldap://localhost:389"):
        self.server_url = server_url
        self.base_dn = "DC=bssn,DC=go,DC=id"
        self.users: dict[str, MockLDAPUser] = {}
        self.groups: dict[str, dict] = {}
        self._init_bssn_structure()
    
    def _init_bssn_structure(self):
        """Initialize BSSN organization structure"""
        # Define BSSN groups
        self.groups = {
            "CN=Admin_PUSDATIK,CN=Groups,DC=bssn,DC=go,DC=id": {
                "cn": "Admin_PUSDATIK",
                "members": [],
                "description": "PUSDATIK Administrators"
            },
            "CN=Evaluator_SPBE,CN=Groups,DC=bssn,DC=go,DC=id": {
                "cn": "Evaluator_SPBE",
                "members": [],
                "description": "SPBE Evaluators"
            },
            "CN=Staf_PUSDATIK,CN=Groups,DC=bssn,DC=go,DC=id": {
                "cn": "Staf_PUSDATIK",
                "members": [],
                "description": "PUSDATIK Staff"
            },
            "CN=Manager_Evaluasi,CN=Groups,DC=bssn,DC=go,DC=id": {
                "cn": "Manager_Evaluasi",
                "members": [],
                "description": "Evaluation Managers"
            }
        }
        
        # Add test users
        self._add_test_users()
    
    def _add_test_users(self):
        """Add predefined test users"""
        # Admin user - member of Admin_PUSDATIK and Manager_Evaluasi
        admin = MockLDAPUser(
            username="admin",
            password="AdminPassword123!",
            email="admin@bssn.go.id",
            display_name="Administrator BSSN",
            department="IT Security",
            employee_id="EMP001",
            groups=[
                "CN=Admin_PUSDATIK,CN=Groups,DC=bssn,DC=go,DC=id",
                "CN=Manager_Evaluasi,CN=Groups,DC=bssn,DC=go,DC=id"
            ]
        )
        self.users["admin"] = admin
        
        # Evaluator user - member of Evaluator_SPBE
        evaluator = MockLDAPUser(
            username="evaluator",
            password="EvaluatorPass123!",
            email="evaluator@bssn.go.id",
            display_name="Evaluator SPBE",
            department="Evaluation Division",
            employee_id="EMP002",
            groups=[
                "CN=Evaluator_SPBE,CN=Groups,DC=bssn,DC=go,DC=id",
                "CN=Staf_PUSDATIK,CN=Groups,DC=bssn,DC=go,DC=id"
            ]
        )
        self.users["evaluator"] = evaluator
        
        # Staff user - member of Staf_PUSDATIK
        staff = MockLDAPUser(
            username="staff",
            password="StaffPass123!",
            email="staff@bssn.go.id",
            display_name="Staff PUSDATIK",
            department="Operations",
            employee_id="EMP003",
            groups=[
                "CN=Staf_PUSDATIK,CN=Groups,DC=bssn,DC=go,DC=id"
            ]
        )
        self.users["staff"] = staff
    
    def authenticate_user(self, username: str, password: str) -> dict | None:
        """
        Authenticate a user against mock LDAP.
        Returns user data dict if valid credentials, None otherwise.
        """
        user = self.users.get(username)
        if not user or user.password != password:
            return None
        
        return {
            "username": user.username,
            "email": user.email,
            "display_name": user.display_name,
            "department": user.department,
            "employee_id": user.employee_id,
            "groups": user.groups,
            "dn": user.dn,
        }
    
    def add_user(self, user: MockLDAPUser):
        """Add a user to mock LDAP directory"""
        self.users[user.username] = user
    
    def add_user_to_group(self, username: str, group_dn: str):
        """Add user to a group"""
        user = self.users.get(username)
        if user and group_dn not in user.groups:
            user.groups.append(group_dn)
            if group_dn in self.groups:
                self.groups[group_dn]["members"].append(user.dn)


@pytest.fixture
def mock_ldap_server() -> Generator[MockLDAPServer, None, None]:
    """
    Pytest fixture that provides a mock LDAP server.
    Yields the server, then cleans up after test completes.
    """
    server = MockLDAPServer()
    yield server


@pytest.fixture
def mock_ldap_connection(mock_ldap_server):
    """
    Pytest fixture that patches ldap3.Connection to use mock LDAP.
    Use this in tests that call real LDAP code.
    """
    original_connection = None
    
    def mock_connection_init(self, *args, **kwargs):
        # Store the mock server reference
        self._mock_server = mock_ldap_server
    
    def mock_bind(self):
        """Mock bind operation"""
        user = kwargs.get("user")
        password = kwargs.get("password")
        
        if not user or not password:
            return False
        
        # Parse username from UPN (user@domain)
        if "@" in user:
            username = user.split("@")[0]
        else:
            username = user
        
        result = self._mock_server.authenticate_user(username, password)
        self._is_authenticated = result is not None
        return self._is_authenticated
    
    def mock_search(self, search_base, search_filter, attributes=None):
        """Mock search operation"""
        if not self._is_authenticated:
            return False
        
        # Simple filter parsing for sAMAccountName=username
        if "sAMAccountName=" in search_filter:
            username = search_filter.split("sAMAccountName=")[1].rstrip(")")
            user = self._mock_server.users.get(username)
            
            if user:
                # Create mock entry
                entry = MagicMock()
                
                # Mock attributes
                entry.displayName = MagicMock()
                entry.displayName.__str__ = MagicMock(return_value=user.display_name)
                
                entry.mail = MagicMock()
                entry.mail.__str__ = MagicMock(return_value=user.email)
                
                entry.department = MagicMock()
                entry.department.__str__ = MagicMock(return_value=user.department)
                
                entry.employeeID = MagicMock()
                entry.employeeID.__str__ = MagicMock(return_value=user.employee_id)
                
                entry.memberOf = MagicMock()
                entry.memberOf.values = user.groups
                
                self.entries = [entry]
                return True
        
        self.entries = []
        return False
    
    def mock_unbind(self):
        """Mock unbind operation"""
        self._is_authenticated = False
    
    with patch("ldap3.Connection") as mock_conn_class:
        mock_conn_class.side_effect = mock_connection_init
        mock_conn = MagicMock()
        mock_conn._is_authenticated = False
        mock_conn._mock_server = mock_ldap_server
        mock_conn.bind = mock_bind.__get__(mock_conn)
        mock_conn.search = mock_search.__get__(mock_conn)
        mock_conn.unbind = mock_unbind.__get__(mock_conn)
        mock_conn_class.return_value = mock_conn
        
        yield mock_conn


class TestRealLDAPOperations:
    """
    Integration tests for real LDAP operations using mock LDAP server.
    These tests simulate real LDAP scenarios without requiring actual AD.
    """
    
    def test_authenticate_valid_user_against_mock_ldap(self, mock_ldap_server):
        """Test authenticating valid user against mock LDAP"""
        result = mock_ldap_server.authenticate_user("admin", "AdminPassword123!")
        
        assert result is not None
        assert result["username"] == "admin"
        assert result["email"] == "admin@bssn.go.id"
        assert result["display_name"] == "Administrator BSSN"
        assert result["employee_id"] == "EMP001"
        assert len(result["groups"]) == 2  # Two groups
    
    def test_authenticate_invalid_password_against_mock_ldap(self, mock_ldap_server):
        """Test authentication fails with wrong password"""
        result = mock_ldap_server.authenticate_user("admin", "WrongPassword")
        assert result is None
    
    def test_authenticate_nonexistent_user_against_mock_ldap(self, mock_ldap_server):
        """Test authentication fails for nonexistent user"""
        result = mock_ldap_server.authenticate_user("nonexistent", "password")
        assert result is None
    
    def test_all_test_users_present_in_mock_ldap(self, mock_ldap_server):
        """Test that all predefined test users exist in mock LDAP"""
        assert "admin" in mock_ldap_server.users
        assert "evaluator" in mock_ldap_server.users
        assert "staff" in mock_ldap_server.users
    
    def test_user_group_memberships_in_mock_ldap(self, mock_ldap_server):
        """Test user group memberships match expected structure"""
        admin = mock_ldap_server.users["admin"]
        assert "CN=Admin_PUSDATIK,CN=Groups,DC=bssn,DC=go,DC=id" in admin.groups
        assert "CN=Manager_Evaluasi,CN=Groups,DC=bssn,DC=go,DC=id" in admin.groups
        
        evaluator = mock_ldap_server.users["evaluator"]
        assert "CN=Evaluator_SPBE,CN=Groups,DC=bssn,DC=go,DC=id" in evaluator.groups
    
    def test_add_custom_user_to_mock_ldap(self, mock_ldap_server):
        """Test adding custom user to mock LDAP"""
        custom_user = MockLDAPUser(
            username="custom",
            password="CustomPass123!",
            email="custom@bssn.go.id",
            display_name="Custom User",
            department="Custom Dept",
            employee_id="EMP999",
            groups=[]
        )
        mock_ldap_server.add_user(custom_user)
        
        assert "custom" in mock_ldap_server.users
        result = mock_ldap_server.authenticate_user("custom", "CustomPass123!")
        assert result is not None
        assert result["email"] == "custom@bssn.go.id"
    
    def test_add_user_to_group_in_mock_ldap(self, mock_ldap_server):
        """Test adding user to group"""
        initial_groups = len(mock_ldap_server.users["staff"].groups)
        
        mock_ldap_server.add_user_to_group(
            "staff",
            "CN=Manager_Evaluasi,CN=Groups,DC=bssn,DC=go,DC=id"
        )
        
        staff = mock_ldap_server.users["staff"]
        assert len(staff.groups) == initial_groups + 1
        assert "CN=Manager_Evaluasi,CN=Groups,DC=bssn,DC=go,DC=id" in staff.groups


class TestLDAPProviderWithMockLDAP:
    """
    Tests for LDAP auth provider using mock LDAP server.
    These test the real provider code with mocked LDAP backend.
    """
    
    def test_ldap_provider_authenticate_with_mock_ldap(self, mock_ldap_server):
        """Test LDAP provider authenticates against mock LDAP"""
        from app.auth.ldap_provider import LDAPDirectoryClient, LDAPAuthProvider
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from app.models.db_models import Base, User
        
        # Setup in-memory test DB
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        TestSession = sessionmaker(bind=engine)
        db = TestSession()
        
        # Mock the directory client to return mock LDAP data
        mock_client = MagicMock(spec=LDAPDirectoryClient)
        ldap_data = mock_ldap_server.authenticate_user("admin", "AdminPassword123!")
        
        # Parse group DNs to extract group names for role mapping
        groups_parsed = [g.split(",")[0].replace("CN=", "") for g in ldap_data["groups"]]
        ldap_data["groups"] = groups_parsed
        
        mock_client.authenticate.return_value = ldap_data
        
        provider = LDAPAuthProvider(directory_client=mock_client)
        user = provider.authenticate("admin", "AdminPassword123!", db)
        
        assert user is not None
        assert user.email == "admin@bssn.go.id"
        assert "admin_pusdatik" in user.roles
        assert "manager_evaluasi" in user.roles
    
    def test_ldap_group_mapping_with_all_test_users(self, mock_ldap_server):
        """Test role mapping works for all test users"""
        from app.auth.role_mapper import map_directory_groups_to_roles
        
        for username in ["admin", "evaluator", "staff"]:
            user = mock_ldap_server.users[username]
            # Parse group DNs to just group names (DN format: CN=GroupName,...)
            group_names = [g.split(",")[0].replace("CN=", "") for g in user.groups]
            
            roles = map_directory_groups_to_roles(group_names)
            assert len(roles) > 0  # Should have at least one role
            
            # Verify specific roles
            if username == "admin":
                assert "admin_pusdatik" in roles
                assert "manager_evaluasi" in roles
            elif username == "evaluator":
                assert "evaluator_spbe" in roles
            elif username == "staff":
                assert "staf_pusdatik" in roles


class TestRealLDAPScenarios:
    """
    Real-world scenario tests for LDAP integration.
    Test common authentication flows and edge cases.
    """
    
    def test_ldap_user_first_login_creates_shadow_user(self, mock_ldap_server):
        """Test first LDAP login creates shadow user"""
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from app.models.db_models import Base, User
        from app.auth.ldap_provider import LDAPAuthProvider, LDAPDirectoryClient
        
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        TestSession = sessionmaker(bind=engine)
        db = TestSession()
        
        # Mock the directory client
        client = MagicMock(spec=LDAPDirectoryClient)
        client.authenticate.return_value = mock_ldap_server.authenticate_user(
            "evaluator", "EvaluatorPass123!"
        )
        
        provider = LDAPAuthProvider(directory_client=client)
        user = provider.authenticate("evaluator", "EvaluatorPass123!", db)
        
        # Verify shadow user was created
        assert user is not None
        assert user.email == "evaluator@bssn.go.id"
        assert user.auth_provider == "ldap"
        assert user.external_id == "EMP002"
        
        # Verify user in database
        db_user = db.query(User).filter_by(email="evaluator@bssn.go.id").first()
        assert db_user is not None
    
    def test_ldap_user_subsequent_login_updates_shadow_user(self, mock_ldap_server):
        """Test subsequent LDAP login updates shadow user"""
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from app.models.db_models import Base, User
        from app.auth.ldap_provider import LDAPAuthProvider, LDAPDirectoryClient
        
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        TestSession = sessionmaker(bind=engine)
        db = TestSession()
        
        # Mock the directory client
        client = MagicMock(spec=LDAPDirectoryClient)
        client.authenticate.return_value = mock_ldap_server.authenticate_user(
            "staff", "StaffPass123!"
        )
        
        provider = LDAPAuthProvider(directory_client=client)
        
        # First login
        user1 = provider.authenticate("staff", "StaffPass123!", db)
        user1_id = user1.id
        
        # Second login (simulating user update)
        user2 = provider.authenticate("staff", "StaffPass123!", db)
        
        # Should be same user (same ID)
        assert user2.id == user1_id
        assert user2.email == user1.email
    
    def test_ldap_invalid_credentials_returns_none(self, mock_ldap_server):
        """Test LDAP with invalid credentials returns None"""
        from app.auth.ldap_provider import LDAPAuthProvider, LDAPDirectoryClient
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from app.models.db_models import Base
        
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        TestSession = sessionmaker(bind=engine)
        db = TestSession()
        
        client = MagicMock(spec=LDAPDirectoryClient)
        client.authenticate.return_value = None  # Auth failed
        
        provider = LDAPAuthProvider(directory_client=client)
        user = provider.authenticate("admin", "WrongPassword", db)
        
        assert user is None
