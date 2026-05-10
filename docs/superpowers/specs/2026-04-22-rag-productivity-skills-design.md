# RAG Productivity Skills — Design Spec (Hybrid: Hooks + Magnetic Skill)

**Date:** 2026-04-22
**Status:** Design approved, pending implementation plan
**Scope:** Automate repetitive RAG workflows: (A) post-edit regression check, (C) answer-quality debugging.

## Context

Dua alur kerja paling repetitif di proyek SPBE RAG:

- **(A) Evaluasi & regresi** — setiap kali mengubah retrieval/prompt, harus jalankan `_tmp_table_batch.py` + `_tmp_generic_quality_sanity.py`, baca report, dan bandingkan manual dengan run sebelumnya. Tidak ada baseline otomatis. Fase 5 plan `sementara-ini-saya-memiliki-playful-kay.md` memang merencanakan regression guard tapi belum dieksekusi.
- **(C) Debugging jawaban** — investigasi kenapa jawaban ngarang, sumber salah, atau filter bocor. Contoh konkret: bug `doc_id` filter yang baru ditemukan pada 2026-04-22 butuh ~15 menit probing Qdrant payload, BM25 index, dan `_table_literal_search` secara manual. Alur investigasi tersebut berulang cukup sering.

## Goals

1. Jalankan regresi canary **otomatis** (tanpa Anda minta) setelah sesi editing retrieval selesai — sekali per sesi, bukan per edit.
2. Memicu **runbook tracing** otomatis saat user mengeluhkan kualitas jawaban, supaya investigasi mengikuti langkah yang sama (reproducible, tidak bergantung ingatan Claude).
3. Tidak memblok alur kerja normal: kalau backend mati, hook diam; kalau edit tidak menyentuh RAG, tidak ada overhead.

## Non-Goals

- **Tidak** mengganti skill `superpowers:test-driven-development` atau `systematic-debugging`. Skill debug baru hanya memicu tracing lalu menyerahkan fix ke TDD flow.
- **Tidak** menjalankan full eval suite (14 tabel + generic) secara otomatis — terlalu mahal (~10 menit). Full suite tetap manual.
- **Tidak** membuat CI/CD pipeline. Ini tooling lokal Claude Code.
- **Tidak** menulis ulang `_tmp_table_batch.py` / `_tmp_generic_quality_sanity.py`. Baseline canary adalah subset cepat independen.

## Architecture

```
┌─ Edit di backend/app/core/rag/** atau backend/app/api/routes/chat.py ─┐
│  PostToolUse hook → tulis flag .claude/_state/rag_dirty                 │
└─────────────────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─ Claude selesai respons (Stop hook) ──────────────────────────────────┐
│  Jika flag ada:                                                         │
│    python backend/scripts/eval_regression_check.py                      │
│      → POST 4 canary queries ke http://localhost:8000                   │
│      → compare vs docs/evaluation/baselines/canary_baseline.json        │
│      → stderr: tabel diff PASS/FAIL + delta skor                        │
│    hapus flag                                                           │
└─────────────────────────────────────────────────────────────────────────┘

┌─ User mengeluh jawaban RAG ────────────────────────────────────────────┐
│  Claude baca description skill rag-debug-answer (magnetic)              │
│  → auto-invoke → jalankan backend/scripts/rag_trace.py                  │
│  → analisis output per seksi (classify_query, filter, retrieval paths,  │
│     rerank, context, answer) dengan checklist hipotesis                 │
│  → lapor root cause + rekomendasi file/baris (TIDAK apply fix)          │
└─────────────────────────────────────────────────────────────────────────┘
```

## Components

### A1 — Dirty flag hook (`.claude/hooks/rag_mark_dirty.py`)

- Input: JSON event dari stdin (sesuai protokol hook Claude Code), struktur `{"tool_name": "...", "tool_input": {"file_path": "..."}}`.
- Logic: parse stdin, ekstrak `tool_input.file_path`. Kalau path match glob `backend/app/core/rag/**/*.py` atau `backend/app/api/routes/chat.py`, tulis file kosong `.claude/_state/rag_dirty`. Kalau tidak, exit 0 diam.
- Exit code: selalu 0 (hook tidak boleh memblok edit).
- Dependencies: pathlib stdlib saja.

