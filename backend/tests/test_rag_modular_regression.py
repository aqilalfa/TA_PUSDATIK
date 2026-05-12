"""
TDD Regression Tests — RAG Modularization Bugs
Covers:
  Bug #1 — context_stitching.py uses wrong 'payload.doc_id' Qdrant key
  Bug #2 — langchain_engine.py does not pass doc_id filter to vector_search
  Bug #3 — num_ctx=4096 truncates context silently

Run with:
    cd backend && python -m pytest tests/test_rag_modular_regression.py -v
"""
import types
from unittest.mock import MagicMock, patch, call
from typing import List

import pytest
from langchain_core.documents import Document
from qdrant_client.models import FieldCondition, Filter, MatchAny, MatchValue


# ============================================================================
# Helpers
# ============================================================================

def _make_point(doc_id: str, chunk_index: int, text: str = "sample text"):
    """Build a mock Qdrant ScoredPoint with flat payload (no nesting)."""
    p = MagicMock()
    p.id = f"{doc_id}_{chunk_index}"
    # Flat payload — matching real Qdrant structure confirmed by retrievers.py
    p.payload = {
        "doc_id": doc_id,
        "chunk_index": chunk_index,
        "text": text,
        "hierarchy": f"Indikator {chunk_index}:",
    }
    return p


# ============================================================================
# Bug #1 — ContextStitcher: Qdrant filter uses wrong 'payload.doc_id' key
# ============================================================================

class TestContextStitcherNeighborFetch:
    """
    Bug: fetch_neighbor_documents builds Filter with 'payload.doc_id' and
    'payload.chunk_index' — keys that don't exist in Qdrant flat payload.
    Result: scroll() receives a valid-looking filter that matches nothing,
    so neighbor fetch always returns [].
    Fix: keys must be 'doc_id' and 'chunk_index' (top-level, no prefix).
    """

    def _get_stitcher(self):
        from app.core.rag.engine.context_stitching import ContextStitcher
        client = MagicMock()
        return ContextStitcher(client), client

    def test_neighbor_fetch_uses_flat_doc_id_key(self):
        """scroll() filter must use key='doc_id', NOT 'payload.doc_id'."""
        stitcher, mock_client = self._get_stitcher()
        mock_client.scroll.return_value = ([], None)

        centers = {"doc-1": {3}}
        stitcher.fetch_neighbor_documents(centers, "test_collection")

        assert mock_client.scroll.called, "scroll() should have been called"
        call_kwargs = mock_client.scroll.call_args
        flt: Filter = call_kwargs.kwargs.get("scroll_filter") or call_kwargs.args[1] if call_kwargs.args else None
        if flt is None and call_kwargs.kwargs:
            flt = call_kwargs.kwargs.get("scroll_filter")

        assert flt is not None, "scroll_filter must be provided"
        keys_used = [c.key for c in flt.must if hasattr(c, "key")]
        assert "doc_id" in keys_used, (
            f"Filter must use key='doc_id', got keys: {keys_used}. "
            "Bug: code uses 'payload.doc_id' which never matches Qdrant flat payload."
        )
        assert "payload.doc_id" not in keys_used, (
            "Filter must NOT use 'payload.doc_id' — this is the bug!"
        )

    def test_neighbor_fetch_uses_flat_chunk_index_key(self):
        """scroll() filter must use key='chunk_index', NOT 'payload.chunk_index'."""
        stitcher, mock_client = self._get_stitcher()
        mock_client.scroll.return_value = ([], None)

        centers = {"doc-1": {3}}
        stitcher.fetch_neighbor_documents(centers, "test_collection")

        call_kwargs = mock_client.scroll.call_args
        flt: Filter = call_kwargs.kwargs.get("scroll_filter")
        if flt is None:
            flt = call_kwargs.args[1] if call_kwargs.args else None

        assert flt is not None
        keys_used = [c.key for c in flt.must if hasattr(c, "key")]
        assert "chunk_index" in keys_used, (
            f"Filter must use key='chunk_index', got: {keys_used}"
        )
        assert "payload.chunk_index" not in keys_used, (
            "Filter must NOT use 'payload.chunk_index' — this is the bug!"
        )

    def test_neighbor_fetch_returns_docs_when_points_exist(self):
        """When Qdrant returns points, fetch_neighbor_documents must return Documents."""
        stitcher, mock_client = self._get_stitcher()

        prev_chunk = _make_point("doc-1", 2, "chunk before center")
        next_chunk = _make_point("doc-1", 4, "chunk after center")
        mock_client.scroll.return_value = ([prev_chunk, next_chunk], None)

        centers = {"doc-1": {3}}
        docs = stitcher.fetch_neighbor_documents(centers, "test_collection")

        assert len(docs) == 2, (
            f"Expected 2 neighbor docs, got {len(docs)}. "
            "If 0, the Qdrant filter key bug is still present."
        )

    def test_neighbor_payload_not_double_nested(self):
        """
        Bug variant: code did p.payload.get('payload', {}) which silently
        extracts an inner dict that doesn't exist — doc_id becomes ''.
        Fix: always use p.payload directly (flat).
        """
        stitcher, mock_client = self._get_stitcher()

        pt = _make_point("doc-99", 2, "neighbor text")
        mock_client.scroll.return_value = ([pt], None)

        centers = {"doc-99": {3}}
        docs = stitcher.fetch_neighbor_documents(centers, "test_collection")

        assert len(docs) > 0, "Should have returned at least one neighbor"
        assert docs[0].metadata.get("doc_id") == "doc-99", (
            f"doc_id must be 'doc-99' from flat payload, got: {docs[0].metadata.get('doc_id')}. "
            "If empty/None, the double-nesting bug is still present."
        )


