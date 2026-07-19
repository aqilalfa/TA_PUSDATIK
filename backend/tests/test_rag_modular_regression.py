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
        keys_used = []
        for cond in (flt.should or []):
            if hasattr(cond, "must") and cond.must:
                keys_used.extend([c.key for c in cond.must if hasattr(c, "key")])
            elif hasattr(cond, "key"):
                keys_used.append(cond.key)
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
        keys_used = []
        for cond in (flt.should or []):
            if hasattr(cond, "must") and cond.must:
                keys_used.extend([c.key for c in cond.must if hasattr(c, "key")])
            elif hasattr(cond, "key"):
                keys_used.append(cond.key)
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

    def test_retrieve_context_uses_broader_candidate_pool_before_final_rerank(self):
        """Legal reranking needs more candidates than the final top_k sent to the LLM."""
        engine = self._build_engine()

        with patch("app.core.rag.langchain_engine.expand_query", return_value=["test query"]):
            engine.retrieve_context("test query", top_k=5, doc_id=None)

        vector_call = engine.retriever.vector_search.call_args_list[0]
        bm25_call = engine.retriever.bm25_search.call_args_list[0]
        rrf_call = engine.ranker.rrf_fusion.call_args
        rerank_call = engine.ranker.rerank.call_args

        assert vector_call.args[1] == 15
        assert bm25_call.args[1] == 30
        assert rrf_call.kwargs["max_candidates"] >= 100
        assert rerank_call.args[2] == 5

    def test_retrieve_context_passes_profile_and_traces_adaptive_candidate_stats(self):
        from app.core.rag.observability import RagTrace

        engine = self._build_engine()
        reranked = Document(
            page_content="Pasal 4",
            metadata={
                "doc_id": "doc-1",
                "rerank_score": 0.9,
                "rerank_candidate_limit": 32,
                "rerank_candidate_count": 32,
                "rerank_candidate_policy": "adaptive-specialized",
            },
        )
        engine.ranker.rrf_fusion.return_value = [reranked]
        engine.stitcher.expand_docs_with_neighbor_context.return_value = [reranked]
        engine.ranker.rerank.return_value = [reranked]
        trace = RagTrace.create(session_id="test", user_id=1, query="Apa isi Pasal 4?")

        with patch("app.core.rag.langchain_engine.expand_query", return_value=["Apa isi Pasal 4?"]):
            engine.retrieve_context("Apa isi Pasal 4?", top_k=5, trace=trace)

        assert engine.ranker.rerank.call_args.kwargs["retrieval_type"] == "pasal"
        rerank_stage = next(
            stage for stage in trace.snapshot()["stages"] if stage["stage"] == "rerank.completed"
        )
        assert rerank_stage["candidate_limit"] == 32
        assert rerank_stage["candidate_count"] == 32
        assert rerank_stage["candidate_policy"] == "adaptive-specialized"

    def test_retrieve_context_supports_explicit_candidate_limit_for_ablation(self):
        engine = self._build_engine()

        with patch("app.core.rag.langchain_engine.expand_query", return_value=["test query"]):
            engine.retrieve_context(
                "test query",
                top_k=5,
                rerank_candidate_limit_override=64,
            )

        assert engine.ranker.rerank.call_args.kwargs["candidate_limit_override"] == 64

    def test_retrieve_context_uses_expanded_queries_for_bm25(self):
        """BM25 should receive legal-anchor expanded queries, not only the original query."""
        engine = self._build_engine()

        with patch("app.core.rag.langchain_engine.expand_query", return_value=["original", "legal anchor"]):
            engine.retrieve_context("original", top_k=5, doc_id=None)

        bm25_queries = [call.args[0] for call in engine.retriever.bm25_search.call_args_list]
        assert bm25_queries == ["original", "legal anchor"]

    def test_retrieve_context_uses_expanded_queries_for_literal_searches(self):
        """Implicit table anchors should reach literal table search, not just vector/BM25."""
        engine = self._build_engine()

        with patch("app.core.rag.langchain_engine.expand_query", return_value=["original", "Tabel 13 anchor"]):
            engine.retrieve_context("original", top_k=5, doc_id=None)

        table_queries = [call.args[0] for call in engine.retriever.table_literal_search.call_args_list]
        indicator_queries = [call.args[0] for call in engine.retriever.indicator_literal_search.call_args_list]

        assert table_queries == ["original", "Tabel 13 anchor"]
        assert indicator_queries == ["original", "Tabel 13 anchor"]

    def test_vector_only_mode_skips_non_vector_pipeline_stages(self):
        """Vector-only baseline must not use expansion, BM25, literal search, RRF, stitching, or rerank."""
        engine = self._build_engine()
        engine.retriever.vector_search.return_value = [Document(page_content="v", metadata={})]

        with patch("app.core.rag.langchain_engine.expand_query") as expand:
            result = engine.retrieve_context("original", top_k=5, retrieval_mode="vector_only")

        expand.assert_not_called()
        engine.retriever.vector_search.assert_called_once()
        engine.retriever.bm25_search.assert_not_called()
        engine.retriever.table_literal_search.assert_not_called()
        engine.retriever.indicator_literal_search.assert_not_called()
        engine.ranker.rrf_fusion.assert_not_called()
        engine.ranker.rerank.assert_not_called()
        engine.stitcher.expand_docs_with_neighbor_context.assert_not_called()
        assert result["retrieval_mode"] == "vector_only"

    def test_bm25_only_mode_skips_vector_and_hybrid_pipeline_stages(self):
        """BM25-only baseline must not use vector, literal search, RRF, stitching, or rerank."""
        engine = self._build_engine()
        engine.retriever.bm25_search.return_value = [Document(page_content="b", metadata={})]

        with patch("app.core.rag.langchain_engine.expand_query") as expand:
            result = engine.retrieve_context("original", top_k=5, retrieval_mode="bm25_only")

        expand.assert_not_called()
        engine.retriever.vector_search.assert_not_called()
        engine.retriever.bm25_search.assert_called_once()
        engine.retriever.table_literal_search.assert_not_called()
        engine.retriever.indicator_literal_search.assert_not_called()
        engine.ranker.rrf_fusion.assert_not_called()
        engine.ranker.rerank.assert_not_called()
        engine.stitcher.expand_docs_with_neighbor_context.assert_not_called()
        assert result["retrieval_mode"] == "bm25_only"

    def test_hybrid_mode_uses_rrf_without_expansion_stitching_or_rerank(self):
        """Hybrid baseline uses vector+BM25+literal+RRF only, then takes Top-5."""
        engine = self._build_engine()
        fused_docs = [Document(page_content=str(i), metadata={}) for i in range(6)]
        engine.ranker.rrf_fusion.return_value = fused_docs

        with patch("app.core.rag.langchain_engine.expand_query") as expand:
            result = engine.retrieve_context("original", top_k=5, retrieval_mode="hybrid")

        expand.assert_not_called()
        engine.retriever.vector_search.assert_called_once()
        engine.retriever.bm25_search.assert_called_once()
        engine.retriever.table_literal_search.assert_called_once()
        engine.retriever.indicator_literal_search.assert_called_once()
        engine.ranker.rrf_fusion.assert_called_once()
        engine.ranker.rerank.assert_not_called()
        engine.stitcher.expand_docs_with_neighbor_context.assert_not_called()
        assert result["retrieval_mode"] == "hybrid"
        assert len(result["raw_docs"]) == 5

    def test_final_mode_keeps_expansion_stitching_and_rerank(self):
        """Final config keeps query expansion, RRF, context stitching, and metadata reranking."""
        engine = self._build_engine()

        with patch("app.core.rag.langchain_engine.expand_query", return_value=["original", "expanded"]):
            result = engine.retrieve_context("original", top_k=5, retrieval_mode="final")

        assert engine.retriever.vector_search.call_count == 2
        assert engine.retriever.bm25_search.call_count == 2
        assert engine.retriever.table_literal_search.call_count == 2
        assert engine.retriever.indicator_literal_search.call_count == 2
        engine.ranker.rrf_fusion.assert_called_once()
        engine.stitcher.expand_docs_with_neighbor_context.assert_called_once()
        engine.ranker.rerank.assert_called_once()
        assert result["retrieval_mode"] == "final"

    def test_retrieval_outcome_is_ok_empty_when_all_searches_succeed_without_hits(self):
        engine = self._build_engine()

        with patch("app.core.rag.langchain_engine.expand_query", return_value=["original"]):
            result = engine.retrieve_context("original", top_k=5)

        assert result["retrieval_status"] == "ok-empty"
        assert result["failed_retrievers"] == []

    def test_retrieval_outcome_is_partial_when_one_search_family_fails(self):
        engine = self._build_engine()
        engine.retriever.vector_search.side_effect = RuntimeError("vector unavailable")

        with patch("app.core.rag.langchain_engine.expand_query", return_value=["original"]):
            result = engine.retrieve_context("original", top_k=5)

        assert result["retrieval_status"] == "partial"
        assert result["failed_retrievers"] == ["vector"]

    def test_retrieval_outcome_is_failed_when_every_search_family_fails(self):
        engine = self._build_engine()
        engine.retriever.vector_search.side_effect = RuntimeError("vector unavailable")
        engine.retriever.bm25_search.side_effect = RuntimeError("bm25 unavailable")
        engine.retriever.table_literal_search.side_effect = RuntimeError("literal unavailable")
        engine.retriever.indicator_literal_search.side_effect = RuntimeError("literal unavailable")

        with patch("app.core.rag.langchain_engine.expand_query", return_value=["original"]):
            result = engine.retrieve_context("original", top_k=5)

        assert result["retrieval_status"] == "failed"
        assert set(result["failed_retrievers"]) == {"vector", "bm25", "table_literal", "indicator_literal"}

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
        from app.core.rag.engine.llm_client import build_ollama_options

        options = build_ollama_options()

        assert options["num_ctx"] >= 8192

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
