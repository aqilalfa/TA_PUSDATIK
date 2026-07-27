---
name: spbe-rag-workflow
description: "Gunakan saat testing SPBE RAG dari nol di workspace ini: setup stack, verifikasi backend dan frontend UI/UX, uji retrieval/chat, dan triase akar masalah."
argument-hint: "Tujuan sesi (contoh: validasi end-to-end sebelum demo internal)"
user-invocable: true
---

# SPBE RAG Workflow

Skill ini adalah runbook end-to-end agar pengujian/triase SPBE RAG konsisten dan tidak mengarang command/endpoints.

## Kapan Dipakai
- Menjalankan pengujian dari nol untuk memastikan sistem benar-benar bisa jalan.
- Menangani error runtime pada startup backend, model, atau Docker stack.
- Memvalidasi kualitas retrieval dan jawaban sebelum perubahan besar.
- Melakukan smoke test UI/UX agar alur pengguna tetap usable.

## Referensi “source of truth” di repo

- Standard commands & endpoint canonical: `.github/instructions/project-standard-commands.instructions.md`
- UI/UX regression checklist (berbasis routes/fitur aktual): `.github/prompts/regression-test-uiux.prompt.md`
- Retrieval regression (query set tetap + metrik HitRate/MRR): `.github/prompts/retrieval-quality-eval.prompt.md`
- Audit kesesuaian dokumen vs chunk: `.github/skills/document-chunk-alignment-workflow/SKILL.md`
- Audit pertanyaan berbasis tabel (mis. Tabel 13): `.github/skills/table-query-audit-workflow/SKILL.md`

## Input Yang Perlu Ditentukan
1. Tujuan utama sesi (contoh: “validasi end-to-end sebelum demo”).
2. Apa yang berubah (contoh: “chunking parser”, “reranker”, “UI documents flow”).
3. Mode eksekusi:
   - Smoke (10–20 menit)
   - Full workflow (30–90 menit)
4. Apakah perlu evaluation retrieval berbasis ground truth? (ya/tidak)

## Prosedur

Ikuti urutan ini agar diagnosis tidak lompat-lompat.

### 1) Tetapkan target hasil (output terukur)

Contoh target minimal:

- `GET /api/health` respons dan tidak error
- Frontend bisa dibuka
- 1 query chat streaming berhasil

Jika mode “Full workflow”, tambahkan:

- UI/UX regression PASS untuk alur utama
- Retrieval eval (HitRate/MRR) tidak turun dibanding baseline terakhir

### 2) Pre-check environment & dependencies

Gunakan perintah yang sudah ada di `.github/instructions/project-standard-commands.instructions.md`.

Checklist cepat:

- Docker berjalan (untuk Qdrant)
- Qdrant up: `curl -s http://localhost:6333/collections`
- Ollama up: `curl -s http://localhost:11434/api/tags`

### 3) Start stack (local atau docker)

Pilih satu (lihat instructions untuk variasi):

- `start_all.bat` (backend + frontend)
- atau: `start_full.bat` (backend) + `npm run dev` (frontend)

### 4) Verifikasi health + contract API

- Backend health: `GET http://localhost:8000/api/health`
- API docs: `GET http://localhost:8000/docs`
- Pastikan endpoint streaming dipakai untuk RAG utama: `POST /api/chat/stream`

### 5) Pastikan data siap (dokumen sudah ter-index)

Kalau environment baru / koleksi kosong:

- Ingest tanpa wipe: `backend/scripts/ingest_documents.py` (lihat instructions untuk command lengkap)

Kalau ada indikasi “stale answers” setelah edit/delete chunk atau perubahan ingestion:

- Sync ulang Qdrant: `backend/scripts/sync_vectors.py --force`

Kalau perlu reset total:

- Full re-ingest: `backend/scripts/reingest_all.py --docs-dir ..\\data\\documents`

### 6) Smoke test UI/UX

Jalankan prompt checklist UI (jangan improvisasi):

- `.github/prompts/regression-test-uiux.prompt.md`

Output harus berupa laporan PASS/FAIL + repro steps.

### 7) Retrieval regression (query set tetap)

Jika diminta “kualitas retrieval” yang reproducible:

- Jalankan prompt evaluasi retrieval:
   - `.github/prompts/retrieval-quality-eval.prompt.md`

Ini akan menjalankan `backend/scripts/evaluate_retrieval.py` dan menghasilkan metrik HitRate/MRR + report detail.

### 8) Triase akar masalah (decision tree)

Klasifikasikan problem dulu, baru tindakan:

1) **Service tidak jalan / health gagal**
- Fokus: dependency, venv, port conflict, Docker/Qdrant, Ollama

2) **UI rusak tapi health OK**
- Fokus: route Vue, API contract (`/api/chat/stream`, `/api/documents`, `/api/models`), error handling frontend

3) **Retrieval miss / metrik turun**
- Fokus: Qdrant index stale, chunking berubah (chunk_index shift), embedding model berubah, metadata payload

4) **Retrieval OK tapi jawaban buruk**
- Fokus: model Ollama, prompt system, max token, streaming, validasi sitasi

Catatan penting tentang `qdrant_storage/`:

- Perubahan file di `qdrant_storage/` adalah normal (RocksDB/WAL/segment) setiap ada upsert atau recreate collection.
- Script `sync_vectors.py` dan `reingest_all.py` melakukan delete+recreate collection → wajar terlihat seperti banyak file berubah.

### 9) Tutup sesi dengan ringkasan

Output akhir wajib memuat:

- Apa yang berubah
- Langkah yang dijalankan (command yang dipakai)
- Hasil health/UI/retrieval
- Bug list + prioritas
- Next step 1–3 yang paling berdampak

## Decision Rules

- Prioritaskan stabilitas sistem sebelum tuning kualitas.
- Jangan optimasi prompt jika health backend, startup service, dan ingestion belum valid.
- Ubah satu komponen per iterasi agar dampaknya bisa diukur.
- Pisahkan temuan backend vs frontend agar diagnosis tidak tercampur.

## Completion Checklist

- Health endpoint normal.
- Backend dan frontend sama-sama dapat diakses tanpa error blocker.
- Pipeline query dasar berjalan tanpa error kritis.
- Query uji menghasilkan konteks yang masuk akal.
- Alur UI/UX minimum (navigasi, submit query, tampil respons) lolos smoke test.
- Ada ringkasan tindakan dan next step yang jelas.

## Output Skill

- Rencana eksekusi sesi full workflow.
- Daftar cek yang dieksekusi.
- Diagnosis akar masalah dengan prioritas perbaikan.
- Ringkasan hasil backend + UI/UX untuk dokumentasi tim.
