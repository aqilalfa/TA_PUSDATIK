# Laporan Lengkap Evaluasi RAGAS dan Iterasi Perbaikan RAG SPBE

Tanggal penyusunan: 2026-06-05  
Sistem: SPBE RAG System  
Model jawaban RAG: `qwen3.5:4b`  
Evaluator utama: RAGAS 0.2.x dengan Groq LLM-as-judge  
Metrik: `context_precision`, `context_recall`, `faithfulness`, `answer_relevancy`

---

## 1. Ringkasan Eksekutif

Evaluasi dilakukan dalam dua lapisan:

1. **Evaluasi penuh 40 pertanyaan** untuk mengukur performa umum sistem RAG.
2. **Iterasi targeted low8** untuk memperbaiki kasus-kasus dengan skor rendah tanpa menurunkan recall.

Hasil utama evaluasi penuh menunjukkan bahwa sistem sudah kuat pada kemampuan menemukan konteks (`context_recall=0.9250`) dan cukup baik dalam menjaga jawaban tetap berbasis konteks (`faithfulness=0.8352`). Titik lemah utama berada pada `answer_relevancy=0.6659`, yaitu jawaban sering benar tetapi terlalu panjang, menambahkan informasi tambahan, atau kurang langsung menjawab inti pertanyaan.

Pada iterasi low8, perbaikan reranker berhasil menaikkan kualitas retrieval:

- `hit@1` naik dari **0.625** menjadi **0.750**.
- `hit@5` tetap **1.000**.
- `recall@5` tetap **0.8333**, sehingga constraint recall tidak turun terpenuhi.
- `citation_match@5` naik dari **0.875** menjadi **1.000**.

Update setelah unggah ulang dokumen Laporan 2024: kasus **GT-039** sudah diuji ulang secara terpisah dan kini **resolved**. Retrieval top-5 seluruhnya mengambil konteks dari dokumen `Laporan Pelaksanaan Evaluasi SPBE 2024.pdf`, jawaban menyebut **Domain Manajemen SPBE dengan skor 1,86**, dan RAGAS Qwen menunjukkan `context_precision=0.9500`, `context_recall=1.0000`, `faithfulness=1.0000`, serta `answer_relevancy=0.6690`.

---

## 2. Penjelasan Metrik

| Metrik | Makna | Interpretasi Tinggi |
|---|---|---|
| `context_precision` | Mengukur apakah konteks yang diambil relevan terhadap pertanyaan. | Semakin tinggi berarti konteks minim noise. |
| `context_recall` | Mengukur apakah konteks mencakup fakta yang dibutuhkan untuk menjawab. | Semakin tinggi berarti fakta penting tidak hilang. |
| `faithfulness` | Mengukur apakah jawaban setia pada konteks dan tidak berhalusinasi. | Semakin tinggi berarti jawaban grounded. |
| `answer_relevancy` | Mengukur apakah jawaban langsung relevan dengan pertanyaan. | Semakin tinggi berarti jawaban tepat sasaran. |

Skala semua metrik adalah 0 sampai 1.

---

## 3. Hasil Skor Keseluruhan Evaluasi Penuh 40 Pertanyaan

Sumber data: `backend/data/eval_ragas_aggregate_4metrics_groq_auto.json`

| Metrik | Rata-rata | Valid | Null | Interpretasi |
|---|---:|---:|---:|---|
| context_precision | 0.8193 | 40 | 0 | Baik; sebagian besar konteks relevan, tetapi masih ada noise pada beberapa pertanyaan. |
| context_recall | 0.9250 | 40 | 0 | Sangat baik; fakta yang dibutuhkan umumnya masuk ke konteks top-k. |
| faithfulness | 0.8352 | 40 | 0 | Baik; jawaban cukup grounded, walau beberapa jawaban masih menambahkan detail. |
| answer_relevancy | 0.6659 | 40 | 0 | Cukup; jawaban sering benar tetapi belum selalu ringkas/tepat sasaran. |

### Interpretasi Keseluruhan

