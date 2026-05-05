import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.core.ingestion.structured_chunker import (
    chunk_peraturan,
    chunk_laporan,
    append_chunk_with_limit,
)


def _make_peraturan_doc(ayat_texts):
    """Minimal peraturan doc structure untuk testing."""
    return {
        "type": "peraturan",
        "metadata_dokumen": {
            "jenis_peraturan": "PP",
            "nomor": "1",
            "tahun": "2024",
            "tentang": "Test",
            "sumber_file": "test.pdf",
        },
        "preamble": "",
        "batang_tubuh": [
            {
                "bab_nomor": "I",
                "bab_judul": "Umum",
                "pasal": [
                    {
                        "nomor": "1",
                        "isi": "",
                        "ayat": [
                            {"nomor": str(i + 1), "isi": t}
                            for i, t in enumerate(ayat_texts)
                        ],
                        "bagian": "",
                    }
                ],
            }
        ],
        "lampiran": {},
    }


def test_chunk_peraturan_groups_ayat_up_to_900_chars():
    """
    Dua ayat masing-masing 350 karakter = ~709 karakter gabungan.
    Dengan batas 900 harus masuk 1 chunk; dengan batas lama 600 akan dipisah.
    Test ini HARUS GAGAL sebelum konstanta diubah.
    """
    ayat1 = "A" * 350
    ayat2 = "B" * 350
    doc = _make_peraturan_doc([ayat1, ayat2])
    chunks = chunk_peraturan(doc)

    # Cari chunk yang berisi teks dari Pasal 1
    pasal_chunks = [
        c for c in chunks if "Pasal 1" in c["metadata"].get("hierarchy", "")
    ]
    assert pasal_chunks, "Tidak ada chunk untuk Pasal 1"

    combined_in_one = any(
        "A" * 10 in c["text"] and "B" * 10 in c["text"] for c in pasal_chunks
    )
    assert combined_in_one, (
        "Dengan batas 900 karakter, dua ayat 350-char seharusnya dalam 1 chunk. "
        "Jika test ini gagal, konstanta MAX_CHUNK_SIZE_PERATURAN belum diubah ke 900."
    )


def test_chunk_laporan_buffers_paragraphs_up_to_1800_chars():
    """
    Dua paragraf masing-masing 700 karakter = 1401 karakter total.
    Dengan batas 1800 harus masuk 1 chunk; dengan batas lama 600 akan dipisah.
    Test ini HARUS GAGAL sebelum konstanta diubah.
    """
    para1 = "X" * 700
    para2 = "Y" * 700
    doc = {
        "type": "laporan",
        "judul": "Test Laporan",
        "source_filename": "test.pdf",
        "sections": [
            {"heading": "Bab I", "level": 1, "paragraphs": [para1, para2]}
        ],
    }
    chunks = chunk_laporan(doc)
    assert len(chunks) == 1, (
        f"Dengan batas 1800 karakter, dua paragraf 700-char seharusnya 1 chunk. "
        f"Dapat {len(chunks)} chunk. Konstanta MAX_CHUNK_SIZE_LAPORAN belum diubah ke 1800."
    )
    assert "X" * 10 in chunks[0]["text"] and "Y" * 10 in chunks[0]["text"]


def test_append_chunk_with_limit_respects_custom_max_size():
    """
    append_chunk_with_limit harus menerima max_size dan overlap sebagai parameter.
    Test ini HARUS GAGAL sebelum signature fungsi diubah (TypeError: unexpected keyword arg).
    """
    chunks_large = []
    text = "W" * 1000
    append_chunk_with_limit(
        chunks_large, text, {"doc_type": "test"}, max_size=1200, overlap=100
    )
    # 1000 chars < 1200 max → 1 chunk
    assert len(chunks_large) == 1, (
        f"Teks 1000 char dengan max_size=1200 seharusnya 1 chunk, dapat {len(chunks_large)}."
    )

    chunks_small = []
    append_chunk_with_limit(
        chunks_small, text, {"doc_type": "test"}, max_size=400, overlap=40
    )
    # 1000 chars > 400 max → lebih dari 1 chunk
    assert len(chunks_small) > 1, (
        "Teks 1000 char dengan max_size=400 seharusnya dipecah jadi >1 chunk."
    )
