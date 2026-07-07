# Laporan Mekanisme Evaluasi RAGAS SPBE RAG System

Tanggal penyusunan: 2026-06-06  
Sistem yang dievaluasi: SPBE RAG System  
Model jawaban RAG: `qwen3.5:4b`  
Framework evaluasi: RAGAS 0.2.x  
Provider LLM-as-judge: Groq  
Metrik utama: `context_precision`, `context_recall`, `faithfulness`, `answer_relevancy`

---

## 1. Tujuan Evaluasi

Evaluasi RAGAS dilakukan untuk mengukur kualitas sistem Retrieval-Augmented Generation (RAG) dari dua sisi utama:

1. **Kualitas retrieval**: apakah konteks yang diambil dari corpus dokumen relevan dan mencakup fakta yang dibutuhkan.
2. **Kualitas jawaban**: apakah jawaban model sesuai konteks, tidak berhalusinasi, dan langsung menjawab pertanyaan.

Evaluasi ini tidak hanya melihat apakah jawaban tampak benar, tetapi juga memeriksa hubungan antara:

```text
Pertanyaan → Konteks yang diambil → Jawaban model → Ground truth
```

---

## 2. Sumber Data Evaluasi

Data evaluasi berasal dari ground truth canonical:

```text
backend/data/ground_truth_spbe_ragas_canonical.jsonl
```

Dataset ini berisi 40 pertanyaan. Setiap item evaluasi memiliki komponen utama:

| Field | Fungsi |
|---|---|
| `id` | ID kasus evaluasi, misalnya `GT-001`. |
| `question` | Pertanyaan yang akan dikirim ke sistem RAG. |
| `ground_truth` | Jawaban referensi/ideal. |
| `source_doc` | Dokumen sumber yang diharapkan. |
| `doc_type` | Jenis dokumen, misalnya `peraturan` atau `laporan`. |

Ground truth ini menjadi pembanding utama untuk menilai apakah jawaban dan konteks hasil retrieval sudah sesuai.

---

## 3. Tahap 1 — Collect Jawaban dari RAG

Tahap pertama dilakukan oleh script:

```text
backend/scripts/evaluate_rag.py
```

Pada tahap ini, setiap pertanyaan dari ground truth dikirim ke pipeline RAG. Mekanismenya:

1. Sistem membaca pertanyaan dari ground truth.
2. Sistem menjalankan retrieval terhadap corpus dokumen.
3. Retrieval memakai **top-5 context**.
4. Lima konteks tersebut dikirim ke model jawaban `qwen3.5:4b`.
5. Model menghasilkan jawaban berbasis konteks.
6. Hasil disimpan ke file JSON.

Potongan mekanisme penting dari evaluator:

```python
retrieval = langchain_engine.retrieve_context(
    query=question,
    top_k=5,
    use_rag=True,
    doc_id=None,
)
```

Artinya, selama evaluasi ini retrieval tetap menggunakan **top-5**. Ini penting karena sebelumnya ada constraint agar recall tidak turun.

Output collect berisi:

| Field | Isi |
|---|---|
| `question` | Pertanyaan evaluasi. |
| `ground_truth` | Jawaban referensi. |
| `answer` | Jawaban yang dihasilkan sistem RAG. |
| `contexts` | Full text dari konteks top-5. |
| `retrieved_context_ids` | ID konteks yang diambil. |
| `retrieved_sources` | Metadata dokumen dan ranking konteks. |
| `latency_s` | Waktu proses per pertanyaan. |

Untuk evaluasi penuh setelah prompt fix, output collect tersimpan di:

```text
backend/data/eval_results_full_prompt_fix.json
```

Ringkasan collect/score heuristic:

| Metrik heuristic | Nilai |
|---|---:|
| Total pertanyaan | 40 |
| Berhasil dievaluasi | 40 |
| Gagal | 0 |
| Rata-rata latency | 36.11 detik/pertanyaan |
| semantic_similarity | 0.6263 |
| context_recall heuristic | 0.9195 |
| answer_coverage heuristic | 0.8828 |

