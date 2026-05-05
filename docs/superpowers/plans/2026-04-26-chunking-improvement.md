# Chunking Improvement — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Perbaiki dua kelemahan struktural chunking: (1) ukuran chunk per-tipe agar memanfaatkan kapasitas model embedding lebih baik, dan (2) bersihkan BM25 corpus dari metadata dokumen-level yang mendilusi skor retrieval.

**Architecture:** Tambah 4 konstanta baru ke `config.py`; tambah 4 modul-level constant di `structured_chunker.py` dan perbarui semua fungsi chunker agar pakai konstanta tipe-spesifik; ganti `build_bm25_search_text()` di `rebuild_bm25.py` agar hanya gunakan metadata struktural per-chunk. Setelah kedua perbaikan committed, jalankan re-ingest penuh.

**Tech Stack:** Python 3.10+, pydantic-settings (`config.py`), pytest, `venv/Scripts/python` (Windows)

**Spec:** `docs/superpowers/specs/2026-04-26-chunking-improvement-design.md`

---

## File Map

| File | Action | Tanggung Jawab |
|---|---|---|
| `backend/app/config.py` | Modify | Tambah `CHUNK_SIZE_PERATURAN`, `CHUNK_OVERLAP_PERATURAN`, `CHUNK_SIZE_LAPORAN`, `CHUNK_OVERLAP_LAPORAN` |
| `backend/app/core/ingestion/structured_chunker.py` | Modify | Tambah modul-konstanta per-tipe; update `append_chunk_with_limit` + semua `chunk_X()` |
| `backend/scripts/rebuild_bm25.py` | Modify | Hapus `judul_dokumen`, `filename`, `doc_type` dari `build_bm25_search_text()` |
| `backend/tests/test_chunker_sizes.py` | Create | TDD: verifikasi ukuran chunking per-tipe |
| `backend/tests/test_bm25_corpus.py` | Create | TDD: verifikasi komposisi search_text BM25 |

---

## Task 1: Per-Type Chunk Size — Config + Chunker

**Files:**
- Create: `backend/tests/test_chunker_sizes.py`
- Modify: `backend/app/config.py`
- Modify: `backend/app/core/ingestion/structured_chunker.py`

---

- [ ] **Step 1: Tulis test yang gagal**

Buat `backend/tests/test_chunker_sizes.py`:

```python
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
```

---

- [ ] **Step 2: Jalankan test — verifikasi GAGAL**

```bash
cd backend
venv/Scripts/python -m pytest tests/test_chunker_sizes.py -v 2>&1
```

Expected: 3 test FAIL.
- `test_chunk_peraturan_groups_ayat_up_to_900_chars` → FAIL (current limit 600)
- `test_chunk_laporan_buffers_paragraphs_up_to_1800_chars` → FAIL (current limit 600)
- `test_append_chunk_with_limit_respects_custom_max_size` → FAIL atau ERROR (`TypeError: unexpected keyword argument 'max_size'`)

**Jangan lanjut ke Step 3 sebelum 3 test ini gagal.**

---

- [ ] **Step 3: Tambah 4 konstanta ke `backend/app/config.py`**

Di `config.py`, setelah baris `MAX_CHUNK_SIZE: int = 600` (baris 69), tambahkan:

```python
    # Per-type chunk sizes — each chunker reads the appropriate constant
    CHUNK_SIZE_PERATURAN: int = 900
    CHUNK_OVERLAP_PERATURAN: int = 150
    CHUNK_SIZE_LAPORAN: int = 1800
    CHUNK_OVERLAP_LAPORAN: int = 200
```

Indentasi sesuai class `Settings`. Baris 66–69 sekarang menjadi:

```python
    CHUNK_SIZE: int = 600
    CHUNK_OVERLAP: int = 100
    MIN_CHUNK_SIZE: int = 80  # Minimum chars per chunk (merge smaller ones)
    MAX_CHUNK_SIZE: int = 600  # Maximum chars before splitting
    # Per-type chunk sizes — each chunker reads the appropriate constant
    CHUNK_SIZE_PERATURAN: int = 900
    CHUNK_OVERLAP_PERATURAN: int = 150
    CHUNK_SIZE_LAPORAN: int = 1800
    CHUNK_OVERLAP_LAPORAN: int = 200
```

---

- [ ] **Step 4: Tambah modul-konstanta per-tipe di `structured_chunker.py`**

