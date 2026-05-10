# 📋 Plan Perbaikan Kualitas RAG

> **Dibuat:** 14 April 2026  
> **Konteks:** Hasil analisis kritis menunjukkan skor 1/3 (33%) pertanyaan dijawab dengan benar  
> **Prioritas:** Kritis — sistem tidak dapat digunakan secara andal sebelum perbaikan ini

---

## 🔍 Latar Belakang — Mengapa RAG Saat Ini Kurang Berkualitas

Setelah re-ingestion 1578 chunks dari 9 dokumen dan browser test dengan 3 pertanyaan benchmark menggunakan model `qwen3.5:4b`, ditemukan bahwa:

### Hasil Test (13 April 2026)

| Pertanyaan | Verdict | Keterangan |
|-----------|---------|-----------|
| Definisi SPBE (Perpres 95/2018) | ⚠️ POOR | Jawaban ambigu, tidak kutip Pasal 1 secara langsung |
| Isi Pasal 3 Perpres 95/2018 | ❌ FAIL | AI bilang "tidak ditemukan", padahal Pasal 3 ada di dokumen |
| Domain evaluasi SPBE | ✅ GOOD | 4 domain teridentifikasi benar dari Pedoman + Laporan |

**Skor: 1 dari 3 (33%)** — tidak memadai untuk sistem RAG yang fungsional.

---

## 🔬 Root Cause Analysis

### Masalah 1 — BM25 Index Tidak Ada (KRITIS ⚠️)

**Bukti:**
```
ModuleNotFoundError: No module named 'app.core.rag.bm25_retriever'
```

`reingest_all.py` mencoba import dari class `BM25Retriever` di modul yang tidak ada. Akibatnya, setiap re-ingestion **gagal membuat BM25 index**. File `data/bm25_index.pkl` tidak pernah dibuat.

**Dampak konkret:**
- Di `langchain_engine.py`, `_load_bm25()` dipanggil saat startup — jika file tidak ada, ia di-skip dengan `logger.warning`
- `_bm25_search()` selalu return `[]` (list kosong)
- Pipeline hybrid search hanya jalan dengan **vector only** — bukan hybrid
- Query seperti `"Pasal 3"` atau `"Pasal 1"` yang mengandung nomor tidak dapat di-match secara exact

**Solusi:** Rebuild ulang `rebuild_bm25.py` dengan format yang compatible dengan `langchain_engine.py` (tidak perlu class `BM25Retriever`, cukup inline).

---

### Masalah 2 — OCR Missing Beberapa Pasal (KRITIS ⚠️)

**Bukti dari analisis chunk Perpres 95 Tahun 2018:**

```
chunk 2: meta={pasal=Pasal 4, bab=kosong}  → text: "MEMUTUSKAN: PERATURAN PRESIDEN..."
chunk 3: meta={bab=BAB I, pasal=kosong}    → text: "KETENTUAN UMUM"
chunk 4: meta={bab=BAB I, pasal=Pasal 1}   → text: "Dalam Peraturan Presiden ini..."
```

Pasal 1 memang terdeteksi (chunk 4), tetapi **Pasal 2 dan Pasal 3 tidak memiliki chunk tersendiri** dengan `pasal=Pasal 2` atau `pasal=Pasal 3`. Teks Pasal 2 dan 3 mungkin tergabung ke chunk Pasal 1 karena OCR layout tidak mengandung baris `"Pasal 2"` atau `"Pasal 3"` yang berdiri sendiri (teks OCR PDF langsung dari text layer, tapi header pasal bisa terlewat).

**Dampak:**
- Query "Pasal 3" tidak ada chunk dengan metadata `pasal=Pasal 3`
- Vector search juga tidak menemukan karena vocabulary "Pasal 3" tidak ada dalam chunk text manapun

**Solusi:** Periksa teks asli Perpres 95 Pasal 3 dan tambahkan strategi parsing khusus untuk menangkap pasal yang terlewat dari teks OCR.

---

### Masalah 3 — Semantic Search Bias ke Dokumen Noise (MEDIUM 🟡)

**Bukti:**
Untuk pertanyaan "Isi Pasal 3 Perpres 95/2018", sources yang diambil:
1. PP 71/2019 Pasal 100 ← dokumen berbeda!
2. Perpres 95/2018 Lampiran
3. PP 71/2019 Pasal 47 ← dokumen berbeda!
4. Perpres 82/2023 Pasal 4
5. Pedoman 3/2024

**Akar masalah:** Semua dokumen SPBE menggunakan vocabulary yang sangat mirip. Vector embedding tidak dapat membedakan "Pasal 3 Perpres 95" vs "Pasal 3 PP 71" karena secara semantic mirip.