Catatan: metrik heuristic ini bukan skor RAGAS final. Ini hanya pengecekan awal berbasis embedding/token overlap.

---

## 4. Tahap 2 — Konversi Hasil RAG ke Format RAGAS

Tahap kedua dilakukan oleh script:

```text
backend/scripts/evaluate_ragas.py
```

Script ini membaca hasil collect dari `eval_results_*.json`, lalu mengubahnya ke format `SingleTurnSample` RAGAS.

Struktur yang dikirim ke RAGAS:

```python
SingleTurnSample(
    user_input=r["question"],
    response=r["answer"],
    retrieved_contexts=r["contexts"],
    reference=r["ground_truth"],
)
```

Maknanya:

| Komponen RAGAS | Sumber dari hasil collect | Fungsi |
|---|---|---|
| `user_input` | `question` | Pertanyaan asli. |
| `response` | `answer` | Jawaban sistem RAG. |
| `retrieved_contexts` | `contexts` | Konteks top-5 yang digunakan sistem. |
| `reference` | `ground_truth` | Jawaban ideal untuk pembanding. |

Sebelum dikirim ke RAGAS, teks dibersihkan dari marker sitasi seperti `[1]`, HTML break, dan karakter non-printable agar judge tidak terganggu oleh format teknis.

---

## 5. Tahap 3 — Konfigurasi LLM-as-Judge

RAGAS membutuhkan LLM judge untuk menilai beberapa metrik. Pada evaluasi ini digunakan Groq sebagai provider.

Model judge yang digunakan:

| Kebutuhan | Model |
|---|---|
| Judge utama | `qwen/qwen3-32b` |
| Judge fallback | `meta-llama/llama-4-scout-17b-16e-instruct` |
| Embedding RAGAS | `firqaaa/indo-sentence-bert-base` |

RAGAS dijalankan dengan konfigurasi:

```text
provider: groq
temperature: 0.0
max_workers: 1
timeout: 600
raise_exceptions: false
```

`max_workers=1` dipakai agar lebih aman terhadap rate limit. `raise_exceptions=false` membuat evaluasi tetap menghasilkan laporan walaupun sebagian item gagal dinilai oleh judge.

---

## 6. Tahap 4 — Metrik yang Dihitung

Empat metrik utama yang digunakan:

| Metrik | Yang Dinilai | Input yang Dipakai | Interpretasi |
|---|---|---|---|
| `context_precision` | Apakah konteks yang diambil relevan. | Pertanyaan + retrieved contexts + reference. | Tinggi berarti top-5 minim noise. |
| `context_recall` | Apakah konteks mencakup fakta ground truth. | Retrieved contexts + reference. | Tinggi berarti fakta penting tidak hilang. |
| `faithfulness` | Apakah jawaban setia pada konteks. | Response + retrieved contexts. | Tinggi berarti jawaban tidak berhalusinasi. |
| `answer_relevancy` | Apakah jawaban langsung relevan dengan pertanyaan. | User input + response. | Tinggi berarti jawaban tepat sasaran. |

Skala semua metrik adalah 0 sampai 1.

---

## 7. Tahap 5 — Agregasi Skor

Setelah RAGAS selesai, hasil per pertanyaan dikonversi ke dataframe, lalu disimpan sebagai JSON.

Script menyimpan:

| Bagian laporan | Fungsi |
|---|---|
| `averages` | Rata-rata skor per metrik. |
| `by_doc_type` | Rata-rata per jenis dokumen. |
| `per_question` | Skor setiap pertanyaan. |

Mekanisme agregasi:

```python
col = scores_df[m].dropna()
averages[m] = round(float(col.mean()), 4) if len(col) else None
```

Artinya:

- Nilai `null` tidak ikut dihitung dalam rata-rata.
- Jika judge gagal menilai sebagian item karena rate limit/parser error, rata-rata hanya dihitung dari nilai valid.
- Karena itu, valid count penting untuk membaca skor.

---

## 8. Baseline Evaluasi Awal 40 Pertanyaan

Baseline awal berasal dari:

