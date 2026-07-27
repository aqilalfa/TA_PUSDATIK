"""Unit tests for LLM09 hardening — Tahap C (table completeness).

Covers PRD unit test item 4:
    4. retrieval tabel tidak lengkap
"""

from app.core.rag.llm09_guard import assess_llm09_pre_generation_guard

FULL_TABLE_SOURCE = {
    "id": 1,
    "document": "Pedoman Nomor 3 Tahun 2024",
    "snippet": "Tabel 1. Indeks SPBE Nasional: 2021: 2,24; 2022: 2,34; 2023: 2,79.",
    "is_table": True,
    "table_label": "Tabel 1",
    "chunk_part": None,
    "chunk_parts_total": None,
}

PARTIAL_TABLE_SOURCE = {
    "id": 1,
    "document": "Pedoman Nomor 3 Tahun 2024",
    "snippet": "Tabel 1. Indeks SPBE Nasional: 2021: 2,24.",
    "is_table": True,
    "table_label": "Tabel 1",
    "chunk_part": 1,
    "chunk_parts_total": 3,
}


def test_split_table_chunk_blocks_aggregation_query():
    result = assess_llm09_pre_generation_guard(
        "Hitung rata-rata indeks SPBE nasional dari tabel tersebut.",
        PARTIAL_TABLE_SOURCE["snippet"],
        [PARTIAL_TABLE_SOURCE],
    )
    assert result.allowed is False
    assert result.risk_category == "aggregation_completeness"


def test_complete_table_chunk_allows_aggregation_query():
    result = assess_llm09_pre_generation_guard(
        "Hitung rata-rata indeks SPBE nasional secara agregat dari tabel tersebut.",
        "Tabel 1. Indeks SPBE Nasional: 2021: 2,24; 2022: 2,34; 2023: 2,79 rata-rata agregat.",
        [FULL_TABLE_SOURCE],
    )
    assert result.allowed is True


def test_non_table_source_is_unaffected_by_table_check():
    result = assess_llm09_pre_generation_guard(
        "Apa yang dimaksud dengan SPBE?",
        "SPBE adalah penyelenggaraan pemerintahan yang memanfaatkan teknologi informasi.",
        [{"id": 1, "document": "doc", "snippet": "SPBE adalah penyelenggaraan pemerintahan."}],
    )
    assert result.allowed is True
