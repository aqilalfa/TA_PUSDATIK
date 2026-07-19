from unittest.mock import MagicMock, patch

from app.core.rag.engine.llm_client import _build_ollama_messages
from app.core.rag.langchain_engine import LangchainRAGEngine
from app.core.rag.query_profile import classify_query_profile
from app.config import settings


def test_production_messages_include_answer_style_and_scope_instruction():
    profile = classify_query_profile("Apa tujuan SPBE secara nasional?")
    messages = _build_ollama_messages(
        query="Apa tujuan SPBE secara nasional?",
        context="[1] tujuan SPBE",
        history=[],
        query_profile=profile,
    )
    joined = "\n".join(message["content"] for message in messages)
    assert "PROFIL JAWABAN BERDASARKAN TIPE PERTANYAAN" in joined
    assert "cakupan nasional" in joined.lower()


def test_local_cpu_cross_encoder_loads_once_without_network():
    engine = LangchainRAGEngine.__new__(LangchainRAGEngine)
    engine._reranker = None
    engine.reranker_readiness = {"status": "not_loaded"}
    fake = MagicMock()

    with patch("sentence_transformers.CrossEncoder", return_value=fake) as cross_encoder:
        first = engine._load_reranker()
        second = engine._load_reranker()

    assert first is fake and second is fake
    cross_encoder.assert_called_once()
    assert cross_encoder.call_args.kwargs["device"] == "cpu"
    assert cross_encoder.call_args.kwargs["local_files_only"] is True


def test_missing_local_cross_encoder_degrades_explicitly():
    engine = LangchainRAGEngine.__new__(LangchainRAGEngine)
    engine._reranker = None
    engine.reranker_readiness = {"status": "not_loaded"}

    with patch("sentence_transformers.CrossEncoder", side_effect=OSError("cache missing")):
        assert engine._load_reranker() is None

    assert engine.reranker_readiness["status"] == "degraded"
    assert engine.reranker_readiness["reason"] == "local_model_unavailable"


def test_cross_encoder_prefers_downloaded_snapshot_directory(tmp_path, monkeypatch):
    snapshot = tmp_path / "bge-reranker-base"
    snapshot.mkdir()
    (snapshot / "config.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(settings, "RERANKER_CACHE_DIR", str(tmp_path))

    engine = LangchainRAGEngine.__new__(LangchainRAGEngine)
    engine._reranker = None
    engine.reranker_readiness = {"status": "not_loaded"}
    fake = MagicMock()

    with patch("sentence_transformers.CrossEncoder", return_value=fake) as cross_encoder:
        assert engine._load_reranker() is fake

    assert cross_encoder.call_args.args[0] == str(snapshot)
