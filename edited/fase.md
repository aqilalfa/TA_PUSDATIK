# 🗺️ Roadmap Pengembangan — SPBE RAG System

> Dokumen ini berisi rencana lengkap semua fase pengembangan.
> Diperbarui setiap sesi. Status terakhir: **April 2026**

---

## Status Overview

```
FASE 0  ████████████████████ 100%  ✅ Selesai
FASE 1  ████████████████████ 100%  ✅ Selesai
FASE 2  ████████████████████ 100%  ✅ Selesai
FASE 3  ████████████████████ 100%  ✅ Selesai
```

---

## ✅ FASE 0 — Critical Bug Fixes
> **Status: SELESAI** | Risiko: Rendah | Estimasi: ~2 jam

Memperbaiki bug yang membuat sistem tidak bisa berjalan sama sekali.

### Yang Sudah Dikerjakan

| Step | Fix | File | Status |
|------|-----|------|--------|
| 0.1 | Entry point server salah (`server_full` → `app.main`) | `start_full.bat` | ✅ |
| 0.2 | Python path menggunakan venv eksplisit | `start_full.bat` | ✅ |
| 0.3 | `logger` tidak pernah di-import di `chat.py` | `chat.py` | ✅ |
| 0.4 | Model hardcoded `qwen3.5:4b`, request.model diabaikan | `chat.py` | ✅ |
| 0.5 | Session creation `user_id=1` hardcoded tanpa validasi | `chat.py`, `main.py` | ✅ |
| 0.6 | Qdrant collection name hardcoded di scripts | `add_bssn_audit_chunk.py` | ✅ |
| 0.7 | Health check `SELECT 1` tanpa `text()` di SQLAlchemy 2.x | `health.py` | ✅ |

### Catatan Teknis
- Semua `app/` sudah baca `settings.QDRANT_COLLECTION` dengan benar.
- Scripts (`add_bssn_audit_chunk.py`) sudah diperbaiki untuk baca dari config.
- `verify_p0.py` tidak perlu diubah — hanya file testing sementara.

---

## ✅ FASE 1 — Database Consolidation
> **Status: SELESAI** | Risiko: Medium | Estimasi: ~1 hari

Menghilangkan dual database layer (raw SQL + ORM) menjadi hanya SQLAlchemy ORM.

### Masalah yang Diselesaikan

**Sebelumnya — 2 dunia database yang konflik:**
```
ORM Model (db_models.py)     Raw SQL (core/database.py)
┌──────────────────────┐     ┌──────────────────────┐
│ Document:            │     │ Document:            │
│  - id                │     │  - doc_id  ← MISSING │
│  - filename          │     │  - document_title    │
│  - doc_type          │     │  - file_size         │
│  (NO doc_id!)        │     │  - chunk_count       │
└──────────────────────┘     └──────────────────────┘
          ↑ CREATE ALL               ↑ INSERT fails silently
```

### Yang Sudah Dikerjakan

| Step | Perubahan | File | Status |
|------|-----------|------|--------|
| 1.1 | Tambah 6 kolom baru ke ORM (`doc_id`, `document_title`, dll) | `db_models.py` | ✅ |
| 1.2 | Migration script idempotent (ALTER TABLE) | `migrations/001_*.py` | ✅ |
| 1.3 | Auto-run migration saat startup | `main.py` | ✅ |
| 1.4 | Semua method DocumentManager diganti raw SQL → ORM | `document_manager.py` | ✅ |
| 1.5 | API tidak akses database langsung, lewat DocumentManager | `api/documents.py` | ✅ |

---

## ✅ FASE 1b — RAG Metadata Fix (Sesi 1 & 2)
> **Status: SELESAI** | Risiko: Medium | Estimasi: ~3 jam

Fix root cause jawaban selalu kosong + fix model thinking mode.

### Yang Sudah Dikerjakan

| Step | Fix | File | Status |
|------|-----|------|--------|
| 1b.1 | Metadata key mismatch (`judul_dokumen` → `document_title`) | `langchain_engine.py` | ✅ |
| 1b.2 | Format context dengan hierarchy bab/pasal/ayat | `langchain_engine.py` | ✅ |
| 1b.3 | Disable thinking mode `qwen3` via `reasoning=False` | `langchain_engine.py` | ✅ |
| 1b.4 | Fix duplikat prefix `"Pasal Pasal"`, `"Ayat (Ayat)"` | `langchain_engine.py` | ✅ |
| 1b.5 | Timeout naik 300s → 600s (support model besar) | `langchain_engine.py` | ✅ |

---

## ✅ FASE 2 — RAG Pipeline Upgrade
> **Status: SELESAI** | Risiko: Medium | Realisasi: April 2026

Mengaktifkan pipeline retrieval hybrid dan validasi jawaban agar kualitas konteks + guardrail meningkat.

### Pipeline Aktif (Sekarang)

```
Query ──→ [Expand Query]
            │
            ▼
      [Vector top-20] + [BM25 top-20]
            │
            ▼
        [RRF Fusion] ──→ kandidat terurut
            │
            ▼
   [Cross-Encoder Reranker] ──→ top-k final
            │
            ▼
         [LLM Stream]
            │
            ▼
      [Validate Answer]
            │
            ▼
 Response + Sources + Validation Warnings
```

### Yang Sudah Dikerjakan

