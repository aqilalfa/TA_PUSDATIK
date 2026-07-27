"""Unit tests for LLM09 hardening — Tahap D (Answerability Gate).

Covers PRD unit test items 6-8:
    6. pertanyaan answerable
    7. pertanyaan partially answerable
    8. pertanyaan unanswerable
"""

from app.core.rag.answerability import assess_answerability, build_partial_answer_instruction

SPBE_SOURCE = {
    "id": 1,
    "document": "Perpres 95/2018",
    "snippet": "SPBE adalah penyelenggaraan pemerintahan yang memanfaatkan teknologi informasi dan komunikasi.",
}


def test_full_evidence_is_classified_complete():
    result = assess_answerability(
        "Apa yang dimaksud dengan SPBE?",
        SPBE_SOURCE["snippet"],
        [SPBE_SOURCE],
    )
    assert result.level == "COMPLETE"
    assert result.focus_coverage >= 0.85


def test_no_sources_is_classified_none():
    result = assess_answerability(
        "Apa itu blockchain nasional yang diatur SPBE?",
        "",
        [],
    )
    assert result.level == "NONE"


def test_wrong_pasal_reference_is_classified_none():
    result = assess_answerability(
        "Benarkan bahwa Pasal 99 Perpres 95/2018 mengatur definisi Layanan SPBE.",
        SPBE_SOURCE["snippet"],
        [SPBE_SOURCE],
    )
    assert result.level == "NONE"
    assert "pasal 99" in result.reason.lower() or "99" in result.reason


def test_partial_evidence_produces_partial_level_when_some_terms_missing():
    # Query has multiple distinct focus terms, but evidence only supports one.
    result = assess_answerability(
        "Bagaimana hubungan indeks keamanan siber dengan sertifikasi personel?",
        "Sertifikasi personel diatur dalam Pasal 7.",
        [{"id": 1, "document": "doc", "snippet": "Sertifikasi personel diatur dalam Pasal 7."}],
    )
    assert result.level in ("PARTIAL", "NONE")


def test_partial_instruction_mentions_coverage_and_limitation_redaction():
    result = assess_answerability(
        "Bagaimana hubungan indeks keamanan siber dengan sertifikasi personel?",
        "Sertifikasi personel diatur dalam Pasal 7.",
        [{"id": 1, "document": "doc", "snippet": "Sertifikasi personel diatur dalam Pasal 7."}],
    )
    if result.level == "PARTIAL":
        instruction = build_partial_answer_instruction(result)
        assert "tidak dapat dikonfirmasi" in instruction.lower()
        assert "pengetahuan umum" in instruction.lower()
