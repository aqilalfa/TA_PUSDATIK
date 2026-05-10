"""
TDD RED Phase Test for CR-05: BM25 pickle integrity checks

The loader must reject malformed payloads to avoid unsafe or corrupted indices.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pickle


def test_bm25_loader_rejects_invalid_payload(tmp_path, monkeypatch):
    """
    When the bm25_index.pkl payload is malformed, _load_bm25() must reject it
    and leave the in-memory BM25 state empty.
    """
    from app.core.rag.langchain_engine import LangchainRAGEngine

    engine = LangchainRAGEngine()

    bad_path = tmp_path / "bm25_index.pkl"
    bad_payload = {
        "bm25": "not-a-bm25-object",
        "documents": "not-a-list",
        "doc_ids": [],
        "corpus_texts": [],
    }
    with bad_path.open("wb") as f:
        pickle.dump(bad_payload, f)

    monkeypatch.setattr(engine, "_bm25_index_path", lambda: bad_path)

    # Seed previous state to ensure it gets cleared
    engine._bm25 = object()
    engine._bm25_docs = ["stale"]
    engine._bm25_loaded = False

    engine._load_bm25(force=True)

    assert engine._bm25 is None, "Invalid BM25 payload should reset bm25 to None"
    assert engine._bm25_docs == [], "Invalid BM25 payload should clear documents list"
