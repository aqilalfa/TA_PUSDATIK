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
    assert set(out.keys()) == {
        "classify_query",
        "filter_resolution",
        "vector_search",
        "bm25_search",
        "table_literal_search",
        "rerank",
        "final_context_and_answer",
    }
    assert out["classify_query"] == "table"
    assert out["filter_resolution"]["resolved"] == (3, "peraturan-bssn-no-8-tahun-2024.pdf")


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
