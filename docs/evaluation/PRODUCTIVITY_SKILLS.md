# RAG Productivity Skills

Dokumentasi fitur-fitur produktivitas yang ditambahkan untuk membantu development dan debugging sistem RAG SPBE.

---

## Latar Belakang

Sebelum perubahan ini, ada dua masalah utama:

1. **Bug filter `doc_id`** — saat user bertanya dengan filter dokumen tertentu, sistem sering mengembalikan jawaban dari dokumen lain. Root cause: Qdrant menyimpan payload dengan key `metadata.document_id` (integer), tapi kode lama mencari `doc_id` (string). Jalur BM25 dan tabel-literal juga tidak ter-scope sama sekali.

2. **Tidak ada jaring pengaman** — tidak ada cara otomatis untuk mendeteksi jika perubahan kode merusak kualitas jawaban RAG.

Dua skill utama ditambahkan untuk mengatasi ini: **Canary Regression Check** (otomatis, berbasis hook) dan **RAG Debug Tracer** (manual, berbasis CLI + skill Claude).

---

## Perubahan yang Dilakukan

### 1. Fix Bug `doc_id` Filter (`langchain_engine.py`)

**File:** `backend/app/core/rag/langchain_engine.py`

Ditambahkan method `_resolve_doc_target(doc_id)` yang melakukan lookup ke DB untuk mendapatkan `(db_id: int, filename: str)`. Method `_build_doc_filter()` diperbarui menggunakan key `metadata.document_id` dengan value integer dari DB. Jalur BM25 (`_bm25_search`) dan table-literal (`_table_literal_search`) juga diperbarui untuk melakukan filtering berdasarkan filename.

**Dampak:** Query dengan `document_id` kini benar-benar di-scope ke satu dokumen saja — tidak ada kebocoran lintas dokumen.

Respons API di `/api/chat/stream` juga diperbaiki: setiap source kini menyertakan field `doc_id` sehingga frontend dapat menampilkan sumber dengan tepat.

---

### 2. RAG Retrieval Tracer (`rag_trace.py`)

**File:** `backend/scripts/rag_trace.py`

Script CLI yang menjalankan seluruh pipeline retrieval secara bertahap dan menampilkan hasilnya per seksi. Berguna untuk mendiagnosis mengapa jawaban RAG salah tanpa harus menambah print statement ke kode produksi.

**Cara pakai:**

```bash
cd backend

# Query umum (tanpa filter dokumen)
venv/Scripts/python scripts/rag_trace.py --query "apa itu SPBE?"

# Query dengan filter ke dokumen tertentu
venv/Scripts/python scripts/rag_trace.py --query "apa isi tabel 13?" --doc-id 1

# Output JSON mentah (untuk piping atau analisis lebih lanjut)
venv/Scripts/python scripts/rag_trace.py --query "apa isi pasal 5?" --doc-id 6 --json
```

**7 seksi output:**

| Seksi | Isi |
|---|---|
| `classify_query` | Tipe query yang terdeteksi (general / table / pasal) |
| `filter_resolution` | Apakah `doc_id` berhasil di-resolve ke DB + nama file |
| `vector_search` | Dokumen yang dikembalikan jalur Qdrant vector search |
| `bm25_search` | Dokumen yang dikembalikan jalur BM25 |
| `table_literal_search` | Dokumen yang dikembalikan jalur pencarian tabel literal |
| `rerank` | Urutan dokumen setelah cross-encoder reranking |
| `final_context_and_answer` | Context yang dikirim ke LLM + potongan jawaban |

---

### 3. Skill `rag-debug-answer` (Magnetic Skill)

**File:** `.claude/skills/rag-debug-answer/SKILL.md`

Skill Claude Code yang aktif otomatis ketika Anda melaporkan masalah jawaban RAG. Tidak perlu dipanggil manual — cukup deskripsikan masalahnya dan skill akan memandu diagnosis.

**Contoh kalimat yang memicu skill:**
- "kenapa sumbernya dari dokumen yang salah?"
- "jawabannya ngarang Pasal 99 yang tidak ada"
- "filter document_id tidak jalan"
- "tabel 13 diambil dari dokumen lain"

**Yang dilakukan skill:**
1. Meminta query persisnya dan `document_id` jika ada
2. Menjalankan `rag_trace.py --json`
3. Menganalisis output dengan checklist 6 hipotesis (H1–H6)
4. Melaporkan root cause + file:line yang perlu diperbaiki
5. Menyerahkan perbaikan ke `superpowers:test-driven-development` (bukan langsung edit)

**6 Hipotesis Diagnosis:**

| Kode | Hipotesis | Sinyal |
|---|---|---|
| H1 | `doc_id` tidak ter-resolve | `filter_resolution.resolved` = null |
| H2 | Qdrant payload key mismatch | `qdrant_hit_count == 0` padahal dokumen ada |
| H3 | Satu jalur retrieval bocor | Filename di vector/BM25/table berbeda dari target |
| H4 | Fallback terlalu agresif | Hit count > 0 tapi dokumen lain ikut masuk |
| H5 | Rerank menenggelamkan target | Top-5 rerank tidak ada dari dokumen target |
| H6 | Unavailable detector over-trigger | Answer bilang "tidak ada" padahal context ada |

---

### 4. Canary Regression Check

**File:** `backend/scripts/eval_regression_check.py`

Script yang mengirim 4 query canary ke backend dan membandingkan hasilnya dengan baseline. Digunakan untuk memastikan perubahan kode tidak merusak kualitas jawaban.