Sistem RAG sudah memiliki **retrieval recall yang kuat**. Ini penting karena jawaban tidak bisa benar jika konteks sumber tidak ditemukan. Masalah utama setelah retrieval adalah **kualitas formulasi jawaban**, terutama jawaban yang terlalu panjang atau menambahkan konteks lain yang tidak ditanyakan. Oleh karena itu, strategi iterasi berikutnya sebaiknya tetap menjaga top-5 recall, tetapi memperbaiki ranking, mengurangi noise, dan memperketat prompt jawaban ringkas untuk pertanyaan definisi, tujuan, dan siapa/berapa.

---

## 4. Hasil Per Pertanyaan Evaluasi Penuh 40 Pertanyaan

Keterangan singkat:

- **Baik**: mayoritas metrik kuat.
- **Cukup**: jawaban/konteks benar tetapi masih ada noise atau relevansi kurang.
- **Perlu perhatian**: salah satu metrik inti sangat rendah.

| ID | Pertanyaan | CP | CR | Faith | AR | Interpretasi |
|---|---|---:|---:|---:|---:|---|
| GT-001 | Apa yang dimaksud dengan Layanan SPBE? | 1.0000 | 1.0000 | 0.6000 | 0.8042 | Konteks dan relevansi baik, tetapi faithfulness sedang; jawaban kemungkinan menambah detail di luar klaim inti. |
| GT-002 | Apa definisi Rencana Induk SPBE Nasional? | 1.0000 | 1.0000 | 0.7500 | 0.9398 | Baik; konteks lengkap dan jawaban sangat relevan, hanya grounding perlu sedikit diperketat. |
| GT-003 | Apa pengertian Arsitektur SPBE? | 0.7000 | 1.0000 | 1.0000 | 0.9268 | Baik; fakta ditemukan lengkap dan jawaban grounded, meski ada sedikit noise konteks. |
| GT-004 | Apa yang dimaksud dengan Keamanan SPBE menurut Perpres 95 Tahun 2018? | 0.2500 | 1.0000 | 1.0000 | 0.9377 | Jawaban baik, tetapi precision rendah; konteks benar ada namun banyak konteks tambahan tidak relevan. |
| GT-005 | Siapa saja yang termasuk sebagai Pengguna SPBE? | 1.0000 | 1.0000 | 1.0000 | 0.8751 | Sangat baik; retrieval dan jawaban kuat. |
| GT-006 | Apa saja prinsip-prinsip dalam pelaksanaan SPBE? | 0.8333 | 1.0000 | 1.0000 | 0.7846 | Baik; semua fakta ditemukan dan grounded, relevansi cukup tinggi. |
| GT-007 | Apa tujuan diadakannya Tata Kelola SPBE? | 0.6389 | 1.0000 | 0.7500 | 0.0000 | Perlu perhatian pada baseline; jawaban tidak dianggap relevan oleh judge walau konteks ada. Sudah menjadi target iterasi. |
| GT-008 | Apa saja yang mencakup unsur-unsur SPBE? | 1.0000 | 1.0000 | 1.0000 | 0.4332 | Retrieval dan grounding sangat baik, tetapi jawaban dinilai kurang relevan/kurang langsung. |
| GT-009 | Untuk berapa lama Arsitektur SPBE Nasional disusun? | 0.2000 | 1.0000 | 0.3333 | 0.8639 | Perlu perhatian pada baseline; konteks benar ada tetapi precision dan faithfulness rendah. Sudah diperbaiki pada iterasi. |
| GT-010 | Apa definisi Audit Teknologi Informasi dan Komunikasi (TIK)? | 1.0000 | 1.0000 | 0.8000 | 0.8545 | Baik; semua metrik kuat. |
| GT-011 | Apa yang dimaksud dengan Pemantauan SPBE? | 1.0000 | 1.0000 | 1.0000 | 0.9476 | Sangat baik. |
| GT-012 | Apa definisi Evaluasi SPBE? | 1.0000 | 1.0000 | 0.7500 | 0.8922 | Baik; sedikit perlu penguatan grounding. |
| GT-013 | Siapa yang berhak melakukan Penilaian Dokumen? | 1.0000 | 0.0000 | 0.8000 | 0.4696 | Judge memberi recall rendah, tetapi evaluasi manual menunjukkan konteks Tim Asesor Eksternal ada. Kemungkinan judge variance. |
| GT-014 | Apa yang dimaksud dengan Penilaian Visitasi? | 1.0000 | 1.0000 | 1.0000 | 0.9246 | Sangat baik. |
| GT-015 | Apa tujuan utama dilakukannya Pemantauan dan Evaluasi SPBE? | 0.9500 | 1.0000 | 1.0000 | 0.6656 | Baik; jawaban benar tetapi relevansi masih bisa dibuat lebih ringkas. |
| GT-016 | Sebutkan 5 tingkatan kematangan kapabilitas proses SPBE! | 1.0000 | 1.0000 | 1.0000 | 0.5705 | Retrieval kuat; jawaban kemungkinan terlalu panjang atau format kurang sesuai ekspektasi judge. |
| GT-017 | Apa yang mendefinisikan SPBE Tingkat 1 (Rintisan)? | 1.0000 | 1.0000 | 0.6667 | 0.9181 | Baik; relevansi tinggi, faithfulness sedang. |
| GT-018 | Berapa persentase bobot penilaian untuk Domain Layanan SPBE? | 1.0000 | 1.0000 | 0.9091 | 0.6472 | Baik; jawaban factual, relevansi cukup. |
| GT-019 | Predikat apa yang disematkan pada rentang nilai indeks SPBE 3,5 hingga kurang dari 4,2? | 1.0000 | 1.0000 | 0.7500 | 0.6825 | Baik; tabel ditemukan, tetapi jawaban bisa dibuat lebih langsung. |
| GT-020 | Apa predikat SPBE untuk nilai indeks di bawah 1,8? | 0.8875 | 1.0000 | 0.3333 | 0.6153 | Konteks benar, jawaban inti benar, tetapi faithfulness rendah karena wording/elaborasi. |
| GT-021 | Apa yang dimaksud dengan Aplikasi SPBE Prioritas? | 0.0000 | 0.0000 | 0.7500 | 0.0000 | Baseline gagal pada konteks/relevansi. Sudah diperbaiki pada iterasi sebelumnya dan low8. |
| GT-022 | Berapa minimal target pengguna agar sebuah aplikasi beroperasi disebut Aplikasi SPBE Prioritas? | 1.0000 | 1.0000 | 1.0000 | 0.5577 | Retrieval dan grounding sangat baik, relevansi sedang. |
| GT-023 | Siapa lembaga yang secara khusus ditugaskan pemerintah untuk menyelenggarakan Aplikasi SPBE Prioritas? | 0.9500 | 1.0000 | 0.8000 | 0.6438 | Baik; jawaban bisa dipadatkan. |
| GT-024 | Kapan batas akhir pertama kali Aplikasi SPBE Prioritas harus diluncurkan secara terpadu? | 1.0000 | 1.0000 | 1.0000 | 0.6195 | Retrieval dan grounding kuat, relevansi cukup. |
| GT-025 | Apa yang dimaksud dengan Audit Keamanan SPBE? | 0.8667 | 1.0000 | 0.6667 | 0.8704 | Baik; relevansi tinggi, faithfulness sedang. |
| GT-026 | Apa sajakah yang dapat menjadi objek dari Audit Keamanan SPBE? | 0.5833 | 1.0000 | 0.7500 | 0.7003 | Cukup; fakta ditemukan tetapi konteks masih cukup noisy. |
| GT-027 | Siapa entitas yang bertugas sebagai Pelaksana Audit Keamanan SPBE? | 0.2000 | 1.0000 | 0.8333 | 0.6186 | Perlu perhatian pada baseline; konteks benar ada tapi precision rendah. Sudah diperbaiki pada iterasi. |
| GT-028 | Aspek apa saja yang harus dipenuhi oleh bukti Audit Keamanan SPBE? | 0.7556 | 1.0000 | 1.0000 | 0.4762 | Grounded dan recall baik, tetapi jawaban kurang sesuai ekspektasi relevansi. |
| GT-029 | Apa tiga konklusi akhir dari Audit Keamanan SPBE? | 0.9500 | 1.0000 | 0.5714 | 0.6044 | Konteks baik, tetapi faithfulness dan relevansi perlu diperbaiki. |
| GT-030 | Siapa saja pihak yang termasuk dalam Penyelenggara Sistem Elektronik Lingkup Publik? | 1.0000 | 1.0000 | 0.6667 | 0.5943 | Retrieval kuat, tetapi jawaban perlu lebih langsung/grounded. |
| GT-031 | Apa yang dimaksud sistem elektronik yang "andal" secara hukum? | 1.0000 | 1.0000 | 0.7500 | 0.6414 | Baik; perlu sedikit penguatan jawaban ringkas. |
| GT-032 | Apa sanksi administratif jika Penyelenggara Sistem Elektronik melakukan pelanggaran? | 0.5000 | 1.0000 | 1.0000 | 0.4513 | Konteks benar dan grounded, tetapi precision/relevansi rendah karena jawaban terlalu elaboratif. |
| GT-033 | Apa bentuk teknis dari pelaksanaan sanksi pemutusan Akses? | 0.9167 | 1.0000 | 0.8889 | 0.4471 | Konteks dan grounding baik, relevansi rendah; perlu jawaban lebih singkat. |
| GT-034 | Apa pengertian dari Manajemen SPBE di lingkungan BSSN? | 1.0000 | 1.0000 | 0.8000 | 0.7712 | Baik. |
| GT-035 | Apa saja yang menjadi ruang lingkup penyelenggaraan SPBE di BSSN? | 0.8333 | 1.0000 | 0.8571 | 0.5676 | Baik pada retrieval, relevansi sedang. |
| GT-036 | Apa yang menjadi kewajiban Tim Koordinasi SPBE BSSN? | 0.7556 | 1.0000 | 1.0000 | 0.7932 | Baik. |
| GT-037 | Siapa yang bertanggung jawab langsung atas pelaksanaan Audit Keamanan Internal di BSSN? | 1.0000 | 1.0000 | 1.0000 | 0.5837 | Retrieval dan grounding sangat baik, relevansi sedang. |
| GT-038 | Kapan LATIK Terakreditasi wajib menyampaikan laporan periodik audit keamanan mereka? | 1.0000 | 1.0000 | 1.0000 | 0.7380 | Baik. |
| GT-039 | Apa domain yang mencetak skor evaluasi terendah secara nasional pada Laporan 2024? | 0.0000 | 0.0000 | 0.8000 | 0.5288 | Baseline awal gagal karena sumber agregat nasional 2024 belum masuk ke chunk aktif. Setelah unggah ulang dokumen dan retest focused, kasus ini resolved; lihat Bagian 6.1. |
| GT-040 | Instansi pemerintah daerah mana yang meraih nilai SPBE tertinggi di tahun 2024? | 1.0000 | 1.0000 | 0.8333 | 0.6739 | Baik; jawaban cukup relevan dan grounded. |

