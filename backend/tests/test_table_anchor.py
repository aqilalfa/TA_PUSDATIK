# backend/tests/test_table_anchor.py
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from langchain_core.documents import Document
from app.core.rag.langchain_engine import LangchainRAGEngine


def test_extract_anchors_finds_recurring_phrases():
    """Phrases appearing in ≥2 chunks of the target table should be anchors."""
    engine = LangchainRAGEngine.__new__(LangchainRAGEngine)
    docs = [
        Document(
            page_content="Tabel 5: domain satu nilai bobot 80\naspek teknis memuaskan",
            metadata={"table_label": "Tabel 5"},
        ),
        Document(
            page_content="Tabel 5 lanjutan\ndomain satu aspek teknis nilai 90",
            metadata={"table_label": "Tabel 5"},
        ),
    ]
    anchors = engine._extract_table_anchors(docs, "5", min_hits=2)
    assert isinstance(anchors, list)
    # "domain satu" and "aspek teknis" each appear in 2 chunks
    anchor_blob = " ".join(anchors)
    assert "domain satu" in anchor_blob and "aspek teknis" in anchor_blob


def test_extract_anchors_empty_when_no_table_chunks():
    """No matching table chunks → no anchors extracted."""
    engine = LangchainRAGEngine.__new__(LangchainRAGEngine)
    docs = [
        Document(page_content="ini pasal biasa tidak ada tabel", metadata={}),
    ]
    anchors = engine._extract_table_anchors(docs, "5", min_hits=2)
    assert anchors == []


def test_extract_anchors_empty_doc_list():
    """Empty document list → no anchors extracted."""
    engine = LangchainRAGEngine.__new__(LangchainRAGEngine)
    anchors = engine._extract_table_anchors([], "13", min_hits=2)
    assert anchors == []


def test_extract_anchors_respects_max_anchors():
    """Never return more than max_anchors entries."""
    engine = LangchainRAGEngine.__new__(LangchainRAGEngine)
    content_a = "alpha beta gamma delta epsilon zeta alpha beta gamma delta epsilon zeta"
    content_b = "alpha beta gamma delta epsilon zeta alpha beta gamma delta epsilon zeta"
    docs = [
        Document(page_content=f"Tabel 7\n{content_a}", metadata={"table_label": "Tabel 7"}),
        Document(page_content=f"Tabel 7\n{content_b}", metadata={"table_label": "Tabel 7"}),
    ]
    anchors = engine._extract_table_anchors(docs, "7", min_hits=2, max_anchors=3)
    assert len(anchors) == 3


def test_extract_anchors_empty_table_no():
    """Empty string as table_no → no anchors extracted."""
    engine = LangchainRAGEngine.__new__(LangchainRAGEngine)
    docs = [
        Document(page_content="Tabel 5: domain satu nilai bobot 80", metadata={"table_label": "Tabel 5"}),
    ]
    anchors = engine._extract_table_anchors(docs, "", min_hits=2)
    assert anchors == []


def test_anchor_coverage_counts_present_anchors():
    """Score = number of anchors present in combined docs text."""
    engine = LangchainRAGEngine.__new__(LangchainRAGEngine)
    docs = [
        Document(page_content="domain satu nilai 80 domain dua nilai 90", metadata={}),
    ]
    anchors = ["domain satu", "domain dua", "domain tiga"]
    score = engine._table_anchor_coverage_score(docs, anchors)
    assert score == 2  # domain tiga not present


def test_anchor_coverage_zero_with_no_anchors():
    """Empty anchor list → 0 (no penalty)."""
    engine = LangchainRAGEngine.__new__(LangchainRAGEngine)
    docs = [Document(page_content="anything", metadata={})]
    assert engine._table_anchor_coverage_score(docs, []) == 0


def test_anchor_coverage_zero_with_empty_docs():
    """Empty document list → 0 coverage score."""
    engine = LangchainRAGEngine.__new__(LangchainRAGEngine)
    assert engine._table_anchor_coverage_score([], ["domain satu"]) == 0
