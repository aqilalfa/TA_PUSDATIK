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


def test_explicit_regulation_penalty_prevents_wrong_source_exact_phrase_from_winning():
    ranker = RAGRanker()
    wrong_source_exact = _doc(
        "Keamanan SPBE adalah pengendalian keamanan yang terpadu dalam SPBE.",
        title="Peraturan BSSN Nomor 8 Tahun 2024",
        section="Pasal 1",
    )
    requested_source = _doc(
        "Keamanan SPBE adalah pengendalian keamanan yang terpadu di dalam pelaksanaan SPBE.",
        title="Perpres Nomor 95 Tahun 2018",
        section="Pasal 1",
    )

    ranked = ranker.rerank(
        "Apa yang dimaksud dengan Keamanan SPBE menurut Perpres 95 Tahun 2018?",
        [wrong_source_exact, requested_source],
        top_k=2,
    )

    assert ranked[0].metadata["document_title"] == "Perpres Nomor 95 Tahun 2018"


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


def test_monitoring_evaluation_purpose_boost_prioritizes_permenpan_pasal_2():
    ranker = RAGRanker()
    target = _doc(
        "Pasal 2 Pemantauan dan Evaluasi SPBE bertujuan untuk mengukur capaian kemajuan penerapan SPBE pada Instansi Pusat dan Pemerintah Daerah.",
        title="Permenpan RB Nomor 59 Tahun 2020",
        section="Pasal 2",
    )
    generic = _doc(
        "Pedoman pemantauan dan evaluasi SPBE menjelaskan proses persiapan, pelaksanaan, dan pelaporan.",
        title="Pedoman Nomor 3 Tahun 2024",
        section="BAB III",
    )

    ranked = ranker.rerank(
        "Apa tujuan utama dilakukannya Pemantauan dan Evaluasi SPBE?",
        [generic, target],
        top_k=2,
    )

    assert ranked[0].metadata["context_header"] == "Pasal 2"


def test_table_1_maturity_boost_prioritizes_rintisan_rubric():
    ranker = RAGRanker()
    target = _doc(
        "Lampiran I Tabel 1 Tingkat 1 Rintisan: proses penerapan SPBE dilakukan tanpa perencanaan dan sewaktu-waktu.",
        title="Permenpan RB Nomor 59 Tahun 2020",
        section="Lampiran I Tabel 1",
    )
    generic = _doc(
        "SPBE adalah penyelenggaraan pemerintahan yang memanfaatkan teknologi informasi dan komunikasi.",
        title="Perpres Nomor 95 Tahun 2018",
        section="Pasal 1",
    )

    ranked = ranker.rerank(
        "Apa yang mendefinisikan SPBE Tingkat 1 (Rintisan)?",
        [generic, target],
        top_k=2,
    )

    assert ranked[0].metadata["context_header"] == "Lampiran I Tabel 1"


def test_table_7_domain_weight_boost_prioritizes_domain_layanan():
    ranker = RAGRanker()
    target = _doc(
        "Lampiran I Tabel 7 Bobot (%) Domain 4 Layanan SPBE 45,50 Total Bobot.",
        title="Permenpan RB Nomor 59 Tahun 2020",
        section="Lampiran I Tabel 7",
    )
    generic = _doc(
        "Domain Layanan SPBE memiliki indikator layanan administrasi pemerintahan dan layanan publik.",
        title="Pedoman Nomor 3 Tahun 2024",
        section="Lampiran Instrumen",
    )

    ranked = ranker.rerank(
        "Berapa persentase bobot penilaian untuk Domain Layanan SPBE?",
        [generic, target],
        top_k=2,
    )

    assert ranked[0].metadata["context_header"] == "Lampiran I Tabel 7"


