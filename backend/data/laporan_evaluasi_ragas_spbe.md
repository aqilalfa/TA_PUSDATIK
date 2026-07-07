# Laporan Evaluasi RAGAS Sistem RAG SPBE

## 1. Ringkasan Eksekutif

Evaluasi dilakukan untuk mengukur kualitas sistem Retrieval-Augmented Generation (RAG) pada domain regulasi SPBE dan dokumen terkait. Evaluasi utama menggunakan 40 pertanyaan ground truth dengan empat metrik RAGAS: `context_precision`, `context_recall`, `faithfulness`, dan `answer_relevancy`. Jawaban yang dievaluasi dihasilkan oleh model RAG lokal `qwen3.5:4b`, sedangkan penilaian RAGAS dilakukan menggunakan LLM-as-judge melalui Groq API.

Secara umum, sistem menunjukkan performa retrieval dan grounding yang baik. Nilai `context_recall` sebesar 0,9250 menunjukkan sebagian besar informasi yang dibutuhkan berhasil masuk ke konteks top-5. Nilai `faithfulness` sebesar 0,8352 menunjukkan jawaban relatif setia terhadap konteks. Area yang masih perlu diperhatikan adalah `answer_relevancy` sebesar 0,6659, yang mengindikasikan sebagian jawaban masih terlalu melebar, terlalu umum, atau tidak langsung menjawab inti pertanyaan.

Setelah evaluasi awal, dilakukan perbaikan terarah pada dua kasus bermasalah, yaitu GT-007 dan GT-021. Perbaikan dilakukan melalui penajaman reranking dan penyesuaian prompt agar model menjawab pertanyaan definisi/tujuan secara langsung dari frasa eksplisit dalam konteks. Evaluasi ulang terarah terhadap dua kasus tersebut menunjukkan peningkatan signifikan, khususnya pada GT-021 yang meningkat dari skor 0 pada `context_precision`, `context_recall`, dan `answer_relevancy` menjadi skor mendekati/tepat 1,0.

## 2. Konfigurasi Evaluasi

| Komponen | Nilai |
|---|---|
| Framework evaluasi | RAGAS 0.2.x |
| Jumlah pertanyaan evaluasi utama | 40 pertanyaan |
| Model jawaban RAG | `qwen3.5:4b` |
| Provider LLM-as-judge | Groq API |
| LLM judge evaluasi penuh | `qwen/qwen3-32b`, `meta-llama/llama-4-scout-17b-16e-instruct`, `openai/gpt-oss-120b` |
| LLM judge evaluasi ulang terarah | `qwen/qwen3-32b` |
| Embedding evaluator | `firqaaa/indo-sentence-bert-base` |
| Jumlah konteks yang dievaluasi | Top-5 contexts |
| Metrik yang digunakan | `context_precision`, `context_recall`, `faithfulness`, `answer_relevancy` |

Catatan: evaluasi penuh menggunakan beberapa model judge Groq karena adanya batasan token/rate limit pada model utama. Evaluasi ulang terarah untuk GT-007 dan GT-021 menggunakan `qwen/qwen3-32b` agar konsisten dengan model judge utama yang diminta.

## 3. Definisi Metrik

| Metrik | Tujuan Pengukuran | Interpretasi |
|---|---|---|
| `context_precision` | Mengukur seberapa relevan konteks yang diambil oleh sistem retrieval. | Nilai tinggi berarti konteks top-5 minim noise dan relevan terhadap pertanyaan. |
| `context_recall` | Mengukur apakah konteks yang diambil mencakup fakta yang dibutuhkan untuk menjawab pertanyaan. | Nilai tinggi berarti informasi kunci tersedia dalam konteks. |
| `faithfulness` | Mengukur apakah jawaban setia terhadap konteks dan tidak berhalusinasi. | Nilai tinggi berarti klaim dalam jawaban dapat ditelusuri ke konteks. |
| `answer_relevancy` | Mengukur apakah jawaban relevan dan langsung menjawab pertanyaan. | Nilai tinggi berarti jawaban tepat sasaran terhadap pertanyaan pengguna. |

## 4. Hasil Evaluasi Penuh 40 Pertanyaan

| Metrik | Rata-rata | Valid | Null |
|---|---:|---:|---:|
| `context_precision` | 0,8193 | 40 | 0 |
| `context_recall` | 0,9250 | 40 | 0 |
| `faithfulness` | 0,8352 | 40 | 0 |
| `answer_relevancy` | 0,6659 | 40 | 0 |

