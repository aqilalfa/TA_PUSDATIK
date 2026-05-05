import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scripts.rebuild_bm25 import build_bm25_search_text


def _sample_metadata():
    return {
        "judul_dokumen": "PP Nomor 95 Tahun 2018 tentang SPBE",
        "filename": "PP_95_2018_SPBE.pdf",
        "doc_type": "peraturan",
        "hierarchy": "PP 95/2018 > BAB I > Pasal 5 > Ayat (2)",
        "bab": "BAB I - KETENTUAN UMUM",
        "bagian": "Bagian Kedua",
        "pasal": "Pasal 5",
        "ayat": "Ayat (2)",
    }


def test_bm25_excludes_document_level_fields():
    """
    judul_dokumen, filename, doc_type TIDAK boleh ada di search_text.
    Test ini HARUS GAGAL sebelum build_bm25_search_text diubah.
    """
    result = build_bm25_search_text("isi chunk teks", _sample_metadata())
    assert "PP Nomor 95 Tahun 2018" not in result, (
        "judul_dokumen masih ada di search_text — harus dihapus"
    )
    assert "PP_95_2018_SPBE.pdf" not in result, (
        "filename masih ada di search_text — harus dihapus"
    )
    assert result.strip().startswith("PP") is False or "PP_95" not in result, (
        "filename masih ada di search_text"
    )
    # doc_type = "peraturan" should not appear as a standalone field
    words = result.lower().split()
    assert "peraturan" not in words, (
        "doc_type 'peraturan' sebagai field standalone masih ada di search_text"
    )


def test_bm25_includes_structural_metadata():
    """
    pasal, ayat, hierarchy, bab, bagian HARUS ada di search_text.
    """
    result = build_bm25_search_text("isi chunk teks", _sample_metadata())
    assert "Pasal 5" in result, "pasal harus ada di search_text"
    assert "Ayat (2)" in result, "ayat harus ada di search_text"
    assert "BAB I" in result, "bab harus ada di search_text"
    assert "Bagian Kedua" in result, "bagian harus ada di search_text"
    assert "isi chunk teks" in result, "chunk text harus ada di search_text"


def test_bm25_handles_empty_structural_fields():
    """
    Metadata dengan field kosong tidak boleh menghasilkan spasi ganda atau crash.
    """
    metadata = {
        "judul_dokumen": "Judul",
        "filename": "file.pdf",
        "doc_type": "laporan",
        "hierarchy": "Judul > Bab I",
        "bab": "",
        "bagian": "",
        "pasal": "",
        "ayat": "",
    }
    result = build_bm25_search_text("teks chunk", metadata)
    assert "  " not in result, "Tidak boleh ada double-space dalam search_text"
    assert result.strip() != "", "search_text tidak boleh kosong"
    assert "teks chunk" in result