```bash
cd backend

# Jalankan regression check manual
venv/Scripts/python scripts/eval_regression_check.py

# Keluar 0 = semua canary stabil
# Keluar 1 = ada regresi, lihat output untuk detail
```

**4 Query Canary:**

| ID | Query | Dokumen | Yang Diuji |
|---|---|---|---|
| `canary_tabel13_doc1` | "apa isi tabel 13?" | Doc 1 | Jawaban harus sebut Sekretariat Kabinet atau Kejaksaan Agung |
| `canary_pasal5_doc6` | "apa isi pasal 5?" | Doc 6 | Jawaban harus sebut Ayat (7) atau Rencana Induk |
| `canary_leakage_guard` | "apa isi tabel 13?" | Doc 3 | Jawaban harus bilang tidak ditemukan (tidak ada tabel 13 di doc 3) |
| `canary_general_spbe` | "apa itu SPBE?" | — | Jawaban harus sebut "Sistem Pemerintahan Berbasis Elektronik" |

**Kriteria regresi:** score turun >15% dari baseline.

---

### 5. Canary Baseline Generator

**File:** `backend/scripts/eval_canary_baseline.py`

Script untuk merekam ulang baseline setelah perubahan yang disengaja dan sudah diverifikasi.

```bash
cd backend

# Rekam ulang baseline (backend harus berjalan, timeout 300s per query)
venv/Scripts/python scripts/eval_canary_baseline.py --force
```

Baseline tersimpan di: `docs/evaluation/baselines/canary_baseline.json`

> **Kapan perlu dijalankan:** Hanya setelah Anda sengaja mengubah perilaku RAG dan sudah memverifikasi hasilnya benar. Jangan jalankan untuk "menyembunyikan" regresi.

---

### 6. Automation via Claude Code Hooks

**File:** `.claude/hooks/rag_mark_dirty.py`, `.claude/hooks/rag_run_regression.py`, `.claude/settings.json`

Dua hook yang bekerja bersama untuk menjalankan regression check secara otomatis di akhir sesi:

```
Edit file RAG core
       ↓
PostToolUse hook: rag_mark_dirty.py
       ↓
Menyentuh .claude/_state/rag_dirty (flag file)
       ↓
[... Claude bekerja ...]
       ↓
Stop hook: rag_run_regression.py
       ↓
Flag ada? → Jalankan eval_regression_check.py
       ↓
Hapus flag
```

**File yang memicu flag (RAG-critical):**
- Semua `.py` di `backend/app/core/rag/`
- `backend/app/api/routes/chat.py`

**File yang TIDAK memicu flag:**
- Frontend, ingestion, scripts, tests, dokumentasi, dsb.

**Catatan penting:**
- Hook selalu keluar 0 — tidak pernah memblokir pekerjaan Anda
- Jika backend mati saat hook berjalan, check dilewati dan flag tetap dihapus
- Flag tersimpan di `.claude/_state/rag_dirty` (tidak di-commit ke git)

---

## Struktur File Baru

```
.claude/
├── _state/
│   └── .gitkeep          # Dir untuk runtime flags (isi tidak di-commit)
├── hooks/
│   ├── rag_mark_dirty.py     # PostToolUse: tandai jika RAG file diubah
│   └── rag_run_regression.py # Stop: jalankan canary jika flag ada
├── settings.json             # Konfigurasi hooks Claude Code
└── skills/
    └── rag-debug-answer/
        └── SKILL.md          # Magnetic debug skill

backend/scripts/
├── rag_trace.py              # Structured 7-section retrieval tracer
├── eval_regression_check.py  # Canary regression comparator + runner
└── eval_canary_baseline.py   # Baseline generator

backend/tests/
├── test_eval_regression.py   # 7 unit tests untuk regression check logic
├── test_rag_mark_dirty.py    # 4 unit tests untuk mark_dirty hook
├── test_rag_trace.py         # 2 integration tests untuk tracer
└── test_api_sources_doc_id.py # 1 test untuk doc_id di sources response

docs/evaluation/baselines/
└── canary_baseline.json      # Baseline 4 canary (commit: 2c97101)
```

---

## Cara Kerja Sehari-hari

### Skenario 1: Edit RAG dan ingin tahu dampaknya

1. Edit file di `backend/app/core/rag/` seperti biasa.
2. Di akhir sesi Claude, Stop hook otomatis menjalankan 4 canary.
3. Jika ada canary yang gagal, output akan muncul di terminal Claude.
4. Tidak ada tindakan manual — semuanya otomatis.

### Skenario 2: Jawaban RAG terasa salah

1. Ceritakan masalahnya ke Claude: "kenapa jawaban tentang tabel 13 mengambil dari dokumen lain?"
2. Skill `rag-debug-answer` aktif otomatis.
3. Claude menjalankan `rag_trace.py`, menganalisis 6 hipotesis, dan melaporkan root cause + file:line.
4. Perbaikan dilakukan dengan TDD: test dulu, baru fix.

### Skenario 3: Sudah pasti perubahan RAG benar, ingin update baseline

```bash
cd backend
venv/Scripts/python scripts/eval_canary_baseline.py --force
git add docs/evaluation/baselines/canary_baseline.json
git commit -m "chore(eval): update canary baseline after <perubahan>"
```

### Skenario 4: Debug manual tanpa Claude

```bash
cd backend

# Lihat semua tahap retrieval
venv/Scripts/python scripts/rag_trace.py --query "apa isi pasal 5?" --doc-id 6

# Jalankan regression check langsung
venv/Scripts/python scripts/eval_regression_check.py
```
