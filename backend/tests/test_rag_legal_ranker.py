import sys
from pathlib import Path

from langchain_core.documents import Document

sys.path.append(str(Path(__file__).parent.parent))

from app.core.rag.engine.rankers import RAGRanker


def _doc(text: str, *, title: str, section: str = "") -> Document:
    return Document(
        page_content=text,
        metadata={
            "document_title": title,
            "document_short": title,
            "context_header": section,
            "pasal": section,
            "rrf_score": 0.01,
        },
    )


def test_document_boost_prioritizes_named_regulation_number_and_year():
    ranker = RAGRanker()
    perpres_95 = _doc(
        "Keamanan SPBE adalah pengendalian keamanan yang terpadu di dalam pelaksanaan SPBE.",
        title="Perpres Nomor 95 Tahun 2018",
        section="Pasal 1",
    )
    perpres_82 = _doc(
        "SPBE adalah penyelenggaraan pemerintahan yang memanfaatkan teknologi informasi.",
        title="Perpres Nomor 82 Tahun 2023",
        section="Pasal 1",
    )

    ranked = ranker.rerank(
        "Apa yang dimaksud dengan Keamanan SPBE menurut Perpres 95 Tahun 2018?",
        [perpres_82, perpres_95],
        top_k=2,
    )

    assert ranked[0].metadata["document_title"] == "Perpres Nomor 95 Tahun 2018"
    assert ranked[0].metadata["query_boost"] > ranked[1].metadata["query_boost"]


def test_definition_intent_boost_prioritizes_pasal_1_for_apa_yang_dimaksud():
    ranker = RAGRanker()
    definition = _doc(
        "24. Keamanan SPBE adalah pengendalian keamanan yang terpadu di dalam pelaksanaan SPBE.",
        title="Perpres Nomor 95 Tahun 2018",
        section="Pasal 1",
    )
    audit = _doc(
        "Audit keamanan SPBE terdiri atas audit keamanan Infrastruktur SPBE dan audit keamanan Aplikasi.",
        title="Perpres Nomor 95 Tahun 2018",
        section="Pasal 58",
    )

    ranked = ranker.rerank(
        "Apa yang dimaksud dengan Keamanan SPBE menurut Perpres 95 Tahun 2018?",
        [audit, definition],
        top_k=2,
    )

    assert ranked[0].metadata["context_header"] == "Pasal 1"


def test_principle_intent_boost_prioritizes_pasal_2_over_unsur_spbe():
    ranker = RAGRanker()
    principles = _doc(
        "SPBE dilaksanakan berdasarkan prinsip efektivitas, keterpaduan, kesinambungan, efisiensi, akuntabilitas, interoperabilitas, dan keamanan.",
        title="Perpres Nomor 95 Tahun 2018",
        section="Pasal 2",
    )
    elements = _doc(
        "Unsur-unsur SPBE meliputi Rencana Induk, Arsitektur, Peta Rencana, Proses Bisnis, Data, Infrastruktur, Aplikasi, Keamanan, dan Layanan SPBE.",
        title="Perpres Nomor 95 Tahun 2018",
        section="Pasal 4",
    )

    ranked = ranker.rerank(
        "Apa saja prinsip-prinsip dalam pelaksanaan SPBE?",
        [elements, principles],
        top_k=2,
    )

    assert ranked[0].metadata["context_header"] == "Pasal 2"


def test_exact_definition_phrase_boost_beats_same_document_near_miss():
    ranker = RAGRanker()
    exact = _doc(
        "Keamanan SPBE adalah pengendalian keamanan yang terpadu di dalam pelaksanaan SPBE.",
        title="Perpres Nomor 95 Tahun 2018",
        section="Pasal 1",
    )
    near_miss = _doc(
        "Audit keamanan SPBE dilaksanakan berdasarkan standar dan tata cara pelaksanaan audit Keamanan SPBE.",
        title="Perpres Nomor 95 Tahun 2018",
        section="Pasal 58",
    )

    ranked = ranker.rerank(
        "Apa yang dimaksud dengan Keamanan SPBE menurut Perpres 95 Tahun 2018?",
        [near_miss, exact],
        top_k=2,
    )

    assert ranked[0].metadata["context_header"] == "Pasal 1"
    assert ranked[0].metadata["query_boost"] > ranked[1].metadata["query_boost"]
