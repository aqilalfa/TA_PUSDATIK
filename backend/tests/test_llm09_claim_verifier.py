"""Unit tests for LLM09 hardening — Tahap G (post-generation verifier).

Covers PRD unit test items 10-11:
    10. jawaban yang mengandung unsupported claim
    11. verifier menghapus unsupported claim
"""

from app.core.rag.claim_verifier import (
    PARTIALLY_SUPPORTED,
    SUPPORTED,
    UNSUPPORTED,
    apply_verifier_edits,
    extract_claims,
    verify_claims,
)

CONTEXT = (
    "[1] Pasal 7 mengatur kompetensi Auditor Keamanan SPBE dan bentuk pembuktiannya.\n"
    "[2] Layanan SPBE adalah keluaran yang dihasilkan oleh satu atau beberapa fungsi aplikasi SPBE."
)
SOURCES = [{"id": 1}, {"id": 2}]


def test_extract_claims_skips_non_claim_and_short_sentences():
    answer = "Maaf, silakan ajukan ulang pertanyaan. Pasal 7 mengatur kompetensi Auditor Keamanan SPBE [1]."
    claims = extract_claims(answer)
    assert len(claims) == 1
    assert "kompetensi" in claims[0]["text"].lower()


def test_supported_claim_is_graded_supported():
    answer = "Pasal 7 mengatur kompetensi Auditor Keamanan SPBE [1]."
    verdicts = verify_claims(answer, CONTEXT, SOURCES)
    assert len(verdicts) == 1
    assert verdicts[0].status == SUPPORTED


def test_unsupported_claim_is_graded_unsupported():
    answer = "Audit SPBE wajib dilakukan setiap bulan dengan denda administratif besar [1]."
    verdicts = verify_claims(answer, CONTEXT, SOURCES)
    assert len(verdicts) == 1
    assert verdicts[0].status == UNSUPPORTED


def test_claim_without_citation_is_unsupported():
    answer = "Audit SPBE wajib dilakukan setiap bulan tanpa pengecualian apapun."
    verdicts = verify_claims(answer, CONTEXT, SOURCES)
    assert len(verdicts) == 1
    assert verdicts[0].status == UNSUPPORTED
    assert "tanpa sitasi" in verdicts[0].reason.lower()


def test_verifier_strips_only_unsupported_sentence_keeps_supported():
    answer = (
        "Pasal 7 mengatur kompetensi Auditor Keamanan SPBE [1]. "
        "Audit SPBE wajib dilakukan setiap bulan dengan sanksi berat [1]."
    )
    verdicts = verify_claims(answer, CONTEXT, SOURCES)
    edited, has_remaining = apply_verifier_edits(answer, verdicts)

    assert has_remaining is True
    assert "kompetensi Auditor Keamanan SPBE" in edited
    assert "setiap bulan dengan sanksi berat" not in edited


def test_verifier_signals_fallback_when_nothing_remains():
    answer = "Audit SPBE wajib dilakukan setiap bulan dengan sanksi berat sekali tanpa dasar [1]."
    verdicts = verify_claims(answer, CONTEXT, SOURCES)
    edited, has_remaining = apply_verifier_edits(answer, verdicts)

    assert has_remaining is False
    assert edited == ""


def test_verifier_does_not_touch_answer_when_all_supported():
    answer = "Pasal 7 mengatur kompetensi Auditor Keamanan SPBE [1]."
    verdicts = verify_claims(answer, CONTEXT, SOURCES)
    edited, has_remaining = apply_verifier_edits(answer, verdicts)

    assert has_remaining is True
    assert edited == answer


def test_invalid_citation_id_marks_claim_unsupported():
    answer = "Klaim aneh dengan sitasi ke sumber yang tidak ada [99]."
    verdicts = verify_claims(answer, CONTEXT, SOURCES)
    assert verdicts[0].status == UNSUPPORTED