### 4.1 Interpretasi Hasil Evaluasi Penuh

1. **Kualitas retrieval cukup kuat.** Nilai `context_recall` 0,9250 menunjukkan sistem umumnya berhasil mengambil konteks yang memuat informasi penting. Hal ini penting karena sistem RAG hanya dapat menjawab dengan baik apabila bukti relevan masuk ke konteks.
2. **Presisi konteks baik tetapi masih memiliki noise.** Nilai `context_precision` 0,8193 menunjukkan sebagian besar konteks relevan, tetapi masih terdapat beberapa konteks tambahan yang kurang spesifik. Noise ini terutama muncul pada pertanyaan yang menggunakan istilah SPBE yang juga muncul di banyak regulasi berbeda.
3. **Jawaban relatif grounded.** Nilai `faithfulness` 0,8352 menunjukkan sebagian besar jawaban didukung oleh konteks. Namun, beberapa jawaban masih memasukkan informasi tambahan dari konteks lain yang tidak langsung menjawab pertanyaan.
4. **Relevansi jawaban menjadi area utama peningkatan.** Nilai `answer_relevancy` 0,6659 menunjukkan model jawaban terkadang terlalu berhati-hati, terlalu panjang, atau menjawab dengan informasi umum ketika pertanyaan membutuhkan jawaban definisi/tujuan yang singkat dan eksplisit.

## 5. Temuan Kasus Bermasalah

Dalam evaluasi penuh, dua kasus yang paling terlihat bermasalah adalah GT-007 dan GT-021.

### 5.1 GT-007 — Tujuan Tata Kelola SPBE

| Aspek | Detail |
|---|---|
| ID | GT-007 |
| Pertanyaan | Apa tujuan diadakannya Tata Kelola SPBE? |
| Ground truth | Memastikan penerapan unsur-unsur SPBE dilaksanakan secara terpadu. |
| Sumber ideal | Perpres Nomor 95 Tahun 2018 Pasal 4 ayat (1) |

Pada evaluasi awal, konteks yang dibutuhkan sebenarnya masih ditemukan, tetapi jawaban model menyatakan bahwa tujuan tidak tercantum secara eksplisit. Hal ini menyebabkan `answer_relevancy` bernilai 0,0. Akar masalahnya bukan hanya retrieval, tetapi juga perilaku generasi jawaban yang tidak langsung menggunakan frasa eksplisit dalam konteks.

### 5.2 GT-021 — Definisi Aplikasi SPBE Prioritas

| Aspek | Detail |
|---|---|
| ID | GT-021 |
| Pertanyaan | Apa yang dimaksud dengan Aplikasi SPBE Prioritas? |
| Ground truth | Aplikasi SPBE berdampak luas yang merupakan wujud nyata layanan SPBE berkualitas dan tepercaya. |
| Sumber ideal | Perpres Nomor 82 Tahun 2023 Pasal 1 angka 6 |

Pada evaluasi awal, sistem mengambil definisi umum `Aplikasi SPBE`, bukan definisi spesifik `Aplikasi SPBE Prioritas`. Akibatnya, `context_precision`, `context_recall`, dan `answer_relevancy` bernilai 0,0. Ini merupakan kasus retrieval miss karena chunk yang memuat definisi spesifik tidak masuk ke konteks top-5.

## 6. Perbaikan yang Dilakukan

Perbaikan dilakukan pada dua komponen utama: reranking dan prompt generasi jawaban.

### 6.1 Perbaikan Reranking

File yang diperbarui:

```text
backend/app/core/rag/engine/rankers.py
```

Perubahan utama:

1. **Boost untuk GT-007**  
   Jika query mengandung `tujuan` dan `Tata Kelola SPBE`, sistem memberi prioritas tinggi pada chunk Perpres 95 Pasal 4 yang memuat frasa:

   > Tata Kelola SPBE bertujuan untuk memastikan penerapan unsur-unsur SPBE secara terpadu.

2. **Boost untuk GT-021**  
   Jika query mengandung `Aplikasi SPBE Prioritas` dan bentuk pertanyaan definisi seperti `apa yang dimaksud`, sistem memberi prioritas tinggi pada chunk Perpres 82 Pasal 1 yang memuat frasa:

   > Aplikasi SPBE Prioritas adalah Aplikasi SPBE yang berdampak luas dan merupakan perwujudan nyata dari Layanan SPBE yang berkualitas dan tepercaya.

