"""
TDD Red Phase Tests for CR-03: BM25 Metadata Missing Filename

These tests verify that filename is properly propagated to BM25 metadata
during document indexing and retrieval. They are written to FAIL first,
then production code is fixed to make them pass (Green phase).

Test Priority: CRITICAL - blocking issue for doc-scoped retrieval
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path


def test_bm25_metadata_includes_filename_during_indexing():
    """
    RED TEST: BM25 metadata dict must include 'filename' field during _build_bm25_index().
    
    Regression test for CR-03.
    
    Currently FAILS because document_manager.py lines 1588-1596 don't include filename.
    Expected: After fix, all BM25 docs have metadata["filename"] populated.
    """
    from app.core.ingestion.document_manager import DocumentManager
    from app.models.db_models import Document, Chunk
    
    # Setup: Create mock database with document containing chunks with filename
    with patch('app.core.ingestion.document_manager.get_db') as mock_get_db:
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db
        
        # Create mock document
        mock_doc = Mock(spec=Document)
        mock_doc.id = 1
        mock_doc.doc_id = "doc-123"
        mock_doc.filename = "peraturan_spbe_2023.pdf"
        mock_doc.original_filename = "peraturan_spbe_2023.pdf"
        
        # Create mock chunks with filename in metadata
        mock_chunk1 = Mock(spec=Chunk)
        mock_chunk1.id = 1
        mock_chunk1.chunk_text = "Pasal 1: Ketentuan Umum"
        mock_chunk1.chunk_metadata = '{"filename": "peraturan_spbe_2023.pdf", "pasal": "1"}'
        
        mock_chunk2 = Mock(spec=Chunk)
        mock_chunk2.id = 2
        mock_chunk2.chunk_text = "Pasal 2: Definisi SPBE"
        mock_chunk2.chunk_metadata = '{"filename": "peraturan_spbe_2023.pdf", "pasal": "2"}'
        
        mock_db.query.return_value.filter.return_value.all.return_value = [mock_chunk1, mock_chunk2]
        
        # Call the method that builds BM25 index
        manager = DocumentManager.__new__(DocumentManager)
        manager._db = mock_db
        
        # This should build BM25 with filename in metadata
        manager._build_bm25_index()
        
        # ASSERTION: Check that BM25 docs have filename in metadata
        assert hasattr(manager, '_bm25_docs'), "BM25 docs should be populated"
        assert len(manager._bm25_docs) >= 2, f"Expected ≥2 BM25 docs, got {len(manager._bm25_docs)}"
        
        for doc in manager._bm25_docs:
            metadata = doc.get("metadata", {})
            # MUST HAVE: filename field populated
            assert "filename" in metadata, (
                f"BM25 metadata missing 'filename' field. "
                f"Metadata keys: {list(metadata.keys())}"
            )
            assert metadata["filename"] != "", (
                f"BM25 metadata 'filename' must not be empty. "
                f"Metadata: {metadata}"
            )
            assert metadata["filename"] == "peraturan_spbe_2023.pdf", (
                f"Expected filename='peraturan_spbe_2023.pdf', "
                f"got '{metadata['filename']}'"
            )


def test_bm25_doc_scoped_filter_uses_filename():
    """
    RED TEST: BM25 doc-scoped filtering must work via filename in metadata.
    
    Regression test for CR-03 fallout: langchain_engine.py line 294.
    
    Currently FAILS because:
    1. Filename not in BM25 metadata (CR-03)
    2. Filter at line 294 tries to match filename but field is always ""
    
    Expected: After CR-03 fix, filtering returns only chunks from target document.
    """
    from app.core.rag.langchain_engine import LangchainRAGEngine
    from langchain_core.documents import Document
    
    # Setup: Mock RAGEngine with populated BM25 docs
    engine = LangchainRAGEngine.__new__(LangchainRAGEngine)
    
    # Create mock BM25 docs from two different documents
    engine._bm25_docs = [
        {
            "text": "Peraturan SPBE: Pasal 1 berbunyi tentang ketentuan umum",
            "metadata": {
                "filename": "peraturan_spbe_2023.pdf",
                "pasal": "1",
                "doc_id": "doc_a_123"
            }
        },
        {
            "text": "Peraturan SPBE: Pasal 2 mendefinisikan SPBE",
            "metadata": {
                "filename": "peraturan_spbe_2023.pdf",
                "pasal": "2",
                "doc_id": "doc_a_123"
            }
        },
        {
            "text": "Laporan Audit: Keamanan siber perlu ditingkatkan",
            "metadata": {
                "filename": "laporan_audit_2024.pdf",
                "doc_id": "doc_b_456"
            }
        },
    ]
    
    # Mock _resolve_doc_target to map doc_id to filename
    def mock_resolve_doc_target(doc_id):
        mapping = {
            "doc_a_123": (1, "peraturan_spbe_2023.pdf"),
            "doc_b_456": (2, "laporan_audit_2024.pdf"),
        }
        return mapping.get(doc_id)
    
    engine._resolve_doc_target = mock_resolve_doc_target
    
    # Call _bm25_search with doc_id constraint
    results = engine._bm25_search(
        query="pasal SPBE",
        top_k=10,
        doc_id="doc_a_123"  # Should return ONLY from peraturan_spbe_2023.pdf
    )
    
    # ASSERTIONS
    assert len(results) > 0, (
        "Expected results from peraturan_spbe_2023.pdf, got 0. "
        "Filename filtering not working (CR-03 symptom)."
    )
    
    for doc in results:
        filename = doc.metadata.get("filename", "")
        assert filename == "peraturan_spbe_2023.pdf", (
            f"Doc-scoped query to doc_a_123 returned chunk from '{filename}'. "
            f"Expected only from 'peraturan_spbe_2023.pdf' (CR-03 issue)."
        )
    
    # Verify we filtered OUT the laporan_audit chunk
    filenames_returned = {doc.metadata.get("filename") for doc in results}
    assert "laporan_audit_2024.pdf" not in filenames_returned, (
        "Doc-scoped query should NOT include chunks from other documents. "
        "Filename filtering broken (CR-03 symptom)."
    )


def test_bm25_table_metadata_not_lost_in_indexing():
    """
    BONUS RED TEST: BM25 should preserve is_table, table_label, table_context.
    
    Related to CR-02 but validates same propagation pipeline as CR-03.
    
    Currently FAILS because document_manager.py doesn't carry table metadata to BM25.
    """
    from app.core.ingestion.document_manager import DocumentManager
    from app.models.db_models import Chunk
    
    # Setup: Mock database with table chunks
    with patch('app.core.ingestion.document_manager.get_db') as mock_get_db:
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db
        
        # Create mock table chunk
        mock_chunk = Mock(spec=Chunk)
        mock_chunk.id = 1
        mock_chunk.chunk_text = "Tabel 5: Domain Evaluasi | Skor"
        mock_chunk.chunk_metadata = '''{
            "filename": "laporan_2024.pdf",
            "is_table": true,
            "table_label": "Tabel 5",
            "table_context": "Hasil evaluasi SPBE tahun 2024",
            "chunk_type": "table"
        }'''
        
        mock_db.query.return_value.filter.return_value.all.return_value = [mock_chunk]
        
        # Build BM25 index
        manager = DocumentManager.__new__(DocumentManager)
        manager._db = mock_db
        manager._build_bm25_index()
        
        # ASSERTIONS: BM25 must have table metadata
        assert len(manager._bm25_docs) >= 1, "BM25 docs should have the chunk"
        
        bm25_doc = manager._bm25_docs[0]
        metadata = bm25_doc.get("metadata", {})
        
        # MUST HAVE: table-related fields
        assert "is_table" in metadata, (
            f"BM25 missing 'is_table' field. "
            f"Available: {list(metadata.keys())}"
        )
        assert metadata["is_table"] is True, (
            f"Expected is_table=True, got {metadata.get('is_table')}"
        )
        assert "table_label" in metadata, "BM25 missing 'table_label' field"
        assert metadata["table_label"] == "Tabel 5", (
            f"Expected table_label='Tabel 5', got '{metadata.get('table_label')}'"
        )
        assert "table_context" in metadata, "BM25 missing 'table_context' field"


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])