### A2 — Regression runner hook (`.claude/hooks/rag_run_regression.py`)

- Trigger: `Stop` event.
- Logic:
  1. Kalau `.claude/_state/rag_dirty` tidak ada → exit 0 diam.
  2. Kalau ada, panggil `python backend/scripts/eval_regression_check.py`.
  3. Print output ke stderr (agar muncul sebagai tool result yang Claude baca).
  4. Hapus flag di akhir, regardless of pass/fail.
- Timeout: 90 detik hard cap (4 canary × ~20 detik + overhead).
- Exit code: 0 kalau tidak ada regresi, 1 kalau ada. Harness dapat menampilkan peringatan merah kalau 1.

### A3 — Regression comparator (`backend/scripts/eval_regression_check.py`)

- Mode: `--fast` (default, 4 canary) dan `--full` (semua query di `_tmp_table_batch.py` + `_tmp_generic_quality_sanity.py`).
- Input: baseline JSON di `docs/evaluation/baselines/canary_baseline.json`.
- Proses per query:
  1. POST ke `http://localhost:8000/api/chat/stream` dengan body sesuai baseline.
  2. Parse event `complete`, ambil `answer`, `sources`, `quality_check`.
  3. Evaluasi vs `expected` di baseline:
     - `answer_must_contain_any`: minimal satu string harus substring dari answer (case-insensitive).
     - `sources_allowed_doc_ids`: jika ada, semua `doc_id` di `sources` harus subset dari list ini (kebocoran lintas-dokumen = fail).
     - `min_score`: `quality_check.score >= min_score`.
     - `has_unavailable_claim`: persis sama dengan baseline.
  4. Regresi = salah satu dari:
     - Query yang sebelumnya lulus semua evaluasi kini gagal salah satu.
     - `quality_check.score` turun > 15% relatif terhadap baseline (bukan `min_score`).
     - `sources_allowed_doc_ids` dilanggar (leakage).
- Output:
  - Bersih: satu baris `✓ 4/4 canary stable` ke stdout, exit 0.
  - Regresi: tabel markdown ke stderr (query | expected | actual | delta), exit 1.
- Error handling:
  - Backend tidak merespons dalam 5 detik → print `[WARN] backend down, skipped`, exit 0.
  - Baseline JSON tidak ada → print instruksi regenerate, exit 0 (tidak fail).

### A4 — Baseline generator (`backend/scripts/eval_canary_baseline.py`)

- Dipicu manual oleh Anda (bukan hook): `python backend/scripts/eval_canary_baseline.py`.
- Jalankan 4 canary query, rekam hasil ke baseline JSON.
- Selalu overwrite (dengan konfirmasi prompt `--force` untuk non-interaktif).

### A5 — Baseline data (`docs/evaluation/baselines/canary_baseline.json`)

Struktur:

```json
{
  "generated_at": "2026-04-22T14:00:00+07:00",
  "commit": "becf3d9",
  "queries": [
    {
      "id": "canary_tabel13_doc1",
      "request": {"message": "apa isi tabel 13?", "document_id": "1"},
      "expected": {
        "answer_must_contain_any": ["Sekretariat Kabinet", "Kejaksaan Agung"],
        "sources_allowed_doc_ids": [1],
        "min_score": 20,
        "has_unavailable_claim": false
      },
      "baseline_actual": {
        "score": 28,
        "source_count": 5,
        "answer_length": 920
      }
    },
    {
      "id": "canary_pasal5_doc6",
      "request": {"message": "apa isi pasal 5?", "document_id": "6"},
      "expected": {
        "answer_must_contain_any": ["Ayat (7)", "Rencana Induk"],
        "sources_allowed_doc_ids": [6],
        "min_score": 20,
        "has_unavailable_claim": false
      }
    },
    {
      "id": "canary_leakage_guard",
      "request": {"message": "apa isi tabel 13?", "document_id": "3"},
      "expected": {
        "answer_must_contain_any": ["tidak ditemukan", "tidak ada tabel"],
        "sources_allowed_doc_ids": [3],
        "min_score": 0,
        "has_unavailable_claim": true
      }
    },
    {
      "id": "canary_general_spbe",
      "request": {"message": "apa itu SPBE?"},
      "expected": {
        "answer_must_contain_any": ["Sistem Pemerintahan Berbasis Elektronik"],
        "min_score": 15,
        "has_unavailable_claim": false
      }
    }
  ]
}
```

