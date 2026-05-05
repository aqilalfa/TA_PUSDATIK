# Chunking Improvement — Design Spec

**Date:** 2026-04-26
**Scope:** Backend only — `config.py`, `structured_chunker.py`, `rebuild_bm25.py`
**Trigger:** Diagnosis sesi ini — dua kelemahan struktural ditemukan yang menurunkan kualitas RAG meski tidak ada kegagalan eksplisit yang dilaporkan

---

## Problem

### Masalah 1 — Chunk Terlalu Kecil

Semua tipe dokumen menggunakan satu nilai global `CHUNK_SIZE = 600` karakter. Untuk bahasa Indonesia, 600 karakter ≈ 80–120 token. Model embedding yang digunakan (`firqaaa/indo-sentence-bert-base`) mendukung hingga 512 token — artinya setiap chunk hanya menggunakan **15–25% kapasitas representasi model**. Konteks per chunk terlalu sempit, terutama untuk laporan dan pedoman yang tidak memiliki struktur pasal/ayat.

### Masalah 2 — BM25 Corpus Terdilusi Metadata Dokumen-Level

`rebuild_bm25.py` membangun `search_text` dari gabungan teks chunk + semua metadata, termasuk `judul_dokumen`, `filename`, dan `doc_type`. Field-field ini identik untuk semua chunk dalam satu dokumen — muncul ratusan kali dalam korpus BM25. Akibatnya:
- IDF (Inverse Document Frequency) term-term tersebut mendekati 0 (tidak diskriminatif)
- Skor BM25 didominasi noise metadata, bukan konten relevan
- Query "Pasal 5 ayat 2" tersembunyi di balik noise `judul_dokumen` yang sama di setiap chunk

---

## Decisions Made

| Keputusan | Pilihan |
|---|---|
| Ukuran chunk | Per-tipe (bukan satu nilai global) |
| Peraturan: ukuran baru | 900 karakter (↑ dari 600) |
| Laporan/Pedoman/Fallback: ukuran baru | 1800 karakter (↑ dari 600) |
| Overlap scaling | Peraturan: 150 kar; Laporan/Pedoman: 200 kar |
| BM25 corpus | Hapus `judul_dokumen`, `filename`, `doc_type` — pertahankan `hierarchy`, `bab`, `bagian`, `pasal`, `ayat` |
| Backend changes | Ya — `config.py`, `structured_chunker.py`, `rebuild_bm25.py` |
| Frontend changes | Tidak ada |

### Alasan Ukuran Peraturan Tidak Sama dengan Laporan

`CHUNK_SIZE` di `chunk_peraturan()` berfungsi ganda: sebagai batas teks **dan** sebagai ambang pengelompokan ayat. Nilai 900 karakter ≈ 2–3 ayat pendek — masih granular secara hukum. Nilai 1800 karakter pada peraturan akan menggabungkan 4–6 ayat yang membahas hal berbeda dalam satu chunk, merusak presisi retrieval per pasal.

---

## Architecture

Tidak ada perubahan arsitektur — hanya parameter dan satu fungsi utilitas di `rebuild_bm25.py`. Pipeline ingestion tetap:

```
PDF → Text Extraction → JSON Parsing → Chunking (ukuran baru) → DB + Qdrant + BM25 (corpus baru)
```

---

## File Map

| File | Action | Tanggung Jawab |
|---|---|---|
| `backend/app/config.py` | **Modify** | Tambah 4 konstanta per-tipe: `CHUNK_SIZE_PERATURAN`, `CHUNK_OVERLAP_PERATURAN`, `CHUNK_SIZE_LAPORAN`, `CHUNK_OVERLAP_LAPORAN` |
| `backend/app/core/ingestion/structured_chunker.py` | **Modify** | Setiap `chunk_X()` membaca konstanta yang sesuai, bukan `CHUNK_SIZE` global |
| `backend/scripts/rebuild_bm25.py` | **Modify** | Hapus `judul_dokumen`, `filename`, `doc_type` dari `search_text`; gunakan `filter(None, [...])` |

---

## Detailed Design

### 1. `config.py` — Tambah Konstanta Per-Tipe

```python
# Existing (keep as fallback)
CHUNK_SIZE: int = 600
CHUNK_OVERLAP: int = 100
MIN_CHUNK_SIZE: int = 80

# New — per-type chunk sizes
CHUNK_SIZE_PERATURAN: int = 900
CHUNK_OVERLAP_PERATURAN: int = 150

CHUNK_SIZE_LAPORAN: int = 1800
CHUNK_OVERLAP_LAPORAN: int = 200
```

`CHUNK_SIZE = 600` dipertahankan agar tidak ada breaking change pada kode yang sudah menggunakannya di luar chunker.

