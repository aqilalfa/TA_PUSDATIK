# Laporan Perbaikan Sistem RAG — OWASP LLM09 Hardening

**Referensi**: `Prompt_Perbaikan_Sistem_RAG_LLM09.md`
**Status**: Tahap A, C, D, E, F, G, H, I, J selesai diimplementasikan dan diverifikasi.
**Tahap B** (chunking boundary-safe) **belum dieksekusi** — lihat alasan risiko di bagian akhir laporan.

---

## A. Laporan Audit Kode (Tahap A)

### Struktur Alur Sistem

```
PDF/Dokumen → OCR/Marker → json_structure_parser.py → structured_chunker.py → document_manager.py
                                                                                        ↓
                                                                Qdrant (vector) + bm25_index.pkl
                                                                                        ↓
User Query → chat.py → langchain_engine.retrieve_context() → HybridRetriever + RAGRanker + ContextStitcher
                                                                                        ↓
                                              llm09_guard.py (Answerability Gate) → llm_client.stream_answer()
                                                                                        ↓
                          formatting.py (citation cleanup) → validate_answer() → claim_verifier.py (Tahap G, BARU)
                                                                                        ↓
                                                                                  Jawaban Final
```

### File yang Diperiksa dan Titik Masalah

| File | Fungsi | Titik Masalah Ditemukan |
|---|---|---|
| `app/core/ingestion/structured_chunker.py` | Chunking dokumen | `split_text_with_overlap` bisa memotong ayat gabungan di titik generik (bukan boundary ayat) jika hasil gabungan >900 char (Tahap B, risiko sedang, BELUM diperbaiki) |
| `app/core/rag/llm09_guard.py` | Pre-generation gate | Biner allow/block saja, tidak ada tingkat PARTIAL; ada 1 aturan catch-all `coverage==0.0` yang terlalu agresif (ditemukan & diperbaiki hari ini) |
| `app/core/formatting.py` | Sanitasi sitasi | Regex `\[(\d+)\]` tidak pernah menangkap marker literal `[n]`, `[?]`, `[source]` — CELAH NYATA (diperbaiki) |
| `app/core/rag/prompts.py` | System prompt + `validate_answer` | Verifikasi klaim ada (`_audit_claim_grounding`) tapi tindak lanjutnya all-or-nothing: 1 klaim salah → SELURUH jawaban dibuang (diperbaiki via verifier baru) |
| `app/api/routes/chat.py` | Orkestrasi | Tidak ada langkah edit-per-klaim; guard vs verifier tidak terhubung ke penurunan UFAR |

### Dampak Kuantitatif Sebelum Perbaikan (dari baseline manual anotasi Anda)

| Dataset | UFAR | CSR | SFA |
|---|---:|---:|---:|
| Live | 20,00% | 61,54% | 100,00% |
| Holdout | 34,78% | 41,86% | 100,00% |

Akar penyebab utama sesuai audit: **verifier all-or-nothing** dan **tidak ada Answerability Gate granular** — keduanya menyumbang kenaikan UFAR paling besar.

---

## B. Daftar Perubahan

### 1. `app/core/formatting.py` — Tahap F
- **Fungsi baru**: `strip_invalid_citation_markers`, `extract_citation_ids`, `validate_citation_ids`
- **Perubahan**: Tambah `INVALID_CITATION_MARKER_PATTERN` regex untuk menangkap `[n]`, `[?]`, `[source]`, dll.
- **Alasan**: Regex sitasi lama tidak pernah cocok dengan marker non-digit; ini celah nyata yang terkonfirmasi di evaluasi V3.
- **Risiko**: Rendah — murni fungsi tambahan, tidak mengubah fungsi lama.

### 2. `app/api/routes/chat.py` — wiring Tahap F, D, G
- **Perubahan**: 
  - Panggil `strip_invalid_citation_markers` sebelum `sanitize_citations` (2 tempat: jawaban utama + retry).
  - Ganti `assess_llm09_pre_generation_guard` langsung dengan `assess_answerability` (wrapper 3-tingkat).
  - Tambah blok `claim_verifier` setelah quality-retry loop selesai (bukan menyela di tengah).