**Solusi:** BM25 yang aktif akan memberikan bobot lebih besar ke chunk yang mengandung exact string "Perpres 95" + "Pasal 3". RRF fusion kemudian menggabungkan kedua sinyal.

---

### Masalah 4 — `reingest_all.py` Menggunakan Class Non-Existent (KRITIS ⚠️)

**Kode bermasalah di `reingest_all.py` baris 41-56:**
```python
from app.core.rag.bm25_retriever import BM25Retriever  # ← MODULE TIDAK ADA!

retriever = BM25Retriever()
retriever.build_index(documents, doc_id_field="id", text_field="text")
retriever.save_index(path=bm25_path)
```

Sedangkan `rebuild_bm25.py` (script standalone) sudah benar formatnya — langsung pakai `rank_bm25.BM25Okapi` dan `pickle.dump`. Format ini juga yang diharapkan `langchain_engine._load_bm25()`.

---

### Masalah 5 — Chunk Size Terlalu Kecil untuk Dokumen Legal (MEDIUM 🟡)

**Bukti dari summary re-ingestion:**
```
[peraturan] Permenpan RB Nomor 59 Tahun 2020: 75 chunks (avg 1033, max 1918 chars)
```

Chunk rata-rata 1033 char, max 1918 char — **jauh melebihi batas 600 char** yang dikonfigurasi. Ini terjadi karena dokumen Permenpan 59 mengandung indikator panjang yang tidak dipecah dengan benar. Akibatnya beberapa chunks sangat panjang dan gagal di-truncate sesuai setting.

---

## 🛠️ Plan Perbaikan — 5 Item Berurutan

### FASE A — Fix Kritikal (Harus Dilakukan Sebelum Test Lagi)

---

#### A1. Fix `reingest_all.py` — Hapus Dependensi BM25Retriever

**File:** `backend/scripts/reingest_all.py`  
**Perubahan:** Ganti fungsi `rebuild_bm25_index()` agar menggunakan implementasi inline dari `rebuild_bm25.py` (bukan import class yang tidak ada).

**Before (rusak):**
```python
def rebuild_bm25_index(db):
    from app.core.rag.bm25_retriever import BM25Retriever   # ← ERROR!
    retriever = BM25Retriever()
    retriever.build_index(documents, ...)
    retriever.save_index(path=bm25_path)
```

**After (benar):**
```python
def rebuild_bm25_index(db):
    from rank_bm25 import BM25Okapi
    import pickle, re
    chunks = db.query(Chunk).all()
    corpus, documents = [], []
    for c in chunks:
        tokens = re.findall(r"\b\w+\b", (c.chunk_text or "").lower())
        corpus.append(tokens)
        meta = json.loads(c.chunk_metadata) if c.chunk_metadata else {}
        documents.append({"text": c.chunk_text, "metadata": meta})
    bm25 = BM25Okapi(corpus)
    bm25_path = Path(__file__).parent.parent / "data" / "bm25_index.pkl"
    with open(bm25_path, "wb") as f:
        pickle.dump({"bm25": bm25, "documents": documents}, f)
```

**Estimasi:** 10 menit  
**Dampak:** BM25 index AKAN dibuat saat re-ingestion berikutnya

---

#### A2. Jalankan `rebuild_bm25.py` Standalone — Bangun Index Sekarang

Karena data sudah ada di DB (1578 chunks), tidak perlu re-ingest ulang. Cukup jalankan script rebuild standalone yang sudah benar:

```bash
cd backend
.\venv\Scripts\python.exe scripts\rebuild_bm25.py
```

Verifikasi hasil:
```bash
.\venv\Scripts\python.exe -c "import pickle; d=pickle.load(open('data/bm25_index.pkl','rb')); print(len(d['documents']))"
# Output harus: 1578
```

**Estimasi:** 2 menit  
**Dampak:** Hybrid search langsung aktif, test ulang diperkirakan membaik signifikan

---

#### A3. Investigasi Pasal yang Hilang di Perpres 95

**File:** `backend/app/core/ingestion/json_structure_parser.py`  
**Tujuan:** Memahami mengapa Pasal 2 dan Pasal 3 tidak terdeteksi sebagai chunk terpisah.

Script investigasi cepat:
```python
# di backend/
from app.database import SessionLocal
from app.models.db_models import Chunk
import json

db = SessionLocal()
chunks = db.query(Chunk).filter(Chunk.document_id == 7).all()
for c in chunks[:20]:
    meta = json.loads(c.chunk_metadata or '{}')
    print(f"chunk {c.chunk_index:3d} | bab={meta.get('bab',''):<8} | pasal={meta.get('pasal',''):<12} | {c.chunk_text[:80]}")
```

