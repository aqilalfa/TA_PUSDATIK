---
description: "Use when: starting/running SPBE RAG services, debugging Qdrant/Ollama, ingesting documents, syncing vector index, running backend test scripts, or doing retrieval regression evaluation. Contains canonical commands, endpoints, and safe reset procedures for this repo."
name: "SPBE RAG Standard Commands"
---

# SPBE RAG — Standard Commands (Source of Truth)

Instruksi ini adalah referensi perintah **yang benar-benar ada di repo ini**. Gunakan ini agar agent tidak mengarang command/endpoints.

## Canonical Entrypoints & URLs

- Backend FastAPI entrypoint: `backend/app/main.py` → `app.main:app`
- API docs: `GET http://localhost:8000/docs`
- Health check: `GET http://localhost:8000/api/health`
- Streaming chat (RAG aktif): `POST http://localhost:8000/api/chat/stream` (SSE)
- Catatan: endpoint non-stream `POST /api/chat/` saat ini placeholder (bukan RAG utama).

## Start/Stop (Local dev — Windows)

Prereq: Docker (Qdrant) & Ollama harus jalan.

- Start backend + frontend: `start_all.bat`
- Start backend saja: `start_full.bat`

Alternatif manual (backend):

1) `cd backend`
2) `call venv\Scripts\activate.bat`
3) `venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload`

Frontend:

1) `cd frontend`
2) `npm install` (sekali)
3) `npm run dev`

Quick checks:

- Qdrant: `curl -s http://localhost:6333/collections`
- Ollama: `curl -s http://localhost:11434/api/tags`
- Backend health: `curl -s http://localhost:8000/api/health`

## One-Command Smoke Check (Local)

Gunakan ini setelah perubahan ingestion/indexing untuk validasi cepat end-to-end dasar.

Coverage:

- Backend health endpoint (`/api/health`)
- Ketersediaan koleksi Qdrant aktif
- Jumlah point di Qdrant
- Jumlah chunk di SQLite
- Alignment count Qdrant vs SQLite

Command dari root repo:

- `smoke_check.bat`

Alternatif langsung dari folder `backend`:

- `venv\Scripts\python.exe scripts\smoke_check.py`

Opsi output:

- JSON: `smoke_check.bat --json`
- Toleransi mismatch count (warn only): `smoke_check.bat --allow-drift`

## Start/Stop (Docker Compose dev)

Stack lengkap (Qdrant + backend + frontend):

- `docker compose -f docker-compose.dev.yml up --build`

Hanya Qdrant:

- `docker compose -f docker-compose.dev.yml up -d qdrant`

Stop:

- `docker compose -f docker-compose.dev.yml down`

## Ingestion & Index Maintenance

### Ingest PDF (tanpa wipe)

Script: `backend/scripts/ingest_documents.py`

- Dari folder `backend`:
  - `venv\Scripts\python.exe scripts\ingest_documents.py --input-dir ..\data\documents --doc-type auto`

Catatan:

- Script akan membuat record Document/Chunk di SQLite + menambahkan vektor ke Qdrant.

### Sync ulang Qdrant dari SQLite (mengatasi “stale answers”)

Gunakan jika data SQLite berubah (mis. edit/delete chunk) tetapi retrieval masih memakai vektor lama di Qdrant.

- Dari folder `backend`:
  - `venv\Scripts\python.exe scripts\sync_vectors.py --force`

Efek:

- Menghapus & membuat ulang koleksi Qdrant (`delete_collection` + `create_collection`) lalu upsert ulang dari SQLite.

### Full re-ingest (wipe SQLite + Qdrant)

Script: `backend/scripts/reingest_all.py`

- Dari folder `backend`:
  - `venv\Scripts\python.exe scripts\reingest_all.py --docs-dir ..\data\documents`

Efek:

- Menghapus seluruh `Document` + `Chunk` di SQLite.
- Menghapus & membuat ulang koleksi Qdrant.
- Rebuild BM25 index (output ke `backend/data/bm25_index.pkl`).

## Retrieval Regression Evaluation (Query set tetap)

Ground truth:

- `data/ground_truth/ground_truth_evaluasi_spbe.csv`

Evaluator:

- `backend/scripts/evaluate_retrieval.py` (menghasilkan report JSON + ringkasan HitRate/MRR)

