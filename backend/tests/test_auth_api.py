import sys
from pathlib import Path
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Add backend to path
sys.path.append(str(Path(__file__).parent.parent))

from app.api.auth_routes import router as auth_router
from app.auth.jwt_manager import jwt_manager
from app.auth.local_authenticator import get_password_hash
from app.database import Base, get_db
from app.models.db_models import TokenBlacklist, User

app = FastAPI()
app.include_router(auth_router, prefix="/api/auth", tags=["Auth"])


@pytest.fixture()
def client(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'auth_test.db'}",
        connect_args={"check_same_thread": False},
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    db = TestingSessionLocal()
    db.add(
        User(
            name="Admin BSSN",
            email="admin@bssn.go.id",
            hashed_password=get_password_hash("password123"),
            roles='["admin_pusdatik"]',
            department="PUSDATIK",
            auth_provider="local",
        )
    )
    db.commit()
    db.close()

    def override_get_db():
        session = TestingSessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()

def test_login_invalid_credentials(client):
    """Test login with wrong password"""
    response = client.post(
        "/api/auth/login",
        data={"username": "admin@bssn.go.id", "password": "wrongpassword"}
    )
    assert response.status_code == 401

def test_login_valid_credentials(client):
    """Test login with correct password returns access token and refresh cookie"""
    response = client.post(
        "/api/auth/login",
        data={"username": "admin@bssn.go.id", "password": "password123"}
    )
    
    if response.status_code == 404:
        pytest.fail("Endpoint /api/auth/login not found")
        
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    
    # Check for refresh token cookie
    assert "refresh_token" in response.cookies

    set_cookie = response.headers.get("set-cookie", "")
    assert "HttpOnly" in set_cookie
    assert "Path=/api/auth/refresh" in set_cookie


def test_refresh_returns_full_claims_and_rotates_refresh_cookie(client):
    login_response = client.post(
        "/api/auth/login",
        data={"username": "admin@bssn.go.id", "password": "password123"},
    )
    assert login_response.status_code == 200
    old_refresh_token = login_response.cookies["refresh_token"]

    refresh_response = client.post("/api/auth/refresh")
    assert refresh_response.status_code == 200

    data = refresh_response.json()
    payload = jwt_manager.verify_token(data["access_token"])
    assert payload is not None
    assert payload["sub"] == "admin@bssn.go.id"
    assert payload["username"] == "Admin BSSN"
    assert payload["roles"] == ["admin_pusdatik"]
    assert payload["dept"] == "PUSDATIK"
    assert payload["auth_provider"] == "local"
    assert payload["sid"] == jwt_manager.verify_token(old_refresh_token)["sid"]

    new_refresh_token = refresh_response.cookies["refresh_token"]
    assert new_refresh_token != old_refresh_token
    assert "Path=/api/auth/refresh" in refresh_response.headers.get("set-cookie", "")


def test_reusing_rotated_refresh_token_is_rejected(client):
    login_response = client.post(
        "/api/auth/login",
        data={"username": "admin@bssn.go.id", "password": "password123"},
    )
    old_refresh_token = login_response.cookies["refresh_token"]

    first_refresh = client.post("/api/auth/refresh")
    assert first_refresh.status_code == 200

    client.cookies.set("refresh_token", old_refresh_token)
    reuse_response = client.post("/api/auth/refresh")
    assert reuse_response.status_code == 401


def test_logout_blacklists_access_token_and_clears_refresh_cookie(client):
    login_response = client.post(
        "/api/auth/login",
        data={"username": "admin@bssn.go.id", "password": "password123"},
    )
    access_token = login_response.json()["access_token"]
    payload = jwt_manager.verify_token(access_token)

    logout_response = client.post(
        "/api/auth/logout",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert logout_response.status_code == 200
    assert "Path=/api/auth/refresh" in logout_response.headers.get("set-cookie", "")

    db = next(app.dependency_overrides[get_db]())
    try:
        assert db.query(TokenBlacklist).filter(TokenBlacklist.jti == payload["jti"]).first()
    finally:
        db.close()
