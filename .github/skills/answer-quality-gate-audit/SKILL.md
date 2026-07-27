---
name: answer-quality-gate-audit
description: "Gunakan saat jawaban RAG buruk meskipun retrieval OK — menyelidiki false-positive detector unavailable, skor quality gate rendah, atau regresi pasca-perubahan kode."
argument-hint: "Deskripsi masalah (contoh: Q3_PERBANDINGAN masih FAIL, atau tabel X klaim 'tidak tersedia')"
user-invocable: true
---

# Answer Quality Gate Audit

Skill ini mendiagnosis masalah pada **layer generation/quality gate**, bukan retrieval. Gunakan setelah dipastikan retrieval sudah menarik konteks yang relevan.

## Kapan Dipakai

- Jawaban RAG menyebut "tidak tersedia/tidak ditemukan" padahal konteks relevan sudah ada di source.
- `conflicting_unavailable_claim=true` pada payload quality_check meski focus_coverage tinggi.
- Score quality gate turun atau query yang sebelumnya PASS kini FAIL.
- Setelah tuning detector/retrieval, ingin memastikan tidak ada regresi.

## Referensi

- Standard commands: `.github/instructions/project-standard-commands.instructions.md`
- Retrieval audit: `.github/skills/table-query-audit-workflow/SKILL.md`
- End-to-end workflow: `.github/skills/spbe-rag-workflow/SKILL.md`

## Arsitektur Quality Gate (ringkas)

File utama: `backend/app/api/routes/chat.py`

- `_find_unavailable_triggers(text)` — scan teks jawaban; setiap hit melaporkan `phrase`, `window`, `local_evidence_present`, `suppressed`.
- `_has_local_evidence(window)` — supress hit jika window ±140 char mengandung angka, stage marker, indikator/aspek/domain ref, rating, bobot, atau sitasi `[n]`.
- `_contains_unavailable_signal(text)` — True jika ada trigger yang tidak disupress.
- `_build_answer_quality_report(...)` — menghasilkan `score`, `needs_retry`, `retry_reasons`, `unavailable_triggers_active`, `unavailable_triggers_suppressed`.
- Quality gate aktif di `POST /api/chat/stream`; complete event memuat `quality_check`.

Env flag `QUALITY_DEBUG=1`: mencetak ke log setiap trigger aktif (phrase + window).

## Prosedur Diagnosis

### 1) Konfirmasi retrieval OK terlebih dahulu

- Cek `sources` di payload complete event: apakah source sudah mengarah ke dokumen/bagian yang tepat?
- Jika sumber masih salah: selesaikan retrieval dulu (lihat `table-query-audit-workflow`).

### 2) Aktifkan observability

Jalankan backend dengan debug mode:

```
set QUALITY_DEBUG=1
venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Kirim query problematik via `POST /api/chat/stream` lalu lihat:

- Log backend: trigger aktif + window konteks.
- Payload SSE event `complete` → `quality_check.unavailable_triggers_active`.

### 3) Klasifikasi trigger

Untuk setiap `unavailable_triggers_active`:

| `local_evidence_present` | `suppressed` | Artinya |
|---|---|---|
| `true` | `true` | Sudah disupress — frasa deskriptif, bukan klaim absen |
| `false` | `false` | Trigger aktif — model benar-benar mengklaim data hilang |

Jika trigger seharusnya disupress (ada angka/stage/indikator di window) tapi tidak: kemungkinan pola evidence belum mencakup konteks itu → perluas `LOCAL_EVIDENCE_PATTERNS` di `chat.py`.

### 4) Jalankan audit batch tabel

```
venv\Scripts\python.exe scripts\_tmp_table_batch.py
```

Lihat kolom `Triggers` di report Markdown — frasa aktif per tabel. Target: kolom ini kosong (`-`) untuk tabel yang PASS.

### 5) Jalankan sanity check non-tabel

```
venv\Scripts\python.exe scripts\_tmp_generic_quality_sanity.py
```

Target: semua 4 query PASS (termasuk Q3_PERBANDINGAN).

### 6) Jalankan regression guard

```
venv\Scripts\python.exe scripts\eval_regression_check.py
```

- Exit 0: tidak ada regresi.
- Exit 1: ada query yang berubah PASS → FAIL, atau skor turun >15%.

Baseline tersimpan di: `data/evaluation/baselines/quality_gate_baseline.json`

Update baseline setelah perubahan yang disengaja:

```
venv\Scripts\python.exe scripts\eval_regression_check.py --update-baseline
```

### 7) Tindakan per temuan

| Temuan | Tindakan |
|---|---|
| Trigger aktif tapi frasa deskriptif | Perluas `LOCAL_EVIDENCE_PATTERNS` di `chat.py` |
| Trigger supress semuanya, tapi skor tetap rendah | Cek sinyal lain: `focus_coverage < 0.45`, `citation_count = 0`, `list_structure` |
| Semua sinyal OK tapi jawaban tetap buruk | Masalah model (prompt/token limit) → tuning `_build_retry_query` atau prompt LLM |
| Regresi pada tabel yang sebelumnya PASS | Cek apakah `is_table` metadata hilang (perlu backfill ulang) atau perubahan threshold |

## Output Skill

- Status per query: PASS/FAIL + retry_reasons eksplisit.
- Daftar trigger aktif dengan window konteks.
- Skor sebelum vs sesudah (baseline regression diff).
- Rekomendasi konkret (kode / script / env flag).

## Definition of Done

- Semua query uji (tabel + non-tabel) mencapai PASS konsisten.
- Tidak ada `conflicting_unavailable_claim` pada frasa yang secara konten deskriptif.
- Regression guard exit 0 terhadap baseline terakhir.
- Perubahan apapun dicatat: apakah skor naik, turun, atau stabil.
