"""Confirmation tests for LLM09 hardening — Tahap I (wrong pasal/ayat).

Verifies the existing `_legal_reference_is_supported` guard logic (Tahap A
audit finding: "sudah cukup baik") still fail-closes correctly for wrong
Pasal/Ayat traps through the new Answerability Gate wrapper (Tahap D),
after all other hardening changes landed.
"""

from app.core.rag.answerability import assess_answerability

REAL_PASAL_7_SOURCE = {
    "id": 1,
    "document": "Peraturan BSSN 8/2024",
    "snippet": "Pasal 7 mengatur kompetensi Auditor Keamanan SPBE dan bentuk pembuktiannya.",
}


def test_wrong_pasal_number_is_none_via_gate():
    result = assess_answerability(
        "Benarkan bahwa Pasal 99 mengatur kompetensi Auditor Keamanan SPBE.",
        REAL_PASAL_7_SOURCE["snippet"],
        [REAL_PASAL_7_SOURCE],
    )
    assert result.level == "NONE"
    assert "99" in result.reason


def test_wrong_ayat_number_is_none_via_gate():
    result = assess_answerability(
        "Jelaskan isi Pasal 7 Ayat (99) tentang kompetensi auditor.",
        REAL_PASAL_7_SOURCE["snippet"],
        [REAL_PASAL_7_SOURCE],
    )
    assert result.level == "NONE"
    assert "99" in result.reason


def test_correct_pasal_number_is_allowed_via_gate():
    result = assess_answerability(
        "Apa isi Pasal 7 tentang kompetensi auditor?",
        REAL_PASAL_7_SOURCE["snippet"],
        [REAL_PASAL_7_SOURCE],
    )
    assert result.level in ("COMPLETE", "PARTIAL")
