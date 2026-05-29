import importlib.util
import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).parent.parent))

from app.api.routes import chat as chat_routes
from app.auth.login_rate_limiter import chat_rate_limiter
from app.core.security_metrics import security_metrics
from app.database import get_db
from app.dependencies.auth_dependencies import get_current_user
from app.models.db_models import User
from app.models.schemas import ChatRequest


class DummySession:
    id = "session-1"
    user_id = 42
    updated_at = None


class DummyDB:
    def query(self, *_args):
        return self

    def filter(self, *_args):
        return self

    def first(self):
        return DummySession()

    def add(self, *_args):
        return None

    def flush(self):
        return None

    def commit(self):
        return None

    def rollback(self):
        return None


@pytest.fixture()
def client(monkeypatch):
    app = FastAPI()
    app.include_router(chat_routes.router, prefix="/api/chat", tags=["Chat"])
    chat_rate_limiter.clear()
    security_metrics.clear()

    user = User(id=42, name="Chat User", email="chat@bssn.go.id", roles='["admin_pusdatik"]')

    def override_get_current_user():
        return user

    def override_get_db():
        yield DummyDB()

    async def fake_stream_answer(**_kwargs):
        yield "pure rag answer [1]"

    monkeypatch.setattr(
        chat_routes.langchain_engine,
        "retrieve_context",
        lambda **_kwargs: {
            "sources": [{"document_short": "Dokumen RAG", "section": "Bagian 1"}],
            "context": "konteks RAG",
            "query_type": "general",
        },
    )
    monkeypatch.setattr(chat_routes.langchain_engine, "load_history", lambda _session_id: [])
    monkeypatch.setattr(chat_routes.langchain_engine, "stream_answer", fake_stream_answer)
    monkeypatch.setattr(chat_routes, "validate_answer", lambda *_args, **_kwargs: {"warnings": []})

    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
    chat_rate_limiter.clear()
    security_metrics.clear()


def test_chat_request_defaults_to_structured_fact_disabled():
    request = ChatRequest(message="Apa yang dimaksud dengan Layanan SPBE?")

    assert request.use_structured_fact is False


def test_chat_stream_skips_structured_fact_by_default(client):
    response = client.post(
        "/api/chat/stream",
        json={
            "session_id": "session-1",
            "message": "Apa saja prinsip-prinsip dalam pelaksanaan SPBE?",
            "use_rag": True,
        },
    )

    assert response.status_code == 200
    assert "pure rag answer" in response.text
    assert "structured-fact-index" not in response.text
    assert '"structured_fact"' not in response.text


def test_chat_stream_uses_structured_fact_when_explicitly_enabled(client):
    response = client.post(
        "/api/chat/stream",
        json={
            "session_id": "session-1",
            "message": "Apa saja prinsip-prinsip dalam pelaksanaan SPBE?",
            "use_rag": True,
            "use_structured_fact": True,
        },
    )

    assert response.status_code == 200
    assert '"mode": "structured_fact"' in response.text
    assert '"model_used": "structured-fact-index"' in response.text


def test_chat_stream_can_disable_structured_fact_for_pure_rag(client):
    response = client.post(
        "/api/chat/stream",
        json={
            "session_id": "session-1",
            "message": "Apa saja prinsip-prinsip dalam pelaksanaan SPBE?",
            "use_rag": True,
            "use_structured_fact": False,
        },
    )

    assert response.status_code == 200
    assert "pure rag answer" in response.text
    assert "structured-fact-index" not in response.text
    assert '"structured_fact"' not in response.text


def test_ground_truth_eval_defaults_to_pure_rag_report_semantics():
    script = Path(__file__).parents[2] / "TUGAS AKHIR" / "resume_ground_truth_eval.py"
    if not script.exists():
        pytest.skip("TUGAS AKHIR evaluator script is outside the backend container mount")

    spec = importlib.util.spec_from_file_location("resume_ground_truth_eval", script)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    assert module.MODES["pure-rag"]["use_structured_fact"] is False
    assert module.MODES["structured"]["use_structured_fact"] is True

    report = module.report(
        [],
        mode="pure-rag",
        metadata=module.MODES["pure-rag"],
    )

    assert "Mode evaluasi: `pure-rag`" in report
    assert "Structured fact fallback: nonaktif" in report
    assert "tidak mencampur" not in report.lower()