```text
backend/data/eval_ragas_aggregate_4metrics_groq_auto.json
```

Baseline ini merupakan hasil agregasi evaluasi 40 pertanyaan sebelum prompt fix.

| Metrik | Rata-rata | Valid | Null |
|---|---:|---:|---:|
| context_precision | 0.8193 | 40 | 0 |
| context_recall | 0.9250 | 40 | 0 |
| faithfulness | 0.8352 | 40 | 0 |
| answer_relevancy | 0.6659 | 40 | 0 |

Interpretasi baseline:

- Retrieval sudah kuat karena `context_recall=0.9250`.
- Grounding cukup baik karena `faithfulness=0.8352`.
- Titik lemah utama adalah `answer_relevancy=0.6659`, karena sebagian jawaban benar tetapi terlalu panjang atau melebar.

---

## 9. Evaluasi Setelah Prompt Fix

Setelah prompt diperbaiki agar jawaban lebih langsung berdasarkan tipe pertanyaan, dilakukan evaluasi ulang full 40.

### 9.1 Collect RAG Setelah Prompt Fix

File:

```text
backend/data/eval_results_full_prompt_fix.json
backend/data/eval_report_full_prompt_fix.json
```

Hasil collect:

| Item | Nilai |
|---|---:|
| Total pertanyaan | 40 |
| Berhasil | 40 |
| Gagal | 0 |
| Rata-rata latency | 36.11 detik |
| context_recall heuristic | 0.9195 |
| answer_coverage heuristic | 0.8828 |

### 9.2 RAGAS Qwen Setelah Prompt Fix

File:

```text
backend/data/eval_ragas_full_prompt_fix_qwen3_32b.json
```

Hasil yang keluar:

| Metrik | Rata-rata Qwen partial | Valid | Null |
|---|---:|---:|---:|
| context_precision | 0.9022 | 17 | 23 |
| context_recall | 1.0000 | 16 | 24 |
| faithfulness | 0.8152 | 11 | 29 |
| answer_relevancy | 0.6924 | 15 | 25 |

Catatan penting: hasil Qwen ini **partial**, karena Groq terkena token-per-day/rate limit saat evaluasi berjalan. Maka skor ini belum bisa dianggap skor full 40 final.

### 9.3 RAGAS Fallback Llama 4 Setelah Prompt Fix

File:

```text
backend/data/eval_ragas_full_prompt_fix_llama4.json
```

Hasil yang keluar:

| Metrik | Rata-rata Llama partial | Valid | Null |
|---|---:|---:|---:|
| context_precision | 0.9006 | 35 | 5 |
| context_recall | 0.9714 | 35 | 5 |
| faithfulness | 0.8552 | 34 | 6 |
| answer_relevancy | 0.6908 | 33 | 7 |

Fallback Llama lebih lengkap daripada Qwen, tetapi masih partial karena rate limit juga terjadi di bagian akhir.

---

## 10. Cara Skor “Segitu” Dihasilkan

Skor akhir yang terlihat pada laporan dihasilkan dari rata-rata nilai valid per metrik.

Contoh untuk `answer_relevancy` pada Qwen:

1. RAGAS menilai answer relevancy untuk setiap pertanyaan.
2. Karena rate limit, hanya 15 dari 40 item memiliki nilai valid.
3. Nilai valid tersebut dirata-ratakan.
4. Hasilnya menjadi `answer_relevancy=0.6924`.

Contoh untuk fallback Llama:

1. RAGAS menilai answer relevancy untuk 40 item.
2. 33 item valid, 7 item null.
3. Rata-rata dari 33 item valid menghasilkan `answer_relevancy=0.6908`.

Jadi skor tidak muncul dari satu jawaban, melainkan dari agregasi banyak penilaian per pertanyaan.

---

## 11. Perbandingan Baseline vs Setelah Prompt Fix

Karena hasil full setelah prompt fix masih partial, perbandingan paling fair adalah membandingkan item yang sama-sama valid.

### 11.1 Perbandingan Same-ID Valid Set

Perbandingan ini memakai hasil gabungan: Qwen sebagai primary, Llama sebagai fallback jika Qwen null.