---

## 5. Hasil Iterasi Targeted Low8 Setelah Perbaikan

Subset low8 berisi pertanyaan yang sebelumnya memiliki skor rendah atau menunjukkan pola kegagalan. ID yang dievaluasi ulang:

`GT-007`, `GT-009`, `GT-013`, `GT-020`, `GT-021`, `GT-027`, `GT-032`, `GT-039`.

### 5.1 Hasil Retrieval Low8 Setelah Fix

Sumber data: `backend/data/eval_retrieval_ids_report_iterasi_low8_after_fixes_v2.json`

| Metrik Retrieval | Nilai Setelah Fix | Makna |
|---|---:|---|
| hit@1 | 0.7500 | 75% pertanyaan memiliki konteks target di rank pertama. |
| hit@5 | 1.0000 | Semua pertanyaan memiliki konteks target di top-5. |
| recall@5 | 0.8333 | Cakupan konteks top-5 tetap aman dan tidak turun dari baseline low8. |
| precision@5 | 0.5000 | Separuh konteks top-5 rata-rata relevan menurut ID matching. |
| citation_match@5 | 1.0000 | Semua pertanyaan memiliki sitasi yang cocok di top-5. |
| source_doc_hit@5 | 1.0000 | Semua pertanyaan mengambil dokumen sumber yang benar di top-5. |