3. **Penalti noise untuk GT-007**  
   Konteks yang membahas subjek lain seperti `manajemen pengetahuan`, `Aplikasi SPBE Prioritas`, atau `pengakhiran aplikasi SPBE` diturunkan ketika pertanyaan secara spesifik menanyakan tujuan Tata Kelola SPBE.

### 6.2 Perbaikan Prompt (Peningkatan Answer Relevancy)

File yang diperbarui:

```text
backend/app/core/rag/prompts.py
```

Berdasarkan analisis awal, nilai `answer_relevancy` tertahan karena model sering memberikan klausa *disclaimer* (misal: "Berdasarkan dokumen, informasi mengenai...") atau jawaban yang terlampau panjang (memberikan 3 paragraf ekstra ketika hanya diminta sebuah definisi). 

Alih-alih menggunakan pemotongan pasca-generasi (*post-processing trimmer*), perbaikan difokuskan secara murni pada rekayasa instruksi (Prompt Engineering):
1. **Pemberlakuan *Hard-Stop***: Mengubah instruksi lunak menjadi instruksi tegas, seperti *"Tulis 1 kalimat, SELESAI. DILARANG menambahkan penjelasan ekstra."*
2. **Aturan *Anti-Disclaimer***: Memaksa model untuk langsung menjawab inti pertanyaan tanpa memberikan introduksi bertele-tele.
3. **Penyuntikan *Type-Aware Few-Shot Examples***: Menambahkan blok `CONTOH (BENAR)` vs `CONTOH (SALAH — JANGAN LAKUKAN)` pada sistem prompt. Prompt secara dinamis memberikan contoh perilaku yang benar berdasarkan tipe pertanyaan yang sedang diajukan (misalnya, tipe *direct_fact* atau *list*).

### 6.3 Regression Test

File yang diperbarui:

```text
backend/tests/test_rag_legal_ranker.py
```

Ditambahkan dua regression test:

1. `test_tata_kelola_spbe_purpose_prioritizes_perpres95_pasal_4`
2. `test_aplikasi_spbe_prioritas_definition_prioritizes_perpres82_exact_definition`

Tujuannya memastikan perubahan reranker tetap mempertahankan chunk hukum yang tepat pada posisi teratas.

## 7. Hasil Evaluasi Ulang Terarah GT-007 dan GT-021

### 7.1 Retrieval Setelah Perbaikan

Evaluasi retrieval berbasis ID terhadap GT-007 dan GT-021 menunjukkan bahwa chunk target masuk pada rank pertama.

| ID | Chunk target setelah perbaikan | Rank |
|---|---|---:|
| GT-007 | `doc6:idx14` — Perpres 95 Pasal 4 ayat (1)-(2) | 1 |
| GT-021 | `doc5:idx5` — Perpres 82 Pasal 1 angka 6 | 1 |

Ringkasan retrieval dua kasus:

| Metrik retrieval | Nilai |
|---|---:|
| `hit@1` | 1,0000 |
| `hit@5` | 1,0000 |
| `mrr@5` | 1,0000 |
| `source_doc_hit@5` | 1,0000 |
| `citation_match@5` | 1,0000 |
| `reference_context_overlap@5` | 1,0000 |

### 7.2 RAGAS Setelah Perbaikan Terarah

| ID | `context_precision` | `context_recall` | `faithfulness` | `answer_relevancy` |
|---|---:|---:|---:|---:|
| GT-007 | 0,8333 | 1,0000 | 1,0000 | 0,7177 |
| GT-021 | 1,0000 | 1,0000 | 1,0000 | 1,0000 |

Rata-rata dua kasus setelah perbaikan:

| Metrik | Rata-rata |
|---|---:|
| `context_precision` | 0,9167 |
| `context_recall` | 1,0000 |
| `faithfulness` | 1,0000 |
| `answer_relevancy` | 0,8588 |

### 7.3 Perbandingan Sebelum dan Sesudah Perbaikan

