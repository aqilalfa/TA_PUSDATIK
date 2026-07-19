import inspect
from unittest.mock import Mock

import numpy as np

from app.core.ingestion.document_manager import DocumentManager
from app.core.rag.engine.retrievers import HybridRetriever


def test_rebuild_bm25_preserves_filename_and_table_metadata():
    source = inspect.getsource(DocumentManager._rebuild_bm25_index)

    assert '"filename": chunk.get("filename", "")' in source
    assert '"is_table": chunk.get("is_table", False)' in source
    assert '"table_label": chunk.get("table_label", "")' in source
    assert '"table_context": chunk.get("table_context", "")' in source


def test_bm25_doc_scope_filters_by_doc_id():
    bm25 = Mock()
    bm25.get_scores.return_value = np.array([2.0, 1.5, 3.0])
    retriever = HybridRetriever(Mock(), Mock(), bm25)
    docs = [
        {
            "text": "Pasal 1 SPBE",
            "metadata": {"filename": "peraturan.pdf", "doc_id": "doc-a"},
        },
        {
            "text": "Pasal 2 SPBE",
            "metadata": {"filename": "peraturan.pdf", "document_id": 7},
        },
        {
            "text": "Laporan audit",
            "metadata": {"filename": "audit.pdf", "doc_id": "doc-b"},
        },
    ]

    by_uuid = retriever.bm25_search("SPBE", 10, docs, doc_id="doc-a")
    by_numeric_id = retriever.bm25_search("SPBE", 10, docs, doc_id="7")

    assert [doc.metadata["filename"] for doc in by_uuid] == ["peraturan.pdf"]
    assert [doc.metadata["filename"] for doc in by_numeric_id] == ["peraturan.pdf"]