def test_table_13_predicate_boost_prioritizes_index_range_table():
    ranker = RAGRanker()
    target = _doc(
        "Lampiran I Tabel 13 Nilai Indeks SPBE Predikat Sangat Baik untuk 3,5 sampai kurang dari 4,2 dan Kurang untuk di bawah 1,8.",
        title="Permenpan RB Nomor 59 Tahun 2020",
        section="Lampiran I Tabel 13",
    )
    report = _doc(
        "Laporan Evaluasi SPBE Tahun 2024. Instansi memiliki Indeks SPBE Akhir 3,99 dengan Predikat Sangat Baik.",
        title="Laporan Evaluasi SPBE Tahun 2024",
        section="Data Capaian Instansi",
    )

    ranked = ranker.rerank(
        "Predikat apa yang disematkan pada rentang nilai indeks SPBE 3,5 hingga kurang dari 4,2?",
        [report, target],
        top_k=2,
    )

    assert ranked[0].metadata["context_header"] == "Lampiran I Tabel 13"


def test_pp71_andal_query_prioritizes_pasal_3_explanation_over_pasal_1_definition():
    ranker = RAGRanker()
    target = _doc(
        "Pasal 3 Ayat (1) Sistem elektronik yang andal adalah sistem elektronik yang memiliki kemampuan sesuai dengan kebutuhan penggunanya.",
        title="PP Nomor 71 Tahun 2019",
        section="Pasal 3",
    )
    pasal_1 = _doc(
        "Pasal 1 Sistem Elektronik adalah serangkaian perangkat dan prosedur elektronik yang berfungsi mempersiapkan informasi elektronik.",
        title="PP Nomor 71 Tahun 2019",
        section="Pasal 1",
    )

    ranked = ranker.rerank(
        'Apa yang dimaksud sistem elektronik yang "andal" secara hukum?',
        [pasal_1, target],
        top_k=2,
    )

    assert ranked[0].metadata["context_header"] == "Pasal 3"


def test_pp71_sanctions_query_prioritizes_pasal_100_list():
    ranker = RAGRanker()
    target = _doc(
        "Pasal 100 Ayat (2) Sanksi administratif dapat berupa teguran tertulis, denda administratif, penghentian sementara, pemutusan Akses, dan/atau dikeluarkan dari daftar.",
        title="PP Nomor 71 Tahun 2019",
        section="Pasal 100",
    )
    near_miss = _doc(
        "Pasal 98 Penyelenggara Sistem Elektronik wajib melakukan pemutusan Akses terhadap Informasi Elektronik.",
        title="PP Nomor 71 Tahun 2019",
        section="Pasal 98",
    )

    ranked = ranker.rerank(
        "Apa sanksi administratif jika Penyelenggara Sistem Elektronik melakukan pelanggaran?",
        [near_miss, target],
        top_k=2,
    )

    assert ranked[0].metadata["context_header"] == "Pasal 100"


def test_bssn_audit_evidence_query_prioritizes_exact_pasal_ayat():
    ranker = RAGRanker()
    target = _doc(
        "Pasal 17 Ayat (1) Bukti Audit Keamanan SPBE harus memenuhi aspek cukup, kompeten, relevan, dan berguna.",
        title="Peraturan BSSN Nomor 8 Tahun 2024",
        section="Pasal 17",
    )
    target.metadata["ayat"] = "Ayat (1)"
    near_miss = _doc(
        "Pasal 71 Ayat (1) LATIK menyampaikan laporan audit keamanan SPBE secara berkala kepada Badan.",
        title="Peraturan BSSN Nomor 8 Tahun 2024",
        section="Pasal 71",
    )
    near_miss.metadata["ayat"] = "Ayat (1)"

    ranked = ranker.rerank(
        "Aspek apa saja yang harus dipenuhi oleh bukti Audit Keamanan SPBE?",
        [near_miss, target],
        top_k=2,
    )

    assert ranked[0].metadata["context_header"] == "Pasal 17"