# ============================================================================
# Bug #2 — langchain_engine: doc_id NOT propagated to vector_search
# ============================================================================

class TestLangchainEngineDocIdFilter:
    """
    Bug: retrieve_context() calls vector_search(sq, k) without passing
    the doc_id filter. Only BM25 is scoped — vector search leaks docs
    from the whole Qdrant collection into the RRF pool.
    Fix: build a Qdrant Filter from doc_id and pass it to vector_search().
    """

    def _build_engine(self):
        """Build a partially mocked LangchainRAGEngine."""
        from app.core.rag.langchain_engine import LangchainRAGEngine
        engine = LangchainRAGEngine.__new__(LangchainRAGEngine)
        engine._initialized = True
        engine.collection_name = "test_collection"
        engine._bm25_docs = []

        # Mock sub-components
        engine.retriever = MagicMock()
        engine.retriever.vector_search.return_value = []
        engine.retriever.bm25_search.return_value = []
        engine.retriever.table_literal_search.return_value = []
        engine.retriever.indicator_literal_search.return_value = []

        engine.ranker = MagicMock()
        engine.ranker.rrf_fusion.return_value = []
        engine.ranker.rerank.return_value = []

        engine.stitcher = MagicMock()
        engine.stitcher.expand_docs_with_neighbor_context.return_value = []

        return engine

    def test_vector_search_called_with_qdrant_filter_when_doc_id_given(self):
        """When doc_id is provided, vector_search must receive a non-None filter."""
        engine = self._build_engine()

        with patch("app.core.rag.langchain_engine.expand_query", return_value=["test query"]):
            engine.retrieve_context("test query", top_k=5, doc_id="42")

        assert engine.retriever.vector_search.called
        # Inspect all calls — at least one must have a non-None third argument (qdrant_filter)
        calls = engine.retriever.vector_search.call_args_list
        filters_passed = [c.args[2] if len(c.args) > 2 else c.kwargs.get("qdrant_filter") for c in calls]
        assert any(f is not None for f in filters_passed), (
            "vector_search() must receive a non-None qdrant_filter when doc_id='42'. "
            f"Actual filters passed: {filters_passed}. "
            "This is Bug #2 — doc_id scope not propagated to vector search."
        )

    def test_vector_search_called_without_filter_when_no_doc_id(self):
        """When doc_id is None, vector_search may pass None filter (global search)."""
        engine = self._build_engine()

        with patch("app.core.rag.langchain_engine.expand_query", return_value=["test query"]):
            engine.retrieve_context("test query", top_k=5, doc_id=None)

        assert engine.retriever.vector_search.called, "vector_search should always be called"

    def test_build_qdrant_filter_returns_none_for_no_doc_id(self):
        """_build_qdrant_filter(None) must return None (no filter = global search)."""
        from app.core.rag.langchain_engine import LangchainRAGEngine
        engine = LangchainRAGEngine.__new__(LangchainRAGEngine)
        result = engine._build_qdrant_filter(None)
        assert result is None

    def test_build_qdrant_filter_returns_filter_for_doc_id(self):
        """_build_qdrant_filter('42') must return a Qdrant Filter object."""
        from app.core.rag.langchain_engine import LangchainRAGEngine
        engine = LangchainRAGEngine.__new__(LangchainRAGEngine)
        flt = engine._build_qdrant_filter("42")
        assert flt is not None, "_build_qdrant_filter should return a Filter"
        assert isinstance(flt, Filter), f"Expected Filter, got {type(flt)}"
        # Filter must target 'doc_id' field with value '42'
        assert any(
            hasattr(c, "key") and c.key == "doc_id"
            for c in (flt.must or [])
        ), f"Filter.must should contain a condition on 'doc_id', got: {flt.must}"

