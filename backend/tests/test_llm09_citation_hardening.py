"""Unit tests for LLM09 hardening — Tahap F (citation validation).

Covers PRD unit test items 1-3:
    1. sitasi valid
    2. sitasi di luar jumlah sumber
    3. marker `[n]`
"""

from app.core.formatting import (
    extract_citation_ids,
    strip_invalid_citation_markers,
    validate_citation_ids,
)


def test_valid_citation_passes_validation():
    answer = "Pasal 7 mengatur kompetensi Auditor Keamanan SPBE [1]."
    errors = validate_citation_ids(answer, source_count=2)
    assert errors == []


def test_citation_beyond_source_count_is_flagged():
    answer = "Klaim ini bersumber pada [5], padahal hanya ada 2 sumber."
    errors = validate_citation_ids(answer, source_count=2)
    assert any("berada di luar jumlah sumber" in e for e in errors)


def test_literal_n_marker_is_flagged_and_stripped():
    answer = "Pasal 7 mengatur kompetensi Auditor Keamanan SPBE [n]."
    errors = validate_citation_ids(answer, source_count=2)
    assert any("tidak valid" in e for e in errors)

    cleaned = strip_invalid_citation_markers(answer)
    assert "[n]" not in cleaned
    assert "[N]" not in cleaned


def test_placeholder_markers_variants_are_stripped():
    for marker in ["[?]", "[source]", "[citation needed]", "[ref]"]:
        answer = f"Klaim tanpa sumber jelas {marker}."
        cleaned = strip_invalid_citation_markers(answer)
        assert marker.lower() not in cleaned.lower()


def test_extract_citation_ids_preserves_all_occurrences():
    answer = "Klaim A [1]. Klaim B [1][2]."
    ids = extract_citation_ids(answer)
    assert ids == [1, 1, 2]


def test_citation_id_below_one_is_flagged():
    answer = "Klaim aneh [0]."
    errors = validate_citation_ids(answer, source_count=3)
    assert any("nomor harus >= 1" in e for e in errors)


def test_valid_multiple_citations_pass():
    answer = "Klaim A [1]. Klaim B [2][3]."
    errors = validate_citation_ids(answer, source_count=3)
    assert errors == []
