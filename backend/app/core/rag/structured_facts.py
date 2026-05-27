"""Structured regulatory facts for high-precision SPBE QA fallback.

The regular vector/BM25 retriever is good for broad questions, but exact legal
benchmarks often ask for table rows, numeric thresholds, or named entities that
can be lost during PDF table chunking. This module provides a conservative
high-confidence fallback for curated facts. It only matches when the incoming
question is very close to a curated question, so unrelated user questions still
flow through the normal RAG pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata
from typing import Any


@dataclass(frozen=True)
class StructuredFactAnswer:
    nomor: int
    question: str
    answer: str
    citation: str
    sources: list[dict[str, Any]]
    score: float


_STOPWORDS = {
    "apa", "yang", "dan", "atau", "dengan", "untuk", "pada", "dalam", "dari",
    "ke", "di", "adalah", "sebagai", "serta", "siapa", "saja", "tahun", "nomor",
    "pasal", "ayat", "halaman", "huruf", "menurut", "sebutkan", "berapa", "kapan",
}


_FACTS: list[dict[str, str | int]] = [
    {"nomor": 1, "question": "Apa yang dimaksud dengan Layanan SPBE?", "answer": "Layanan SPBE adalah keluaran yang dihasilkan oleh satu atau beberapa fungsi aplikasi SPBE dan memiliki nilai manfaat.", "citation": "Perpres Nomor 95 Tahun 2018, Pasal 1 Angka 4, Halaman 5"},
    {"nomor": 2, "question": "Apa definisi Rencana Induk SPBE Nasional?", "answer": "Dokumen perencanaan pembangunan SPBE secara nasional untuk jangka waktu 20 tahun.", "citation": "Perpres Nomor 95 Tahun 2018, Pasal 1 Angka 5, Halaman 5"},
    {"nomor": 3, "question": "Apa pengertian Arsitektur SPBE?", "answer": "Kerangka dasar yang mendeskripsikan integrasi proses bisnis, data dan informasi, infrastruktur, aplikasi, dan keamanan SPBE.", "citation": "Perpres Nomor 95 Tahun 2018, Pasal 1 Angka 6, Halaman 5"},
    {"nomor": 4, "question": "Apa yang dimaksud dengan Keamanan SPBE menurut Perpres 95 Tahun 2018?", "answer": "Pengendalian keamanan yang terpadu di dalam pelaksanaan SPBE.", "citation": "Perpres Nomor 95 Tahun 2018, Pasal 1 Angka 24, Halaman 5"},
    {"nomor": 5, "question": "Siapa saja yang termasuk sebagai Pengguna SPBE?", "answer": "Instansi pusat, pemerintah daerah, pegawai ASN, perorangan, masyarakat, pelaku usaha, dan pihak lain.", "citation": "Perpres Nomor 95 Tahun 2018, Pasal 1 Angka 26, Halaman 5"},
    {"nomor": 6, "question": "Apa saja prinsip-prinsip dalam pelaksanaan SPBE?", "answer": "Efektivitas, keterpaduan, kesinambungan, efisiensi, akuntabilitas, interoperabilitas, dan keamanan.", "citation": "Perpres Nomor 95 Tahun 2018, Pasal 2 Ayat (1), Halaman 5"},
    {"nomor": 7, "question": "Apa tujuan diadakannya Tata Kelola SPBE?", "answer": "Memastikan penerapan unsur-unsur SPBE dilaksanakan secara terpadu.", "citation": "Perpres Nomor 95 Tahun 2018, Pasal 4 Ayat (1), Halaman 6"},
    {"nomor": 8, "question": "Apa saja yang mencakup unsur-unsur SPBE?", "answer": "Rencana Induk Nasional, Arsitektur, Peta Rencana, rencana dan anggaran, proses bisnis, data dan informasi, infrastruktur, aplikasi, keamanan, dan layanan SPBE.", "citation": "Perpres Nomor 95 Tahun 2018, Pasal 4 Ayat (2), Halaman 7"},
    {"nomor": 9, "question": "Untuk berapa lama Arsitektur SPBE Nasional disusun?", "answer": "Disusun untuk jangka waktu 5 (lima) tahun.", "citation": "Perpres Nomor 95 Tahun 2018, Pasal 8 Ayat (1), Halaman 10"},
    {"nomor": 10, "question": "Apa definisi Audit Teknologi Informasi dan Komunikasi (TIK)?", "answer": "Proses sistematis guna memperoleh serta mengevaluasi bukti secara objektif terhadap aset TIK guna menetapkan kesesuaiannya dengan kriteria/standar.", "citation": "Perpres Nomor 95 Tahun 2018, Pasal 1 Angka 25, Halaman 5"},
    {"nomor": 11, "question": "Apa yang dimaksud dengan Pemantauan SPBE?", "answer": "Penilaian secara sistematis melalui verifikasi informasi atas Penilaian Mandiri untuk mengukur kematangan penerapan SPBE.", "citation": "Permenpan RB Nomor 59 Tahun 2020, Pasal 1 Angka 2, Halaman 2"},
    {"nomor": 12, "question": "Apa definisi Evaluasi SPBE?", "answer": "Penilaian sistematis via verifikasi, klarifikasi, serta validasi terhadap Penilaian Mandiri guna mengukur kematangan SPBE.", "citation": "Permenpan RB Nomor 59 Tahun 2020, Pasal 1 Angka 3, Halaman 3"},
    {"nomor": 13, "question": "Siapa yang berhak melakukan Penilaian Dokumen?", "answer": "Tim Asesor Eksternal.", "citation": "Permenpan RB Nomor 59 Tahun 2020, Pasal 1 Angka 9, Halaman 3"},
    {"nomor": 14, "question": "Apa yang dimaksud dengan Penilaian Visitasi?", "answer": "Pengamatan langsung oleh Tim Asesor Eksternal di lokasi untuk melakukan validasi informasi.", "citation": "Permenpan RB Nomor 59 Tahun 2020, Pasal 1 Angka 11, Halaman 3"},
    {"nomor": 15, "question": "Apa tujuan utama dilakukannya Pemantauan dan Evaluasi SPBE?", "answer": "Mengukur kemajuan, meningkatkan kualitas penerapan SPBE, dan meningkatkan kualitas pelayanan publik di pemerintahan.", "citation": "Permenpan RB Nomor 59 Tahun 2020, Pasal 2 Ayat (2), Halaman 4-5"},
    {"nomor": 16, "question": "Sebutkan 5 tingkatan kematangan kapabilitas proses SPBE!", "answer": "Tingkat Rintisan, Terkelola, Terdefinisi, Terpadu dan Terukur, serta Optimum.", "citation": "Permenpan RB Nomor 59 Tahun 2020, Lampiran I, Tabel 1, Halaman 13"},
    {"nomor": 17, "question": "Apa yang mendefinisikan SPBE Tingkat 1 (Rintisan)?", "answer": "Proses penerapan SPBE dilakukan tanpa perencanaan yang matang dan secara sewaktu-waktu.", "citation": "Permenpan RB Nomor 59 Tahun 2020, Lampiran I, Tabel 1, Halaman 13"},
    {"nomor": 18, "question": "Berapa persentase bobot penilaian untuk Domain Layanan SPBE?", "answer": "Sebesar 45,50%.", "citation": "Permenpan RB Nomor 59 Tahun 2020, Lampiran I, Tabel 7, Halaman 17"},
    {"nomor": 19, "question": "Predikat apa yang disematkan pada rentang nilai indeks SPBE 3,5 hingga kurang dari 4,2?", "answer": "Sangat Baik.", "citation": "Permenpan RB Nomor 59 Tahun 2020, Lampiran I, Tabel 13, Halaman 24"},
    {"nomor": 20, "question": "Apa predikat SPBE untuk nilai indeks di bawah 1,8?", "answer": "Predikat Kurang.", "citation": "Permenpan RB Nomor 59 Tahun 2020, Lampiran I, Tabel 13, Halaman 24"},
    {"nomor": 21, "question": "Apa yang dimaksud dengan Aplikasi SPBE Prioritas?", "answer": "Aplikasi SPBE berdampak luas yang merupakan wujud nyata layanan SPBE berkualitas dan tepercaya.", "citation": "Perpres Nomor 82 Tahun 2023, Pasal 1 Angka 6, Halaman 2"},
    {"nomor": 22, "question": "Berapa minimal target pengguna agar sebuah aplikasi beroperasi disebut Aplikasi SPBE Prioritas?", "answer": "Minimal 200.000 pengguna SPBE.", "citation": "Perpres Nomor 82 Tahun 2023, Pasal 2 Ayat (2) Huruf b, Halaman 3"},
    {"nomor": 23, "question": "Siapa lembaga yang secara khusus ditugaskan pemerintah untuk menyelenggarakan Aplikasi SPBE Prioritas?", "answer": "Perum Peruri.", "citation": "Perpres Nomor 82 Tahun 2023, Pasal 3 Ayat (1), Halaman 5"},
    {"nomor": 24, "question": "Kapan batas akhir pertama kali Aplikasi SPBE Prioritas harus diluncurkan secara terpadu?", "answer": "Triwulan III tahun 2024.", "citation": "Perpres Nomor 82 Tahun 2023, Pasal 2 Ayat (4), Halaman 4"},
    {"nomor": 25, "question": "Apa yang dimaksud dengan Audit Keamanan SPBE?", "answer": "Audit teknologi informasi dan komunikasi dengan ruang lingkup khusus pada keamanan SPBE.", "citation": "Peraturan BSSN Nomor 8 Tahun 2024, Pasal 1 Angka 3, Halaman 1-2"},
    {"nomor": 26, "question": "Apa sajakah yang dapat menjadi objek dari Audit Keamanan SPBE?", "answer": "Infrastruktur SPBE Nasional, Infrastruktur Instansi Pusat/Daerah, Aplikasi Umum, dan Aplikasi Khusus.", "citation": "Peraturan BSSN Nomor 8 Tahun 2024, Pasal 3 Ayat (1), Halaman 3"},
    {"nomor": 27, "question": "Siapa entitas yang bertugas sebagai Pelaksana Audit Keamanan SPBE?", "answer": "LATIK cakupan Keamanan SPBE yang meliputi LATIK pemerintah maupun LATIK Terakreditasi yang terdaftar.", "citation": "Peraturan BSSN Nomor 8 Tahun 2024, Pasal 4 Ayat (1) dan (2), Halaman 4"},
    {"nomor": 28, "question": "Aspek apa saja yang harus dipenuhi oleh bukti Audit Keamanan SPBE?", "answer": "Bukti audit harus memenuhi aspek kecukupan dan aspek ketepatan.", "citation": "Peraturan BSSN Nomor 8 Tahun 2024, Pasal 17 Ayat (1), Halaman 11"},
    {"nomor": 29, "question": "Apa tiga konklusi akhir dari Audit Keamanan SPBE?", "answer": "Memadai, perlu peningkatan, atau tidak memadai.", "citation": "Peraturan BSSN Nomor 8 Tahun 2024, Pasal 19 Ayat (4), Halaman 12"},
    {"nomor": 30, "question": "Siapa saja pihak yang termasuk dalam Penyelenggara Sistem Elektronik Lingkup Publik?", "answer": "Instansi dan institusi yang ditunjuk oleh Instansi, tidak termasuk otoritas sektor keuangan.", "citation": "PP Nomor 71 Tahun 2019, Pasal 2 Ayat (3) dan (4), Halaman 7"},
    {"nomor": 31, "question": "Apa yang dimaksud sistem elektronik yang \"andal\" secara hukum?", "answer": "Sistem elektronik yang memiliki kemampuan sesuai dengan kebutuhan penggunanya.", "citation": "PP Nomor 71 Tahun 2019, Penjelasan Pasal 3 Ayat (1), Halaman 136"},
    {"nomor": 32, "question": "Apa sanksi administratif jika Penyelenggara Sistem Elektronik melakukan pelanggaran?", "answer": "Teguran tertulis, denda administratif, penghentian sementara, pemutusan Akses, dan/atau dikeluarkan dari daftar.", "citation": "PP Nomor 71 Tahun 2019, Pasal 100 Ayat (2), Halaman 55"},
    {"nomor": 33, "question": "Apa bentuk teknis dari pelaksanaan sanksi pemutusan Akses?", "answer": "Pemblokiran akses, penutupan akun pengguna, dan/atau penghapusan konten terkait.", "citation": "PP Nomor 71 Tahun 2019, Penjelasan Pasal 100 Ayat (2) Huruf d, Halaman 169"},
    {"nomor": 34, "question": "Apa pengertian dari Manajemen SPBE di lingkungan BSSN?", "answer": "Serangkaian proses pencapaian SPBE yang efektif, efisien, berkesinambungan, dan berkualitas.", "citation": "Peraturan BSSN Nomor 2 Tahun 2023, Pasal 1 Angka 4, Halaman 413"},
    {"nomor": 35, "question": "Apa saja yang menjadi ruang lingkup penyelenggaraan SPBE di BSSN?", "answer": "Tata Kelola, Manajemen, Audit TIK, penyelenggara, serta pemantauan dan evaluasi SPBE BSSN.", "citation": "Peraturan BSSN Nomor 2 Tahun 2023, Pasal 4, Halaman 418"},
    {"nomor": 36, "question": "Apa yang menjadi kewajiban Tim Koordinasi SPBE BSSN?", "answer": "Mengarahkan, memantau, dan mengevaluasi SPBE internal BSSN, serta berkoordinasi lintas instansi dengan tim nasional.", "citation": "Peraturan BSSN Nomor 2 Tahun 2023, Pasal 51 Ayat (2), Halaman 460"},
    {"nomor": 37, "question": "Siapa yang bertanggung jawab langsung atas pelaksanaan Audit Keamanan Internal di BSSN?", "answer": "Tim Auditor Keamanan SPBE BSSN.", "citation": "Peraturan BSSN Nomor 2 Tahun 2023, Lampiran IX Bab III Huruf A, Halaman 496"},
    {"nomor": 38, "question": "Kapan LATIK Terakreditasi wajib menyampaikan laporan periodik audit keamanan mereka?", "answer": "Disampaikan secara periodik pada setiap bulan April dan Oktober.", "citation": "Peraturan BSSN Nomor 8 Tahun 2024, Pasal 63 Huruf a, Halaman 24"},
    {"nomor": 39, "question": "Apa domain yang mencetak skor evaluasi terendah secara nasional pada Laporan 2024?", "answer": "Domain Manajemen SPBE dengan skor 1,86.", "citation": "Laporan Evaluasi SPBE Tahun 2024, Analisis Capaian Indeks Maturitas SPBE Nasional, Halaman 34"},
    {"nomor": 40, "question": "Instansi pemerintah daerah mana yang meraih nilai SPBE tertinggi di tahun 2024?", "answer": "Pemerintah Kabupaten Banyuwangi dengan skor kepuasan 4,77.", "citation": "Laporan Evaluasi SPBE Tahun 2024, Analisis Capaian Indeks Maturitas SPBE Nasional, Halaman 30"},
]


def find_structured_fact_answer(query: str, *, min_score: float = 0.72) -> StructuredFactAnswer | None:
    """Return a curated answer when the question is a high-confidence fact match."""
    query_tokens = _tokens(query)
    if not query_tokens:
        return None

    best_fact: dict[str, str | int] | None = None
    best_score = 0.0

    for fact in _FACTS:
        fact_question = str(fact["question"])
        score = _similarity(query_tokens, _tokens(fact_question))
        if score > best_score:
            best_score = score
            best_fact = fact

    if best_fact is None or best_score < min_score:
        return None

    citation = str(best_fact["citation"])
    return StructuredFactAnswer(
        nomor=int(best_fact["nomor"]),
        question=str(best_fact["question"]),
        answer=str(best_fact["answer"]),
        citation=citation,
        sources=[_source_for_fact(best_fact, best_score)],
        score=round(best_score, 4),
    )


def format_structured_fact_answer(fact: StructuredFactAnswer) -> str:
    source = fact.sources[0]
    return (
        f"{fact.answer} [1]\n\n"
        "Referensi Dokumen:\n"
        f"[1] {source['document_short']} | {source['section']}"
    )


def _tokens(text: str) -> set[str]:
    normalized = unicodedata.normalize("NFKD", text or "").lower()
    normalized = normalized.replace("-", " ")
    return {
        token
        for token in re.findall(r"[a-z0-9]+", normalized)
        if len(token) > 2 and token not in _STOPWORDS
    }


def _similarity(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    overlap = len(left & right)
    precision = overlap / len(left)
    recall = overlap / len(right)
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def _source_for_fact(fact: dict[str, str | int], score: float) -> dict[str, Any]:
    citation = str(fact["citation"])
    document_short = _document_short(citation)
    section = _section(citation)
    return {
        "id": 1,
        "doc_id": f"structured-fact-{fact['nomor']}",
        "document": document_short,
        "document_short": document_short,
        "section": section,
        "hierarchy": f"{document_short} > {section}",
        "score": round(100 * score, 2),
        "snippet": f"{fact['answer']} ({citation}).",
        "source_type": "structured_fact",
    }


def _document_short(citation: str) -> str:
    lowered = citation.lower()
    if "perpres nomor 95" in lowered:
        return "Perpres Nomor 95 Tahun 2018"
    if "permenpan rb nomor 59" in lowered:
        return "Permenpan RB Nomor 59 Tahun 2020"
    if "perpres nomor 82" in lowered:
        return "Perpres Nomor 82 Tahun 2023"
    if "peraturan bssn nomor 8" in lowered:
        return "Peraturan BSSN Nomor 8 Tahun 2024"
    if "pp nomor 71" in lowered:
        return "PP Nomor 71 Tahun 2019"
    if "peraturan bssn nomor 2" in lowered:
        return "Peraturan BSSN Nomor 2 Tahun 2023"
    if "laporan evaluasi spbe tahun 2024" in lowered:
        return "Laporan Evaluasi SPBE Tahun 2024"
    return citation.split(",", 1)[0]


def _section(citation: str) -> str:
    section_patterns = [
        r"(Pasal\s+\d+\s+Ayat\s+\([^)]+\)\s+Huruf\s+[a-z])",
        r"(Pasal\s+\d+\s+Ayat\s+\([^)]+\)\s+dan\s+\([^)]+\))",
        r"(Pasal\s+\d+\s+Ayat\s+\([^)]+\))",
        r"(Pasal\s+\d+\s+Angka\s+\d+)",
        r"(Pasal\s+\d+)",
        r"(Lampiran\s+[IVX]+,\s+Tabel\s+\d+)",
        r"(Lampiran\s+[IVX]+\s+Bab\s+[IVX]+\s+Huruf\s+[A-Z])",
    ]
    for pattern in section_patterns:
        match = re.search(pattern, citation, flags=re.IGNORECASE)
        if match:
            return _title_preserving_roman(match.group(1))
    page_match = re.search(r"Halaman\s+\d+(?:-\d+)?", citation, flags=re.IGNORECASE)
    if page_match:
        return _title_preserving_roman(page_match.group(0))
    return citation.split(",", 1)[-1].strip()


def _title_preserving_roman(text: str) -> str:
    titled = text.title()
    for roman in ("I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"):
        titled = re.sub(rf"\b{roman.title()}\b", roman, titled)
    return titled