def test_bssn_latik_periodic_report_prioritizes_exact_pasal_63():
    ranker = RAGRanker()
    target = _doc(
        "Pasal 63 LATIK Terakreditasi wajib menyampaikan laporan periodik paling sedikit 1 kali dalam 1 tahun.",
        title="Peraturan BSSN Nomor 8 Tahun 2024",
        section="Pasal 63",
    )
    near_miss = _doc(
        "Pasal 46 LATIK melaksanakan audit keamanan SPBE sesuai tata cara yang ditetapkan.",
        title="Peraturan BSSN Nomor 8 Tahun 2024",
        section="Pasal 46",
    )

    ranked = ranker.rerank(
        "Kapan LATIK Terakreditasi wajib menyampaikan laporan periodik audit keamanan mereka?",
        [near_miss, target],
        top_k=2,
    )

    assert ranked[0].metadata["context_header"] == "Pasal 63"


def test_report_2024_lowest_domain_query_prioritizes_national_summary_over_2023():
    ranker = RAGRanker()
    target = _doc(
        "Laporan Evaluasi SPBE Tahun 2024 Analisis Capaian Indeks Maturitas SPBE Nasional. Tabel 5 nilai indeks domain nasional menunjukkan Domain Manajemen SPBE memiliki rerata 1.86 dan posisi paling bawah.",
        title="Laporan Evaluasi SPBE Tahun 2024",
        section="Analisis Capaian Indeks Maturitas SPBE Nasional",
    )
    stale = _doc(
        "Laporan Evaluasi SPBE Tahun 2023 Data Capaian Instansi. Rincian Nilai Domain: Kebijakan Internal, Tata Kelola, Manajemen SPBE, Layanan SPBE.",
        title="Laporan Evaluasi SPBE Tahun 2023",
        section="Data Capaian Instansi",
    )

    ranked = ranker.rerank(
        "Apa domain yang mencetak skor evaluasi terendah secara nasional pada Laporan 2024?",
        [stale, target],
        top_k=2,
    )

    assert ranked[0].metadata["document_title"] == "Laporan Evaluasi SPBE Tahun 2024"


def test_report_2024_lowest_domain_query_prioritizes_aggregate_summary_over_instansi_rows():
    ranker = RAGRanker()
    target = _doc(
        "Laporan Evaluasi SPBE Tahun 2024 Analisis Capaian Indeks Maturitas SPBE Nasional. Nilai indeks domain nasional menunjukkan Domain Manajemen SPBE memiliki rerata 1.86 dan menjadi skor terendah.",
        title="Laporan Evaluasi SPBE Tahun 2024",
        section="Analisis Capaian Indeks Maturitas SPBE Nasional",
    )
    row = _doc(
        "Laporan Pelaksanaan Evaluasi SPBE Tahun 2024. Instansi: Pemerintah Kab. Merauke. Rincian Nilai Domain: Kebijakan Internal (1.2), Tata Kelola (1.4), Manajemen SPBE (1.0), Layanan SPBE (3.47).",
        title="Laporan Evaluasi SPBE Tahun 2024",
        section="Data Capaian Instansi",
    )
    row.metadata["rrf_score"] = 3.5
    target.metadata["rrf_score"] = 0.01

    ranked = ranker.rerank(
        "Apa domain yang mencetak skor evaluasi terendah secara nasional pada Laporan 2024?",
        [row, target],
        top_k=2,
    )

    assert ranked[0].metadata["context_header"] == "Analisis Capaian Indeks Maturitas SPBE Nasional"


def test_arsitektur_spbe_nasional_duration_prioritizes_pasal_8_over_related_architecture_chunks():
    ranker = RAGRanker()
    target = _doc(
        "Pasal 8 Ayat (1) Arsitektur SPBE Nasional disusun untuk jangka waktu 5 (lima) tahun.",
        title="Perpres Nomor 95 Tahun 2018",
        section="Pasal 8",
    )
    local_architecture = _doc(
        "Pasal 12 Ayat (2) Arsitektur SPBE Pemerintah Daerah disusun untuk jangka waktu 5 (lima) tahun.",
        title="Perpres Nomor 95 Tahun 2018",
        section="Pasal 12",
    )
    local_architecture.metadata["rrf_score"] = 3.5
    target.metadata["rrf_score"] = 0.01

    ranked = ranker.rerank(
        "Untuk berapa lama Arsitektur SPBE Nasional disusun?",
        [local_architecture, target],
        top_k=2,
    )

    assert ranked[0].metadata["context_header"] == "Pasal 8"


