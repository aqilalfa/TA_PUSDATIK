"""Regression tests for LLM09 guardrail review fixes (2026-07 audit).

Each test pins one confirmed defect from the multi-agent LLM09 logic review:

    K1  - claim graders must map renumbered citation ids back to the original
          context block ids (and fall back to source snippets) instead of
          grading claims against the wrong source block.
    M5  - renumber_citations_and_sources must preserve the retrieval-layer
          original_id across repeated passes.
    K2  - named-regulation Pasal scoping must match production document titles
          ('Peraturan Presiden 95 Tahun 2018'), not only '95/2018' strings.
    H1  - the mandated PARTIAL-answer disclosure sentence must survive the
          post-generation claim verifier.
    H2  - ayat existence checks must be scoped to the named pasal, not pooled
          across every retrieved chunk.
    H3  - split-table detection must only block aggregation when sibling parts
          are actually missing from retrieval.
    H5  - numeric values in claims must participate in grounding; a wrong
          number must not be graded SUPPORTED.
    H6  - hallucinated-ayat cleanup must strip only the flagged ayat numbers,
          leaving supported references and the reference block intact.
    H7  - comparison guard must not require the comparison trigger word itself
          in evidence and must reuse acronym-expansion matching.
    H4  - apply_verifier_edits must preserve newline/list formatting.
"""

import re

from app.core.formatting import (
    renumber_citations_and_sources,
    strip_flagged_ayat_references,
)
from app.core.rag.claim_verifier import (
    PARTIALLY_SUPPORTED,
    SUPPORTED,
    UNSUPPORTED,
    apply_verifier_edits,
    verify_claims,
)
from app.core.rag.llm09_guard import assess_llm09_pre_generation_guard
from app.core.rag.prompts import validate_answer


# ---------------------------------------------------------------------------
# K1 — renumbered citation ids vs original context block ids
# ---------------------------------------------------------------------------

RENUMBERED_CONTEXT = (
    "[1] Perlindungan data pribadi diatur bagi pengendali dan pemroses data elektronik nasional.\n"
    "[4] Audit Keamanan SPBE dilaksanakan oleh BSSN terhadap infrastruktur SPBE secara berkala."
)


def test_verify_claims_uses_original_id_after_renumbering():
    # Model cited retrieval source [4]; renumbering rewrote it to [1].
    answer = "Audit Keamanan SPBE dilaksanakan oleh BSSN terhadap infrastruktur SPBE secara berkala [1]."
    sources = [
        {
            "id": 1,
            "original_id": 4,
            "snippet": "Audit Keamanan SPBE dilaksanakan oleh BSSN terhadap infrastruktur SPBE secara berkala.",
        }
    ]
    verdicts = verify_claims(answer, RENUMBERED_CONTEXT, sources)
    assert len(verdicts) == 1
    assert verdicts[0].status == SUPPORTED


def test_verify_claims_falls_back_to_snippet_when_block_missing():
    answer = "Audit Keamanan SPBE dilaksanakan oleh BSSN terhadap infrastruktur SPBE secara berkala [1]."
    sources = [
        {
            "id": 1,
            "original_id": 9,  # no [9] block exists in context
            "snippet": "Audit Keamanan SPBE dilaksanakan oleh BSSN terhadap infrastruktur SPBE secara berkala.",
        }
    ]
    verdicts = verify_claims(answer, RENUMBERED_CONTEXT, sources)
    assert len(verdicts) == 1
    assert verdicts[0].status == SUPPORTED


def test_validate_answer_claim_grounding_maps_renumbered_ids():
    answer = "Audit Keamanan SPBE dilaksanakan oleh BSSN terhadap infrastruktur SPBE secara berkala [1]."
    sources = [
        {
            "id": 1,
            "original_id": 4,
            "snippet": "Audit Keamanan SPBE dilaksanakan oleh BSSN terhadap infrastruktur SPBE secara berkala.",
        }
    ]
    result = validate_answer(answer, RENUMBERED_CONTEXT, sources)
    assert result["claim_grounding"]["unsupported_claims"] == 0
    assert result["is_valid"] is True


