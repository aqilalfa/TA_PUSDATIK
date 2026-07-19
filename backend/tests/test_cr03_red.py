"""
TDD RED Phase Test for CR-03: BM25 Metadata Missing Filename

Simple direct test: Inspect _rebuild_bm25_index() source code to verify
that filename field is included in metadata dict being built.

This test will FAIL if filename is not present in the metadata dict at line ~1596.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import inspect


def test_cr03_filename_present_in_rebuild_bm25_index_source():
    """
    RED TEST: Verify that _rebuild_bm25_index builds BM25 metadata with 'filename' field.
    
    Current status: FAILS because source code at document_manager.py:1588-1596 
    does NOT include "filename" in the metadata dict.
    
    This test reads the source code of _rebuild_bm25_index and checks that
    the metadata dict construction includes "filename" key.
    """
    from app.core.ingestion.document_manager import DocumentManager
    
    # Get source code of _rebuild_bm25_index method
    source = inspect.getsource(DocumentManager._rebuild_bm25_index)
    
    # The metadata dict construction should include "filename"
    # Currently it looks like:
    # metadata": {
    #     "document_title": doc.get("document_title", ""),
    #     "context_header": chunk.get("context_header", ""),
    #     ... OTHER FIELDS ...
    #     # MISSING: "filename": chunk.get("filename", ""),
    # }
    
    # RED TEST ASSERTION: Check that metadata dict construction includes filename
    assert '"filename"' in source or "'filename'" in source, (
        "CR-03 NOT FIXED: _rebuild_bm25_index() source does not build "
        "'filename' field in metadata dict. "
        "This causes BM25 queries to not have filename for filtering (see langchain_engine.py:294)"
    )
    
    # Also verify it's being set from chunk data (not hardcoded)
    assert 'chunk.get("filename"' in source or "chunk['filename']" in source, (
        "CR-03 NOT FIXED: 'filename' field is not being read from chunk metadata. "
        "Must use: 'filename': chunk.get('filename', '')"
    )


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