Cara jalan (dari folder `backend`):

- `venv\Scripts\python.exe scripts\evaluate_retrieval.py`

Catatan penting:

- Script evaluator saat ini memakai path absolut ke CSV/output. Jika repo dipindah folder, update konstanta `CSV_PATH`/`output_path` di script tersebut.

## Quality Gate Evaluation (Answer Quality)

Script-script berikut menguji kualitas jawaban (bukan retrieval) — detector unavailable, stage coverage, dan skor quality gate.

### Backfill metadata `is_table` pada chunk existing

Jalankan sekali setelah perubahan chunker atau sesudah pull yang menyertakan perubahan `structured_chunker.py`:

- `DATABASE_URL="sqlite:///./backend/data/spbe_rag.db" venv\Scripts\python.exe scripts\backfill_table_metadata.py`
- Dry-run (preview tanpa tulis): `... backfill_table_metadata.py --dry-run`
- Setelah backfill, rebuild BM25: `DATABASE_URL="sqlite:///./backend/data/spbe_rag.db" venv\Scripts\python.exe scripts\rebuild_bm25.py`
- Lalu sync Qdrant: `venv\Scripts\python.exe scripts\sync_vectors.py --force`

### Audit jawaban tabel (Permenpan 59 Tabel 1-14)

Membutuhkan backend + Ollama berjalan:

- `venv\Scripts\python.exe scripts\_tmp_table_batch.py`
- Subset tertentu: `... --start-table 6 --end-table 9`
- Report disimpan otomatis di: `data/evaluation/permenpan59_tabel_1_14_audit_<timestamp>.json`

### Sanity check non-tabel (definisi, daftar, perbandingan, indikator)

- `venv\Scripts\python.exe scripts\_tmp_generic_quality_sanity.py`
- Report disimpan di: `data/evaluation/generic_quality_sanity_<timestamp>.json`

### Regression guard (bandingkan run vs baseline)

Pertama kali (simpan baseline):

- `venv\Scripts\python.exe scripts\eval_regression_check.py` → otomatis simpan baseline jika belum ada
- Atau eksplisit: `venv\Scripts\python.exe scripts\eval_regression_check.py --update-baseline`

Run berikutnya (cek regresi):

- `venv\Scripts\python.exe scripts\eval_regression_check.py` → exit 0 jika tidak ada regresi, exit 1 + diff jika ada
- Baseline tersimpan di: `data/evaluation/baselines/quality_gate_baseline.json`

### Debug detector unavailable

Untuk melihat trigger phrase + window konteks saat quality detector memicu:

- Set env `QUALITY_DEBUG=1` sebelum start backend: `set QUALITY_DEBUG=1 && venv\Scripts\python.exe -m uvicorn app.main:app ...`
- Trigger detail muncul di log backend dan dalam `quality_check.unavailable_triggers_active` di payload SSE `complete`.

## Database & Cache

Clear chat/session SQLite (bukan reset Qdrant):

- `cd backend`
- `venv\Scripts\python.exe clear_db_cache.py`

## Testing (script-style)

Sebagian besar “tests” di repo ini adalah Python scripts (bukan pytest). Jalankan dari folder `backend` memakai interpreter venv:

- `venv\Scripts\python.exe test_api.py`
- `venv\Scripts\python.exe test_full_pipeline.py`
- `venv\Scripts\python.exe test_langchain_rag.py`
- `venv\Scripts\python.exe test_error_handling.py`

## Notes khusus: Kenapa `qdrant_storage/` sering berubah?

- `qdrant_storage/` adalah data persist Qdrant (RocksDB, WAL, segments). Setiap upsert vektor, compaction, atau recreate collection akan memodifikasi file-file di sana.
- Script seperti `scripts/sync_vectors.py` dan `scripts/reingest_all.py` melakukan `delete_collection(...)` → perubahan bisa terlihat seperti banyak file “deleted/added”. Itu normal untuk volume DB.

## Agent Guardrails

- Jangan gunakan endpoint `/health` (tanpa prefix) — di app ini health ada di `/api/health`.
- Untuk RAG/streaming token, pakai `/api/chat/stream`.
- Saat menjalankan python command untuk backend, selalu gunakan `backend/venv` (`venv\\Scripts\\python.exe`) agar dependency konsisten.