# ---------------------------------------------------------------------------
# M5 — original_id preserved across repeated renumber passes
# ---------------------------------------------------------------------------

def test_renumber_preserves_original_id_across_passes():
    answer = "Klaim pertama tentang audit keamanan [4]. Klaim kedua tentang layanan aplikasi [2]."
    sources = [{"id": 2, "document": "Dok B"}, {"id": 4, "document": "Dok A"}]

    first_answer, first_sources = renumber_citations_and_sources(answer, sources)
    second_answer, second_sources = renumber_citations_and_sources(first_answer, first_sources)

    by_id = {src["id"]: src for src in second_sources}
    assert by_id[1]["original_id"] == 4
    assert by_id[2]["original_id"] == 2


# ---------------------------------------------------------------------------
# K2 — named-regulation Pasal scoping vs production title format
# ---------------------------------------------------------------------------

def test_named_regulation_pasal_allows_production_title_format():
    query = "Apa isi Pasal 5 Perpres Nomor 95 Tahun 2018?"
    context = (
        "[1] Pasal 5 Tata kelola SPBE bertujuan untuk memastikan penerapan "
        "unsur-unsur SPBE secara terpadu."
    )
    sources = [
        {
            "id": 1,
            "document": "Peraturan Presiden Nomor 95 Tahun 2018 tentang Sistem Pemerintahan Berbasis Elektronik",
            "section": "Pasal 5",
            "hierarchy": "Peraturan Presiden 95 Tahun 2018 > BAB II > Pasal 5",
            "snippet": "Pasal 5 Tata kelola SPBE bertujuan untuk memastikan penerapan unsur-unsur SPBE secara terpadu.",
        }
    ]
    decision = assess_llm09_pre_generation_guard(query, context, sources)
    assert decision.allowed is True


def test_named_regulation_pasal_still_blocks_wrong_regulation():
    query = "Apa isi Pasal 99 Perpres Nomor 95 Tahun 2018?"
    context = "[1] Pasal 99 mengatur ketentuan peralihan penyelenggaraan sistem elektronik."
    sources = [
        {
            "id": 1,
            "document": "Peraturan Pemerintah Nomor 71 Tahun 2019 tentang Penyelenggaraan Sistem dan Transaksi Elektronik",
            "section": "Pasal 99",
            "hierarchy": "Peraturan Pemerintah 71 Tahun 2019 > BAB X > Pasal 99",
            "snippet": "Pasal 99 mengatur ketentuan peralihan penyelenggaraan sistem elektronik.",
        }
    ]
    decision = assess_llm09_pre_generation_guard(query, context, sources)
    assert decision.allowed is False
    assert decision.risk_category == "legal_reference"


def test_named_regulation_pasal_accepts_pasal_only_in_snippet():
    # md_fallback-style chunk: metadata labels lack 'Pasal 5' but the body has it.
    query = "Jelaskan Pasal 5 Perpres Nomor 95 Tahun 2018."
    context = "[1] Pasal 5 Tata kelola SPBE bertujuan untuk memastikan penerapan unsur SPBE."
    sources = [
        {
            "id": 1,
            "document": "Peraturan Presiden 95 Tahun 2018 tentang SPBE",
            "section": "BAB II PENYELENGGARAAN",
            "hierarchy": "Peraturan Presiden 95 Tahun 2018 > BAB II PENYELENGGARAAN",
            "snippet": "Pasal 5 Tata kelola SPBE bertujuan untuk memastikan penerapan unsur SPBE.",
        }
    ]
    decision = assess_llm09_pre_generation_guard(query, context, sources)
    assert decision.allowed is True


# ---------------------------------------------------------------------------
# H1 — PARTIAL disclosure sentence must survive the claim verifier
# ---------------------------------------------------------------------------