Di `backend/app/core/ingestion/structured_chunker.py`, setelah baris 29 (`MIN_CHUNK_SIZE = 80`), tambahkan:

```python
MAX_CHUNK_SIZE_PERATURAN = getattr(settings, "CHUNK_SIZE_PERATURAN", 900)
CHUNK_OVERLAP_PERATURAN  = getattr(settings, "CHUNK_OVERLAP_PERATURAN", 150)
MAX_CHUNK_SIZE_LAPORAN   = getattr(settings, "CHUNK_SIZE_LAPORAN", 1800)
CHUNK_OVERLAP_LAPORAN    = getattr(settings, "CHUNK_OVERLAP_LAPORAN", 200)
```

Blok konstanta modul sekarang menjadi (baris 27–35):

```python
MAX_CHUNK_SIZE = getattr(settings, "CHUNK_SIZE", 600)
CHUNK_OVERLAP = getattr(settings, "CHUNK_OVERLAP", 100)
MIN_CHUNK_SIZE = 80  # Don't create tiny chunks
MIN_JSON_CHUNKS_THRESHOLD = 20

MAX_CHUNK_SIZE_PERATURAN = getattr(settings, "CHUNK_SIZE_PERATURAN", 900)
CHUNK_OVERLAP_PERATURAN  = getattr(settings, "CHUNK_OVERLAP_PERATURAN", 150)
MAX_CHUNK_SIZE_LAPORAN   = getattr(settings, "CHUNK_SIZE_LAPORAN", 1800)
CHUNK_OVERLAP_LAPORAN    = getattr(settings, "CHUNK_OVERLAP_LAPORAN", 200)
```

---

- [ ] **Step 5: Update `append_chunk_with_limit` — tambah parameter `max_size` dan `overlap`**

Ganti seluruh fungsi `append_chunk_with_limit` (baris 218–258) dengan:

```python
def append_chunk_with_limit(
    chunks: List[Dict[str, Any]],
    text: str,
    metadata: Dict[str, Any],
    max_size: int = MAX_CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP,
) -> None:
    """Append chunk(s) while keeping each piece under configured max size."""
    normalized = (text or "").strip()
    if not normalized:
        return

    is_table_block = _is_table_like_text(normalized)
    if is_table_block:
        pieces = _split_table_like_text(
            normalized,
            max_size=max_size,
            overlap=overlap,
        )
    else:
        pieces = []

    if not pieces:
        pieces = split_text_with_overlap(
            normalized,
            max_size=max_size,
            overlap=overlap,
        )

    base_meta = dict(metadata)
    if is_table_block:
        base_meta["is_table"] = True
        label = base_meta.get("table_label") or _detect_table_label(normalized)
        if label:
            base_meta["table_label"] = label

    if len(pieces) == 1:
        chunks.append({"text": pieces[0], "metadata": _with_table_metadata(pieces[0], base_meta)})
        return

    total = len(pieces)
    for idx, piece in enumerate(pieces, 1):
        piece_meta = {**base_meta, "chunk_part": idx, "chunk_parts_total": total}
        hierarchy = piece_meta.get("hierarchy", "")
        if hierarchy:
            piece_meta["hierarchy"] = f"{hierarchy} [Bagian {idx}/{total}]"
        chunks.append({"text": piece, "metadata": _with_table_metadata(piece, piece_meta)})
```

---

- [ ] **Step 6: Update `chunk_peraturan` — gunakan PERATURAN constants**

Di fungsi `chunk_peraturan()`, lakukan 8 penggantian berikut. Setiap penggantian menunjukkan teks SEBELUM dan SESUDAH:

**6a. Preamble split (sekitar baris 434):**
```python
# SEBELUM:
        for piece in split_text_with_overlap(preamble):
# SESUDAH:
        for piece in split_text_with_overlap(preamble, MAX_CHUNK_SIZE_PERATURAN, CHUNK_OVERLAP_PERATURAN):
```

**6b. Ayat buffer condition (sekitar baris 488):**
```python
# SEBELUM:
                    if len(buffer_text) + len(candidate) + 1 <= MAX_CHUNK_SIZE:
# SESUDAH:
                    if len(buffer_text) + len(candidate) + 1 <= MAX_CHUNK_SIZE_PERATURAN:
```

