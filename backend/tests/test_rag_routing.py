import sys
import os
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


def test_build_doc_filter_with_doc_id():
    from app.core.rag.langchain_engine import LangchainRAGEngine
    engine = LangchainRAGEngine.__new__(LangchainRAGEngine)
    f = engine._build_doc_filter("abc-123")
    assert f is not None
    assert len(f.must) == 1


def test_build_doc_filter_without_doc_id():
    from app.core.rag.langchain_engine import LangchainRAGEngine
    engine = LangchainRAGEngine.__new__(LangchainRAGEngine)
    assert engine._build_doc_filter(None) is None
    assert engine._build_doc_filter("") is None
