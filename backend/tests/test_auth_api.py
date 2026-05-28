import sys
from datetime import timedelta
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
from app.auth.login_rate_limiter import login_failed_rate_limiter
from app.auth.token_revocation import token_revocation_store
from app.core.security_metrics import security_metrics
from app.database import Base, get_db
from app.models.db_models import TokenBlacklist, User

app = FastAPI()
app.include_router(auth_router, prefix="/api/auth", tags=["Auth"])


@pytest.fixture()
def client(tmp_path):
    login_failed_rate_limiter.clear()
    token_revocation_store.clear()
    security_metrics.clear()

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
    login_failed_rate_limiter.clear()
    token_revocation_store.clear()
    security_metrics.clear()

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
    old_refresh_payload = jwt_manager.verify_token(old_refresh_token)
    assert payload is not None
    assert old_refresh_payload is not None
    assert payload["sub"] == "admin@bssn.go.id"
    assert payload["username"] == "Admin BSSN"
    assert payload["roles"] == ["admin_pusdatik"]
    assert payload["dept"] == "PUSDATIK"
    assert payload["auth_provider"] == "local"
    assert payload["sid"] == old_refresh_payload["sid"]

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


def test_repeated_failed_login_attempts_return_429_with_retry_after(client):
    credentials = {"username": "flood-test@bssn.go.id", "password": "wrongpassword"}

    for _ in range(5):
        response = client.post("/api/auth/login", data=credentials)
        assert response.status_code == 401

    response = client.post("/api/auth/login", data=credentials)

    assert response.status_code == 429
    assert response.headers["Retry-After"].isdigit()


def test_failed_login_rate_limit_updates_security_metrics(client):
    credentials = {"username": "metrics-user@bssn.go.id", "password": "wrongpassword"}

    for _ in range(6):
        client.post("/api/auth/login", data=credentials)

    assert security_metrics.get("auth.failed_login", username="metrics-user@bssn.go.id", ip="testclient") == 5
    assert security_metrics.get("http.401", endpoint="auth/login") == 5
    assert security_metrics.get("http.429", endpoint="auth/login") == 1


def test_logout_blacklists_access_token_and_clears_refresh_cookie(client):
    login_response = client.post(
        "/api/auth/login",
        data={"username": "admin@bssn.go.id", "password": "password123"},
    )
    access_token = login_response.json()["access_token"]
    payload = jwt_manager.verify_token(access_token)
    assert payload is not None

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
    assert token_revocation_store.is_revoked(payload["jti"])
    assert security_metrics.get("auth.token_revoked", username="admin@bssn.go.id") == 1


def test_logout_rejects_malformed_bearer_token(client):
    response = client.post(
        "/api/auth/logout",
        headers={"Authorization": "Bearer not-a-valid-jwt"},
    )

    assert response.status_code == 401


def test_logout_rejects_expired_access_token(client):
    expired_token = jwt_manager.create_access_token(
        {"sub": "admin@bssn.go.id", "roles": ["admin_pusdatik"]},
        expires_delta=timedelta(seconds=-1),
    )

    response = client.post(
        "/api/auth/logout",
        headers={"Authorization": f"Bearer {expired_token}"},
    )

    assert response.status_code == 401


def test_logout_rejects_access_token_after_revocation(client):
    login_response = client.post(
        "/api/auth/login",
        data={"username": "admin@bssn.go.id", "password": "password123"},
    )
    access_token = login_response.json()["access_token"]

    first_logout = client.post(
        "/api/auth/logout",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert first_logout.status_code == 200

    second_logout = client.post(
        "/api/auth/logout",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert second_logout.status_code == 401