def test_partial_disclosure_survives_claim_verifier():
    context = "[1] Sanksi administratif berupa teguran tertulis bagi pelanggar ketentuan keamanan informasi."
    answer = (
        "Sanksi administratif berupa teguran tertulis [1]. "
        "Bagian lain tidak dapat dikonfirmasi dari retrieved context yang tersedia."
    )
    sources = [{"id": 1}]
    verdicts = verify_claims(answer, context, sources)
    edited, has_remaining = apply_verifier_edits(answer, verdicts)

    assert has_remaining is True
    assert "teguran tertulis" in edited
    assert "tidak dapat dikonfirmasi" in edited


# ---------------------------------------------------------------------------
# H2 — ayat check scoped to the named pasal
# ---------------------------------------------------------------------------

AYAT_SCOPE_CONTEXT = (
    "[1] Pasal 7 (1) Auditor wajib memiliki sertifikat kompetensi. "
    "(2) Sertifikat diterbitkan oleh lembaga terakreditasi.\n"
    "[2] Pasal 12 ayat (3) mengatur sanksi administratif bagi pelanggaran ketentuan audit."
)
AYAT_SCOPE_SOURCES = [
    {
        "id": 1,
        "document": "Peraturan BSSN 8 Tahun 2024",
        "section": "Pasal 7",
        "hierarchy": "Peraturan BSSN 8 Tahun 2024 > BAB III > Pasal 7",
        "snippet": "Pasal 7 (1) Auditor wajib memiliki sertifikat kompetensi. (2) Sertifikat diterbitkan oleh lembaga terakreditasi.",
    },
    {
        "id": 2,
        "document": "Peraturan BSSN 8 Tahun 2024",
        "section": "Pasal 12",
        "hierarchy": "Peraturan BSSN 8 Tahun 2024 > BAB V > Pasal 12",
        "snippet": "Pasal 12 ayat (3) mengatur sanksi administratif bagi pelanggaran ketentuan audit.",
    },
]


def test_ayat_scoped_to_named_pasal_blocks_wrong_ayat():
    # Pasal 7 only has ayat (1)-(2); ayat (3) exists only under Pasal 12.
    query = "Apa bunyi Pasal 7 ayat (3) Peraturan BSSN?"
    decision = assess_llm09_pre_generation_guard(query, AYAT_SCOPE_CONTEXT, AYAT_SCOPE_SOURCES)
    assert decision.allowed is False


def test_ayat_scoped_to_named_pasal_allows_correct_ayat():
    query = "Apa bunyi Pasal 7 ayat (2) Peraturan BSSN?"
    decision = assess_llm09_pre_generation_guard(query, AYAT_SCOPE_CONTEXT, AYAT_SCOPE_SOURCES)
    assert decision.allowed is True


# ---------------------------------------------------------------------------
# H3 — split-table detection vs sibling completeness
# ---------------------------------------------------------------------------

def _table_source(part: int, total: int, source_id: int) -> dict:
    return {
        "id": source_id,
        "document": "Laporan Hasil Evaluasi SPBE 2024",
        "section": "Tabel 3",
        "hierarchy": f"Laporan Hasil Evaluasi SPBE 2024 > Tabel 3 [Bagian {part}/{total}]",
        "snippet": f"Baris data indeks bagian {part} dari tabel skor evaluasi.",
        "is_table": True,
        "table_label": "Tabel 3",
        "chunk_part": part,
        "chunk_parts_total": total,
    }


def test_aggregation_allowed_when_all_table_parts_present():
    query = "Berapa skor rata-rata indeks SPBE pemerintah daerah?"
    context = (
        "[1] Baris data indeks bagian 1 dari tabel skor evaluasi.\n"
        "[2] Baris data indeks bagian 2 dari tabel skor evaluasi."
    )
    sources = [_table_source(1, 2, 1), _table_source(2, 2, 2)]
    decision = assess_llm09_pre_generation_guard(query, context, sources)
    assert decision.allowed is True


def test_aggregation_blocked_when_table_part_missing():
    query = "Berapa skor rata-rata indeks SPBE pemerintah daerah?"
    context = "[1] Baris data indeks bagian 1 dari tabel skor evaluasi."
    sources = [_table_source(1, 2, 1)]
    decision = assess_llm09_pre_generation_guard(query, context, sources)
    assert decision.allowed is False
    assert decision.risk_category == "aggregation_completeness"