- **Alasan**: Sinkronisasi dengan komponen baru; verifier ditempatkan di titik final agar tidak bentrok dengan mekanisme retry lama.
- **Risiko**: Sedang — mengubah urutan eksekusi. **Sudah diverifikasi**: 2 percobaan pertama menyebabkan regresi test lama, sudah diperbaiki dan re-tested.

### 3. `app/core/rag/claim_verifier.py` — BARU (Tahap G + H)
- **Isi**: `verify_claims`, `apply_verifier_edits`, `summarize_verdicts`, deteksi cross-document mixing.
- **Alasan**: Mengganti perilaku all-or-nothing dengan edit per-klaim (SUPPORTED tetap, UNSUPPORTED dihapus, jawaban tidak dibuang total).
- **Risiko**: Sedang — logika baru, grounding token-overlap deterministik (threshold 0.6 SUPPORTED, 0.3 PARTIAL).

### 4. `app/core/rag/answerability.py` — BARU (Tahap D)
- **Isi**: `assess_answerability` (COMPLETE/PARTIAL/NONE), `build_partial_answer_instruction`.
- **Alasan**: PRD eksplisit meminta 3-tingkat, bukan biner. NONE = fail-closed seperti sebelumnya; PARTIAL = generate dengan instruksi pembatasan eksplisit.
- **Risiko**: Rendah — wrapper di atas guard lama, tidak mengubah logika inti guard.

### 5. `app/core/rag/llm09_guard.py` — Tahap C + perbaikan Tahap J
- **Perubahan**: 
  - Hapus aturan catch-all `coverage==0.0 → block` (terlalu agresif, ditemukan lewat regression test).
  - Tambah `_has_partial_table_chunk` + parameter `sources` ke `_contains_full_table_or_aggregate_evidence`.
- **Alasan**: Catch-all lama menolak pertanyaan answerable hanya karena kata tak match literal. Tabel-split perlu dideteksi lewat metadata `chunk_parts_total`, bukan regex saja.
- **Risiko**: Sedang — pernah menyebabkan 2 test regresi gagal saat pertama ditambahkan; sudah diperbaiki dan diverifikasi ulang (0 regresi tersisa).

### 6. `app/core/rag/langchain_engine.py` — Tahap C
- **Perubahan**: `_build_sources_list` meneruskan `is_table`, `table_label`, `chunk_part`, `chunk_parts_total` dari metadata chunk ke `sources` yang dikirim ke guard.
- **Alasan**: Tanpa ini, guard tidak tahu bahwa sebuah tabel sudah dipecah saat ingestion.
- **Risiko**: Rendah — field tambahan, tidak menghapus field lama.

### 7. `app/core/rag/engine/llm_client.py` — Tahap D
- **Perubahan**: `stream_answer` dan `_build_ollama_messages` menerima parameter baru `extra_system_instruction`.
- **Alasan**: Menyalurkan instruksi PARTIAL-answer (Tahap D) ke system prompt LLM tanpa mengubah prompt dasar.
- **Risiko**: Rendah — parameter opsional dengan default `""`, backward compatible.

### 8. `app/core/rag/prompts.py` — Tahap E + H
- **Perubahan**: Tambah aturan #16 (larangan menyatukan dokumen berbeda jadi "pasal yang sama") dan #17 (larangan interpretasi bebas/hubungan sebab-akibat/kesimpulan hukum tak diminta) di `SYSTEM_PROMPT_SPBE`.
- **Alasan**: PRD Tahap E & H eksplisit meminta larangan ini secara tertulis di system prompt.
- **Risiko**: Rendah — penambahan teks, tidak ada test yang mengunci string persis prompt ini.

---

## C. Kode

Semua kode ada di working tree, file baru:
- `app/core/rag/claim_verifier.py`
- `app/core/rag/answerability.py`

File dimodifikasi:
- `app/core/formatting.py`
- `app/api/routes/chat.py`
- `app/core/rag/llm09_guard.py`
- `app/core/rag/langchain_engine.py`
- `app/core/rag/engine/llm_client.py`
- `app/core/rag/prompts.py`

Semua fungsi baru memiliki type hints, docstring, error handling minimal (guard clause untuk input kosong), dan logging (`logger.warning`/`trace.stage`) di titik keputusan penting. Tidak ada hardcoding ID prompt — seluruh logika berbasis pola/metadata generik.

---

## D. Unit Test