Interpretasi: perbaikan berhasil menaikkan posisi konteks yang benar, khususnya GT-009 dan GT-027, tanpa mengorbankan recall@5.

### 5.2 Hasil RAGAS Low8 Setelah Fix

#### Primary judge: Qwen/Qwen3-32B

Sumber data: `backend/data/eval_ragas_iterasi_low8_after_fixes_v2_qwen3_32b.json`

| Metrik | Nilai Parsial |
|---|---:|
| context_precision | 0.8792 |
| context_recall | 1.0000 |
| faithfulness | 0.8750 |
| answer_relevancy | 0.7210 |

Catatan: hasil Qwen bersifat parsial karena Groq terkena token-per-day/rate limit. Beberapa pertanyaan memiliki nilai `null`, sehingga nilai ini tidak boleh dianggap sebagai pengganti penuh evaluasi lengkap.

#### Fallback judge: Llama 4 Scout

Sumber data: `backend/data/eval_ragas_iterasi_low8_after_fixes_v2_llama4.json`

| Metrik | Rata-rata |
|---|---:|
| context_precision | 0.8450 |
| context_recall | 0.7500 |
| faithfulness | 0.7946 |
| answer_relevancy | 0.6289 |

Catatan: fallback Llama lengkap, tetapi menunjukkan beberapa indikasi judge variance. Contohnya GT-013 diberi `context_recall=0.0`, padahal konteks eksplisit tentang Tim Asesor Eksternal ada di hasil retrieval. Karena itu, fallback digunakan sebagai pembanding saat Qwen limit, bukan sebagai satu-satunya dasar keputusan.

