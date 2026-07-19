# Analisis Pertanyaan Berskor Rendah pada Evaluasi RAGAS

## 1. Tujuan Analisis

Analisis ini dilakukan untuk menjelaskan pertanyaan-pertanyaan yang memperoleh skor rendah pada evaluasi RAGAS. Pembahasan tidak hanya berfokus pada nilai rata-rata, tetapi juga mengidentifikasi pola kegagalan pada tingkat pertanyaan.

Analisis ini menjawab beberapa aspek berikut:

- kategori pertanyaan yang gagal;
- apakah kegagalan berasal dari retrieval atau generation;
- apakah jawaban terlalu panjang;
- apakah konteks tidak lengkap;
- apakah model gagal memahami maksud pertanyaan;
- apakah struktur pasal dan tabel memengaruhi hasil.

Analisis dilakukan terhadap hasil evaluasi RAGAS pada 40 pertanyaan yang sama (`gt_001` sampai `gt_040`) untuk konfigurasi:

- Vector-only;
- BM25-only;
- Hybrid.

Konfigurasi final belum dimasukkan dalam analisis ini karena hasil evaluasi RAGAS untuk konfigurasi final baru belum lengkap/valid.

---

## 2. Ringkasan Pola Kegagalan

Berdasarkan hasil per pertanyaan, skor rendah paling sering muncul pada pertanyaan yang membutuhkan:

1. rujukan pasal spesifik, misalnya Pasal 2, Pasal 3, Pasal 46, dan Pasal 47;
2. definisi hukum yang berada pada bagian awal dokumen, misalnya Pasal 1;
3. data tabel atau tren numerik lintas tahun;
4. pemahaman struktur dokumen hukum seperti BAB, Pasal, Ayat, Lampiran, dan tabel;
5. pemahaman maksud pertanyaan yang sangat spesifik, seperti “tujuan”, “komponen”, “objek”, “prinsip”, atau “nilai maksimum”.

Secara umum, skor rendah lebih banyak disebabkan oleh **kegagalan retrieval** dibandingkan kegagalan generation. Banyak respons model sebenarnya bersikap hati-hati dengan menyatakan bahwa informasi tidak ditemukan, tetapi skor tetap rendah karena konteks yang diberikan kepada model tidak memuat bagian dokumen yang tepat.

---

## 3. Contoh Pertanyaan Berskor Rendah

### 3.1 `gt_037` — Definisi Interoperabilitas dalam Prinsip SPBE

| Aspek | Temuan |
|---|---|
| Pertanyaan | Apa yang dimaksud dengan interoperabilitas dalam prinsip SPBE menurut Perpres Nomor 95 Tahun 2018? |
| Kategori | Definisi/prinsip regulasi |
| Skor rendah | Pada vector-only, seluruh metrik bernilai 0. Pada BM25 dan hybrid, context precision dan context recall juga rendah. |
| Sumber kegagalan | Retrieval |
| Masalah utama | Sistem tidak selalu mengambil Pasal 2 Perpres Nomor 95 Tahun 2018 yang memuat prinsip SPBE. |
| Dampak | Model menyatakan informasi tidak ditemukan atau menjawab secara parsial. |

Pada konfigurasi vector-only, konteks yang terambil lebih banyak berasal dari dokumen lain seperti PERKA BSSN Nomor 2 Tahun 2023 dan Perpres Nomor 82 Tahun 2023. Padahal pertanyaan secara eksplisit meminta prinsip SPBE menurut Perpres Nomor 95 Tahun 2018.

Dengan demikian, kegagalan utama pada pertanyaan ini berasal dari retrieval yang tidak menemukan pasal yang tepat.

---

### 3.2 `gt_025` — Definisi SPBE menurut Perpres Nomor 95 Tahun 2018

| Aspek | Temuan |
|---|---|
| Pertanyaan | Apa yang dimaksud dengan SPBE menurut Perpres Nomor 95 Tahun 2018? |
| Kategori | Definisi hukum / Pasal 1 |
| Skor rendah | Vector-only dan hybrid rendah; BM25 lebih baik tetapi masih belum optimal. |
| Sumber kegagalan | Retrieval dan struktur dokumen |
| Masalah utama | Konteks sering mengambil lampiran atau dokumen lain, bukan Pasal 1 Perpres Nomor 95 Tahun 2018. |
| Dampak | Model menyatakan definisi lengkap tidak ditemukan, padahal definisi SPBE seharusnya tersedia pada Pasal 1. |