# ---------------------------------------------------------------------------
# H5 — numeric grounding in the claim verifier
# ---------------------------------------------------------------------------

NUMERIC_CONTEXT = "[1] Audit Infrastruktur SPBE dilaksanakan paling sedikit 1 kali dalam 2 tahun."
NUMERIC_SOURCES = [{"id": 1}]


def test_wrong_number_in_claim_is_not_supported():
    answer = "Audit Infrastruktur SPBE dilaksanakan paling sedikit 1 kali dalam 5 tahun [1]."
    verdicts = verify_claims(answer, NUMERIC_CONTEXT, NUMERIC_SOURCES)
    assert len(verdicts) == 1
    assert verdicts[0].status != SUPPORTED


def test_correct_number_in_claim_stays_supported():
    answer = "Audit Infrastruktur SPBE dilaksanakan paling sedikit 1 kali dalam 2 tahun [1]."
    verdicts = verify_claims(answer, NUMERIC_CONTEXT, NUMERIC_SOURCES)
    assert len(verdicts) == 1
    assert verdicts[0].status == SUPPORTED


# ---------------------------------------------------------------------------
# H6 — flagged-ayat stripping is number-scoped and core-only
# ---------------------------------------------------------------------------

def test_strip_flagged_ayat_removes_only_flagged_numbers():
    answer = (
        "Pasal 38 Ayat (1) mewajibkan penilaian mandiri [1]. "
        "Pasal 38 Ayat (9) mengatur sanksi pidana [1].\n\n"
        "Referensi Dokumen:\n"
        "[1] Peraturan BSSN 8 Tahun 2024 | Pasal 38 > Ayat (1)"
    )
    warnings = ["Kemungkinan Ayat yang tidak ada di konteks: 9"]
    cleaned = strip_flagged_ayat_references(answer, warnings)

    assert "Ayat (1) mewajibkan" in cleaned
    assert "Ayat (9)" not in cleaned
    assert "Pasal 38 > Ayat (1)" in cleaned  # reference block untouched


def test_strip_flagged_ayat_noop_without_ayat_warning():
    answer = "Pasal 38 Ayat (1) mewajibkan penilaian mandiri [1]."
    warnings = ["Jawaban tidak memiliki referensi/sitasi inline pada klaim jawaban"]
    assert strip_flagged_ayat_references(answer, warnings) == answer


# ---------------------------------------------------------------------------
# H7 — comparison guard matching
# ---------------------------------------------------------------------------

def test_comparison_allowed_without_trigger_word_in_evidence():
    query = "Bandingkan indeks SPBE tahun 2022 dengan tahun 2023 pada laporan audit."
    context = (
        "[1] Tabel indeks SPBE: capaian tahun 2022 sebesar 2,34 dan tahun 2023 "
        "sebesar 2,79 menurut laporan audit nasional."
    )
    sources = [
        {
            "id": 1,
            "document": "Laporan Hasil Evaluasi SPBE 2024",
            "snippet": "Tabel indeks SPBE: capaian tahun 2022 sebesar 2,34 dan tahun 2023 sebesar 2,79 menurut laporan audit nasional.",
        }
    ]
    decision = assess_llm09_pre_generation_guard(query, context, sources)
    assert decision.allowed is True


def test_comparison_matches_acronym_expansion_in_evidence():
    query = "Bandingkan perlindungan IIV dengan perlindungan data pribadi."
    context = (
        "[1] Perlindungan infrastruktur informasi vital dilakukan oleh penyelenggara "
        "sistem elektronik. Perlindungan data pribadi diatur dalam peraturan tersendiri."
    )
    sources = [
        {
            "id": 1,
            "document": "Peraturan Presiden 82 Tahun 2023",
            "snippet": "Perlindungan infrastruktur informasi vital dilakukan oleh penyelenggara sistem elektronik. Perlindungan data pribadi diatur dalam peraturan tersendiri.",
        }
    ]
    decision = assess_llm09_pre_generation_guard(query, context, sources)
    assert decision.allowed is True


