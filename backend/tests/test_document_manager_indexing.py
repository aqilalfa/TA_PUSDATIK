"""
Tests for DocumentManager indexing behavior.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_index_document_warns_on_truncation(monkeypatch):
    """
    Indexing must warn when chunk count exceeds MAX_INDEX_CHUNKS.
    """
    import app.core.ingestion.document_manager as dm
    from app.core.ingestion.document_manager import DocumentManager

    # Use a small limit to keep the test fast
    monkeypatch.setattr(dm, "MAX_INDEX_CHUNKS", 3)

    warnings = []
    monkeypatch.setattr(dm.logger, "warning", lambda msg: warnings.append(msg))

    manager = DocumentManager()
    manager.get_document = lambda doc_id: {
        "doc_id": doc_id,
        "document_title": "Doc Test",
        "original_filename": "doc_test.pdf",
        "doc_type": "other",
    }
    manager.get_chunks = lambda doc_id, limit=None: [
        {"text": "A"},
        {"text": "B"},
        {"text": "C"},
    ]
    manager.get_chunk_count = lambda doc_id: 5
    manager.generate_embedding = lambda text: [0.0]
    manager._upload_document_points = lambda doc_id, doc, chunks, embeddings: len(chunks)
    manager.mark_chunks_indexed = lambda doc_id: None
    manager.update_document = lambda *a, **k: True
    manager._rebuild_bm25_index = lambda: None

    result = manager.index_document("doc-1")

    assert any("Indexing truncated" in msg for msg in warnings), (
        "Expected warning about indexing truncation when chunk count exceeds limit"
    )
    assert result["chunks_indexed"] == 3
