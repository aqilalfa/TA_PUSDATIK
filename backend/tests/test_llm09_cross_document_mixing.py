"""Unit tests for LLM09 hardening — Tahap H (cross-document mixing).

Covers PRD unit test item 9:
    9. cross-document mixing
"""

from app.core.rag.claim_verifier import UNSUPPORTED, verify_claims

CONTEXT = (
    "[1] Layanan SPBE adalah keluaran yang dihasilkan oleh satu atau beberapa fungsi aplikasi SPBE.\n"
    "[2] Sanksi administratif dikenakan berupa teguran tertulis hingga pemutusan akses."
)

SOURCES_DIFFERENT_DOCS = [
    {"id": 1, "document": "Perpres 95 Tahun 2018"},
    {"id": 2, "document": "PP 71 Tahun 2019"},
]

SOURCES_SAME_DOC = [
    {"id": 1, "document": "Perpres 95 Tahun 2018"},
    {"id": 2, "document": "Perpres 95 Tahun 2018"},
]


def test_claim_unifying_two_different_documents_is_unsupported():
    answer = (
        "Definisi Layanan SPBE dan sanksi administratif diatur dalam pasal yang sama [1][2]."
    )
    verdicts = verify_claims(answer, CONTEXT, SOURCES_DIFFERENT_DOCS)
    assert len(verdicts) == 1
    assert verdicts[0].status == UNSUPPORTED
    assert "dokumen berbeda" in verdicts[0].reason.lower()


def test_claim_citing_two_sources_from_same_document_is_not_flagged_as_mixing():
    answer = "Layanan SPBE dan sanksi administratif dijelaskan dalam dokumen ini [1][2]."
    verdicts = verify_claims(answer, CONTEXT, SOURCES_SAME_DOC)
    assert len(verdicts) == 1
    assert verdicts[0].status != UNSUPPORTED or "dokumen berbeda" not in verdicts[0].reason.lower()


def test_claim_with_single_citation_is_never_flagged_as_mixing():
    answer = "Layanan SPBE adalah keluaran yang dihasilkan oleh satu atau beberapa fungsi aplikasi SPBE [1]."
    verdicts = verify_claims(answer, CONTEXT, SOURCES_DIFFERENT_DOCS)
    assert len(verdicts) == 1
    assert "dokumen berbeda" not in verdicts[0].reason.lower()