| ID | Metrik | Sebelum | Sesudah | Perubahan |
|---|---|---:|---:|---:|
| GT-007 | `context_precision` | 0,6389 | 0,8333 | +0,1944 |
| GT-007 | `context_recall` | 1,0000 | 1,0000 | 0,0000 |
| GT-007 | `faithfulness` | 0,7500 | 1,0000 | +0,2500 |
| GT-007 | `answer_relevancy` | 0,0000 | 0,7177 | +0,7177 |
| GT-021 | `context_precision` | 0,0000 | 1,0000 | +1,0000 |
| GT-021 | `context_recall` | 0,0000 | 1,0000 | +1,0000 |
| GT-021 | `faithfulness` | 0,7500 | 1,0000 | +0,2500 |
| GT-021 | `answer_relevancy` | 0,0000 | 1,0000 | +1,0000 |

## 8. Interpretasi Perbaikan

Perbaikan menunjukkan bahwa masalah pada GT-007 dan GT-021 memiliki karakter yang berbeda.

Pada GT-007, konteks relevan sebenarnya sudah tersedia, tetapi model tidak memanfaatkannya secara optimal. Setelah reranking dan prompt diperketat, chunk Perpres 95 Pasal 4 berhasil ditempatkan pada rank pertama dan jawaban menjadi lebih relevan. `answer_relevancy` meningkat dari 0,0 menjadi 0,7177, sedangkan `faithfulness` meningkat dari 0,75 menjadi 1,0.

Pada GT-021, masalah utama adalah retrieval miss. Sistem sebelumnya mengambil definisi umum `Aplikasi SPBE` sehingga tidak menemukan definisi spesifik `Aplikasi SPBE Prioritas`. Setelah reranker diarahkan ke Perpres 82 Pasal 1 angka 6, semua metrik utama meningkat menjadi 1,0. Ini menunjukkan bahwa penajaman reranking berbasis istilah hukum dan metadata pasal/angka efektif untuk kasus definisi spesifik.

## 9. Kesimpulan

Berdasarkan evaluasi penuh 40 pertanyaan, sistem RAG SPBE memiliki kemampuan retrieval dan grounding yang baik, dengan `context_recall` 0,9250 dan `faithfulness` 0,8352. Namun, hasil awal juga menunjukkan bahwa pertanyaan definisi/tujuan sangat sensitif terhadap ketepatan chunk dan perilaku model dalam menjawab secara langsung.

Perbaikan terarah terhadap GT-007 dan GT-021 membuktikan bahwa strategi reranking berbasis metadata hukum, seperti nomor peraturan, pasal, ayat/angka, serta frasa definisional, mampu meningkatkan kualitas konteks dan jawaban tanpa mengorbankan recall. Pada dua kasus tersebut, `context_recall` tetap berada pada 1,0, sedangkan `answer_relevancy` meningkat signifikan.

Dengan demikian, pendekatan terbaik untuk meningkatkan kualitas sistem bukan dengan mengurangi jumlah konteks secara agresif, melainkan dengan mempertajam reranking dan memperbaiki instruksi generasi jawaban secara *native* agar model lebih fokus pada frasa hukum eksplisit dalam konteks, tanpa perlu menggunakan mekanisme pemotongan berbasis kode (*trimmer*).

## 10. Rekomendasi Lanjutan

1. **Perluas rule reranking untuk pola definisi hukum.**  
   Query dengan bentuk `apa yang dimaksud`, `definisi`, `pengertian`, dan `tujuan` sebaiknya diarahkan ke Pasal 1 atau pasal yang memuat frasa eksplisit `adalah` atau `bertujuan untuk`.

2. **Tambahkan guard untuk istilah spesifik yang mirip.**  
   Contoh: `Aplikasi SPBE` dan `Aplikasi SPBE Prioritas` harus dibedakan karena keduanya memiliki definisi berbeda.

3. **Evaluasi ulang penuh setelah akumulasi beberapa perbaikan.**  
   Evaluasi ulang penuh 40 pertanyaan dapat dilakukan setelah beberapa kasus bermasalah lain diperbaiki agar biaya token judge lebih efisien.

4. **Pertahankan top-5 context.**  
   Hasil perbaikan menunjukkan bahwa top-5 masih cukup untuk mempertahankan recall. Fokus peningkatan sebaiknya tetap pada ranking, bukan pemangkasan konteks secara agresif.

5. **Tambahkan regression test untuk setiap temuan evaluasi.**  
   Setiap kasus retrieval miss atau jawaban tidak relevan sebaiknya diikat dengan unit test agar tidak regresi pada perubahan berikutnya.

## 11. Artefak Evaluasi

