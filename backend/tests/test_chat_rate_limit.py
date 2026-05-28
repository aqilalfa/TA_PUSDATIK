import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Add backend to path
sys.path.append(str(Path(__file__).parent.parent))

from app.api.routes import chat as chat_routes
from app.core.security_metrics import security_metrics
from app.auth.login_rate_limiter import chat_rate_limiter
from app.dependencies.auth_dependencies import get_current_user
from app.database import get_db
from app.models.db_models import User


app = FastAPI()
app.include_router(chat_routes.router, prefix="/api/chat", tags=["Chat"])


class DummyDB:
    def query(self, *_args):
        return self

    def filter(self, *_args):
        return self

    def first(self):
        return None


@pytest.fixture()
def client():
    chat_rate_limiter.clear()
    security_metrics.clear()

    user = User(id=42, name="Chat User", email="chat@bssn.go.id", roles='["admin_pusdatik"]')

    def override_get_current_user():
        return user

    def override_get_db():
        yield DummyDB()

    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
    chat_rate_limiter.clear()
    security_metrics.clear()


def test_chat_endpoint_returns_429_after_rate_limit(client):
    payload = {"session_id": "missing-session", "message": "uji rate limit chatbot"}

    for _ in range(10):
        response = client.post("/api/chat/", json=payload)
        assert response.status_code == 404

    response = client.post("/api/chat/", json=payload)

    assert response.status_code == 429
    assert response.headers["Retry-After"].isdigit()
    assert security_metrics.get("http.429", endpoint="chat") == 1


def test_chat_stream_endpoint_returns_429_after_rate_limit(client):
    payload = {"session_id": "missing-session", "message": "uji rate limit stream"}

    for _ in range(10):
        response = client.post("/api/chat/stream", json=payload)
        assert response.status_code == 200

    response = client.post("/api/chat/stream", json=payload)

    assert response.status_code == 429
    assert response.headers["Retry-After"].isdigit()