**6c. First split_text_with_overlap di dalam ayat loop (sekitar baris 495):**
```python
# SEBELUM:
                            for piece in split_text_with_overlap(complete_text):
# SESUDAH:
                            for piece in split_text_with_overlap(complete_text, MAX_CHUNK_SIZE_PERATURAN, CHUNK_OVERLAP_PERATURAN):
```

**6d. Second split_text_with_overlap di flush buffer (sekitar baris 512):**
```python
# SEBELUM:
                    for piece in split_text_with_overlap(complete_text):
# SESUDAH:
                    for piece in split_text_with_overlap(complete_text, MAX_CHUNK_SIZE_PERATURAN, CHUNK_OVERLAP_PERATURAN):
```

**6e. Pasal tanpa ayat split (sekitar baris 525):**
```python
# SEBELUM:
                for piece in split_text_with_overlap(pasal_text):
# SESUDAH:
                for piece in split_text_with_overlap(pasal_text, MAX_CHUNK_SIZE_PERATURAN, CHUNK_OVERLAP_PERATURAN):
```

**6f. Lampiran narasi BAB (sekitar baris 564):**
```python
# SEBELUM:
            append_chunk_with_limit(
                chunks,
                f"{bab_label}\n{isi}",
                narasi_meta,
            )
# SESUDAH:
            append_chunk_with_limit(
                chunks,
                f"{bab_label}\n{isi}",
                narasi_meta,
                max_size=MAX_CHUNK_SIZE_PERATURAN,
                overlap=CHUNK_OVERLAP_PERATURAN,
            )
```

**6g. Kuesioner indikator (sekitar baris 603):**
```python
# SEBELUM:
                append_chunk_with_limit(chunks, full_ind_text, ind_meta)
# SESUDAH:
                append_chunk_with_limit(chunks, full_ind_text, ind_meta,
                                        max_size=MAX_CHUNK_SIZE_PERATURAN,
                                        overlap=CHUNK_OVERLAP_PERATURAN)
```

**6h. Lampiran isi_teks fallback (sekitar baris 608):**
```python
# SEBELUM:
                for piece in split_text_with_overlap(isi):
# SESUDAH:
                for piece in split_text_with_overlap(isi, MAX_CHUNK_SIZE_PERATURAN, CHUNK_OVERLAP_PERATURAN):
```

---

- [ ] **Step 7: Update `chunk_laporan` — gunakan LAPORAN constants**

Di fungsi `chunk_laporan()`, lakukan 3 penggantian:

**7a. Buffer condition (sekitar baris 649):**
```python
# SEBELUM:
            if len(buffer_text) + len(para) + 1 <= MAX_CHUNK_SIZE:
# SESUDAH:
            if len(buffer_text) + len(para) + 1 <= MAX_CHUNK_SIZE_LAPORAN:
```

**7b. Split di tengah loop (sekitar baris 653):**
```python
# SEBELUM:
                    for piece in split_text_with_overlap(buffer_text):
# SESUDAH:
                    for piece in split_text_with_overlap(buffer_text, MAX_CHUNK_SIZE_LAPORAN, CHUNK_OVERLAP_LAPORAN):
```

**7c. Split flush akhir (sekitar baris 661):**
```python
# SEBELUM:
            for piece in split_text_with_overlap(buffer_text):
# SESUDAH:
            for piece in split_text_with_overlap(buffer_text, MAX_CHUNK_SIZE_LAPORAN, CHUNK_OVERLAP_LAPORAN):
```

---

- [ ] **Step 8: Update `chunk_laporan_spbe` — gunakan LAPORAN constants**

Di fungsi `chunk_laporan_spbe()`, lakukan 5 penggantian:

**8a. Ringkasan eksekutif split (sekitar baris 700):**
```python
# SEBELUM:
        for piece in split_text_with_overlap(text_w_topik):
# SESUDAH:
        for piece in split_text_with_overlap(text_w_topik, MAX_CHUNK_SIZE_LAPORAN, CHUNK_OVERLAP_LAPORAN):
```

**8b. Rekomendasi buffer condition (sekitar baris 719):**
```python
# SEBELUM:
            if len(buffer_text) + len(candidate) + 1 <= MAX_CHUNK_SIZE:
# SESUDAH:
            if len(buffer_text) + len(candidate) + 1 <= MAX_CHUNK_SIZE_LAPORAN:
```

