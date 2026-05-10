# 12 — FASE 2: RAG Pipeline Upgrade

## Ringkasan
FASE 2 mengaktifkan retrieval hybrid (Vector + BM25), fusion ranking (RRF), cross-encoder reranker, dan validasi jawaban pasca-stream.

## Perubahan Utama

### 1) Query Expansion
- File: `backend/app/core/rag/langchain_engine.py`
- `retrieve_context()` sekarang memanggil `expand_query()` dari `prompts.py`.
- Variasi query dipakai untuk meningkatkan recall dokumen hukum.

### 2) Hybrid Retrieval (Vector + BM25)
- File: `backend/app/core/rag/langchain_engine.py`
- Menambahkan:
  - `_load_bm25()`
  - `_bm25_search()`
  - `_vector_search()`
- BM25 index dibaca dari `backend/data/bm25_index.pkl`.

### 3) RRF Fusion
- File: `backend/app/core/rag/langchain_engine.py`
- Menambahkan `_rrf_fusion()` dengan konstanta `k=60`.
- Candidate dedupe menggunakan `_chunk_key()`.

### 4) Cross-Encoder Reranker
- File: `backend/app/core/rag/langchain_engine.py`
- Menambahkan:
  - `_get_reranker()`
  - `_rerank()`
- Model default: `BAAI/bge-reranker-base` (dari config).
- Fallback aman ke RRF-only bila reranker gagal load.

### 5) Streaming Answer Validation
- File: `backend/app/api/routes/chat.py`
- Setelah jawaban selesai stream dan sanitasi sitasi:
  - `validate_answer()` dipanggil.
  - SSE mengirim `event: validation` jika ada warning.
  - Payload `complete` sekarang menyertakan `validation`.

### 6) Frontend Validation Display
- File: `frontend/src/views/ChatView.vue`
- Menambahkan handler event SSE `validation`.
- Menambahkan panel `Validation Warnings` pada bubble assistant.

### 7) Konsolidasi Formatter
- File: `backend/app/core/rag/prompts.py`
  - Menghapus duplikat `format_context()`.
- File: `backend/app/core/formatting.py`
  - Menghapus duplikat `format_context_with_parent()`.
- Single source of truth context formatting: `LangchainRAGEngine._format_context()`.

## Verifikasi

### Script
- `backend/verify_p2.py` ditambahkan untuk cek statik FASE 2.

### Runtime
- `GET /api/health` berjalan.
- `POST /api/chat/stream` menghasilkan:
  - `event: token`
  - `event: validation`
  - `event: complete` (dengan field `validation`).

## Catatan
- Jika BM25 index kosong, pipeline tetap berjalan via vector + reranker fallback.
- Untuk kualitas terbaik, pastikan dokumen sudah ter-index sehingga `bm25_index.pkl` berisi chunk aktif.