---

## 6. Penjelasan Hasil Tiap Pertanyaan Low8 Setelah Fix

| ID | Pertanyaan | Ground Truth | Jawaban Sistem Ringkas | CP | CR | Faith | AR | Penjelasan |
|---|---|---|---|---:|---:|---:|---:|---|
| GT-007 | Apa tujuan diadakannya Tata Kelola SPBE? | Memastikan penerapan unsur-unsur SPBE dilaksanakan secara terpadu. | Menjawab benar di kalimat pertama, tetapi menambah konteks BSSN. | 0.7556 | 1.0000 | 0.5000 | 0.9693 | Konteks utama Pasal 4 sudah rank atas dan recall aman. Masalah tersisa adalah jawaban masih menambahkan kalimat tambahan dari konteks BSSN, sehingga faithfulness turun. |
| GT-009 | Untuk berapa lama Arsitektur SPBE Nasional disusun? | Disusun untuk jangka waktu 5 tahun. | Menjawab 5 tahun. | 0.7500 | 1.0000 | 1.0000 | 0.6937 | Perbaikan berhasil: Pasal 8 Perpres 95 naik menjadi konteks utama. Faithfulness sempurna. Relevansi belum maksimal karena jawaban masih menambahkan info review arsitektur. |
| GT-013 | Siapa yang berhak melakukan Penilaian Dokumen? | Tim Asesor Eksternal. | Menjawab Tim Asesor Eksternal. | 1.0000 | 0.0000 | 0.8000 | 0.5333 | Secara isi jawaban benar. Nilai recall 0 dari fallback kemungkinan anomali judge karena konteks definisi dan metode pelaksanaan memuat Tim Asesor Eksternal. Perlu diperlakukan sebagai judge variance. |
| GT-020 | Apa predikat SPBE untuk nilai indeks di bawah 1,8? | Predikat Kurang. | Menjawab Kurang. | 0.8875 | 1.0000 | 0.6000 | 0.8613 | Hasil baik. Tabel 13 ditemukan dan jawaban tepat. Faithfulness sedang karena jawaban masih menyebut uraian dokumen tambahan. |
| GT-021 | Apa yang dimaksud dengan Aplikasi SPBE Prioritas? | Aplikasi SPBE berdampak luas yang merupakan wujud nyata layanan SPBE berkualitas dan tepercaya. | Menjawab definisi inti dengan benar. | 1.0000 | 1.0000 | 0.8571 | 0.9094 | Hasil sangat baik setelah perbaikan sebelumnya. Konteks definisi tepat dan jawaban relevan. |
| GT-027 | Siapa entitas yang bertugas sebagai Pelaksana Audit Keamanan SPBE? | LATIK cakupan Keamanan SPBE, meliputi LATIK pemerintah atau LATIK Terakreditasi yang terdaftar. | Menjawab LATIK cakupan Keamanan SPBE. | 0.8667 | 1.0000 | 1.0000 | 0.6127 | Perbaikan berhasil menaikkan Pasal 4/LATIK ke posisi kuat. Relevansi masih sedang karena jawaban menambahkan informasi tambahan setelah jawaban inti. |
| GT-032 | Apa sanksi administratif jika Penyelenggara Sistem Elektronik melakukan pelanggaran? | Teguran tertulis, denda administratif, penghentian sementara, pemutusan Akses, dan/atau dikeluarkan dari daftar. | Menjawab daftar sanksi administratif. | 0.5000 | 1.0000 | 1.0000 | 0.4513 | Fakta ditemukan dan jawaban grounded, tetapi konteks banyak noise dan jawaban terlalu panjang, sehingga relevansi rendah. |
| GT-039 | Apa domain yang mencetak skor evaluasi terendah secara nasional pada Laporan 2024? | Domain Manajemen SPBE dengan skor 1,86. | Pada iterasi low8 lama sistem belum bisa mengidentifikasi pasti dari konteks. Setelah unggah ulang dokumen dan retest focused, sistem menjawab Domain Manajemen dengan nilai indeks 1,86. | 1.0000 | 0.0000 | 0.6000 | 0.0000 | Nilai pada tabel ini adalah hasil low8 lama. Status terbaru: resolved pada retest focused GT-039; lihat Bagian 6.1. |

