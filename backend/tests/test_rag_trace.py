import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_trace_has_expected_sections(monkeypatch):
    """trace() returns dict with all 7 required sections."""
    import rag_trace

    # Mock engine to avoid boot
    class FakeEngine:
        _initialized = True
        client = None
        def initialize(self): pass
        def _resolve_doc_target(self, d): return (3, "peraturan-bssn-no-8-tahun-2024.pdf") if d == "3" else None
        def _build_doc_filter(self, d): return "FAKE_FILTER" if d else None
        def _vector_search(self, q, top_k, qdrant_filter=None): return []
        def _bm25_search(self, q, top_k, doc_id=None): return []
        def _table_literal_search(self, q, top_k, doc_id=None): return []
        def _run_hybrid_retrieval(self, **kw): return []
        def retrieve_context(self, **kw): return {"context":"", "sources":[], "raw_docs":[], "query_type":"table"}

    monkeypatch.setattr(rag_trace, "_get_engine", lambda: FakeEngine())
    monkeypatch.setattr(rag_trace, "expand_query", lambda q: [q])

    out = rag_trace.trace("apa isi tabel 13?", doc_id="3")
    assert {
        "classify_query",
        "query_profile",
        "expanded_queries",
        "filter_resolution",
        "vector_search",
        "bm25_search",
        "table_literal_search",
        "rerank",
        "retrieval_outcome",
        "pipeline_trace",
        "final_context_and_answer",
    }.issubset(out.keys())
    assert out["classify_query"] == "table"
    assert out["filter_resolution"]["resolved"] == (3, "peraturan-bssn-no-8-tahun-2024.pdf")


def test_trace_uses_public_modular_engine_methods_and_defaults_no_llm(monkeypatch):
    import rag_trace

    class FakeRetriever:
        def vector_search(self, *_args, **_kwargs): return []
        def bm25_search(self, *_args, **_kwargs): return []
        def table_literal_search(self, *_args, **_kwargs): return []

    class FakeEngine:
        _initialized = True
        client = None
        collection_name = "document_chunks"
        _bm25_docs = []
        retriever = FakeRetriever()
        def initialize(self): pass
        def _build_qdrant_filter(self, *_args): return None
        def retrieve_context(self, **_kwargs): return {"context": "", "sources": [], "raw_docs": [], "query_type": "general"}
        def stream_answer(self, **_kwargs): raise AssertionError("LLM must remain disabled by default")

    monkeypatch.setattr(rag_trace, "_get_engine", lambda: FakeEngine())
    out = rag_trace.trace("apa itu SPBE?")
    assert out["final_context_and_answer"]["llm_enabled"] is False


def test_trace_filter_resolution_unknown_doc(monkeypatch):
    import rag_trace

    class FakeEngine:
        _initialized = True
        client = None
        def initialize(self): pass
        def _resolve_doc_target(self, d): return None
        def _build_doc_filter(self, d): return None
        def _vector_search(self, q, top_k, qdrant_filter=None): return []
        def _bm25_search(self, q, top_k, doc_id=None): return []
        def _table_literal_search(self, q, top_k, doc_id=None): return []
        def _run_hybrid_retrieval(self, **kw): return []
        def retrieve_context(self, **kw): return {"context":"","sources":[],"raw_docs":[],"query_type":"general"}

    monkeypatch.setattr(rag_trace, "_get_engine", lambda: FakeEngine())
    monkeypatch.setattr(rag_trace, "expand_query", lambda q: [q])

    out = rag_trace.trace("apa itu X?", doc_id="unknown")
    assert out["filter_resolution"]["resolved"] is None
    assert out["filter_resolution"]["qdrant_hit_count"] is None  # no filter → no hit count


def test_doc_brief_exposes_rrf_and_rerank_contributions():
    import rag_trace

    doc = type(
        "Doc",
        (),
        {
            "metadata": {
                "doc_id": "d1",
                "rrf_score": 0.02,
                "rrf_contributions": [{"family": "vector_original", "weighted_score": 0.02}],
                "rerank_base_score": 0.7,
                "query_boost": 0.1,
                "rerank_score": 0.8,
            }
        },
    )()

    brief = rag_trace._doc_brief(doc)

    assert brief["rrf_score"] == 0.02
    assert brief["rrf_contributions"][0]["family"] == "vector_original"
    assert brief["rerank_base_score"] == 0.7
    assert brief["query_boost"] == 0.1
    assert brief["rerank_score"] == 0.8
