# 🔍 Analisis Kritis Kualitas RAG — SPBE RAG System

> **Tanggal:** 13 April 2026  
> **Model:** qwen3.5:4b (4.7B parameters)  
> **Data:** 9 dokumen, 1578 chunks (fresh re-ingestion)

---

## Demo Browser Test

![RAG Quality Test Recording](/C:/Users/Pluto%2009/.gemini/antigravity/brain/e0b996fa-31ff-4eb9-b6c2-cd47a6e7604a/rag_quality_demo.webp)

---

## 📊 Ringkasan Hasil Test

| # | Pertanyaan | Verdict | Waktu | Masalah |
|---|-----------|---------|-------|---------|
| 1 | Definisi SPBE menurut Perpres 95/2018 | ⚠️ **POOR** | 113s | Definisi di chunk 4 ADA tapi tidak di-retrieve |
| 2 | Isi Pasal 3 Perpres 95/2018 | ❌ **FAIL** | 35s | Pasal 3 tidak terambil, chunk yang benar tidak muncul |
| 3 | Domain evaluasi SPBE | ✅ **GOOD** | 84s | 4 domain ditemukan dengan benar dari Pedoman + Laporan |

---

## Test 1: "Apa definisi SPBE menurut Perpres 95 Tahun 2018?"

![Hasil Pertanyaan 1](/C:/Users/Pluto%2009/.gemini/antigravity/brain/e0b996fa-31ff-4eb9-b6c2-cd47a6e7604a/q1_definisi_spbe.png)

### Jawaban AI
AI **gagal memberikan definisi eksplisit** dari Pasal 1. Alih-alih, AI menyebutkan komponen SPBE dari pasal lain (Pasal 4).

### Fakta dari Dokumen Asli
Chunk 4 (metadata: `BAB I > Pasal 1`) mengandung **PERSIS** definisi yang diminta:

```
Dalam Peraturan Presiden ini yang dimaksud dengan:
1. Sistem Pemerintahan Berbasis Elektronik yang selanjutnya 
   disingkat SPBE adalah penyelenggaraan pemerintahan yang 
   memanfaatkan teknologi informasi...
```

### Root Cause
- ✅ **Data BENAR** — chunk 4 ada di Qdrant dengan metadata `pasal=Pasal 1`
- ❌ **Retrieval GAGAL** — semantic search tidak meng-retrieve chunk ini ke top-5
- ❌ **BM25 MATI** — keyword search "Pasal 1" seharusnya langsung match, tapi BM25 gagal rebuild (modul `bm25_retriever` tidak ditemukan)

### Sources yang Diambil
1. Pedoman 3/2024 (BAB I - Latar Belakang) — kurang relevan
2. Perpres 95/2018 (Lampiran) — bagian lampiran, bukan batang tubuh
3. Perpres 95/2018 (tanpa section) — tidak jelas
4. Perpres 95/2018 (BAB II) — bukan BAB I
5. Perpres 95/2018 (BAB II > Pasal 4) — bukan Pasal 1

---

## Test 2: "Apa isi Pasal 3 Perpres 95 Tahun 2018?"

![Hasil Pertanyaan 2](/C:/Users/Pluto%2009/.gemini/antigravity/brain/e0b996fa-31ff-4eb9-b6c2-cd47a6e7604a/q2_pasal3.png)

### Jawaban AI
AI menyatakan tegas: **"tidak ditemukan"** isi Pasal 3 dari dokumen yang tersedia.

### Fakta dari Dokumen Asli
Pasal 3 Perpres 95/2018 berisi tentang ASAS penyelenggaraan SPBE. **NAMUN** — setelah saya periksa metadata chunk Perpres 95 (chunk 0-7), metadata `pasal` melompat dari kosong langsung ke `Pasal 4` (chunk 2). **Pasal 1, 2, dan 3 memang ada di chunk 4-6 tapi parser hanya tag Pasal 1** — yang berarti:

> [!WARNING]
> **Parser tidak mendeteksi Pasal 2 dan 3** dalam teks OCR Perpres 95! Ini masalah di tahap **chunking/parsing**, bukan retrieval.

### Sources yang Diambil (Salah Total)
1. PP 71/2019 (BAB XI > Pasal 100) — dokumen berbeda!
2. Perpres 95/2018 (Lampiran)
3. PP 71/2019 (BAB XI > Pasal 47)
4. Perpres 82/2023 (Pasal 4)
5. Pedoman 3/2024 (Dasar Hukum)

**Validation Warning muncul:** _"Kemungkinan Pasal yang tidak ada di konteks: 3"_ — validation bekerja dengan benar!

---

## Test 3: "Apa saja domain dalam evaluasi SPBE?"