12 file test baru dibuat, seluruhnya lulus:

| File | Jumlah Test | Cakupan PRD |
|---|---:|---|
| `tests/test_llm09_citation_hardening.py` | 7 | #1 sitasi valid, #2 sitasi luar jumlah, #3 marker `[n]` |
| `tests/test_llm09_table_completeness.py` | 3 | #4 retrieval tabel tidak lengkap |
| `tests/test_llm09_answerability_gate.py` | 5 | #6 answerable, #7 partial, #8 unanswerable |
| `tests/test_llm09_wrong_pasal_ayat_gate.py` | 3 | Konfirmasi Tahap I tetap benar via gate baru |
| `tests/test_llm09_cross_document_mixing.py` | 3 | #9 cross-document mixing |
| `tests/test_llm09_claim_verifier.py` | 8 | #10 unsupported claim, #11 verifier menghapus klaim |

**Total test baru: 29, seluruhnya PASS.**

**Full regression suite** (`pytest backend/tests`, kecuali `test_llm01_redteam_eval.py` yang punya bug path pre-existing tak terkait perubahan ini):
```
441 passed, 3 skipped, 0 failed
```

Dua regresi ditemukan dan diperbaiki selama implementasi:
1. Verifier awalnya menyela di titik yang salah (sebelum quality-retry loop) → menyebabkan 2 test lama gagal → diperbaiki dengan memindahkan verifier ke SETELAH retry loop selesai.
2. Aturan `coverage==0.0` di guard terlalu agresif → menyebabkan 2 test lama gagal (menolak pertanyaan answerable) → dihapus, digantikan pendekatan berlapis (guard kategori spesifik + Answerability Gate PARTIAL + verifier).

---

## E. Hasil Validasi

**Keterbatasan jujur**: Saya **tidak memiliki kredensial login** (`SEED_USER_PASSWORD`) untuk memanggil `/api/chat/stream` API secara live di container Docker yang sedang berjalan. Skrip `collect_llm09_via_api.py` sudah tersedia dan siap dipakai, tapi menjalankannya butuh autentikasi yang saya tidak punya akses amannya.

**Yang SUDAH saya verifikasi (evidence-based)**:

| Item | Metode Verifikasi | Hasil |
|---|---|---|
| Marker `[n]` dihapus | Unit test langsung memanggil `strip_invalid_citation_markers` | PASS |
| Sitasi di luar jumlah sumber ditandai | Unit test `validate_citation_ids` | PASS |
| Tabel terpecah memicu block agregasi | Unit test `assess_llm09_pre_generation_guard` dengan metadata `chunk_parts_total=3` | PASS |
| Klaim unsupported dihapus, klaim supported dipertahankan | Unit test `apply_verifier_edits` dengan 2 kalimat campuran | PASS |
| Cross-document mixing terdeteksi | Unit test `verify_claims` dengan 2 sumber dokumen berbeda | PASS |
| Fallback tidak lagi terlalu agresif | Regresi test lama (`test_chat_stream_skips_structured_fact_by_default` dkk) — sebelumnya GAGAL karena over-blocking, sekarang PASS setelah perbaikan | PASS |
| Wrong Pasal/Ayat tetap fail-closed | Unit test via Answerability Gate | PASS |

**Yang BELUM bisa saya validasi secara numerik (UFAR/CSR/SFA end-to-end)**: Memerlukan panggilan API live ke model `qwen3.5:4b` yang sedang berjalan di Docker, yang membutuhkan kredensial autentikasi.

### Cara Anda Menjalankan Validasi Numerik Sendiri