Pertanyaan definisi hukum sangat bergantung pada pengambilan bagian dokumen yang tepat. Jika retrieval hanya mengambil konteks yang secara semantik terkait SPBE tetapi bukan Pasal 1, model tidak dapat memberikan definisi formal yang sesuai.

Dengan demikian, kegagalan pada pertanyaan ini terutama berasal dari retrieval yang tidak cukup presisi terhadap struktur Pasal 1.

---

### 3.3 `gt_011` — Komponen Standar Audit Keamanan SPBE Pasal 2

| Aspek | Temuan |
|---|---|
| Pertanyaan | Apa saja komponen Standar Audit Keamanan SPBE menurut Peraturan BSSN Nomor 8 Tahun 2024 Pasal 2? |
| Kategori | Pasal spesifik / daftar komponen |
| Skor rendah | Sangat rendah pada vector-only dan hybrid; BM25 lebih baik tetapi tetap belum optimal. |
| Sumber kegagalan | Retrieval |
| Masalah utama | Konteks yang terambil berasal dari Pasal 8, Pasal 11, Pasal 12, Pasal 38, atau pasal lain, bukan Pasal 2. |
| Dampak | Model menjawab bahwa komponen tidak tercantum secara eksplisit atau konteks tidak cukup. |

Pertanyaan ini secara eksplisit menyebut Pasal 2. Namun, retrieval mengambil bagian lain dari dokumen yang masih berada pada topik Standar Audit Keamanan SPBE. Hal ini menunjukkan bahwa kemiripan topik saja belum cukup untuk menjawab pertanyaan berbasis pasal.

Dengan demikian, struktur pasal sangat memengaruhi hasil. Retrieval perlu lebih sensitif terhadap rujukan pasal eksplisit.

---

### 3.4 `gt_012` — Objek Audit Keamanan SPBE Pasal 3

| Aspek | Temuan |
|---|---|
| Pertanyaan | Apa saja objek Audit Keamanan SPBE yang tercantum dalam Pasal 3 Peraturan BSSN Nomor 8 Tahun 2024? |
| Kategori | Pasal spesifik / enumerasi objek |
| Skor rendah | Context precision dan context recall rendah pada beberapa konfigurasi; faithfulness juga rendah pada sebagian hasil. |
| Sumber kegagalan | Retrieval dan generation |
| Masalah utama | Konteks kadang mengambil Pasal 70, Pasal 26, Pasal 28, atau hanya sebagian ayat dari Pasal 3. |
| Dampak | Jawaban dapat menjadi parsial atau tidak mencakup seluruh objek audit. |

Pertanyaan ini meminta daftar objek audit. Jika konteks hanya memuat sebagian ayat atau pasal lain, model dapat menjawab sebagian, tetapi RAGAS memberi skor rendah karena konteks tidak mencakup seluruh fakta yang dibutuhkan.

Dengan demikian, kegagalan berasal dari konteks yang tidak lengkap untuk pertanyaan enumeratif berbasis pasal.

---

### 3.5 `gt_005` — Tren Indeks SPBE Nasional 2018–2024

| Aspek | Temuan |
|---|---|
| Pertanyaan | Bagaimana perkembangan nilai Indeks SPBE Nasional dari tahun 2018 sampai 2024? |
| Kategori | Tren numerik lintas tahun / tabel |
| Skor rendah | BM25 dan hybrid rendah pada context precision, context recall, dan answer relevancy. |
| Sumber kegagalan | Retrieval dan konteks tidak lengkap |
| Masalah utama | Konteks mengambil sebagian laporan, seperti laporan 2023 atau 2024, tetapi tidak memuat deret lengkap 2018–2024. |
| Dampak | Model menyatakan data tidak lengkap atau tidak dapat menyajikan tren penuh. |

Pertanyaan ini membutuhkan konteks lintas tahun. Informasi yang dibutuhkan kemungkinan tersebar di beberapa tabel atau laporan. Jika Top-5 konteks tidak memuat seluruh deret tahun, model tidak dapat menyusun tren lengkap.

Dengan demikian, kegagalan berasal dari context recall yang rendah, bukan semata-mata dari kemampuan model generatif.

---

### 3.6 `gt_001` — Nilai dan Predikat Indeks SPBE Nasional 2024