---

### 2. `structured_chunker.py` — Gunakan Konstanta Per-Tipe

Setiap fungsi chunker membaca konstanta yang sesuai dari config. Tidak ada perubahan logika — hanya parameter `max_size` dan `overlap` yang diperbarui.

#### `chunk_peraturan()`
```python
from app.config import settings

MAX_SIZE = settings.CHUNK_SIZE_PERATURAN    # 900
OVERLAP  = settings.CHUNK_OVERLAP_PERATURAN  # 150
```
Semua pemanggilan `split_text_with_overlap(text, ...)` di dalam fungsi ini menggunakan `MAX_SIZE` dan `OVERLAP` lokal.

#### `chunk_pedoman_spbe()`
```python
MAX_SIZE = settings.CHUNK_SIZE_LAPORAN    # 1800
OVERLAP  = settings.CHUNK_OVERLAP_LAPORAN  # 200
```

#### `chunk_laporan_spbe()`
```python
MAX_SIZE = settings.CHUNK_SIZE_LAPORAN    # 1800
OVERLAP  = settings.CHUNK_OVERLAP_LAPORAN  # 200
```

#### `chunk_laporan()`
```python
MAX_SIZE = settings.CHUNK_SIZE_LAPORAN    # 1800
OVERLAP  = settings.CHUNK_OVERLAP_LAPORAN  # 200
```

#### `chunk_from_markdown()`
```python
MAX_SIZE = settings.CHUNK_SIZE_LAPORAN    # 1800
OVERLAP  = settings.CHUNK_OVERLAP_LAPORAN  # 200
```

**Catatan implementasi:** Jika saat ini konstanta dibaca sebagai variabel modul-level (bukan di dalam fungsi), pindahkan pembacaan ke dalam body fungsi agar menggunakan nilai yang benar per tipe. Contoh:

```python
# Sebelum (modul-level — semua fungsi pakai nilai sama)
MAX_CHUNK_SIZE = settings.CHUNK_SIZE

# Sesudah (lokal per fungsi — masing-masing pakai nilai sesuai tipe)
def chunk_peraturan(...):
    max_size = settings.CHUNK_SIZE_PERATURAN
    overlap  = settings.CHUNK_OVERLAP_PERATURAN
    ...
    parts = split_text_with_overlap(text, max_size, overlap)
```

---

### 3. `rebuild_bm25.py` — Corpus Bersih

**Sebelum:**
```python
search_text = " ".join([
    metadata.get("judul_dokumen", ""),  # ← hapus
    metadata.get("filename", ""),        # ← hapus
    metadata.get("doc_type", ""),        # ← hapus
    metadata.get("hierarchy", ""),
    metadata.get("bab", ""),
    metadata.get("bagian", ""),
    metadata.get("pasal", ""),
    metadata.get("ayat", ""),
    chunk_text,
])
```

**Sesudah:**
```python
search_text = " ".join(filter(None, [
    metadata.get("hierarchy", ""),
    metadata.get("bab", ""),
    metadata.get("bagian", ""),
    metadata.get("pasal", ""),
    metadata.get("ayat", ""),
    chunk_text,
]))
```

`filter(None, [...])` membuang string kosong sebelum join agar tidak ada double-space sia-sia dalam token BM25.

**Penting:** Perubahan ini harus diterapkan di **semua tempat** `search_text` dibangun — termasuk `reingest_all.py` jika di sana ada konstruksi BM25 tersendiri (bukan hanya memanggil `rebuild_bm25.py`). Verifikasi dengan grep `judul_dokumen` di semua script ingestion.

---

## Re-ingestion

Karena `CHUNK_SIZE` berubah, semua dokumen harus di-reingest ulang. Alur:

1. Jalankan `backend/scripts/reingest_all.py`
   - Clears DB + Qdrant
   - Re-embeds semua PDF dengan chunk size baru
   - Memanggil `rebuild_bm25.py` di akhir → otomatis menggunakan corpus baru
2. Verifikasi:
   - Jumlah chunk per dokumen **berkurang** (chunk lebih besar = lebih sedikit chunk)
   - Tidak ada chunk dengan panjang `< MIN_CHUNK_SIZE (80)` yang lolos
   - Tidak ada chunk dengan panjang `> 512 token` (validasi opsional dengan tokenizer)

**Estimasi waktu re-ingest:** 10–30 menit di GTX 1650 4GB, tergantung jumlah dokumen PDF.

---

## What Is NOT in Scope

- Perubahan logika chunking (split algorithm, table handling, preamble dedup)
- Perubahan model embedding
- Perubahan struktur database atau Qdrant schema
- Chunking adaptif berbasis token (bukan karakter)
- Frontend changes
- Penambahan tipe dokumen baru