**8c. Rekomendasi split mid-loop (sekitar baris 722):**
```python
# SEBELUM:
                for piece in split_text_with_overlap(buffer_text):
# SESUDAH:
                for piece in split_text_with_overlap(buffer_text, MAX_CHUNK_SIZE_LAPORAN, CHUNK_OVERLAP_LAPORAN):
```

**8d. Rekomendasi split flush (sekitar baris 727):**
```python
# SEBELUM:
            for piece in split_text_with_overlap(buffer_text):
# SESUDAH:
            for piece in split_text_with_overlap(buffer_text, MAX_CHUNK_SIZE_LAPORAN, CHUNK_OVERLAP_LAPORAN):
```

**8e. Data capaian instansi append (sekitar baris 755):**
```python
# SEBELUM:
        append_chunk_with_limit(chunks, candidate, meta)
# SESUDAH:
        append_chunk_with_limit(chunks, candidate, meta,
                                max_size=MAX_CHUNK_SIZE_LAPORAN,
                                overlap=CHUNK_OVERLAP_LAPORAN)
```

---

- [ ] **Step 9: Update `chunk_pedoman_spbe` — gunakan LAPORAN constants**

Di fungsi `chunk_pedoman_spbe()`, lakukan 2 penggantian:

**9a. Narasi pedoman sub_bab split (sekitar baris 801):**
```python
# SEBELUM:
                for piece in split_text_with_overlap(isi):
# SESUDAH:
                for piece in split_text_with_overlap(isi, MAX_CHUNK_SIZE_LAPORAN, CHUNK_OVERLAP_LAPORAN):
```

**9b. Instrumen indikator append (sekitar baris 838):**
```python
# SEBELUM:
        append_chunk_with_limit(chunks, full_ind_text, meta)
# SESUDAH:
        append_chunk_with_limit(chunks, full_ind_text, meta,
                                max_size=MAX_CHUNK_SIZE_LAPORAN,
                                overlap=CHUNK_OVERLAP_LAPORAN)
```

---

- [ ] **Step 10: Update `chunk_from_markdown` — gunakan LAPORAN constants**

Di fungsi `chunk_from_markdown()`, satu penggantian:

**10a. append_chunk_with_limit di flush_section (sekitar baris 374):**
```python
# SEBELUM:
        append_chunk_with_limit(chunks, section_text, metadata)
# SESUDAH:
        append_chunk_with_limit(chunks, section_text, metadata,
                                max_size=MAX_CHUNK_SIZE_LAPORAN,
                                overlap=CHUNK_OVERLAP_LAPORAN)
```

---

- [ ] **Step 11: Jalankan test — verifikasi LULUS**

```bash
cd backend
venv/Scripts/python -m pytest tests/test_chunker_sizes.py -v 2>&1
```

Expected:
```
PASSED tests/test_chunker_sizes.py::test_chunk_peraturan_groups_ayat_up_to_900_chars
PASSED tests/test_chunker_sizes.py::test_chunk_laporan_buffers_paragraphs_up_to_1800_chars
PASSED tests/test_chunker_sizes.py::test_append_chunk_with_limit_respects_custom_max_size
3 passed
```

Jika ada yang masih FAIL, periksa apakah konstanta yang diubah sudah benar di fungsi yang sesuai.

---

- [ ] **Step 12: Jalankan full test suite — tidak ada regresi**

```bash
cd backend
venv/Scripts/python -m pytest tests/ -v 2>&1
```

Expected: semua test sebelumnya lulus, ditambah 3 test baru.

---

- [ ] **Step 13: Commit**

```bash
cd d:/aqil/pusdatik
git add backend/app/config.py backend/app/core/ingestion/structured_chunker.py backend/tests/test_chunker_sizes.py
git commit -m "feat(chunker): add per-type chunk sizes — peraturan 900 chars, laporan/pedoman 1800 chars"
```

---

## Task 2: BM25 Corpus Cleanup

**Files:**
- Create: `backend/tests/test_bm25_corpus.py`
- Modify: `backend/scripts/rebuild_bm25.py`

---

- [ ] **Step 1: Tulis test yang gagal**

Buat `backend/tests/test_bm25_corpus.py`:

```python
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
    # doc_type = "peraturan" sebagai kata standalone
    words = result.lower().split()
    assert "peraturan" not in words or "PP Nomor 95" not in result, (
        "doc_type 'peraturan' sebagai field standalone masih ada"
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
```

---

- [ ] **Step 2: Jalankan test — verifikasi GAGAL**

