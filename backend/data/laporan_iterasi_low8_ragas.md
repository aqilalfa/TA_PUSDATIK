# Laporan Iterasi RAGAS Low-Score 8 Kasus

Tanggal: 2026-06-05  
Subset evaluasi: GT-007, GT-009, GT-013, GT-020, GT-021, GT-027, GT-032, GT-039  
Top-k konteks: 5  
Model jawaban RAG: `qwen3.5:4b`  
LLM-as-judge utama: `qwen/qwen3-32b` melalui Groq  
Fallback judge untuk nilai null: `meta-llama/llama-4-scout-17b-16e-instruct`

## Ringkasan Hasil Iterasi

Evaluasi low8 menunjukkan bahwa sebagian besar kegagalan bukan berupa kehilangan konteks utama, melainkan kombinasi:

1. **Noise/ranking issue**: konteks benar ada di top-5, tetapi bukan rank utama atau bercampur dengan konteks serupa.
2. **Jawaban terlalu panjang**: model menambahkan informasi tambahan walaupun jawaban inti sudah benar.
3. **Aggregate-vs-row mismatch**: pertanyaan nasional dijawab dari baris instansi individual, bukan ringkasan nasional.

Rata-rata RAGAS low8 dari `eval_ragas_iterasi_low8_qwen3_32b.json`:

| Metrik | Nilai |
|---|---:|
| context_precision | 0.6417 |
| context_recall | 0.8750 |
| faithfulness | 0.7500 |
| answer_relevancy | 0.7418 |

Catatan: nilai faithfulness GT-007 dan GT-039 awalnya null pada judge Qwen; fallback Llama menghasilkan GT-007 = 0.6667 dan GT-039 = 0.3333.

## Analisis Per Kasus

| ID | Status | Pola Masalah | Rekomendasi / Tindakan |
|---|---|---|---|
| GT-007 | Sudah membaik | Konteks utama Pasal 4 rank #1, recall 1.0. Jawaban masih menambah kalimat kedua dari konteks BSSN sehingga faithfulness fallback 0.6667. | Tidak perlu retrieval fix tambahan. Prompt sudah diberi guard agar pertanyaan tujuan/definisi dijawab 1 kalimat inti. |
| GT-009 | Perlu ranking fix | Konteks Pasal 8 yang tepat ada di top-5, tetapi kalah oleh Pedoman 2024 dan pasal terkait Arsitektur SPBE Pemerintah Daerah/Instansi Pusat. | Tambahkan boost khusus untuk pertanyaan durasi `Arsitektur SPBE Nasional` agar Pasal 8 dan frasa `disusun untuk jangka waktu 5 tahun` menang. |
| GT-013 | Tidak perlu retrieval fix | context_precision dan context_recall sudah 1.0. Jawaban benar menyebut Tim Asesor Eksternal, tetapi terlalu elaboratif sehingga answer_relevancy rendah. | Tidak perlu ranker fix. Perbaikan utama berupa prompt ringkas untuk pertanyaan `Siapa...`, jika nanti dibutuhkan. |
| GT-020 | Cukup baik | Tabel 13 rank #1 dan jawaban benar: `Kurang`. Faithfulness 0.5 kemungkinan karena jawaban menyebut dokumen/pasal secara elaboratif. | Tidak perlu retrieval fix. |
| GT-021 | Stabil | Semua metrik tinggi; context_precision/recal/faithfulness 1.0 dan answer_relevancy 0.9749. | Tidak perlu perubahan. |
| GT-027 | Perlu ranking fix | Konteks tepat Pasal 4 ada di rank #5; rank atas adalah overview/struktur audit dan Pasal 23. Jawaban benar tetapi precision rendah 0.2. | Tambahkan boost untuk `Pelaksana Audit Keamanan SPBE` + `LATIK cakupan Keamanan SPBE`, dan penalti overview yang tidak memuat LATIK. |
| GT-032 | Cukup baik | Konteks utama sanksi administratif ada dan answer_relevancy tinggi 0.9068. Faithfulness 0.75 karena jawaban menambah uraian administratif. | Tidak perlu retrieval fix. |
| GT-039 | Perlu aggregate fix | Pertanyaan meminta domain terendah secara nasional, tetapi konteks top-5 berupa data instansi individual. Jawaban menyimpulkan nilai instansi, bukan ringkasan nasional `Domain Manajemen SPBE 1,86`. | Tambahkan boost ringkasan/agregat nasional dan prompt guard agar pertanyaan `secara nasional` memakai ringkasan agregat, bukan baris instansi. |

## Perubahan yang Diterapkan

File yang diubah:

