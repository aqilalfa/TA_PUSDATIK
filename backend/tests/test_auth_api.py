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
from app.auth.local_authenticator import get_password_hash
from app.database import Base, get_db
from app.models.db_models import User

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