| Metrik | Baseline pada ID yang sama | New merged valid | Delta |
|---|---:|---:|---:|
| context_precision | 0.8290 | 0.8990 | +0.0700 |
| context_recall | 0.9429 | 1.0000 | +0.0571 |
| faithfulness | 0.8212 | 0.8341 | +0.0129 |
| answer_relevancy | 0.6610 | 0.6768 | +0.0158 |

Interpretasi:

- Pada item valid yang bisa dibandingkan, semua metrik naik.
- `answer_relevancy` naik tipis pada full set, tetapi naik besar pada subset low relevancy.
- Prompt fix tidak terlihat merusak `context_recall` atau `faithfulness` pada subset valid.

### 11.2 Kenapa Kenaikan Full Set Tidak Sebesar Subset Low Relevancy?

Sebelumnya, subset 9 pertanyaan low relevancy naik dari:

```text
0.3813 → 0.7156
```

Namun full baseline 40 pertanyaan sudah lebih tinggi:

```text
0.6659
```

Karena sebagian besar pertanyaan full set sudah cukup baik, dampak prompt fix pada rata-rata full 40 menjadi lebih kecil.

---

## 12. Keterbatasan Evaluasi

### 12.1 Rate Limit Groq

Evaluasi full RAGAS membutuhkan banyak panggilan LLM. Untuk 40 pertanyaan dan 4 metrik, total pekerjaan teoritis adalah:

```text
40 pertanyaan × 4 metrik = 160 job evaluasi
```

Setiap job dapat memanggil LLM judge satu atau lebih kali. Karena itu, full evaluation mudah terkena token-per-day/rate limit.

Dampaknya:

- Qwen full result hanya valid sebagian.
- Llama fallback juga masih menyisakan null pada beberapa ID akhir.
- Rata-rata post-fix harus dibaca sebagai partial valid result, bukan final 40/40 penuh.

### 12.2 Null Score Tidak Dihitung dalam Average

Script memakai `dropna()`, sehingga nilai null tidak menurunkan rata-rata secara langsung. Ini benar secara teknis, tetapi membuat interpretasi harus memperhatikan valid count.

Contoh:

```text
answer_relevancy Qwen = 0.6924, tetapi valid hanya 15/40.
```

Maka skor tersebut belum setara dengan baseline lama yang valid 40/40.

### 12.3 Judge Variance

Model judge yang berbeda dapat memberi skor berbeda, terutama pada metrik yang bersifat interpretatif seperti `answer_relevancy` dan `faithfulness`.

Karena itu:

- Qwen dipakai sebagai judge utama.
- Llama dipakai sebagai fallback saat Qwen terkena limit.
- Hasil gabungan harus diberi catatan bahwa ada perbedaan judge.

### 12.4 GT-039 Awalnya Masalah Data/Ingestion, Kini Resolved pada Retest Focused

GT-039 menanyakan agregat nasional Laporan 2024. Pada baseline/low8 lama, fakta target `Domain Manajemen SPBE dengan skor 1,86` belum ditemukan jelas di chunk aktif sehingga skor GT-039 tidak boleh diperlakukan sebagai kegagalan prompt semata.

Setelah dokumen `Laporan Pelaksanaan Evaluasi SPBE 2024.pdf` diunggah ulang dan terindeks, retest focused GT-039 menunjukkan top-5 retrieval seluruhnya berasal dari dokumen baru tersebut (`document_id=23`, chunk `39`, `40`, `37`, `36`, `45`). Jawaban sistem juga sudah menyebut Domain Manajemen dengan nilai indeks `1,86`.

Skor focused GT-039 setelah unggah ulang dokumen:

| Metrik | Skor |
|---|---:|
| context_precision | 0.9500 |
| context_recall | 1.0000 |
| faithfulness | 1.0000 |
| answer_relevancy | 0.6690 |

Dengan demikian, GT-039 kini **resolved** secara retrieval dan faithfulness. `answer_relevancy` masih dapat ditingkatkan dengan jawaban yang lebih ringkas.