| Aspek | Temuan |
|---|---|
| Pertanyaan | Berapa nilai Indeks SPBE Nasional pada tahun 2024 dan apa predikatnya? |
| Kategori | Fakta numerik / laporan evaluasi |
| Skor rendah | Vector-only dan hybrid rendah, terutama pada context precision, context recall, dan answer relevancy. |
| Sumber kegagalan | Retrieval dan generation |
| Masalah utama | Konteks bercampur antara laporan 2023 dan laporan 2024, serta tidak selalu mengambil bagian yang memuat nilai dan predikat nasional. |
| Dampak | Model menjawab terlalu hati-hati atau menyatakan tidak ada satu angka tunggal. |

Pertanyaan ini membutuhkan chunk yang memuat angka Indeks SPBE Nasional 2024 dan predikatnya. Ketika konteks yang diambil berupa data capaian instansi atau laporan tahun berbeda, jawaban menjadi tidak langsung dan kurang relevan.

Dengan demikian, kegagalan berasal dari retrieval yang mengambil konteks laporan/tabel yang kurang tepat, kemudian generation menjadi terlalu hati-hati.

---

### 3.7 `gt_028` — Tujuan Manajemen Risiko SPBE Pasal 47

| Aspek | Temuan |
|---|---|
| Pertanyaan | Apa tujuan Manajemen Risiko SPBE menurut Pasal 47 Perpres Nomor 95 Tahun 2018? |
| Kategori | Pasal spesifik / tujuan |
| Skor rendah | Context precision dan context recall rendah pada semua konfigurasi. |
| Sumber kegagalan | Retrieval |
| Masalah utama | Vector-only mengambil Peraturan BSSN Nomor 4 Tahun 2021. BM25/hybrid dapat menemukan Pasal 47, tetapi konteks masih parsial. |
| Dampak | Model menyatakan tujuan spesifik tidak dapat diidentifikasi secara lengkap. |

Pertanyaan ini membutuhkan bagian yang tepat dari Pasal 47. Jika hanya sebagian ayat atau konteks sekitar pasal yang tersedia, model tidak dapat menjawab “tujuan” secara lengkap.

Dengan demikian, struktur pasal dan ayat memengaruhi hasil secara langsung.

---

### 3.8 `gt_033` — Definisi Sistem Elektronik PP Nomor 71 Tahun 2019

| Aspek | Temuan |
|---|---|
| Pertanyaan | Apa yang dimaksud dengan Sistem Elektronik menurut Pasal 1 PP Nomor 71 Tahun 2019? |
| Kategori | Definisi hukum / Pasal 1 |
| Skor rendah | Semua konfigurasi rendah pada context precision dan context recall. |
| Sumber kegagalan | Retrieval |
| Masalah utama | Retrieval sering mengambil Pasal 27, Pasal 34, Pasal 104, atau dokumen lain, bukan Pasal 1. |
| Dampak | Model menyatakan definisi lengkap tidak ditemukan. |

Pertanyaan definisi Pasal 1 sangat sensitif terhadap lokasi dokumen. Jika Pasal 1 tidak terambil, model tidak memiliki dasar untuk memberikan definisi formal.

Dengan demikian, kegagalan disebabkan oleh retrieval yang tidak menemukan definisi utama pada Pasal 1.

---

## 4. Klasifikasi Penyebab Kegagalan

### 4.1 Kegagalan Retrieval

Kegagalan retrieval merupakan penyebab dominan. Pola ini terlihat ketika:

- `context_precision` rendah atau 0;
- `context_recall` rendah atau 0;
- jawaban menyatakan informasi tidak ditemukan;
- sumber yang terambil berasal dari dokumen atau pasal yang salah.

Contoh kasus:

| ID | Pertanyaan Ringkas | Masalah Retrieval |
|---|---|---|
| `gt_011` | Komponen Standar Audit Keamanan SPBE Pasal 2 | Mengambil Pasal 8, 11, 12, atau 38, bukan Pasal 2. |
| `gt_025` | Definisi SPBE menurut Perpres 95/2018 | Mengambil lampiran atau dokumen lain, bukan Pasal 1. |
| `gt_028` | Tujuan Manajemen Risiko SPBE Pasal 47 | Konteks Pasal 47 tidak lengkap atau bercampur dokumen lain. |
| `gt_033` | Definisi Sistem Elektronik PP 71/2019 Pasal 1 | Mengambil Pasal 27, 34, atau 104, bukan Pasal 1. |
| `gt_038` | Keamanan SPBE menurut Peraturan BSSN 8/2024 | Mengambil Peraturan BSSN 4/2021 atau dokumen lain. |

---

### 4.2 Kegagalan Generation

Kegagalan generation muncul ketika konteks sebagian relevan, tetapi model:

- menjawab terlalu hati-hati;
- memberikan fallback meskipun sebagian informasi tersedia;
- memberikan jawaban panjang tetapi tidak langsung menjawab inti pertanyaan;
- gagal menyusun jawaban dari konteks parsial.

Contoh kasus:

| ID | Pertanyaan Ringkas | Masalah Generation |
|---|---|---|
| `gt_001` | Nilai Indeks SPBE Nasional 2024 | Model menyatakan tidak ada satu angka tunggal, padahal pertanyaan meminta nilai dan predikat. |
| `gt_005` | Tren Indeks SPBE 2018–2024 | Model menjelaskan keterbatasan data tetapi tidak menyajikan tren lengkap. |
| `gt_012` | Objek Audit Keamanan SPBE Pasal 3 | Jawaban dapat menjadi parsial karena konteks tidak lengkap. |
| `gt_037` | Interoperabilitas prinsip SPBE | Model kadang menjawab umum, tetapi tidak selalu didukung konteks yang tepat. |

Namun, kegagalan generation ini sering merupakan dampak lanjutan dari retrieval yang tidak memberikan konteks yang lengkap.

---

## 5. Pengaruh Panjang Jawaban

Beberapa jawaban berskor rendah justru cukup panjang. Hal ini menunjukkan bahwa jawaban panjang tidak selalu berkorelasi dengan kualitas yang baik.

| ID | Konfigurasi | Panjang Jawaban | Catatan |
|---|---|---:|---|
| `gt_011` | Vector-only | ±2345 karakter | Jawaban panjang tetapi konteks tidak tepat. |
| `gt_005` | BM25-only | ±1533 karakter | Jawaban menjelaskan keterbatasan, tetapi tidak menjawab tren 2018–2024 secara lengkap. |
| `gt_001` | Hybrid | ±1472 karakter | Jawaban panjang tetapi tidak langsung memberikan nilai dan predikat. |
| `gt_028` | BM25-only | ±1223 karakter | Jawaban menjelaskan keterbatasan konteks Pasal 47. |

Panjang jawaban sering muncul karena model mencoba menjelaskan keterbatasan konteks. Namun, apabila jawaban tidak langsung menjawab pertanyaan, nilai `answer_relevancy` tetap rendah.

---

## 6. Pengaruh Konteks Tidak Lengkap

Konteks tidak lengkap sangat memengaruhi pertanyaan yang membutuhkan beberapa potongan informasi sekaligus.

Contoh:

| ID | Jenis Pertanyaan | Masalah Konteks |
|---|---|---|
| `gt_005` | Tren 2018–2024 | Data lintas tahun tidak seluruhnya muncul dalam Top-5 konteks. |
| `gt_012` | Enumerasi objek audit | Konteks hanya memuat sebagian ayat atau pasal lain. |
| `gt_028` | Tujuan Manajemen Risiko | Konteks Pasal 47 hanya sebagian. |
| `gt_019` | Level 5 Optimum | Informasi skala atau rentang nilai tidak ditemukan secara eksplisit. |

Pada kasus seperti ini, context recall menjadi rendah karena konteks yang diberikan kepada model tidak mencakup seluruh fakta yang diperlukan.

---

## 7. Pengaruh Pemahaman Maksud Pertanyaan

Beberapa pertanyaan membutuhkan pemahaman maksud yang lebih spesifik. Model atau pipeline retrieval kadang memahami topik umum, tetapi gagal menangkap kebutuhan spesifik.

| ID | Maksud Pertanyaan | Kegagalan |
|---|---|---|
| `gt_001` | Meminta nilai dan predikat nasional 2024 | Model menjawab tidak ada satu angka tunggal. |
| `gt_005` | Meminta tren nilai dari 2018 sampai 2024 | Konteks tidak menyajikan deret lengkap. |
| `gt_019` | Meminta nilai maksimum level 5 | Retrieval tidak mengambil tabel/skala yang tepat. |
| `gt_031` | Meminta prinsip keamanan SPBE pada Pasal 2 | Retrieval beralih ke dokumen keamanan lain. |

Hal ini menunjukkan bahwa intent seperti “nilai”, “tren”, “tujuan”, “komponen”, dan “prinsip” perlu dipetakan ke strategi retrieval yang berbeda.

---

## 8. Pengaruh Struktur Pasal dan Tabel

Struktur pasal, ayat, lampiran, dan tabel sangat memengaruhi hasil.

### 8.1 Struktur Pasal

Pertanyaan berbasis pasal gagal ketika retrieval mengambil:

- pasal yang berdekatan;
- ayat yang salah;
- lampiran;
- dokumen lain dengan istilah serupa.

