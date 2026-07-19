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


def test_expand_definition_query_adds_neutral_legal_term_anchor():
    from app.core.rag.prompts import expand_query

    queries = expand_query("Apa yang dimaksud dengan Keamanan SPBE menurut Perpres 95 Tahun 2018?")

    assert queries[0] == "Apa yang dimaksud dengan Keamanan SPBE menurut Perpres 95 Tahun 2018?"
    assert any("Keamanan SPBE adalah" in q for q in queries)
    assert all("pasal 1" not in q.lower() for q in queries)


def test_expand_query_does_not_invent_unstated_legal_or_answer_anchors():
    from app.core.rag.prompts import expand_query

    cases = [
        (
            "Apa tujuan utama dilakukannya Pemantauan dan Evaluasi SPBE?",
            ["permenpan", "pasal 2", "ayat 2"],
        ),
        (
            "Instansi pemerintah daerah mana yang meraih nilai SPBE tertinggi di tahun 2024?",
            ["4,77", "4.77", "predikat memuaskan"],
        ),
    ]

    for query, forbidden_anchors in cases:
        expanded_text = "\n".join(expand_query(query)).lower()
        assert all(anchor not in expanded_text for anchor in forbidden_anchors)


def test_expand_principle_query_does_not_guess_pasal_anchor():
    from app.core.rag.prompts import expand_query

    queries = expand_query("Apa saja prinsip-prinsip dalam pelaksanaan SPBE?")

    assert queries[0] == "Apa saja prinsip-prinsip dalam pelaksanaan SPBE?"
    assert all("pasal 2" not in q.lower() for q in queries)


def test_expand_maturity_query_does_not_guess_table_anchor():
    from app.core.rag.prompts import expand_query

    queries = expand_query("Apa yang mendefinisikan SPBE Tingkat 1 (Rintisan)?")

    assert all("tabel 1" not in q.lower() for q in queries)


def test_expand_domain_weight_query_does_not_guess_table_anchor():
    from app.core.rag.prompts import expand_query

    queries = expand_query("Berapa persentase bobot penilaian untuk Domain Layanan SPBE?")

    assert all("tabel 7" not in q.lower() for q in queries)


def test_expand_predicate_query_does_not_guess_table_anchor():
    from app.core.rag.prompts import expand_query

    queries = expand_query("Predikat apa yang disematkan pada rentang nilai indeks SPBE 3,5 hingga kurang dari 4,2?")

    assert all("tabel 13" not in q.lower() for q in queries)


def test_expand_monitoring_evaluation_purpose_preserves_user_terms_only():
    from app.core.rag.prompts import expand_query

    queries = expand_query("Apa tujuan utama dilakukannya Pemantauan dan Evaluasi SPBE?")

    assert queries[0] == "Apa tujuan utama dilakukannya Pemantauan dan Evaluasi SPBE?"
    assert all("pasal" not in q.lower() and "ayat" not in q.lower() for q in queries)


def test_expand_reliability_query_does_not_guess_regulation_anchor():
    from app.core.rag.prompts import expand_query

    queries = expand_query('Apa yang dimaksud sistem elektronik yang "andal" secara hukum?')

    assert all("pp nomor" not in q.lower() and "pasal" not in q.lower() for q in queries)


def test_expand_administrative_sanctions_does_not_inject_answer_terms():
    from app.core.rag.prompts import expand_query

    queries = expand_query("Apa sanksi administratif jika Penyelenggara Sistem Elektronik melakukan pelanggaran?")

    joined = "\n".join(queries).lower()
    assert "pasal 100" not in joined
    assert "denda administratif" not in joined


def test_expand_report_query_does_not_guess_table_or_domain_answer():
    from app.core.rag.prompts import expand_query

    queries = expand_query("Apa domain yang mencetak skor evaluasi terendah secara nasional pada Laporan 2024?")

    joined = "\n".join(queries).lower()
    assert "tabel 5" not in joined
    assert "domain manajemen" not in joined


def test_expand_report_query_does_not_inject_winning_entity_or_value():
    from app.core.rag.prompts import expand_query

    queries = expand_query("Instansi pemerintah daerah mana yang meraih nilai SPBE tertinggi di tahun 2024?")

    joined = "\n".join(queries).lower()
    assert "pemerintah kabupaten" not in joined
    assert "4,77" not in joined
    assert "4.77" not in joined


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
    monkeypatch.setattr(engine, "_build_qdrant_filter", lambda d, current_user=None: object())
    monkeypatch.setattr(le, "expand_query", lambda q: [q])
    monkeypatch.setattr(le, "classify_query", lambda q: "general")

    engine.retrieve_context("apa itu spbe?", doc_id="doc-123")

    filters = [call.args[2] for call in engine.retriever.vector_search.call_args_list]
    assert filters and all(f is not None for f in filters), (
        "First retrieval must be doc-scoped (qdrant_filter present)."
    )
    assert engine.retriever.bm25_search.call_args.args[3] == "doc-123"