# ---------------------------------------------------------------------------
# H4 — verifier edits preserve answer formatting
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Putaran 2 (temuan review adversarial atas perbaikan putaran 1)
# ---------------------------------------------------------------------------

def test_named_regulation_blocks_wrong_regulation_type_same_number_year():
    # PP 71/2019 exists; the user asks about a (non-existent) Perpres 71/2019.
    # Number+year alone must not satisfy the named-regulation check.
    query = "Apa isi Pasal 5 Perpres Nomor 71 Tahun 2019?"
    context = "[1] Pasal 5 mengatur penyelenggaraan sistem elektronik oleh instansi."
    sources = [
        {
            "id": 1,
            "document": "Peraturan Pemerintah Nomor 71 Tahun 2019 tentang Penyelenggaraan Sistem dan Transaksi Elektronik",
            "section": "Pasal 5",
            "hierarchy": "Peraturan Pemerintah 71 Tahun 2019 > BAB II > Pasal 5",
            "snippet": "Pasal 5 mengatur penyelenggaraan sistem elektronik oleh instansi.",
        }
    ]
    decision = assess_llm09_pre_generation_guard(query, context, sources)
    assert decision.allowed is False
    assert decision.risk_category == "legal_reference"


def test_named_regulation_type_alias_pp_matches_peraturan_pemerintah():
    query = "Apa isi Pasal 5 PP 71/2019?"
    context = "[1] Pasal 5 mengatur penyelenggaraan sistem elektronik oleh instansi."
    sources = [
        {
            "id": 1,
            "document": "Peraturan Pemerintah Nomor 71 Tahun 2019 tentang Penyelenggaraan Sistem dan Transaksi Elektronik",
            "section": "Pasal 5",
            "hierarchy": "Peraturan Pemerintah 71 Tahun 2019 > BAB II > Pasal 5",
            "snippet": "Pasal 5 mengatur penyelenggaraan sistem elektronik oleh instansi.",
        }
    ]
    decision = assess_llm09_pre_generation_guard(query, context, sources)
    assert decision.allowed is True


def test_ayat_paired_with_adjacent_pasal_in_compound_query():
    # 'Pasal 7 dan Pasal 12 ayat (2)': the ayat belongs to Pasal 12; the '(2)'
    # enumeration inside the Pasal 7 chunk must not satisfy it.
    query = "Apa isi Pasal 7 dan Pasal 12 ayat (2) Peraturan BSSN?"
    context = (
        "[1] Pasal 7 (1) Auditor wajib memiliki sertifikat kompetensi. "
        "(2) Sertifikat diterbitkan oleh lembaga terakreditasi.\n"
        "[2] Pasal 12 Sanksi administratif dikenakan bagi pelanggaran ketentuan audit."
    )
    sources = [
        AYAT_SCOPE_SOURCES[0],
        {
            "id": 2,
            "document": "Peraturan BSSN 8 Tahun 2024",
            "section": "Pasal 12",
            "hierarchy": "Peraturan BSSN 8 Tahun 2024 > BAB V > Pasal 12",
            "snippet": "Pasal 12 Sanksi administratif dikenakan bagi pelanggaran ketentuan audit.",
        },
    ]
    decision = assess_llm09_pre_generation_guard(query, context, sources)
    assert decision.allowed is False


def test_cross_reference_ayat_of_other_pasal_does_not_count():
    # A Pasal 7 chunk cross-referencing 'Pasal 12 ayat (5)' must not validate
    # a query about Pasal 7 ayat (5).
    query = "Apa bunyi Pasal 7 ayat (5) Peraturan BSSN?"
    context = (
        "[1] Pasal 7 Auditor wajib tersertifikasi sebagaimana dimaksud dalam "
        "Pasal 12 ayat (5)."
    )
    sources = [
        {
            "id": 1,
            "document": "Peraturan BSSN 8 Tahun 2024",
            "section": "Pasal 7",
            "hierarchy": "Peraturan BSSN 8 Tahun 2024 > BAB III > Pasal 7",
            "snippet": "Pasal 7 Auditor wajib tersertifikasi sebagaimana dimaksud dalam Pasal 12 ayat (5).",
        }
    ]
    decision = assess_llm09_pre_generation_guard(query, context, sources)
    assert decision.allowed is False