Jika Pasal 2 dan 3 ada dalam teks tapi tidak dideteksi, kemungkinan karena teks OCR tidak memiliki baris `"Pasal 2"` secara terpisah (mungkin inline seperti `"Pasal 2 SPBE diselenggarakan..."` tanpa baris kosong sebelumnya).

**Fix di `_RE_PASAL`:**
```python
# Saat ini — hanya match di awal baris:
_RE_PASAL = re.compile(r"^\s*(?:#+\s*)?Pasal\s+(\d+)\s*(.*?)$", re.MULTILINE | re.IGNORECASE)
```

Mungkin perlu tambahkan toleransi untuk pasal yang ditulis setelah teks lain di baris yang sama, atau cek format OCR aslinya.

**Estimasi:** 30-60 menit (tergantung kompleksitas teks OCR)

---

### FASE B — Perbaikan Lanjutan (Setelah FASE A Selesai)

---

#### B1. Fix Chunk Size Permenpan 59 — Chunks Terlalu Besar

**File:** `backend/app/core/ingestion/structured_chunker.py`  
**Masalah:** Chunks Permenpan 59 rata-rata 1033 char (batas 600 char terlewati)  
**Penyebab:** Indikator SPBE di Permenpan 59 sangat panjang tapi tidak dipecah karena splitter tidak tahu kapan harus cut

**Perlu dicek:** Apakah `split_text_with_overlap()` dipanggil dengan benar untuk tipe dokumen ini, atau ada path yang melewati splitting sama sekali.

**Estimasi:** 30 menit

---

#### B2. Sinkronisasi UI "Kelola Dokumen" dengan Status Aktual

**File:** Frontend `DocumentsView.vue`  
**Masalah:** UI mungkin menampilkan dokumen dari DB lama yang sudah dihapus saat re-ingestion  
**Solusi:** Pastikan endpoint `/api/documents` hanya return dokumen yang `status = 'processed'` dan chunk count > 0

**Estimasi:** 15 menit

---

## 📊 Estimasi Dampak Setelah Perbaikan

| Perbaikan | Pertanyaan yang Berhasil (prediksi) |
|-----------|-------------------------------------|
| Sekarang (tanpa BM25) | 1/3 (33%) |
| Setelah A1 + A2 (BM25 aktif) | 2.5/3 (83%) |
| Setelah A1 + A2 + A3 (Pasal terdeteksi) | 3/3 (100%) |

---

## 📁 File yang Akan Diubah

| File | Jenis Perubahan | Fase |
|------|-----------------|------|
| `scripts/reingest_all.py` | Fix fungsi `rebuild_bm25_index()` | A1 |
| `data/bm25_index.pkl` | Dibuat baru via `rebuild_bm25.py` | A2 |
| `app/core/ingestion/json_structure_parser.py` | Fix regex deteksi Pasal | A3 |
| `app/core/ingestion/structured_chunker.py` | Fix chunk size terlalu besar | B1 |
| Frontend `DocumentsView.vue` | Filter status dokumen | B2 |

---

## ✅ Checklist Eksekusi

- [x] **A1** — Fix `rebuild_bm25_index()` di `reingest_all.py`
- [x] **A2** — Jalankan `scripts/rebuild_bm25.py` dan verifikasi 1580 docs (setelah re-ingest Perpres 95)
- [x] **A2b** — Restart backend, verifikasi log: `BM25 loaded (1580 chunks)`
- [x] **A2c** — Test ulang 3 pertanyaan benchmark via endpoint chat stream (jalur backend yang sama dengan browser)
- [x] **A3** — Investigasi teks Pasal 2/3 Perpres 95 dan fix parser/chunking/retrieval
- [x] **A3b** — Re-ingest HANYA Perpres 95
- [x] **B1** — Investigasi dan fix chunk size Permenpan 59
- [x] **B2** — Sinkronisasi UI Kelola Dokumen

---

## 📌 Catatan Penting

> **Yang TIDAK perlu diubah:**  
> - `langchain_engine.py` — BM25 load sudah benar, hanya butuh file-nya ada  
> - Pipeline streaming — sudah berfungsi dengan baik  
> - Reranker — sudah berjalan (BAAI/bge-reranker-base)  
> - Answer validation — sudah berfungsi (mendeteksi Pasal tidak ada di konteks)

> **Urutan eksekusi penting:** A1 harus selesai sebelum A2, dan A2 sebelum test ulang.  
> Fase B bisa dilakukan secara paralel atau di sesi berikutnya.
