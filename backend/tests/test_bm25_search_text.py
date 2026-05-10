"""
Unit tests for BM25 search text composition.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_bm25_search_text_includes_structural_fields():
    from app.core.ingestion.document_manager import _bm25_search_text

    metadata = {
        "hierarchy": "HIER_UNIQUE",
        "context_header": "CTX_UNIQUE",
        "bab": "BAB_UNIQUE",
        "bagian": "BAGIAN_UNIQUE",
        "pasal": "PASAL_UNIQUE",
        "ayat": "AYAT_UNIQUE",
        "document_title": "DOC_TITLE_UNIQUE",
        "filename": "FILENAME_UNIQUE",
        "doc_type": "DOC_TYPE_UNIQUE",
    }
    text = "BODY_UNIQUE"

    output = _bm25_search_text(text, metadata)

    # Included structural fields
    for token in [
        "HIER_UNIQUE",
        "CTX_UNIQUE",
        "BAB_UNIQUE",
        "BAGIAN_UNIQUE",
        "PASAL_UNIQUE",
        "AYAT_UNIQUE",
        "BODY_UNIQUE",
    ]:
        assert token in output

    # Excluded document-level fields
    for token in ["DOC_TITLE_UNIQUE", "FILENAME_UNIQUE", "DOC_TYPE_UNIQUE"]:
        assert token not in output