```bash
cd backend
venv/Scripts/python -m pytest tests/test_bm25_corpus.py -v 2>&1
```

Expected:
- `test_bm25_excludes_document_level_fields` → FAIL (saat ini judul_dokumen/filename/doc_type masih ada)
- `test_bm25_includes_structural_metadata` → PASS (sudah ada di implementasi lama)
- `test_bm25_handles_empty_structural_fields` → mungkin PASS atau FAIL tergantung implementasi lama

**Minimal test pertama harus FAIL sebelum lanjut.**

---

- [ ] **Step 3: Update `build_bm25_search_text` di `rebuild_bm25.py`**

Ganti seluruh fungsi `build_bm25_search_text` (baris 25–39) dengan:

```python
def build_bm25_search_text(text: str, metadata: dict) -> str:
    """Compose lexical search text for BM25 using chunk content + structural metadata.

    Excludes document-level fields (judul_dokumen, filename, doc_type) that are
    identical across all chunks of a document — they inflate term frequency without
    adding discriminative value and hurt BM25 IDF scores.
    """
    fields = [
        metadata.get("hierarchy", ""),
        metadata.get("context_header", ""),
        metadata.get("bab", ""),
        metadata.get("bagian", ""),
        metadata.get("pasal", ""),
        metadata.get("ayat", ""),
        text or "",
    ]
    return " ".join(str(v).strip() for v in fields if str(v).strip())
```

---

- [ ] **Step 4: Jalankan test — verifikasi LULUS**

```bash
cd backend
venv/Scripts/python -m pytest tests/test_bm25_corpus.py -v 2>&1
```

Expected:
```
PASSED tests/test_bm25_corpus.py::test_bm25_excludes_document_level_fields
PASSED tests/test_bm25_corpus.py::test_bm25_includes_structural_metadata
PASSED tests/test_bm25_corpus.py::test_bm25_handles_empty_structural_fields
3 passed
```

---

- [ ] **Step 5: Jalankan full test suite — tidak ada regresi**

```bash
cd backend
venv/Scripts/python -m pytest tests/ -v 2>&1
```

Expected: semua test lulus (termasuk 3 dari Task 1 dan 3 dari Task 2 ini).

---

- [ ] **Step 6: Commit**

```bash
cd d:/aqil/pusdatik
git add backend/scripts/rebuild_bm25.py backend/tests/test_bm25_corpus.py
git commit -m "feat(bm25): remove document-level metadata from BM25 corpus to improve IDF scoring"
```

---

## Task 3: Re-ingest + Verifikasi

**Files:**
- Tidak ada perubahan kode — hanya menjalankan script yang sudah ada

**Konteks:** Re-ingest diperlukan karena CHUNK_SIZE berubah. Script `reingest_all.py` sudah ada dan menangani: clear DB + Qdrant → re-embed semua PDF → rebuild BM25 (dengan `rebuild_bm25.py` yang sudah diupdate).

---

- [ ] **Step 1: Catat jumlah chunk sebelum re-ingest**

```bash
cd backend
venv/Scripts/python -c "
from app.database import SessionLocal
from app.models.db_models import Chunk, Document
db = SessionLocal()
print('Total chunks:', db.query(Chunk).count())
print('Total dokumen:', db.query(Document).count())
for d in db.query(Document).all():
    print(f'  {d.original_filename}: {d.chunk_count} chunks')
db.close()
" 2>&1
```

Catat outputnya — akan dibandingkan setelah re-ingest.

---

- [ ] **Step 2: Jalankan re-ingest penuh**

```bash
cd backend
venv/Scripts/python scripts/reingest_all.py 2>&1
```

Expected output menyebutkan:
- Qdrant collection dihapus dan dibuat ulang
- Setiap dokumen di-embed ulang
- `BM25 index rebuilt: N documents`
- `Done!` atau summary akhir

Estimasi waktu: 10–30 menit di GTX 1650. Tunggu hingga selesai.

---

- [ ] **Step 3: Verifikasi jumlah chunk BERKURANG**

```bash
cd backend
venv/Scripts/python -c "
from app.database import SessionLocal
from app.models.db_models import Chunk, Document
db = SessionLocal()
print('Total chunks SESUDAH:', db.query(Chunk).count())
print('Total dokumen:', db.query(Document).count())
for d in db.query(Document).all():
    print(f'  {d.original_filename}: {d.chunk_count} chunks')
db.close()
" 2>&1
```

