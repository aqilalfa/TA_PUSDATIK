# 📋 Log Perubahan Sistem RAG Pusdatik

> Folder ini mendokumentasikan **semua perubahan** yang dilakukan selama sesi refactoring.  
> Dibuat untuk referensi dan brainstorming bersama.

---

## 🗂️ Daftar File yang Diubah

| No | File | Kategori | Sesi | Status |
|----|------|----------|------|--------|
| 1 | `backend/app/models/db_models.py` | Database ORM | Sesi 1 | ✅ Selesai |
| 2 | `backend/app/main.py` | Startup & Migration | Sesi 1 | ✅ Selesai |
| 3 | `backend/app/core/ingestion/document_manager.py` | Core Logic | Sesi 1 | ✅ Selesai |
| 4 | `backend/app/api/documents.py` | API Route | Sesi 1 | ✅ Selesai |
| 5 | `backend/app/api/routes/health.py` | API Route | Sesi 1 | ✅ Selesai |
| 6 | `backend/app/core/rag/langchain_engine.py` | RAG Engine | Sesi 1 & 2 | ✅ Selesai |
| 7 | `start_full.bat` | Startup Script | Sesi 1 | ✅ Selesai |
| 8 | `backend/scripts/migrations/001_add_doc_metadata_columns.py` | Migration | Sesi 1 | ✅ Baru Dibuat |
| 9 | `backend/app/api/routes/chat.py` | Streaming & Validation | Sesi 3 | ✅ Selesai |
| 10 | `frontend/src/views/ChatView.vue` | Frontend SSE Handling | Sesi 3 | ✅ Selesai |
| 11 | `frontend/src/services/api.js` | Frontend Service Layer | Sesi 4 | ✅ Baru Dibuat |
| 12 | `frontend/src/services/chatService.js` | Frontend Service Layer | Sesi 4 | ✅ Baru Dibuat |
| 13 | `frontend/src/services/documentService.js` | Frontend Service Layer | Sesi 4 | ✅ Baru Dibuat |
| 14 | `frontend/src/components/chat/*` | Frontend Component Split | Sesi 4 | ✅ Selesai |
| 15 | `frontend/src/assets/chat-view.css` | Frontend Styling Modularization | Sesi 4 | ✅ Baru Dibuat |
| 16 | `frontend/src/views/DocumentsView.vue` | Frontend API Refactor | Sesi 4 | ✅ Selesai |
| 17 | `frontend/src/views/DocumentDetailView.vue` | Frontend API Refactor | Sesi 4 | ✅ Selesai |
| 18 | `frontend/src/views/HomeView.vue` | Frontend Tailwind Cleanup | Sesi 4 | ✅ Selesai |
| 19 | `frontend/package.json` | Dependency Cleanup | Sesi 4 | ✅ Selesai |
| 20 | `edited/fase.md` | Roadmap Update | Sesi 4 | ✅ Selesai |
| 21 | `edited/13_fase3_frontend_refactor.md` | Dokumentasi FASE 3 | Sesi 4 | ✅ Baru Dibuat |
| 22 | `edited/19_laporan_sesi_tabel_2026-04-19.md` | Laporan Sesi Query Tabel | Sesi 5 | ✅ Baru Dibuat |
| 23 | `edited/20_laporan_solusi_sistematik_quality_gate_2026-04-20.md` | Laporan Progres Solusi Sistematik (Done vs Pending) | Sesi 6 | ✅ Baru Dibuat |

---

## 📁 Isi Folder `edited/`

```
edited/
├── README.md                          ← index semua perubahan (file ini)
│
│── [SESI 1 — Database Refactoring & Core Fixes]
├── 01_db_models.md                    ← +6 kolom baru di Document, +1 di Chunk
├── 02_main_startup.md                 ← auto-run migration saat startup
├── 03_document_manager.md             ← 10 method diganti dari raw SQL ke ORM
├── 04_api_documents.md                ← API tidak langsung ke database lagi
├── 05_health_route.md                 ← fix text() wrapper SQLAlchemy 2.x
├── 06_langchain_engine.md             ← ROOT CAUSE jawaban kosong → fix key metadata
├── 07_start_full_bat.md               ← fix entry point + venv python path
├── 08_migration_script.md             ← script migrasi database (file baru)
│
│── [SESI 1 — Analisis & Brainstorming]
├── 09_brainstorming.md                ← status sistem & rencana Phase 2
├── 10_full_analysis.md                ← analisis menyeluruh semua bug aktif
│
│── [SESI 2 — RAG Engine & Model Fix]
├── 11_langchain_engine_sesi2.md       ← fix qwen3.5:4b 0-token + duplikat section
│
│── [SESI 3 — FASE 2 Pipeline Upgrade]
├── 12_fase2_pipeline_upgrade.md       ← hybrid retrieval + RRF + reranker + validation
│
│── [SESI 4 — FASE 3 Frontend Refactor]
└── 13_fase3_frontend_refactor.md      ← service layer + component split + markdown security
```

---

## 🎯 Ringkasan Tujuan Refactoring