# ============================================================================
# Bug #3 — llm_client.py: num_ctx=4096 silently truncates context
# ============================================================================

class TestLLMClientNumCtx:
    """
    Bug: num_ctx is hardcoded to 4096.
    5 docs × ~800 chars + system prompt + history ≈ 3000+ tokens → overflow.
    Fix: raise to at least 8192.
    """

    def test_num_ctx_is_at_least_8192(self):
        """
        We inspect the hardcoded options dict by parsing the module source.
        The num_ctx value must be >= 8192 after the fix.
        """
        import ast
        import inspect
        import app.core.rag.engine.llm_client as llm_module

        # Parse the stream_answer function source to extract the options dict
        source = inspect.getsource(llm_module.stream_answer)
        tree = ast.parse(source)

        num_ctx_value = None
        for node in ast.walk(tree):
            # Look for: "num_ctx": <number>  inside any dict
            if isinstance(node, ast.Dict):
                for key, value in zip(node.keys, node.values):
                    if (
                        isinstance(key, ast.Constant)
                        and key.value == "num_ctx"
                        and isinstance(value, ast.Constant)
                    ):
                        num_ctx_value = value.value

        assert num_ctx_value is not None, (
            "Could not find 'num_ctx' key in stream_answer options dict. "
            "It must be explicitly set."
        )
        assert num_ctx_value >= 8192, (
            f"num_ctx={num_ctx_value} is too small — silently truncates context. "
            "5 docs × 800 chars + system prompt + 4 history turns ≈ 3000+ tokens. "
            "Must be >= 8192 to avoid silent truncation. This is Bug #3."
        )

    def test_ollama_model_name_uses_qwen3(self):
        """
        The default/active model in the app must target qwen3:4b (as requested).
        This test documents the expected model name change.
        """
        # This verifies the model setting used in llm_client routing
        # The actual model name comes from the active model config file
        # We verify the LLM client correctly detects qwen3 as a thinking model
        import app.core.rag.engine.llm_client as llm_module
        import inspect

        source = inspect.getsource(llm_module.stream_answer)
        # qwen3 should be detected as a thinking model (with think=False option)
        assert "qwen3" in source.lower(), (
            "llm_client.py should include 'qwen3' in the thinking model detection list. "
            "Required for Qwen3:4b model support."
        )