Expected: total chunk **lebih sedikit** dari sebelumnya (chunk lebih besar = lebih sedikit chunk per dokumen). Jika jumlahnya sama atau lebih banyak, ada yang salah — periksa apakah `reingest_all.py` memanggil fungsi chunker yang sudah diupdate.

---

- [ ] **Step 4: Spot-check ukuran chunk untuk satu dokumen peraturan**

```bash
cd backend
venv/Scripts/python -c "
from app.database import SessionLocal
from app.models.db_models import Chunk, Document
import json
db = SessionLocal()
# Ambil dokumen pertama tipe peraturan
doc = db.query(Document).filter(Document.doc_type == 'peraturan').first()
if doc:
    chunks = db.query(Chunk).filter(Chunk.document_id == doc.id).limit(5).all()
    print(f'Dokumen: {doc.original_filename}')
    for c in chunks:
        meta = json.loads(c.chunk_metadata or '{}')
        print(f'  chunk_index={c.chunk_index}, len={len(c.chunk_text)}, pasal={meta.get(\"pasal\",\"-\")}, ayat={meta.get(\"ayat\",\"-\")}')
else:
    print('Tidak ada dokumen peraturan')
db.close()
" 2>&1
```

Expected: panjang chunk bervariasi, mayoritas antara 200–900 karakter untuk peraturan. Tidak boleh ada chunk dengan `len > 900` kecuali dari peraturan yang ayatnya sangat panjang dan sudah di-split.

---

- [ ] **Step 5: Spot-check BM25 search_text tidak mengandung judul_dokumen**

```bash
cd backend
venv/Scripts/python -c "
import pickle
from pathlib import Path

bm25_path = Path('data/bm25_index.pkl')
with open(bm25_path, 'rb') as f:
    data = pickle.load(f)

docs = data.get('documents', [])
if docs:
    sample = docs[0]
    print('Sample doc keys:', list(sample.keys()))
    print('Sample metadata keys:', list(sample.get('metadata', {}).keys()))
    print()
    # BM25 corpus tersimpan dalam bm25 object, tidak mudah diinspeksi langsung
    # Tapi kita bisa verifikasi bahwa metadata masih lengkap di documents list
    meta = sample.get('metadata', {})
    print('judul_dokumen:', meta.get('judul_dokumen', '(tidak ada)'))
    print('pasal:', meta.get('pasal', '(tidak ada)'))
    print('ayat:', meta.get('ayat', '(tidak ada)'))
    print()
    print(f'Total dokumen di BM25: {len(docs)}')
" 2>&1
```

Expected: `judul_dokumen` tetap ada di `metadata` (field metadata tidak dihapus — hanya tidak dimasukkan ke search_text BM25). `pasal` dan `ayat` juga ada.

---

- [ ] **Step 6: Jalankan health check backend**

```bash
cd backend
venv/Scripts/python -c "
import asyncio
import sys
sys.path.insert(0, '.')
from app.database import SessionLocal
from app.models.db_models import Chunk
db = SessionLocal()
count = db.query(Chunk).count()
print(f'DB chunks: {count}')
db.close()
print('Database OK')
" 2>&1
```

Expected: jumlah chunk sesuai dengan hasil Step 3.

---

- [ ] **Step 7: Commit verifikasi (opsional — jika ada perubahan minor saat re-ingest)**

Jika re-ingest menghasilkan perubahan pada file `backend/data/bm25_index.pkl` atau `backend/data/spbe_rag.db` (binary files), **jangan commit file binary tersebut**. Hanya commit jika ada perbaikan kode yang ditemukan saat verifikasi.

Jika semua verifikasi lulus tanpa perubahan kode:
```bash
cd d:/aqil/pusdatik
git status
# Pastikan tidak ada file kode yang uncommitted
# File binary (*.pkl, *.db) tidak perlu di-commit
```

---

## Ringkasan Perubahan

| Task | File | Baris Kritis | Efek |
|---|---|---|---|
| 1 | `config.py` | 4 konstanta baru | Konfigurasi terpusat |
| 1 | `structured_chunker.py` | 4 modul-konstanta, 15 call-site | Chunk size sesuai tipe |
| 2 | `rebuild_bm25.py` | `build_bm25_search_text()` | BM25 IDF lebih akurat |
| 3 | — | `reingest_all.py` | Semua dokumen di-chunk ulang |