def test_pelaksana_audit_keamanan_spbe_prioritizes_latik_pasal_4():
    ranker = RAGRanker()
    target = _doc(
        "Pasal 4 Ayat (1) Pelaksana Audit Keamanan SPBE sebagaimana dimaksud dalam Pasal 2 huruf b yaitu LATIK cakupan Keamanan SPBE. Ayat (2) LATIK cakupan Keamanan SPBE terdiri atas LATIK pemerintah atau LATIK Terakreditasi yang terdaftar.",
        title="Peraturan BSSN Nomor 8 Tahun 2024",
        section="Pasal 4",
    )
    overview = _doc(
        "Standar Audit Keamanan SPBE terdiri atas objek Audit Keamanan SPBE, pelaksana Audit Keamanan SPBE, kriteria Audit Keamanan SPBE, bukti Audit Keamanan SPBE, dan kesimpulan Audit Keamanan SPBE.",
        title="Peraturan BSSN Nomor 8 Tahun 2024",
        section="BAB II",
    )
    overview.metadata["rrf_score"] = 3.5
    target.metadata["rrf_score"] = 0.01

    ranked = ranker.rerank(
        "Siapa entitas yang bertugas sebagai Pelaksana Audit Keamanan SPBE?",
        [overview, target],
        top_k=2,
    )

    assert ranked[0].metadata["context_header"] == "Pasal 4"


def test_report_2024_highest_local_government_prioritizes_aggregate_summary():
    ranker = RAGRanker()
    target = _doc(
        "Laporan Evaluasi SPBE Tahun 2024. Indeks Maturitas SPBE tertinggi nasional dan lokus Pemerintah Daerah diraih oleh instansi dengan skor 4,77 dan predikat Memuaskan.",
        title="Laporan Evaluasi SPBE Tahun 2024",
        section="Analisis Capaian Indeks Maturitas SPBE Nasional",
    )
    row = _doc(
        "Laporan Evaluasi SPBE Tahun 2024. Instansi: Pemerintah Kab. Bojonegoro. Indeks SPBE Akhir: 4.14. Predikat: Sangat Baik.",
        title="Laporan Evaluasi SPBE Tahun 2024",
        section="Data Capaian Instansi",
    )

    ranked = ranker.rerank(
        "Instansi pemerintah daerah mana yang meraih nilai SPBE tertinggi di tahun 2024?",
        [row, target],
        top_k=2,
    )

    assert ranked[0].metadata["context_header"] == "Analisis Capaian Indeks Maturitas SPBE Nasional"


def test_report_2024_highest_local_government_prioritizes_max_kabupaten_row():
    ranker = RAGRanker()
    target = _doc(
        "Laporan Pelaksanaan Evaluasi SPBE Tahun 2024. Instansi: Pemerintah Kab. Banyuwangi. Indeks SPBE Akhir: 4.77 (Predikat: Memuaskan).",
        title="Laporan Evaluasi SPBE Tahun 2024",
        section="Data Capaian Instansi",
    )
    ministry = _doc(
        "Laporan Pelaksanaan Evaluasi SPBE Tahun 2024. Instansi: Kementerian Keuangan. Indeks SPBE Akhir: 4.74 (Predikat: Memuaskan).",
        title="Laporan Evaluasi SPBE Tahun 2024",
        section="Data Capaian Instansi",
    )

    ranked = ranker.rerank(
        "Instansi pemerintah daerah mana yang meraih nilai SPBE tertinggi di tahun 2024?",
        [ministry, target],
        top_k=2,
    )

    assert "Banyuwangi" in ranked[0].page_content