### Masalah Awal (Before)
- Database diakses via **2 cara berbeda**: Raw SQL (`get_connection()`) DAN SQLAlchemy ORM
- Entry point server salah: mengarah ke modul yang **tidak ada** (`app.api.server_full`)
- RAG Engine menggunakan **nama field yang salah** → jawaban selalu kosong
- Health check error di setiap startup
- `qwen3.5:4b` tidak bisa digunakan → 0 token dihasilkan
- Format section sources tampil duplikat: `"Pasal Pasal 9"`, `"Ayat (Ayat (1))"`

### Hasil Akhir (After)
- ✅ **Satu jalur database**: hanya SQLAlchemy ORM
- ✅ **Server bisa jalan**: entry point diperbaiki ke `app.main`
- ✅ **Chat memberikan jawaban**: metadata key diperbaiki
- ✅ **Health check hijau**: database, Qdrant, semua healthy
- ✅ **Semua model bisa dipakai**: `qwen2.5:3b`, `qwen3.5:4b`, `qwen3:8b`, dll
- ✅ **Sources UI bersih**: format section tidak duplikat lagi

---

## 🔄 Urutan Eksekusi Perubahan

```
═══════════════════════════════════════
SESI 1 — Database Refactoring & Core Fixes
═══════════════════════════════════════

Phase 0: Fix server agar bisa jalan
  └── start_full.bat
        ├── entry point: server_full → app.main
        └── python: global → venv\Scripts\python.exe

Phase 1: Konsolidasi Database (hapus raw SQL)
  ├── db_models.py      → tambah 6 kolom baru di ORM
  ├── main.py           → migration otomatis saat startup
  ├── document_manager.py → 10 method: raw SQL → ORM
  └── api/documents.py  → hapus shortcut langsung ke database

Phase 1b: Fix Core Bugs
  ├── health.py         → fix text() SQLAlchemy 2.x
  └── langchain_engine.py (v1)
        ├── metadata key: judul_dokumen → document_title
        └── _format_context: tambah hierarchy bab/pasal/ayat

═══════════════════════════════════════
SESI 2 — RAG Engine & Model Fix
SESI 3 — FASE 2 RAG Pipeline Upgrade
SESI 4 — FASE 3 Frontend Refactor
═══════════════════════════════════════

Phase 2a: Fix Model Thinking Mode
  └── langchain_engine.py (v2)
        ├── _get_llm: deteksi model qwen3/qwen3.5
        ├── reasoning=False → disable thinking mode
        ├── timeout: 300s → 600s (support model besar)
        └── format section: cek prefix sebelum menambah

Phase 2b: Aktivasi Pipeline RAG Hybrid
  ├── langchain_engine.py (v3)
  │     ├── query expansion aktif (`expand_query`)
  │     ├── hybrid retrieval: vector + BM25
  │     ├── RRF fusion untuk candidate ranking
  │     └── cross-encoder reranker (`BAAI/bge-reranker-base`)
  ├── chat.py
  │     └── answer validation (`event: validation` + payload `validation`)
  ├── ChatView.vue
  │     └── render validation warnings dari SSE
  └── konsolidasi formatter
        ├── hapus duplikat `format_context()` di prompts.py
        └── hapus duplikat `format_context_with_parent()` di formatting.py

  Phase 3: Frontend Refactor
    ├── services/
    │     ├── api.js (axios base + error parser)
    │     ├── chatService.js (model/session/chat SSE)
    │     └── documentService.js (upload/preview/save/sync/chunks)
    ├── components/chat/
    │     ├── ChatSidebar.vue
    │     ├── ChatInput.vue
    │     ├── MessageBubble.vue
    │     └── SourceCard.vue
    ├── ChatView.vue
    │     └── orchestration-only + import `chat-view.css`
    ├── Markdown
    │     └── custom parser → `marked + DOMPurify`
    └── Cleanup
      ├── hapus Tailwind/PostCSS dependencies
      └── hapus `tailwind.config.js` + `postcss.config.js`
```

---

## 📌 Catatan Cepat untuk Brainstorming

### Model yang Tersedia di Ollama
| Model | Ukuran | Kecepatan | Catatan |
|-------|--------|-----------|---------|
| `qwen2.5:3b` | 1.9 GB | ⚡ Cepat | Terbaik untuk dev/test |
| `qwen2.5:3b-instruct` | 1.9 GB | ⚡ Cepat | Sama, versi instruct |
| `qwen3.5:4b` | 3.4 GB | 🐢 Sedang | Thinking mode dinonaktifkan |
| `qwen3.5:9b` | 6.6 GB | 🐢 Lambat | Butuh RAM besar |
| `qwen2.5:7b-instruct` | 4.7 GB | 🐢 Sedang | Pilihan terbaik untuk produksi |

### Fokus Berikutnya (Sesi Berikutnya)
1. **UI Citation/Validation UX** — tampilkan warning validation lebih terstruktur per jawaban
2. **Observability** — tambah metrik retrieval (vector hit, bm25 hit, rerank latency)
3. **Frontend Testing** — tambah unit test untuk service layer dan parser markdown