def test_apply_verifier_edits_does_not_excise_substring_of_kept_sentence():
    # The uncited (unsupported) sentence is an exact substring of the kept,
    # supported sentence — removal must respect sentence boundaries.
    context = "[1] Kegiatan Audit dilakukan setiap bulan menurut jadwal resmi yang ditetapkan instansi."
    answer = (
        "Kegiatan Audit dilakukan setiap bulan menurut jadwal resmi [1].\n"
        "Audit dilakukan setiap bulan menurut jadwal"
    )
    sources = [{"id": 1}]
    verdicts = verify_claims(answer, context, sources)
    by_text = {v.text: v.status for v in verdicts}
    assert by_text["Kegiatan Audit dilakukan setiap bulan menurut jadwal resmi [1]."] == SUPPORTED
    assert by_text["Audit dilakukan setiap bulan menurut jadwal"] == UNSUPPORTED

    edited, has_remaining = apply_verifier_edits(answer, verdicts)
    assert has_remaining is True
    assert "Kegiatan Audit dilakukan setiap bulan menurut jadwal resmi [1]." in edited
    assert "\nAudit dilakukan setiap bulan menurut jadwal" not in edited


def test_hedged_hallucination_with_confirmation_phrase_is_still_graded():
    # 'tidak dapat dikonfirmasi' alone must NOT exempt a sentence that goes on
    # to assert an ungrounded fact; only the mandated disclosure wording is exempt.
    context = "[1] Audit dilaksanakan paling sedikit 1 kali dalam 2 tahun."
    answer = "Durasi retensi tidak dapat dikonfirmasi, namun umumnya bernilai 5 tahun [1]."
    sources = [{"id": 1}]
    verdicts = verify_claims(answer, context, sources)
    assert len(verdicts) == 1
    assert verdicts[0].status != SUPPORTED


def test_verify_claims_accepts_string_source_ids():
    context = "[1] Pasal 7 mengatur kompetensi Auditor Keamanan SPBE dan pembuktiannya."
    answer = "Pasal 7 mengatur kompetensi Auditor Keamanan SPBE [1]."
    sources = [{"id": "1"}]
    verdicts = verify_claims(answer, context, sources)
    assert len(verdicts) == 1
    assert verdicts[0].status == SUPPORTED


def test_strip_flagged_ayat_at_line_start():
    answer = "Ayat (9) mengatur sanksi pidana [1].\nPasal 38 Ayat (1) tetap berlaku [1]."
    warnings = ["Kemungkinan Ayat yang tidak ada di konteks: 9"]
    cleaned = strip_flagged_ayat_references(answer, warnings)
    assert "Ayat (9)" not in cleaned
    assert "Ayat (1) tetap berlaku" in cleaned


def test_apply_verifier_edits_preserves_list_formatting():
    context = (
        "[1] Tahapan audit keamanan SPBE meliputi tahap persiapan audit dan "
        "tahap pelaksanaan audit keamanan."
    )
    answer = (
        "Tahapan audit keamanan meliputi dua tahap utama [1]:\n"
        "1. Tahap persiapan audit keamanan [1]\n"
        "2. Tahap pelaksanaan audit keamanan [1]\n"
        "3. Audit wajib dilakukan setiap bulan dengan sanksi berat [1]"
    )
    sources = [{"id": 1}]
    verdicts = verify_claims(answer, context, sources)
    statuses = {v.text: v.status for v in verdicts}
    assert any(s == UNSUPPORTED for s in statuses.values())

    edited, has_remaining = apply_verifier_edits(answer, verdicts)

    assert has_remaining is True
    assert "\n1. Tahap persiapan audit keamanan [1]" in edited
    assert "\n2. Tahap pelaksanaan audit keamanan [1]" in edited
    assert "setiap bulan" not in edited
    assert re.search(r"(?m)^\s*3\.\s*$", edited) is None  # no dangling list marker