def test_permenpan_evaluasi_spbe_definition_prioritizes_exact_definition_chunk():
    ranker = RAGRanker()
    target = _doc(
        "Pasal 1 Evaluasi SPBE adalah proses penilaian secara sistematis melalui verifikasi, klarifikasi, serta validasi terhadap hasil Penilaian Mandiri untuk mengukur tingkat kematangan penerapan SPBE.",
        title="Permenpan RB Nomor 59 Tahun 2020",
        section="Pasal 1",
    )
    bssn_definition_noise = _doc(
        "Pasal 1 Sistem Pemerintahan Berbasis Elektronik yang selanjutnya disingkat SPBE adalah penyelenggaraan pemerintahan yang memanfaatkan teknologi informasi dan komunikasi.",
        title="Peraturan BSSN Nomor 2 Tahun 2023",
        section="Pasal 1",
    )
    perpres_definition_noise = _doc(
        "Pasal 1 Tata Kelola SPBE adalah kerangka kerja yang memastikan pengaturan, pengarahan, dan pengendalian dalam penerapan SPBE secara terpadu.",
        title="Perpres Nomor 95 Tahun 2018",
        section="Pasal 1",
    )

    ranked = ranker.rerank(
        "Apa definisi Evaluasi SPBE?",
        [bssn_definition_noise, perpres_definition_noise, target],
        top_k=3,
    )

    assert ranked[0].metadata["document_title"] == "Permenpan RB Nomor 59 Tahun 2020"
    assert "Evaluasi SPBE adalah" in ranked[0].page_content


def test_bssn_audit_object_query_prioritizes_pasal_3_objects_over_standard_overview():
    ranker = RAGRanker()
    target = _doc(
        "Pasal 3 Objek Audit Keamanan SPBE terdiri atas Infrastruktur SPBE Nasional, Infrastruktur SPBE Instansi Pusat dan Pemerintah Daerah, Aplikasi Umum, dan Aplikasi Khusus.",
        title="Peraturan BSSN Nomor 8 Tahun 2024",
        section="Pasal 3",
    )
    overview = _doc(
        "Standar Audit Keamanan SPBE meliputi Objek Audit Keamanan SPBE, Pelaksana Audit Keamanan SPBE, Kriteria Audit Keamanan SPBE, Bukti Audit Keamanan SPBE, dan Konklusi Audit Keamanan SPBE.",
        title="Peraturan BSSN Nomor 8 Tahun 2024",
        section="Standar Audit Keamanan SPBE",
    )
    wrong_pasal = _doc(
        "Pasal 71 Alat bantu Audit Keamanan SPBE merupakan perangkat teknologi yang digunakan dalam pelaksanaan audit.",
        title="Peraturan BSSN Nomor 8 Tahun 2024",
        section="Pasal 71",
    )

    ranked = ranker.rerank(
        "Apa sajakah yang dapat menjadi objek dari Audit Keamanan SPBE?",
        [overview, wrong_pasal, target],
        top_k=3,
    )

    assert ranked[0].metadata["context_header"] == "Pasal 3"


def test_perpres82_assigned_institution_query_prioritizes_pasal_3_over_followup_articles():
    ranker = RAGRanker()
    target = _doc(
        "Pasal 3 Ayat (1) Pemerintah menugaskan Perusahaan Umum Percetakan Uang Republik Indonesia untuk menyelenggarakan Aplikasi SPBE Prioritas.",
        title="Perpres Nomor 82 Tahun 2023",
        section="Pasal 3",
    )
    followup_article = _doc(
        "Pasal 6 Pendanaan penyelenggaraan Aplikasi SPBE Prioritas bersumber dari anggaran pendapatan dan belanja negara.",
        title="Perpres Nomor 82 Tahun 2023",
        section="Pasal 6",
    )
    followup_article.metadata["rrf_score"] = 3.5
    target.metadata["rrf_score"] = 0.01

    ranked = ranker.rerank(
        "Siapa lembaga yang secara khusus ditugaskan pemerintah untuk menyelenggarakan Aplikasi SPBE Prioritas?",
        [followup_article, target],
        top_k=2,
    )

    assert ranked[0].metadata["context_header"] == "Pasal 3"