### 6.1 Retest Focused GT-039 Setelah Unggah Ulang Dokumen

Setelah dokumen `Laporan Pelaksanaan Evaluasi SPBE 2024.pdf` diunggah ulang dan terindeks, GT-039 diuji ulang secara khusus dengan top-5 retrieval yang sama. Artefak hasil retest:

- `backend/data/eval_results_gt039_after_new_upload.json`
- `backend/data/eval_report_gt039_after_new_upload.json`
- `backend/data/eval_ragas_gt039_after_new_upload_qwen3_32b.json`
- `backend/data/eval_ragas_gt039_after_new_upload_qwen3_32b_faithfulness_retry.json`

Jawaban sistem pada retest:

```text
Berdasarkan Laporan Pelaksanaan Evaluasi SPBE 2024, Domain Manajemen mencetak skor evaluasi terendah secara nasional dengan nilai indeks sebesar 1,86 [1]. Skor ini merupakan rata-rata paling rendah dibandingkan keempat domain lainnya yang dievaluasi dalam laporan tersebut [3].
```

Top-5 retrieval seluruhnya berasal dari dokumen baru `Laporan Pelaksanaan Evaluasi SPBE 2024.pdf` dengan `document_id=23` dan chunk `39`, `40`, `37`, `36`, `45`. Ini menunjukkan masalah utama GT-039 sebelumnya adalah ketersediaan/hasil ingestion dokumen, bukan kemampuan RAG menjawab setelah evidence tersedia.

Skor heuristic focused GT-039:

| Metrik | Skor |
|---|---:|
| semantic_similarity | 0.7854 |
| context_recall | 1.0000 |
| answer_coverage | 1.0000 |

Skor RAGAS focused GT-039 dengan Qwen/Qwen3-32B:

