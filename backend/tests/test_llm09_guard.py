from app.core.rag.llm09_guard import assess_llm09_pre_generation_guard


SPBE_SOURCE = {
    "id": 1,
    "document": "Perpres Nomor 95 Tahun 2018 tentang Sistem Pemerintahan Berbasis Elektronik",
    "section": "Pasal 1",
    "hierarchy": "Perpres Nomor 95 Tahun 2018 > BAB I > Pasal 1",
    "snippet": "Pasal 1 Sistem Pemerintahan Berbasis Elektronik yang selanjutnya disingkat SPBE adalah penyelenggaraan pemerintahan yang memanfaatkan teknologi informasi dan komunikasi.",
}

PASAL4_SOURCE = {
    "id": 1,
    "document": "Perpres Nomor 95 Tahun 2018 tentang Sistem Pemerintahan Berbasis Elektronik",
    "section": "Pasal 4 Ayat (1)",
    "hierarchy": "Perpres Nomor 95 Tahun 2018 > Pasal 4 > Ayat (1)",
    "snippet": "Pasal 4 Ayat (1) Unsur SPBE meliputi rencana induk, arsitektur, peta rencana, proses bisnis, data dan informasi, infrastruktur, aplikasi, keamanan, dan layanan SPBE.",
}

TABLE_PARTIAL_SOURCE = {
    "id": 1,
    "document": "Laporan Evaluasi SPBE 2024",
    "section": "Tabel Evaluasi SPBE [Bagian 1/4]",
    "hierarchy": "Laporan Evaluasi SPBE 2024 > Tabel Evaluasi SPBE [Bagian 1/4]",
    "snippet": "Tabel evaluasi SPBE menampilkan beberapa baris instansi dengan nilai sebagian. Bagian ini bukan rekapitulasi nasional.",
}


def test_llm09_guard_blocks_unavailable_blockchain_from_tangential_spbe_context():
    decision = assess_llm09_pre_generation_guard(
        "Apa kewajiban SPBE terkait penggunaan blockchain nasional yang tidak disebutkan dalam dokumen?",
        SPBE_SOURCE["snippet"],
        [SPBE_SOURCE],
    )

    assert decision.allowed is False
    assert decision.risk_category == "evidence_sufficiency"


def test_llm09_guard_blocks_wrong_ayat_reference():
    decision = assess_llm09_pre_generation_guard(
        "Jelaskan ketentuan Pasal 4 Ayat (99) tentang unsur-unsur SPBE.",
        PASAL4_SOURCE["snippet"],
        [PASAL4_SOURCE],
    )

    assert decision.allowed is False
    assert decision.risk_category == "legal_reference"
    assert "Ayat (99)" in decision.reason


def test_llm09_guard_allows_supported_legal_reference():
    decision = assess_llm09_pre_generation_guard(
        "Jelaskan ketentuan Pasal 4 Ayat (1) tentang unsur-unsur SPBE.",
        PASAL4_SOURCE["snippet"],
        [PASAL4_SOURCE],
    )

    assert decision.allowed is True


def test_llm09_guard_blocks_unsupported_external_comparison():
    decision = assess_llm09_pre_generation_guard(
        "Bandingkan efektivitas SPBE Indonesia dengan Estonia berdasarkan dokumen yang tersedia.",
        SPBE_SOURCE["snippet"],
        [SPBE_SOURCE],
    )

    assert decision.allowed is False
    assert decision.risk_category == "comparison"


def test_llm09_guard_blocks_incomplete_national_table_aggregation():
    decision = assess_llm09_pre_generation_guard(
        "Hitung domain evaluasi SPBE dengan skor terendah secara nasional dari tabel yang belum tentu lengkap.",
        TABLE_PARTIAL_SOURCE["snippet"],
        [TABLE_PARTIAL_SOURCE],
    )

    assert decision.allowed is False
    assert decision.risk_category == "aggregation_completeness"


def test_llm09_guard_allows_normal_supported_definition():
    decision = assess_llm09_pre_generation_guard(
        "Apa yang dimaksud dengan SPBE?",
        SPBE_SOURCE["snippet"],
        [SPBE_SOURCE],
    )

    assert decision.allowed is True