def test_penilaian_visitasi_definition_prioritizes_permenpan_exact_definition():
    ranker = RAGRanker()
    target = _doc(
        "Pasal 1 Penilaian Visitasi adalah penilaian interviu dan/atau validasi lapangan terhadap hasil Penilaian Mandiri SPBE.",
        title="Permenpan RB Nomor 59 Tahun 2020",
        section="Pasal 1",
    )
    generic_definition = _doc(
        "Pasal 1 Sistem Pemerintahan Berbasis Elektronik adalah penyelenggaraan pemerintahan yang memanfaatkan teknologi informasi dan komunikasi.",
        title="Perpres Nomor 95 Tahun 2018",
        section="Pasal 1",
    )
    generic_definition.metadata["rrf_score"] = 3.5
    target.metadata["rrf_score"] = 0.01

    ranked = ranker.rerank(
        "Apa yang dimaksud dengan Penilaian Visitasi?",
        [generic_definition, target],
        top_k=2,
    )

    assert ranked[0].metadata["document_title"] == "Permenpan RB Nomor 59 Tahun 2020"


def test_tata_kelola_spbe_purpose_prioritizes_perpres95_pasal_4():
    ranker = RAGRanker()
    target = _doc(
        "Pasal 4 Ayat (1) Tata Kelola SPBE bertujuan untuk memastikan penerapan unsur-unsur SPBE secara terpadu.",
        title="Perpres Nomor 95 Tahun 2018",
        section="Pasal 4",
    )
    generic_definition = _doc(
        "Pasal 1 Tata Kelola SPBE adalah kerangka kerja yang memastikan pengaturan, pengarahan, dan pengendalian dalam penerapan SPBE secara terpadu.",
        title="Peraturan BSSN Nomor 2 Tahun 2023",
        section="Pasal 1",
    )
    generic_definition.metadata["rrf_score"] = 3.5
    target.metadata["rrf_score"] = 0.01

    ranked = ranker.rerank(
        "Apa tujuan diadakannya Tata Kelola SPBE?",
        [generic_definition, target],
        top_k=2,
    )

    assert ranked[0].metadata["document_title"] == "Perpres Nomor 95 Tahun 2018"
    assert ranked[0].metadata["context_header"] == "Pasal 4"


def test_aplikasi_spbe_prioritas_definition_prioritizes_perpres82_exact_definition():
    ranker = RAGRanker()
    target = _doc(
        "Pasal 1 Angka 6 Aplikasi SPBE Prioritas adalah Aplikasi SPBE yang berdampak luas dan merupakan perwujudan nyata dari Layanan SPBE yang berkualitas dan tepercaya.",
        title="Perpres Nomor 82 Tahun 2023",
        section="Pasal 1",
    )
    generic_app_definition = _doc(
        "Pasal 1 Angka 5 Aplikasi SPBE adalah satu atau sekumpulan program komputer dan prosedur yang dirancang untuk melakukan tugas atau fungsi Layanan SPBE.",
        title="Perpres Nomor 82 Tahun 2023",
        section="Pasal 1",
    )
    generic_app_definition.metadata["rrf_score"] = 3.5
    target.metadata["rrf_score"] = 0.01

    ranked = ranker.rerank(
        "Apa yang dimaksud dengan Aplikasi SPBE Prioritas?",
        [generic_app_definition, target],
        top_k=2,
    )

    assert ranked[0].metadata["document_title"] == "Perpres Nomor 82 Tahun 2023"
    assert "Aplikasi SPBE Prioritas adalah" in ranked[0].page_content