| Step | Implementasi | File | Status |
|------|--------------|------|--------|
| 2.1 | Query expansion aktif di runtime (`expand_query`) | `backend/app/core/rag/langchain_engine.py` | ✅ |
| 2.2 | Hybrid retrieval: Vector + BM25 + RRF fusion | `backend/app/core/rag/langchain_engine.py` | ✅ |
| 2.3 | Cross-encoder reranker (`BAAI/bge-reranker-base`) + fallback aman | `backend/app/core/rag/langchain_engine.py` | ✅ |
| 2.4 | Answer validation dipanggil setelah stream, emit `event: validation`, payload ikut `complete` | `backend/app/api/routes/chat.py` | ✅ |
| 2.4b | Frontend menampilkan validation warnings dari SSE | `frontend/src/views/ChatView.vue` | ✅ |
| 2.5 | Konsolidasi context formatting ke `LangchainRAGEngine._format_context`; duplikat formatter dihapus | `backend/app/core/rag/prompts.py`, `backend/app/core/formatting.py` | ✅ |

### Verifikasi Fase 2

```bash
# dari backend/
.\venv\Scripts\python.exe verify_p2.py

# cek cepat runtime retrieval
.\venv\Scripts\python.exe -c "from app.core.rag.langchain_engine import langchain_engine; langchain_engine.initialize(); r=langchain_engine.retrieve_context('Pasal 38 tentang apa?', top_k=5); print(len(r['raw_docs']))"
```

**Catatan hasil uji sesi ini:**
- Retrieval hybrid + reranker berjalan sukses.
- SSE sekarang mengirim `event: validation` dan `complete.validation`.
- Frontend build sukses setelah update event handler.

---

## ✅ FASE 3 — Frontend Refactor
> **Status: SELESAI** | Risiko: Rendah | Realisasi: April 2026

Memecah `ChatView.vue` (1178 baris) menjadi komponen-komponen kecil yang maintainable.

### Arsitektur Target

```
SEKARANG:                    TARGET:
src/views/                   src/
└── ChatView.vue (1178 baris) ├── views/
                              │   └── ChatView.vue (<300 baris - orchestration only)
                              ├── components/
                              │   ├── chat/
                              │   │   ├── MessageBubble.vue
                              │   │   ├── ChatInput.vue
                              │   │   ├── ChatSidebar.vue
                              │   │   └── SourceCard.vue
                              └── services/
                                  ├── api.js        ← axios instance
                                  ├── chatService.js
                                  └── documentService.js
```

### Yang Sudah Dikerjakan

| Step | Implementasi | File | Status |
|------|--------------|------|--------|
| 3.1 | Service layer terpusat berbasis axios (`api.js`, `chatService.js`, `documentService.js`) | `frontend/src/services/*` | ✅ |
| 3.2 | Ekstraksi komponen chat: `ChatSidebar`, `ChatInput`, `MessageBubble`, `SourceCard` | `frontend/src/components/chat/*` | ✅ |
| 3.2b | `ChatView.vue` direfaktor menjadi orchestration-only dan style dipindah ke aset terpisah | `frontend/src/views/ChatView.vue`, `frontend/src/assets/chat-view.css` | ✅ |
| 3.3 | Markdown renderer diganti ke `marked + DOMPurify` untuk sanitasi HTML dan mitigasi XSS | `frontend/src/components/chat/MessageBubble.vue` | ✅ |
| 3.4 | Session load mismatch diperbaiki dengan pola `get session + get history` | `frontend/src/views/ChatView.vue` | ✅ |
| 3.5 | Cleanup Tailwind/PostCSS (`npm uninstall`, hapus config, reset CSS global) | `frontend/package.json`, `frontend/src/assets/main.css` | ✅ |
| 3.5b | View dokumen/home ikut migrasi ke service layer agar API call konsisten | `frontend/src/views/DocumentsView.vue`, `frontend/src/views/DocumentDetailView.vue`, `frontend/src/views/HomeView.vue` | ✅ |

### Verifikasi Fase 3
```bash
npm run build
# vite v5 build sukses
# dist/assets/index-*.css: 24.21 kB (gzip 4.74 kB)
# dist/assets/index-*.js : 230.64 kB (gzip 82.78 kB)
```

**Catatan hasil uji sesi ini:**
- Build frontend sukses setelah refactor komponen + service layer.
- Streaming chat tetap berjalan (retrieval/token/complete/validation).
- API call dokumen dan detail dokumen kini melalui service terpusat.

---

## Bug Kecil yang Belum Diperbaiki (TODO)

| Bug | File | Prioritas | Keterangan |
|-----|------|-----------|------------|
| Default model hilang saat server restart | `models.py` | Medium | Simpan ke file JSON |
| Qdrant version warning setiap health check | `health.py` | Low | Tambah `check_compatibility=False` |
| `verify_p0.py` hardcoded `"document_chunks"` | `verify_p0.py` | Low | File testing sementara |

---

## Estimasi Total

| Fase | Deskripsi | Estimasi | Risiko | Status |
|------|-----------|----------|--------|--------|
| **0** | Critical bug fixes | ~2 jam | 🟢 Rendah | ✅ Selesai |
| **1** | Database consolidation | ~1 hari | 🟡 Medium | ✅ Selesai |
| **1b** | RAG metadata & model fix | ~3 jam | 🟡 Medium | ✅ Selesai |
| **2** | RAG pipeline upgrade | ~2 hari | 🟡 Medium | ✅ Selesai |
| **3** | Frontend refactor | ~1 hari | 🟢 Rendah | ✅ Selesai |

**Total sisa:** 0 hari (fase roadmap 0-3 selesai)