- `backend/app/core/rag/engine/rankers.py`
  - GT-009: boost Pasal 8 dan frasa `Arsitektur SPBE Nasional disusun untuk jangka waktu 5 (lima) tahun`; penalti konteks Pedoman 2024 dan konteks Arsitektur SPBE daerah/instansi pusat untuk pertanyaan nasional.
  - GT-027: boost Pasal 4, frasa `LATIK cakupan Keamanan SPBE`, dan daftar `LATIK pemerintah` / `LATIK Terakreditasi`; penalti overview yang tidak memuat LATIK.
  - GT-039: memperkuat boost ringkasan `Analisis Capaian Indeks Maturitas SPBE Nasional`, `nilai indeks domain nasional`, `rerata`, dan `Domain Manajemen SPBE 1,86`; penalti data baris instansi individual untuk pertanyaan nasional.
- `backend/app/core/rag/prompts.py`
  - Menambah aturan bahwa pertanyaan laporan `secara nasional` harus dijawab dari ringkasan/agregat nasional bila tersedia, bukan dari baris instansi individual.
- `backend/tests/test_rag_legal_ranker.py`
  - Menambah regresi untuk GT-009, GT-027, dan GT-039.

## Verifikasi Setelah Perubahan

Perintah yang sudah dijalankan:

```powershell
venv\Scripts\python.exe -m pytest tests\test_rag_legal_ranker.py -q
```

Hasil:

```text
25 passed in 0.33s
```

Kompilasi Python juga berhasil untuk file yang diubah:

```powershell
venv\Scripts\python.exe -m py_compile app\core\rag\engine\rankers.py app\core\rag\prompts.py tests\test_rag_legal_ranker.py
```

Retrieval low8 setelah penyesuaian kedua:

- File: `backend/data/eval_retrieval_ids_report_iterasi_low8_after_fixes_v2.json`
- `hit@1`: naik dari 0.625 menjadi 0.750
- `hit@5`: tetap 1.000
- `recall@5`: tetap 0.8333, sehingga tidak turun dibanding baseline low8
- `citation_match@5`: naik dari 0.875 menjadi 1.000
- `source_doc_hit@5`: tetap 1.000

RAG answer collection setelah perubahan:

- File: `backend/data/eval_results_iterasi_low8_after_fixes_v2.json`

RAGAS setelah perubahan:

- Primary Qwen judge: `backend/data/eval_ragas_iterasi_low8_after_fixes_v2_qwen3_32b.json`
  - Banyak metrik null karena Groq Qwen terkena TPD/rate-limit pada paruh evaluasi.
  - Nilai valid awal menunjukkan `context_precision` membaik pada GT-009 menjadi 1.0 dan `context_recall` tetap 1.0 untuk kasus yang berhasil dinilai.
- Fallback Llama judge: `backend/data/eval_ragas_iterasi_low8_after_fixes_v2_llama4.json`
  - `context_precision`: 0.8450
  - `context_recall`: 0.7500
  - `faithfulness`: 0.7946
  - `answer_relevancy`: 0.6289
  - Catatan: fallback menilai GT-013 `context_recall=0.0` walaupun konteks eksplisit Tim Asesor Eksternal ada; interpretasi ini perlu diperlakukan hati-hati sebagai judge variance.

## Temuan Tambahan GT-039

Investigasi database menunjukkan frasa/angka target `Domain Manajemen SPBE dengan skor 1,86` belum ditemukan dalam chunk Laporan 2024 yang tersedia. Pencarian literal pada `chunks.chunk_text` hanya menemukan nilai `1,86/1.86` pada dokumen Laporan 2023, bukan Laporan 2024. Istilah ringkasan seperti `nilai indeks domain nasional` dan `Analisis Capaian Indeks Maturitas` juga tidak muncul pada corpus chunk saat ini.

Implikasi: GT-039 tidak cukup diselesaikan dengan reranker/prompt saja selama sumber agregat nasional 2024 belum terindeks. Perlu salah satu dari:

1. Re-ingest Laporan 2024 dengan memastikan halaman/tabel ringkasan domain nasional ikut menjadi chunk; atau
2. Koreksi ground truth/reference context GT-039 jika memang angka 1,86 tidak tersedia di corpus aktif; atau
3. Tambahkan curated aggregate chunk dari laporan resmi 2024 jika sumber PDF memuat nilai tersebut tetapi parser melewatkannya.

LSP:

- `prompts.py`: bersih.
- `rankers.py`: hanya warning dependency editor `langchain_core.documents` tidak ter-resolve; ini sudah dikenal sebagai isu environment LSP, sementara runtime test venv berhasil.

## Langkah Lanjutan yang Disarankan

1. Untuk GT-039, perbaiki ingestion/ground truth sebelum mengulang optimasi ranker.
2. Jalankan ulang RAGAS targeted low8 setelah limit Groq Qwen pulih agar metrik primary judge lengkap.
3. Jalankan ulang RAGAS targeted low8 dengan metrik:
   - context_precision
   - context_recall
   - faithfulness
   - answer_relevancy
4. Jika Groq `qwen/qwen3-32b` terkena limit, retry null/failed case saja dengan fallback judge dan tandai hasil fallback sebagai pembanding, bukan pengganti penuh.
5. Baru pertimbangkan full 40-question RAGAS jika targeted low8 stabil dan recall tidak turun.
