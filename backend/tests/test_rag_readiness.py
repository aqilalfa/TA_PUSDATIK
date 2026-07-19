from unittest.mock import MagicMock

from app.api.routes.health import collect_readiness, evaluate_readiness


def test_readiness_reports_alignment_drift_without_syncing(monkeypatch):
    db = MagicMock()
    db.execute.return_value.scalar.return_value = 3138
    qdrant = MagicMock()
    qdrant.count.return_value.count = 3016
    monkeypatch.setattr("app.api.routes.health.QdrantClient", lambda **_kwargs: qdrant)
    monkeypatch.setattr("app.api.routes.health._bm25_count", lambda: 3338)
    monkeypatch.setattr("app.api.routes.health._ollama_model_status", lambda: "present")
    monkeypatch.setattr(
        "app.api.routes.health.langchain_engine.reranker_readiness",
        {"status": "degraded", "reason": "local_model_unavailable"},
        raising=False,
    )

    readiness = collect_readiness(db)

    assert readiness["alignment"] == "drift"
    assert readiness["bm25"] == "ready: 3338 chunks"
    assert readiness["sqlite"] == "ready: 3138 chunks"
    assert readiness["qdrant"] == "ready: 3016 chunks"
    assert readiness["reranker"].startswith("degraded")
    qdrant.upsert.assert_not_called()
    qdrant.delete.assert_not_called()


def test_readiness_requires_alignment_reranker_and_production_model():
    ready_services = {
        "bm25": "ready: 10 chunks",
        "sqlite": "ready: 10 chunks",
        "qdrant": "ready: 10 chunks",
        "reranker": "ready",
        "ollama": "present",
        "alignment": "aligned",
    }

    assert evaluate_readiness(ready_services) is True
    assert evaluate_readiness({**ready_services, "alignment": "drift"}) is False
    assert evaluate_readiness({**ready_services, "reranker": "degraded: local_model_unavailable"}) is False
    assert evaluate_readiness({**ready_services, "ollama": "missing: qwen3.5:4b"}) is False