![Hasil Pertanyaan 3](/C:/Users/Pluto%2009/.gemini/antigravity/brain/e0b996fa-31ff-4eb9-b6c2-cd47a6e7604a/q3_domain.png)

### Jawaban AI
AI **berhasil mengidentifikasi 4 domain** dengan benar:
1. Kebijakan Internal SPBE
2. Tata Kelola SPBE  
3. Manajemen SPBE
4. Layanan SPBE

Juga menyebutkan sub-domain Arsitektur SPBE (Proses Bisnis, Data dll).

### Sources (Akurat)
1. Laporan Evaluasi 2024 (Ringkasan Eksekutif)
2. Pedoman 3/2024 (BAB III - Tata Cara Penilaian)
3. PP 71/2019 (BAB I > Pasal 1)
4. Pedoman 3/2024 (BAB II - Instrumen)
5. Pedoman 3/2024 (BAB III - Tata Cara Penilaian)

---

## 🔬 Analisis Root Cause — Mengapa Kualitas Kurang

### 1. BM25 Index Mati (KRITIS)

```
ModuleNotFoundError: No module named 'app.core.rag.bm25_retriever'
```

Modul `BM25Retriever` yang dipanggil oleh `reingest_all.py` **tidak ada di filesystem**. Tanpa BM25:
- Pencarian `"Pasal 3"` hanya mengandalkan **vector similarity** yang buruk untuk angka/nomor
- Keyword exact match tidak bekerja sama sekali
- **Dampak:** 2 dari 3 pertanyaan gagal

### 2. Semantic Search Terdilusi oleh Dokumen Irrelevan

Dengan 1578 chunks dari 9 dokumen berbeda, vector search cenderung mengeluarkan dokumen yang "mirip semantik" tapi dari **dokumen yang salah** (PP 71/2019 alih-alih Perpres 95/2018). Ini karena:
- Semua dokumen SPBE punya vocabulary yang sangat mirip
- Tanpa BM25 untuk keyword precision, recall jadi noise

### 3. OCR Quality Issues

Teks dari Perpres 95 memiliki artefak OCR:
```
"PEI!ryELENGGARAAN SISTEM DAN TRANSAKSI ELEKT..."  (PP 71)
"Pasal 4" wrongly tagged to chunk tentang "MEMUTUSKAN"
```

Ini menurunkan kualitas chunks dan metadata yang dihasilkan.

### 4. Metadata Parsing Gaps

Parser lompat dari Pembukaan → `Pasal 4` tanpa mendeteksi Pasal 1-3 secara benar pada beberapa dokumen.

---

## 📋 Prioritas Perbaikan (Sesi Berikutnya)

| # | Fix | Dampak | Effort |
|---|-----|--------|--------|
| **1** | **Buat modul `bm25_retriever.py`** atau ganti import path di reingest_all | 🔴 Kritis — tanpa BM25, keyword search mati total | Sedang |
| **2** | **Rebuild BM25 index** setelah fix modul | 🔴 Kritis — mengaktifkan hybrid search | Ringan |
| **3** | Perbaiki parser untuk deteksi Pasal 1-3 dari teks OCR | 🟡 Medium — meningkatkan metadata accuracy | Sedang |
| **4** | Tambah Marker CPU fallback yang benar (CUDA_VISIBLE_DEVICES="") | 🟡 Medium — kualitas OCR lebih baik | Ringan |
| **5** | Sinkronisasi UI "Kelola Dokumen" dengan Qdrant | 🟢 Low — cosmetic, fungsionalitas tidak terpengaruh | Ringan |

> [!IMPORTANT]
> **Fix #1 dan #2 adalah game-changer.** Tanpa BM25, sistem hanya mengandalkan vector search yang sangat lemah untuk pertanyaan spesifik tentang nomor pasal. Setelah BM25 aktif, kualitas diperkirakan meningkat **signifikan** untuk semua pertanyaan yang menyebutkan lokasi spesifik (Pasal X, BAB Y, Indikator Z).

---

## Yang Sudah Bekerja Baik ✅

1. **Pipeline end-to-end** — dari pertanyaan sampai jawaban streaming berfungsi
2. **Model qwen3.5:4b** — streaming lancar, `reasoning=False` bekerja  
3. **Cross-encoder reranker** — aktif dan berfungsi (BAAI/bge-reranker-base)
4. **Answer validation** — mendeteksi pasal yang tidak ada di konteks
5. **Citation numbering** — referensi [1]-[5] akurat dan di-link ke sources
6. **Format section** — tidak ada lagi duplikat "Pasal Pasal"
7. **Frontend refactor** — komponen terpisah, service layer, build sukses