| Metrik | Skor | Catatan |
|---|---:|---|
| context_precision | 0.9500 | Top-5 context sangat relevan. |
| context_recall | 1.0000 | Fakta `Domain Manajemen` dan `1,86` tercakup. |
| faithfulness | 1.0000 | Nilai didapat dari retry khusus faithfulness karena run awal menghasilkan null. |
| answer_relevancy | 0.6690 | Jawaban benar, tetapi masih dapat dibuat lebih ringkas agar relevansi naik. |

Kesimpulan focused retest: **GT-039 resolved**. Untuk menaikkan `answer_relevancy`, jawaban ideal sebaiknya lebih ringkas, misalnya: “Domain dengan skor evaluasi terendah secara nasional pada Laporan Pelaksanaan Evaluasi SPBE 2024 adalah Domain Manajemen SPBE dengan skor 1,86.”

---

## 7. Perbandingan Sebelum dan Sesudah Iterasi Low8

| Aspek | Sebelum Fix | Setelah Fix | Interpretasi |
|---|---:|---:|---|
| hit@1 | 0.6250 | 0.7500 | Konteks target lebih sering berada di rank pertama. |
| hit@5 | 1.0000 | 1.0000 | Tidak ada penurunan cakupan top-5. |
| recall@5 | 0.8333 | 0.8333 | Recall tetap aman sesuai constraint. |
| precision@5 | 0.5250 | 0.5000 | Sedikit turun pada ID metric, tetapi kasus target utama GT-009/GT-027 membaik. |
| citation_match@5 | 0.8750 | 1.0000 | Sitasi top-5 membaik. |
| source_doc_hit@5 | 1.0000 | 1.0000 | Dokumen sumber benar tetap ditemukan. |

Kesimpulan perbandingan: perubahan paling berdampak pada **posisi/ranking konteks target**, bukan pada penambahan coverage. Recall tetap stabil, sehingga iterasi aman dari sisi risiko kehilangan konteks penting.

---

## 8. Analisis Permasalahan yang Masih Tersisa

### 8.1 Jawaban terlalu panjang (Telah Diperbaiki via Prompt Engineering)

Beberapa pertanyaan yang jawabannya seharusnya singkat awalnya dijawab dengan tambahan konteks berlebih. Contoh:

- GT-007 seharusnya cukup: “Memastikan penerapan unsur-unsur SPBE secara terpadu.”
- GT-009 seharusnya cukup: “5 (lima) tahun.”
- GT-027 seharusnya cukup: “LATIK cakupan Keamanan SPBE, yaitu LATIK pemerintah atau LATIK Terakreditasi yang terdaftar.”

Tambahan kalimat membuat `answer_relevancy` atau `faithfulness` turun walaupun jawaban inti benar. Untuk mengatasi hal ini tanpa menggunakan mekanisme pemotongan kode paksa (*post-processing trimmer*), telah dilakukan **Peningkatan Prompt Engineering**:
1. Menambahkan contoh Few-Shot yang membedakan jawaban `BENAR` dan `SALAH` (contoh salah adalah yang bertele-tele).
2. Memasukkan *hard-stop rules* di instruksi utama (contoh: "Tulis 1 kalimat, SELESAI.").
3. Melarang penggunaan pengantar kalimat klise ("Berdasarkan dokumen yang diberikan...").

### 8.2 Judge variance

Ada indikasi perbedaan penilaian antar judge. Contoh paling jelas adalah GT-013: konteks eksplisit tersedia, tetapi fallback Llama memberi `context_recall=0.0`. Karena itu, untuk laporan akademik/evaluasi, hasil fallback harus diberi catatan sebagai pembanding saat Qwen terkena limit.

### 8.3 GT-039 sudah resolved setelah unggah ulang dokumen

GT-039 awalnya menanyakan agregat nasional Laporan 2024, tetapi chunk aktif lama lebih banyak berisi data instansi individual sehingga fakta `Domain Manajemen SPBE dengan skor 1,86` tidak ditemukan oleh retrieval. Setelah dokumen `Laporan Pelaksanaan Evaluasi SPBE 2024.pdf` diunggah ulang dan terindeks, top-5 retrieval mengambil chunk agregat nasional yang benar dan jawaban sistem menjadi tepat. Ini mengonfirmasi bahwa kegagalan awal GT-039 terutama berasal dari ingestion/corpus availability.