Canary #3 adalah regresi guard khusus untuk bug `doc_id` yang diperbaiki 2026-04-22.

### C1 — Trace CLI (`backend/scripts/rag_trace.py`)

- Input: `--query "..." [--doc-id N] [--json] [--port 8000]`.
- Output: 7 seksi, masing-masing satu blok terstruktur.
- Default human-readable (untuk user terminal); `--json` untuk dibaca Claude.
- Implementasi: boot minimum-state engine lokal (tanpa HTTP) supaya bisa trace pipeline internal, tidak hanya endpoint.
  - Impor `classify_query`, `_build_doc_filter`, `_resolve_doc_target`, `_vector_search`, `_bm25_search`, `_table_literal_search`, `rerank`, `retrieve_context`.
  - Panggil satu per satu dengan query + doc_id, rekam intermediate.
- 7 seksi output:
  1. `classify_query` → branch.
  2. `filter_resolution` → resolved `(db_id, filename)`, filter object, hit count di Qdrant scroll (dry-run `scroll_filter` dengan limit 1, `count` endpoint).
  3. `vector_search` → top-5 untuk setiap expanded query (filename, section, score).
  4. `bm25_search` → top-5 (filename, section, bm25_score).
  5. `table_literal_search` → top-5 (filename, table_label, table_literal_score) — skip kalau bukan table query.
  6. `rerank` → before/after order dengan cross-encoder score.
  7. `final_context_and_answer` → context length, generated answer, quality_check payload.

### C2 — Debug skill (`.claude/skills/rag-debug-answer/SKILL.md`)

- Frontmatter:
  ```
  ---
  name: rag-debug-answer
  description: Use when user reports a RAG answer problem in this SPBE project — wrong sources cited, answer contains content from unexpected document, doc_id scoping leaked, fabricated pasal/ayat, unavailable detector triggered incorrectly, or asks why the retriever returned specific docs. Traces classify_query → doc filter → per-path retrieval (vector / BM25 / table-literal) → rerank → context → answer via backend/scripts/rag_trace.py.
  ---
  ```
- Body sections:
  1. **Inputs** — parse query + document_id dari keluhan user; tanya kalau ambigu.
  2. **Run trace** — `python backend/scripts/rag_trace.py --query "..." [--doc-id N] --json`. Baca JSON output.
  3. **Analyze checklist** — 5 hipotesis umum dengan pointer file/line:
     - Filter resolution failure (doc_id tidak ter-resolve) → cek `_resolve_doc_target` di `langchain_engine.py`.
     - Qdrant filter hit = 0 → cek payload key di Qdrant vs `_build_doc_filter`.
     - Satu jalur bocor (filename di top-K berbeda dari target) → cek jalur tsb apakah sudah pass doc_id.
     - Rerank menenggelamkan dokumen target → cek cross-encoder skor vs filename target.
     - `has_unavailable_claim=True` dengan bukti lokal ada → detector over-trigger, rujuk Fase 2 plan `sementara-ini...`.
  4. **Report** — format output: symptom → section trace yang memicu kecurigaan → root cause hipotesis → file:line rekomendasi. **Tidak** apply fix.
  5. **Handoff** — setelah user konfirmasi root cause, serahkan ke `superpowers:test-driven-development` untuk implementasi (tulis test gagal dulu).
  6. **Escalation** — kalau 2 iterasi tidak ketemu, minta user untuk `git bisect` dari commit terakhir yang bekerja.

## Data Flow