---

## 13. Kesimpulan Mekanisme dan Hasil

Mekanisme evaluasi berjalan sebagai berikut:

```text
Ground truth 40 pertanyaan
→ evaluate_rag.py collect jawaban RAG dengan top-5 contexts
→ hasil disimpan ke eval_results_*.json
→ evaluate_ragas.py konversi ke SingleTurnSample
→ RAGAS menilai 4 metrik menggunakan Groq LLM-as-judge
→ skor per pertanyaan disimpan
→ nilai valid dirata-ratakan per metrik
```

Hasil baseline awal 40/40:

| Metrik | Baseline awal |
|---|---:|
| context_precision | 0.8193 |
| context_recall | 0.9250 |
| faithfulness | 0.8352 |
| answer_relevancy | 0.6659 |

Hasil post-fix yang tersedia menunjukkan arah positif, tetapi belum full 40/40 valid karena rate limit:

| Metrik | New merged valid | Valid Count |
|---|---:|---:|
| context_precision | 0.8990 | 35/40 |
| context_recall | 1.0000 | 35/40 |
| faithfulness | 0.8341 | 34/40 |
| answer_relevancy | 0.6768 | 33/40 |

Kesimpulan aman:

> Prompt fix memperbaiki answer relevancy pada subset bermasalah dan pada full-set valid tidak menunjukkan penurunan metrik utama. Namun klaim final full 40/40 perlu menunggu RAGAS ulang setelah kuota Groq reset agar semua metrik valid tanpa null.

Tambahan retest focused GT-039 setelah unggah ulang dokumen menunjukkan bahwa kegagalan GT-039 lama sudah terselesaikan pada corpus baru: retrieval top-5 menemukan sumber agregat nasional yang benar, `context_recall=1.0000`, dan `faithfulness=1.0000`.

---

## 14. Rekomendasi Lanjutan

1. Jalankan ulang RAGAS full 40 setelah limit Groq reset.
2. Gunakan Qwen sebagai primary judge agar konsisten dengan baseline.
3. Jika tetap terkena limit, jalankan batch kecil, misalnya 5 pertanyaan per batch.
4. Agregasikan batch hanya setelah semua ID memiliki skor non-null.
5. Pertahankan quality gate ingestion untuk Laporan 2024 agar fakta agregat nasional seperti `Domain Manajemen SPBE` dan `1,86/1.86` selalu tersedia di chunk aktif.

---

## 15. Artefak Terkait

| Artefak | Fungsi |
|---|---|
| `backend/data/ground_truth_spbe_ragas_canonical.jsonl` | Dataset evaluasi 40 pertanyaan. |
| `backend/scripts/evaluate_rag.py` | Collect jawaban RAG dan top-5 contexts. |
| `backend/scripts/evaluate_ragas.py` | Konversi hasil RAG ke RAGAS dan hitung skor. |
| `backend/data/eval_ragas_aggregate_4metrics_groq_auto.json` | Baseline awal 40/40. |
| `backend/data/eval_results_full_prompt_fix.json` | Jawaban RAG full setelah prompt fix. |
| `backend/data/eval_report_full_prompt_fix.json` | Heuristic report full setelah prompt fix. |
| `backend/data/eval_ragas_full_prompt_fix_qwen3_32b.json` | RAGAS Qwen post-fix, partial. |
| `backend/data/eval_ragas_full_prompt_fix_llama4.json` | RAGAS fallback Llama post-fix, partial. |
| `backend/data/eval_results_gt039_after_new_upload.json` | Jawaban dan top-5 retrieval focused GT-039 setelah unggah ulang dokumen. |
| `backend/data/eval_report_gt039_after_new_upload.json` | Heuristic report focused GT-039 setelah unggah ulang dokumen. |
| `backend/data/eval_ragas_gt039_after_new_upload_qwen3_32b.json` | RAGAS Qwen focused GT-039. |
| `backend/data/eval_ragas_gt039_after_new_upload_qwen3_32b_faithfulness_retry.json` | Retry faithfulness RAGAS Qwen focused GT-039. |