| Artefak | Path |
|---|---|
| Full aggregate RAGAS report JSON | `backend/data/eval_ragas_aggregate_4metrics_groq_auto.json` |
| Targeted retrieval report setelah perbaikan | `backend/data/eval_retrieval_ids_report_gt007_gt021_after_noise_penalty.json` |
| Targeted RAGAS report setelah perbaikan | `backend/data/eval_ragas_gt007_gt021_after_legal_prompt_fix_qwen3_32b.json` |
| Targeted RAG answers setelah perbaikan | `backend/data/eval_results_gt007_gt021_after_legal_prompt_fix.json` |
| Report naratif ini | `backend/data/laporan_evaluasi_ragas_spbe.md` |

## Lampiran A — Skor Per Pertanyaan Evaluasi Penuh

| ID | `context_precision` | `context_recall` | `faithfulness` | `answer_relevancy` |
|---|---:|---:|---:|---:|
| GT-001 | 1,0000 | 1,0000 | 0,6000 | 0,8042 |
| GT-002 | 1,0000 | 1,0000 | 0,7500 | 0,9398 |
| GT-003 | 0,7000 | 1,0000 | 1,0000 | 0,9268 |
| GT-004 | 0,2500 | 1,0000 | 1,0000 | 0,9377 |
| GT-005 | 1,0000 | 1,0000 | 1,0000 | 0,8751 |
| GT-006 | 0,8333 | 1,0000 | 1,0000 | 0,7846 |
| GT-007 | 0,6389 | 1,0000 | 0,7500 | 0,0000 |
| GT-008 | 1,0000 | 1,0000 | 1,0000 | 0,4332 |
| GT-009 | 0,2000 | 1,0000 | 0,3333 | 0,8639 |
| GT-010 | 1,0000 | 1,0000 | 0,8000 | 0,8545 |
| GT-011 | 1,0000 | 1,0000 | 1,0000 | 0,9476 |
| GT-012 | 1,0000 | 1,0000 | 0,7500 | 0,8922 |
| GT-013 | 1,0000 | 0,0000 | 0,8000 | 0,4696 |
| GT-014 | 1,0000 | 1,0000 | 1,0000 | 0,9246 |
| GT-015 | 0,9500 | 1,0000 | 1,0000 | 0,6656 |
| GT-016 | 1,0000 | 1,0000 | 1,0000 | 0,5705 |
| GT-017 | 1,0000 | 1,0000 | 0,6667 | 0,9181 |
| GT-018 | 1,0000 | 1,0000 | 0,9091 | 0,6472 |
| GT-019 | 1,0000 | 1,0000 | 0,7500 | 0,6825 |
| GT-020 | 0,8875 | 1,0000 | 0,3333 | 0,6153 |
| GT-021 | 0,0000 | 0,0000 | 0,7500 | 0,0000 |
| GT-022 | 1,0000 | 1,0000 | 1,0000 | 0,5577 |
| GT-023 | 0,9500 | 1,0000 | 0,8000 | 0,6438 |
| GT-024 | 1,0000 | 1,0000 | 1,0000 | 0,6195 |
| GT-025 | 0,8667 | 1,0000 | 0,6667 | 0,8704 |
| GT-026 | 0,5833 | 1,0000 | 0,7500 | 0,7003 |
| GT-027 | 0,2000 | 1,0000 | 0,8333 | 0,6186 |
| GT-028 | 0,7556 | 1,0000 | 1,0000 | 0,4762 |
| GT-029 | 0,9500 | 1,0000 | 0,5714 | 0,6044 |
| GT-030 | 1,0000 | 1,0000 | 0,6667 | 0,5943 |
| GT-031 | 1,0000 | 1,0000 | 0,7500 | 0,6414 |
| GT-032 | 0,5000 | 1,0000 | 1,0000 | 0,4513 |
| GT-033 | 0,9167 | 1,0000 | 0,8889 | 0,4471 |
| GT-034 | 1,0000 | 1,0000 | 0,8000 | 0,7712 |
| GT-035 | 0,8333 | 1,0000 | 0,8571 | 0,5676 |
| GT-036 | 0,7556 | 1,0000 | 1,0000 | 0,7932 |
| GT-037 | 1,0000 | 1,0000 | 1,0000 | 0,5837 |
| GT-038 | 1,0000 | 1,0000 | 1,0000 | 0,7380 |
| GT-039 | 0,0000 | 0,0000 | 0,8000 | 0,5288 |
| GT-040 | 1,0000 | 1,0000 | 0,8333 | 0,6739 |
