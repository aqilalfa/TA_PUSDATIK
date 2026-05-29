import sys
import os
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest


def test_classify_query_imports():
    from app.core.rag.langchain_engine import classify_query
    assert callable(classify_query)


def test_classify_table_queries():
    from app.core.rag.langchain_engine import classify_query
    assert classify_query("apa isi tabel 13?") == "table"
    assert classify_query("tampilkan tabel 3") == "table"
    assert classify_query("table 5 berisi apa?") == "table"
    assert classify_query("isi dari tabel ke-2") == "table"


def test_classify_pasal_queries():
    from app.core.rag.langchain_engine import classify_query
    assert classify_query("apa isi pasal 5?") == "pasal"
    assert classify_query("ayat 2 berbunyi apa?") == "pasal"
    assert classify_query("perpres nomor 95 mengatur apa?") == "pasal"
    assert classify_query("permenpan rb nomor 5") == "pasal"


def test_classify_general_queries():
    from app.core.rag.langchain_engine import classify_query
    assert classify_query("apa itu SPBE?") == "general"
    assert classify_query("jelaskan domain evaluasi") == "general"
    assert classify_query("siapa yang bertanggung jawab?") == "general"


def test_classify_table_wins_over_pasal():
    from app.core.rag.langchain_engine import classify_query
    assert classify_query("tabel di pasal 5 berisi apa?") == "table"


def test_expand_definition_query_adds_legal_term_anchor():
    from app.core.rag.prompts import expand_query

    queries = expand_query("Apa yang dimaksud dengan Keamanan SPBE menurut Perpres 95 Tahun 2018?")

    assert any("Keamanan SPBE adalah" in q and "pasal 1" in q.lower() for q in queries)


def test_expand_principle_query_adds_pasal_2_anchor():
    from app.core.rag.prompts import expand_query

    queries = expand_query("Apa saja prinsip-prinsip dalam pelaksanaan SPBE?")

    assert any("SPBE dilaksanakan berdasarkan prinsip Pasal 2" in q for q in queries)


def test_expand_maturity_query_adds_table_1_anchor():
    from app.core.rag.prompts import expand_query

    queries = expand_query("Apa yang mendefinisikan SPBE Tingkat 1 (Rintisan)?")

    assert any("Tabel 1" in q and "Rintisan" in q for q in queries)


def test_expand_domain_weight_query_adds_table_7_anchor():
    from app.core.rag.prompts import expand_query

    queries = expand_query("Berapa persentase bobot penilaian untuk Domain Layanan SPBE?")

    assert any("Tabel 7" in q and "Domain Layanan SPBE" in q for q in queries)


def test_expand_predicate_query_adds_table_13_anchor():
    from app.core.rag.prompts import expand_query

    queries = expand_query("Predikat apa yang disematkan pada rentang nilai indeks SPBE 3,5 hingga kurang dari 4,2?")

    assert any("Tabel 13" in q and "predikat indeks SPBE" in q for q in queries)


def test_expand_monitoring_evaluation_purpose_adds_pasal_2_anchor():
    from app.core.rag.prompts import expand_query

    queries = expand_query("Apa tujuan utama dilakukannya Pemantauan dan Evaluasi SPBE?")

    assert any("Pasal 2 Ayat 2" in q and "Pemantauan dan Evaluasi SPBE" in q for q in queries)


def test_expand_pp71_reliability_query_adds_explanation_anchor():
    from app.core.rag.prompts import expand_query

    queries = expand_query('Apa yang dimaksud sistem elektronik yang "andal" secara hukum?')

    assert any("Penjelasan Pasal 3 Ayat 1" in q and "andal" in q for q in queries)


def test_expand_pp71_administrative_sanctions_adds_pasal_100_anchor():
    from app.core.rag.prompts import expand_query

    queries = expand_query("Apa sanksi administratif jika Penyelenggara Sistem Elektronik melakukan pelanggaran?")

    assert any("Pasal 100 Ayat 2" in q and "sanksi administratif" in q for q in queries)


def test_expand_report_2024_lowest_domain_adds_national_index_anchor():
    from app.core.rag.prompts import expand_query

    queries = expand_query("Apa domain yang mencetak skor evaluasi terendah secara nasional pada Laporan 2024?")

    assert any("Laporan Evaluasi SPBE Tahun 2024" in q and "nilai indeks domain nasional" in q for q in queries)


def test_expand_report_2024_highest_local_government_adds_summary_anchor():
    from app.core.rag.prompts import expand_query

    queries = expand_query("Instansi pemerintah daerah mana yang meraih nilai SPBE tertinggi di tahun 2024?")

    assert any("Indeks Maturitas SPBE tertinggi nasional" in q and "Pemerintah Daerah" in q for q in queries)
    assert any("Pemerintah Kabupaten" in q and "Max 4,77" in q for q in queries)
    assert any("Indeks SPBE Akhir 4.77" in q for q in queries)


def test_build_qdrant_filter_with_doc_id():
    from app.core.rag.langchain_engine import LangchainRAGEngine
    engine = LangchainRAGEngine.__new__(LangchainRAGEngine)
    f = engine._build_qdrant_filter("abc-123")
    assert f is not None
    assert len(f.must) == 1
    cond = f.must[0]
    assert cond.key == "doc_id"
    assert cond.match.value == "abc-123"


def test_build_qdrant_filter_unknown_doc_id_still_scopes_directly():
    from app.core.rag.langchain_engine import LangchainRAGEngine
    engine = LangchainRAGEngine.__new__(LangchainRAGEngine)
    f = engine._build_qdrant_filter("unknown-doc")
    assert f is not None
    assert f.must[0].key == "doc_id"
    assert f.must[0].match.value == "unknown-doc"


def test_build_qdrant_filter_without_doc_id():
    from app.core.rag.langchain_engine import LangchainRAGEngine
    engine = LangchainRAGEngine.__new__(LangchainRAGEngine)
    assert engine._build_qdrant_filter(None) is None
    assert engine._build_qdrant_filter("") is None


def test_doc_scoped_retrieval_does_not_fallback(monkeypatch):
    """
    Doc-scoped retrieval must NOT fallback to unscoped search.
    This test should fail before CR-01 fix and pass after.
    """
    import app.core.rag.langchain_engine as le
    from app.core.rag.langchain_engine import LangchainRAGEngine

    engine = LangchainRAGEngine.__new__(LangchainRAGEngine)
    engine._initialized = True
    engine.top_k = 4

    engine.collection_name = "test_collection"
    engine._bm25_docs = []
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

    # Force a qdrant filter to be present
    monkeypatch.setattr(engine, "_build_qdrant_filter", lambda d: object())
    monkeypatch.setattr(le, "expand_query", lambda q: [q])
    monkeypatch.setattr(le, "classify_query", lambda q: "general")

    engine.retrieve_context("apa itu spbe?", doc_id="doc-123")

    filters = [call.args[2] for call in engine.retriever.vector_search.call_args_list]
    assert filters and all(f is not None for f in filters), (
        "First retrieval must be doc-scoped (qdrant_filter present)."
    )
    assert engine.retriever.bm25_search.call_args.args[3] == "doc-123"