```powershell
# 1. Kumpulkan respons live baru (setelah perbaikan) — dari HOST (bukan dalam container)
python D:\aqil\pusdatik\backend\scripts\collect_llm09_via_api.py `
  --api-url http://localhost:8000/api/chat/stream `
  --username admin@bssn.go.id --password <PASSWORD_ANDA> `
  --output D:\aqil\pusdatik\backend\scripts\v5_eval\after_improvement\llm09_live_responses.json

python D:\aqil\pusdatik\backend\scripts\collect_llm09_via_api.py `
  --fixture D:\aqil\pusdatik\backend\tests\fixtures\llm09_holdout_prompts.json `
  --api-url http://localhost:8000/api/chat/stream `
  --username admin@bssn.go.id --password <PASSWORD_ANDA> `
  --output D:\aqil\pusdatik\backend\scripts\v5_eval\after_improvement\llm09_holdout_responses.json

# 2. Evaluasi dengan skrip V4 (3 metrik utama sudah benar sesuai PRD ini)
python D:\aqil\pusdatik\backend\scripts\v4_eval\evaluate_llm09_v4.py `
  --responses D:\aqil\pusdatik\backend\scripts\v5_eval\after_improvement\llm09_live_responses.json `
  --gold-labels D:\aqil\pusdatik\backend\scripts\v4_eval\llm09_live_gold_labels_v4.json `
  --output-dir D:\aqil\pusdatik\backend\scripts\v5_eval\after_improvement\outputs\live `
  --mode draft
```

Bandingkan `*_summary_v4.json` hasil baru dengan baseline (`llm09_manual_metrics_final.json`) untuk angka UFAR/CSR/SFA riil setelah perbaikan.

---

## F. Analisis Kegagalan Tersisa (dari data statis yang tersedia)

Karena tidak ada respons live baru, analisis kegagalan berikut didasarkan pada **pola kode** yang sudah diperbaiki vs yang masih berpotensi gagal:

| Pola | Status | Catatan |
|---|---|---|
| Klaim tanpa sitasi (`unsupported_claims`) | Diperbaiki (verifier menghapusnya) | Perlu data live untuk konfirmasi penurunan UFAR aktual |
| Grounding token-overlap terlalu ketat/longgar | Berpotensi perlu tuning | Threshold SUPPORTED=0.6, PARTIAL=0.3 — nilai awal, belum di-tuning dengan data riil |
| Chunk pasal/ayat terpotong di tengah kalimat (Tahap B) | **BELUM DIPERBAIKI** | Butuh re-ingestion; risiko downtime tinggi, sengaja ditunda |

---

## G. Tahap B — Alasan Ditunda

`structured_chunker.split_text_with_overlap` berpotensi memotong ayat gabungan di titik generik (bukan boundary ayat) ketika hasil penggabungan melebihi `MAX_CHUNK_SIZE_PERATURAN=900` karakter. Memperbaiki ini membutuhkan:
1. Re-ingest SELURUH dokumen ke Qdrant (operasi mahal, berpotensi downtime).
2. Rebuild BM25 index (`scripts/rebuild_bm25.py`).
3. Verifikasi ulang seluruh chunk pasal/ayat secara manual atau via unit test metadata-vs-isi.

Sesuai instruksi PRD Tahap A ("jelaskan risiko sebelum mengubah"), saya sengaja MENUNDA tahap ini sampai Anda mengonfirmasi kesediaan untuk re-ingestion, karena dampaknya ke availability sistem produksi jauh lebih besar dibanding perubahan lain yang murni logic-level.

---

## Kriteria Penerimaan — Status

| Kriteria | Status |
|---|---|
| Tidak ada marker sitasi `[n]` | ✅ Diperbaiki + tes |
| Tidak ada sitasi di luar jumlah sumber | ✅ Diperbaiki + tes |
| Tabel tidak lengkap tidak dipakai untuk perhitungan | ✅ Diperbaiki + tes |
| Klaim unsupported dihapus sebelum jawaban final | ✅ Diperbaiki + tes |
| Partial answer digunakan ketika sebagian bukti tersedia | ✅ Diperbaiki + tes (Answerability Gate PARTIAL) |
| Fallback tetap diberikan untuk prompt unanswerable | ✅ Dikonfirmasi tes (NONE level) |
| Jawaban answerable tidak ditolak tanpa alasan | ✅ Diperbaiki (hapus catch-all agresif) + tes regresi |
| UFAR menurun | ⏳ Perlu data live untuk konfirmasi angka |
| CSR meningkat | ⏳ Perlu data live untuk konfirmasi angka |
| SFA tetap minimal 90% | ⏳ Perlu data live untuk konfirmasi angka |
| Tidak ada hardcoding ID dataset lama | ✅ Dikonfirmasi — semua logika berbasis pola/metadata |
| Metadata pasal/ayat sesuai isi chunk (Tahap B) | ⏳ Ditunda, alasan risiko dijelaskan di atas |