- Edit file RAG → hook tulis flag → (banyak edit lain boleh mengikuti) → respons selesai → Stop hook baca flag → run regression → stderr diff → Claude baca & laporkan → flag dihapus.
- User kirim keluhan → Claude auto-invoke skill (via description matching) → skill runbook → rag_trace.py → analisis → laporan root cause.

Tidak ada state persist antar sesi selain baseline JSON.

## Error Handling

| Skenario | Behavior |
|---|---|
| Backend mati saat Stop hook | `eval_regression_check.py` exit 0 dengan warning "backend down, skipped" |
| Baseline JSON tidak ada | `eval_regression_check.py` exit 0 dengan instruksi generate |
| Hook timeout (>90s) | Harness kill hook, tidak menghalangi user |
| `rag_trace.py` gagal boot engine | Skill laporkan error + fallback minta user jalankan query manual via curl |
| Flag file tidak bisa ditulis (permission) | Hook exit 0, regresi terlewat (tidak fatal) |

## Testing

- **A3 unit tests:** `backend/tests/test_eval_regression.py`
  - Mock HTTP response dari backend, verifikasi `pass/fail` logic.
  - Test keyword matcher (`must_contain_any`), `forbid_doc_ids` leakage detection, threshold delta skor.
- **C1 unit tests:** `backend/tests/test_rag_trace.py`
  - Test `_resolve_doc_target` integration pada database test.
  - Snapshot test output JSON struktur (7 seksi).
- **Hooks:** tidak diunit-test (shell glue), tapi smoke-tested manual sebelum merge.
- **Integration smoke:** setelah implementasi, edit `langchain_engine.py` (no-op whitespace), trigger Stop, verifikasi hook menjalankan regression. Lalu revert.

## Rollout Plan

1. Implementasi C1 (`rag_trace.py`) + C2 (skill) dulu — value immediate, tidak butuh baseline.
2. Implementasi A3 (`eval_regression_check.py`) + A4 (baseline generator) + A5 (baseline JSON).
3. Generate baseline awal (commit saat itu dianggap "known good" — yaitu setelah fix `doc_id`).
4. Implementasi A1 + A2 (hooks) + wire di `settings.json`.
5. Smoke-test end-to-end.
6. Tambah entry di `QUICKSTART.md`: cara regenerate baseline, cara jalankan full eval manual, cara invoke skill debug secara eksplisit.

## Critical Files

| File | Komponen | Baru/Modif |
|---|---|---|
| `.claude/hooks/rag_mark_dirty.py` | A1 | Baru |
| `.claude/hooks/rag_run_regression.py` | A2 | Baru |
| `.claude/settings.json` | Hook wiring | Modif |
| `backend/scripts/eval_regression_check.py` | A3 | Baru |
| `backend/scripts/eval_canary_baseline.py` | A4 | Baru |
| `docs/evaluation/baselines/canary_baseline.json` | A5 | Baru |
| `backend/scripts/rag_trace.py` | C1 | Baru |
| `.claude/skills/rag-debug-answer/SKILL.md` | C2 | Baru |
| `backend/tests/test_eval_regression.py` | Test A3 | Baru |
| `backend/tests/test_rag_trace.py` | Test C1 | Baru |
| `.gitignore` | `.claude/_state/` | Modif |
| `QUICKSTART.md` | Docs | Modif |

## Sengaja Tidak Dilakukan

- **Tidak** menulis skill untuk tuning prompt / ingestion / ops — fokus pada A dan C saja sesuai prioritas user.
- **Tidak** memindah skill ke user-level (`~/.claude/skills/`). Keduanya project-specific; promote ke template global hanya setelah pola terbukti reusable.
- **Tidak** mengganti existing eval scripts (`_tmp_table_batch.py`, `_tmp_generic_quality_sanity.py`). Canary adalah lapisan cepat di atasnya, bukan pengganti.
- **Tidak** menambahkan state/database persistent untuk trace history. Setiap trace one-shot, disimpan di log harness kalau user butuh.
- **Tidak** auto-apply fix dari skill debug. Skill hanya melapor, TDD skill yang implementasi.
