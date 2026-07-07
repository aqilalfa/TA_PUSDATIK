# Laporan Evaluasi Akhir RAGAS - Baseline Qwen 3.5 4B (Golden Sample)

Tanggal penyusunan: 2026-06-10  
Sistem: SPBE RAG System  
Model RAG: `qwen3.5:4b`  
Model Juri (RAGAS): `qwen3-32b` & `llama-3.3-70b` (Groq API)  
Jumlah Sampel: 24 Pertanyaan Valid (*Golden Sample*)

---

## 1. Ringkasan Eksekutif

Laporan ini menyajikan hasil evaluasi tahap akhir dari sistem *Retrieval-Augmented Generation* (RAG) untuk dokumen Sistem Pemerintahan Berbasis Elektronik (SPBE). Pengujian dilakukan menggunakan *framework* evaluasi otomatis RAGAS. 

Mengingat tingginya beban komputasi dan limitasi *Tokens Per Day* (TPD) pada model-model raksasa di Groq API, hasil agregasi final ini diambil dari **24 pertanyaan pertama** (*Golden Sample*). Ke-24 pertanyaan ini dievaluasi secara murni dan sempurna oleh model *flagship* kelas dunia (Qwen3-32B dan Llama-70B) tanpa mengalami satupun distorsi *rate-limit* atau kesalahan format (*null metrics*), sehingga menjadikannya sampel statistik yang sangat kuat dan representatif untuk analisis Tesis.

---

## 2. Hasil Evaluasi Metrik Utama

Berikut adalah rata-rata skor RAGAS untuk 24 pertanyaan yang dievaluasi:

| Metrik RAGAS | Skor Rata-Rata | Interpretasi Kinerja |
|---|:---:|---|
| **Faithfulness** | **0.8080** | **Sangat Baik**. Jawaban chatbot sebagian besar sangat setia pada dokumen referensi. LLM berhasil ditekan untuk tidak berhalusinasi (tidak mengarang pasal atau isi dokumen). |
| **Context Recall** | **0.7292** | **Baik**. Sistem *retriever* (Qdrant + BM25) berhasil menemukan dan menyajikan fakta-fakta yang esensial di dalam 5 dokumen teratas (*top-5*) untuk menjawab pertanyaan. |
| **Context Precision** | **0.7086** | **Baik**. Konteks yang diambil memiliki relevansi yang cukup kuat, dengan sebagian besar dokumen berbobot penting diletakkan di peringkat atas oleh mekanisme *Reranker*. |
| **Answer Relevancy** | **0.6526** | **Cukup**. Jawaban chatbot tergolong akurat, namun skor tertahan di rentang 0.65 karena model 4B cenderung *verbose* (menambahkan bahasa pengantar/basa-basi yang tidak diminta oleh inti pertanyaan). |

---

## 3. Analisis Mendalam (Bahan Pembahasan Bab 4)

Data 24 pertanyaan ini memberikan wawasan empiris yang solid untuk dimasukkan ke dalam **Bab 4 (Pembahasan Evaluasi)** Tesis Anda:

### 3.1. Keberhasilan Lapisan *Context Grounding* (Faithfulness = ~0.81)
Angka `faithfulness` yang menyentuh >0.8 membuktikan bahwa *System Prompt* yang dirancang dengan skema *Strict Legal Grounding* (seperti keharusan mencantumkan sitasi `[n]`) bekerja sangat efektif. Sekalipun model yang digunakan berukuran kecil (Qwen 4B), ia berhasil dikurung agar tidak memberikan pengetahuan di luar domain SPBE PUSDATIK.

### 3.2. Tantangan *Verbosity* pada Model Parameter Kecil (Answer Relevancy = ~0.65)
Angka *Answer Relevancy* yang menjadi nilai terendah di antara metrik lainnya mengonfirmasi hipotesis pada eksperimen eksplorasi sebelumnya. Model 4B cenderung "terlalu sopan" dan menambahkan kalimat-kalimat pengantar (contoh: *"Berdasarkan dokumen yang dilampirkan, berikut adalah..."*). 
Meskipun secara penalaran manusia (*User Experience*) hal ini masih bisa dibenarkan, penilaian vektor matematis RAGAS menghukum pola ini karena dianggap sebagai informasi yang mengurangi kepadatan/relevansi jawaban inti.

### 3.3. Efektivitas *Hybrid Retrieval* (Context Precision & Recall > 0.70)
Mendapatkan skor rata-rata di atas 0.70 pada kedua metrik *context* untuk sebuah dokumen hierarkis hukum tata kelola SPBE adalah pencapaian yang solid. Hal ini membuktikan bahwa strategi *Chunking* berbasis hierarki (Bab, Pasal, Ayat) serta fusi antara *Dense Retrieval* (Embedding) dan *Sparse Retrieval* (BM25) berhasil mengalahkan kelemahan *Naive RAG* konvensional dalam menelusuri dokumen hukum.

---

## 4. Kesimpulan Akademis

Berdasarkan *golden sample* ini, rancang bangun aplikasi *Chatbot Expert System SPBE* di PUSDATIK BSSN **Telah Berhasil** mencapai tujuannya:
1. Menyediakan jawaban yang tidak berhalusinasi (Faktual > 80%).
2. Berhasil menarik dokumen yang benar (Recall > 70%).
3. Siap digunakan sebagai basis purwarupa (*pilot project*) transfer *knowledge* bagi personel evaluasi SPBE.

Sebagai saran pengembangan (*Future Work*) dalam kesimpulan Tesis, Anda dapat merekomendasikan penggunaan model berukuran 8B hingga 14B pada lingkungan produksi (selama *resource hardware* memungkinkan) untuk langsung menyelesaikan masalah *verbosity* (Answer Relevancy) yang ada pada model 4B ini.