Contoh:

| ID | Permintaan | Konteks yang Terambil |
|---|---|---|
| `gt_011` | Pasal 2 Peraturan BSSN 8/2024 | Pasal 8, 11, 12, 38 |
| `gt_033` | Pasal 1 PP 71/2019 | Pasal 27, 34, 104 |
| `gt_028` | Pasal 47 Perpres 95/2018 | Sebagian Pasal 47 atau dokumen BSSN lain |
| `gt_031` | Pasal 2 Perpres 95/2018 | Dokumen keamanan BSSN lain |

### 8.2 Struktur Tabel dan Data Numerik

Pertanyaan berbasis tabel atau tren gagal ketika:

- tabel tidak terambil secara lengkap;
- hanya sebagian baris yang muncul;
- data tersebar di beberapa dokumen;
- model tidak memperoleh semua angka yang dibutuhkan.

Contoh:

| ID | Permintaan | Masalah |
|---|---|---|
| `gt_001` | Nilai dan predikat Indeks SPBE 2024 | Konteks bercampur laporan 2023/2024 dan tidak selalu memuat angka nasional. |
| `gt_005` | Perkembangan indeks 2018–2024 | Data lintas tahun tidak lengkap. |
| `gt_019` | Nilai maksimum level 5 Optimum | Tabel/rentang nilai tidak terambil dengan jelas. |

---

## 9. Tabel Ringkas Pertanyaan Berskor Rendah

| ID | Pertanyaan Ringkas | Kategori | Skor Rendah Utama | Sumber Kegagalan | Analisis |
|---|---|---|---|---|---|
| `gt_011` | Komponen Standar Audit Keamanan SPBE Pasal 2 | Pasal spesifik | Precision, recall, relevancy | Retrieval | Konteks mengambil pasal lain seperti Pasal 8/11/12/38, bukan Pasal 2. |
| `gt_025` | Definisi SPBE menurut Perpres 95/2018 | Definisi Pasal 1 | Precision, recall, relevancy | Retrieval | Konteks mengambil lampiran/dokumen lain, bukan Pasal 1 definisi SPBE. |
| `gt_033` | Definisi Sistem Elektronik PP 71/2019 Pasal 1 | Definisi Pasal 1 | Precision, recall, relevancy | Retrieval | Retrieval mengambil Pasal 27/34/104, bukan Pasal 1. |
| `gt_005` | Tren Indeks SPBE 2018–2024 | Tren/tabel numerik | Recall, relevancy | Retrieval + konteks tidak lengkap | Konteks tidak memuat deret lengkap 2018–2024. |
| `gt_001` | Nilai dan predikat Indeks SPBE Nasional 2024 | Fakta numerik laporan | Recall, relevancy | Retrieval + generation | Konteks bercampur laporan 2023/2024; model menjawab terlalu hati-hati. |
| `gt_028` | Tujuan Manajemen Risiko SPBE Pasal 47 | Pasal spesifik | Precision, recall | Retrieval | Konteks parsial; ayat/pasal tidak cukup untuk menjawab tujuan secara lengkap. |
| `gt_037` | Interoperabilitas prinsip SPBE | Prinsip regulasi | Semua metrik pada vector-only | Retrieval | Vector-only tidak menemukan Pasal 2 Perpres 95/2018. |
| `gt_012` | Objek Audit Keamanan SPBE Pasal 3 | Enumerasi pasal | Recall, faithfulness | Retrieval + generation | Konteks hanya sebagian ayat/pasal lain; jawaban bisa parsial. |

---

## 10. Kesimpulan Analisis

Pertanyaan berskor rendah menunjukkan bahwa kegagalan utama sistem bukan hanya berasal dari model generatif, tetapi terutama dari tahap retrieval. Banyak pertanyaan yang gagal membutuhkan bagian dokumen yang sangat spesifik, seperti Pasal 1, Pasal 2, Pasal 3, Pasal 47, atau tabel tertentu. Ketika retrieval mengambil dokumen yang secara topik mirip tetapi bagian pasalnya salah, model tidak dapat menghasilkan jawaban yang sesuai dengan ground truth.

Kegagalan juga terjadi pada pertanyaan numerik dan tabel, terutama ketika informasi yang dibutuhkan tersebar lintas tahun atau lintas dokumen. Dalam kondisi seperti ini, Top-5 konteks tidak selalu cukup untuk mencakup seluruh fakta yang diperlukan.

Secara umum, jenis kegagalan dominan adalah:

```text
Retrieval failure > Generation failure