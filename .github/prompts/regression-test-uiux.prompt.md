---
description: "Use when: doing UI/UX regression testing on the SPBE RAG frontend after code changes. Covers the actual routes/features in this repo (Chat, Home, Documents, Document Detail) and produces a structured PASS/FAIL report."
name: "SPBE RAG UI/UX Regression"
argument-hint: "What changed? (e.g., chat streaming, documents flow, sidebar, API integration)"
agent: "agent"
---

# UI/UX Regression Test — SPBE RAG Frontend

Tujuan: memastikan perubahan tidak merusak alur utama pengguna di frontend (Vue) dan integrasi API (FastAPI).

## Pre-check (wajib)

1) Pastikan backend & frontend tersedia:

- Backend: `GET http://localhost:8000/api/health` harus respons (status healthy/degraded)
- Frontend: `http://localhost:5173/` terbuka

2) Jika services belum jalan, gunakan perintah standar dari instructions:

- `start_all.bat` (backend+frontend)
- atau: backend `start_full.bat` + frontend `npm run dev` (di folder `frontend`)

## Regression Checklist (sesuai route repo)

### A. Navigasi & layout

- `/` (Chat) terbuka tanpa blank/error
- Sidebar:
  - tombol `New Chat` bekerja
  - tombol collapse/expand bekerja
  - list session tampil (atau state kosong) tanpa error
- Link `Kelola Dokumen` di sidebar menuju `/documents`

### B. Chat — alur utama (SSE streaming)

Di route `/`:

- Status koneksi di header:
  - `Connected` saat backend sehat
  - berubah ke `Disconnected` jika backend mati (tanpa crash)
- Kirim 1 pertanyaan via textarea:
  - tombol send disabled jika input kosong
  - setelah send: muncul bubble user + placeholder assistant `Searching documents...`
  - token streaming muncul bertahap (tidak freeze)
  - selesai: message final tampil + sources/timing (jika tersedia)
- Klik salah satu suggestion di welcome screen (sample questions) dan pastikan terkirim

### C. Chat — toggle RAG

- Matikan toggle `Use RAG` → kirim 1 pertanyaan kontrol
- Nyalakan lagi `Use RAG` → kirim 1 pertanyaan kontrol
- Pastikan UI tetap responsif dan tidak stuck loading

### D. Sessions

- Setelah 1 chat selesai: pastikan session tersimpan dan list `Recent` ter-update
- Reload halaman (F5): sessions tetap muncul
- Load session lama:
  - history tampil sesuai
  - model badge ikut berubah jika session punya model
- Delete session:
  - tombol delete memunculkan confirm
  - setelah delete: item hilang dari list

### E. Models

- Dropdown model:
  - list model tampil (jika backend `/api/models` OK)
  - ganti model → badge model berubah
  - lakukan 1 chat singkat memastikan request tidak error

### F. Home

Di route `/home`:

- Halaman render normal
- Klik card `Chat` kembali ke `/`
- Klik card `Documents` menuju `/documents`
- Panel status:
  - jika backend up → tidak menampilkan “Server tidak tersedia”

### G. Documents (list + sync)

Di route `/documents`:

- Halaman terbuka, tombol `Kembali ke Chat` kembali ke `/`
- Tombol `Sync Qdrant`:
  - bisa diklik
  - menampilkan state `Syncing...` sementara
  - tidak menyebabkan crash
- Tombol refresh memuat ulang list
- Klik salah satu dokumen (jika ada) → ke `/documents/:doc_id`

### H. Documents (upload + preview + index) — opsional tapi disarankan

Jika ada PDF kecil untuk uji:

- Upload 1 file PDF → dapat toast sukses
- Klik `Preview Chunks` → daftar chunk muncul
- Klik `Simpan ke Index` → toast `Berhasil mengindeks ... chunks!`
- Pastikan dokumen masuk daftar `Dokumen Terindeks`

### I. Document Detail (chunks) — smoke

Di route `/documents/:doc_id`:

- Chunks termuat dan bisa scroll
- Tombol edit chunk:
  - modal terbuka
  - edit text → simpan → toast sukses, UI update
- Tombol delete chunk:
  - modal konfirmasi → delete → chunk hilang

Catatan penting:

- Saat ini edit/delete chunk cenderung mengubah SQLite saja; retrieval masih membaca dari Qdrant. Jika setelah edit/delete jawaban masih “stale”, jalankan sync vector index: `backend/scripts/sync_vectors.py --force`.

## Output (format laporan)

Isi laporan dengan format berikut:

**Context**
- Change focus: <ringkas, dari input prompt>
- Backend URL: http://localhost:8000
- Frontend URL: http://localhost:5173

**Results**
- A Navigasi & layout: PASS/FAIL — <catatan>
- B Chat SSE streaming: PASS/FAIL — <catatan>
- C Toggle RAG: PASS/FAIL — <catatan>
- D Sessions: PASS/FAIL — <catatan>
- E Models: PASS/FAIL — <catatan>
- F Home: PASS/FAIL — <catatan>
- G Documents list/sync: PASS/FAIL — <catatan>
- H Upload/preview/index (opsional): PASS/FAIL/SKIP — <catatan>
- I Document Detail (smoke): PASS/FAIL — <catatan>

**Bugs / Repro Steps**
- <Bug 1>: steps + expected vs actual
- <Bug 2>: ...

**Notes**
- Risiko regresi yang perlu dipantau + rekomendasi next action