---

## 9. Kesimpulan Akhir

1. **Retrieval sistem sudah kuat**, ditunjukkan oleh full evaluation `context_recall=0.9250` dan low8 `hit@5=1.0`.
2. **Perbaikan reranker berhasil**, terutama untuk GT-009 dan GT-027, tanpa menurunkan `recall@5`.
3. **Kualitas jawaban masih perlu dibuat lebih ringkas**, terutama untuk pertanyaan definisi, tujuan, siapa, dan berapa.
4. **GT-039 sudah resolved pada retest focused setelah unggah ulang dokumen**, tetapi baseline full 40 lama tetap menyimpan skor lama karena belum dihitung ulang 40/40 penuh.
5. **Full 40 RAGAS tetap menjadi baseline utama**, sementara low8 adalah evaluasi targeted untuk melihat dampak iterasi perbaikan.

---

## 10. Rekomendasi Lanjutan

1. **Tambahkan quality gate ingestion Laporan 2024**  
   Pastikan tabel/ringkasan agregat nasional domain SPBE 2024 masuk ke chunk aktif, khususnya frasa `Domain Manajemen SPBE`, `1,86/1.86`, dan ringkasan agregat nasional.

2. **Pertahankan Pendekatan Prompt Engineering untuk Jawaban Ringkas**  
   Penyelesaian masalah *answer relevancy* sebaiknya murni menggunakan teknik modifikasi prompt (*few-shot*, *hard-stop*) alih-alih menggunakan alat potong (*trimmer*) pasca-generasi agar respons LLM tetap natural dan tidak berisiko menghilangkan sitasi.

3. **Retest Qwen RAGAS setelah limit Groq pulih**  
   Karena hasil Qwen setelah fix masih parsial akibat token limit.

4. **Jalankan full 40 RAGAS ulang setelah kuota Groq pulih**  
   Agar laporan akhir mencerminkan perubahan terbaru GT-039 dan prompt fix, bukan hanya baseline sebelum perbaikan.

5. **Pertahankan top-5 retrieval**  
   Karena top-5 terbukti menjaga recall. Perbaikan berikutnya sebaiknya fokus pada ranking dan generation, bukan mempersempit konteks secara agresif.

---

## 11. Artefak Evaluasi yang Digunakan

| Artefak | Fungsi |
|---|---|
| `backend/data/eval_ragas_aggregate_4metrics_groq_auto.json` | Sumber hasil evaluasi penuh 40 pertanyaan. |
| `backend/data/eval_retrieval_ids_report_iterasi_low8_after_fixes_v2.json` | Sumber hasil retrieval targeted low8 setelah fix. |
| `backend/data/eval_results_iterasi_low8_after_fixes_v2.json` | Jawaban RAG terbaru untuk low8 setelah fix. |
| `backend/data/eval_ragas_iterasi_low8_after_fixes_v2_qwen3_32b.json` | RAGAS low8 setelah fix dengan Qwen judge, parsial karena limit. |
| `backend/data/eval_ragas_iterasi_low8_after_fixes_v2_llama4.json` | RAGAS low8 setelah fix dengan fallback Llama judge. |
| `backend/data/laporan_iterasi_low8_ragas.md` | Laporan ringkas iterasi low8 sebelumnya. |
| `backend/data/eval_results_gt039_after_new_upload.json` | Jawaban dan top-5 retrieval focused GT-039 setelah unggah ulang dokumen. |
| `backend/data/eval_report_gt039_after_new_upload.json` | Skor heuristic focused GT-039 setelah unggah ulang dokumen. |
| `backend/data/eval_ragas_gt039_after_new_upload_qwen3_32b.json` | RAGAS Qwen focused GT-039 untuk context precision, context recall, dan answer relevancy. |
| `backend/data/eval_ragas_gt039_after_new_upload_qwen3_32b_faithfulness_retry.json` | Retry RAGAS Qwen focused GT-039 untuk faithfulness. |
