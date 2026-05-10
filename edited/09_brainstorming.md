# 🧠 Brainstorming — Status Sistem & Rencana Ke Depan

## Status Saat Ini

### ✅ Yang Sudah Selesai (Phase 0 & 1)

| Komponen | Status |
|----------|--------|
| Server bisa dijalankan | ✅ Selesai |
| Database: satu jalur (ORM only) | ✅ Selesai |
| Chat memberikan jawaban | ✅ Selesai |
| Sumber dokumen tampil dengan benar | ✅ Selesai |
| Health check tidak error | ✅ Selesai |

### 🟡 Masih Perlu Diperhatikan

| Komponen | Masalah | Prioritas |
|----------|---------|-----------|
| Frontend port tidak stabil | Kadang 5173, kadang 5174 | Medium |
| Model LLM hanya `qwen2.5:3b` | Kecil, kadang kurang detail | Medium |
| Retrieval hanya vector search | Belum BM25 hybrid | High (Phase 2) |
| Tidak ada reranking | Hasil retrieval bisa tidak relevan | High (Phase 2) |

---

## 🚀 Rencana Phase 2 — RAG Pipeline Upgrade

### 2A: Aktifkan Hybrid Search (BM25 + Vector)
**Tujuan:** Hasil retrieval lebih akurat, terutama untuk query yang spesifik (nama pasal, nomor peraturan).

```
Sekarang: Query → Vector Search → Top 5
Target:   Query → BM25 Search + Vector Search → RRF Fusion → Top 5
```

File yang perlu diubah:
- `langchain_engine.py` → tambah BM25 retriever
- Mungkin perlu install `rank_bm25` library

---

### 2B: Tambah Reranking
**Tujuan:** Dari 10 dokumen kandidat, pilih 5 yang paling relevan menggunakan model khusus.

```
BM25 + Vector → 10 kandidat → Cross-Encoder Reranker → Top 5 terbaik → LLM
```

Model yang akan dipakai: `bge-reranker-v2-m3` (sudah disebutkan di start_full.bat).

---

### 2C: Validasi Jawaban
**Tujuan:** Jika LLM memberikan jawaban yang tidak ada di dokumen, sistem bisa mendeteksi dan minta klarifikasi.

---

## 📁 Struktur Folder `edited/` (Quick Reference)

```
edited/
├── README.md               ← index semua perubahan
├── 01_db_models.md         ← +6 kolom baru di Document, +1 di Chunk
├── 02_main_startup.md      ← auto-run migration saat startup  
├── 03_document_manager.md  ← 10 method diganti dari raw SQL ke ORM
├── 04_api_documents.md     ← API tidak langsung ke database lagi
├── 05_health_route.md      ← fix text() wrapper SQLAlchemy 2.x
├── 06_langchain_engine.md  ← ROOT CAUSE jawaban kosong → fix key metadata
├── 07_start_full_bat.md    ← fix entry point + venv python path
├── 08_migration_script.md  ← script migrasi database (file baru)
└── 09_brainstorming.md     ← file ini (status & rencana)
```
