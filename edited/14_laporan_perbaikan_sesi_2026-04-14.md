# Laporan Perbaikan Sesi

Tanggal: 14 April 2026
Fokus: Perbaikan kualitas RAG untuk kasus regulasi SPBE (target plan A1-B2) dan validasi end-to-end.

## Ringkasan Eksekusi

Pada sesi ini, perbaikan dilakukan dari sisi indexing, parsing/chunking, retrieval ranking, dan sanitasi jawaban streaming. Selain patch teknis, validasi regresi dijalankan ulang melalui endpoint chat stream agar hasil mencerminkan jalur backend yang sama dengan UI.

Status akhir:
- Checklist plan A1-B2 ditandai selesai.
- BM25 berhasil dimuat saat startup dengan 1580 chunk.
- Benchmark 3 pertanyaan utama berhasil mencapai hasil operasional 3/3.

## Daftar Perbaikan yang Dilakukan

### 1) Perbaikan pipeline BM25 (A1-A2)

File:
- backend/scripts/reingest_all.py
- backend/scripts/rebuild_bm25.py

Perbaikan:
- Mengganti alur rebuild BM25 agar tidak bergantung pada modul retriever yang tidak ada.
- Menambahkan builder teks lexical BM25 berbasis gabungan isi chunk + metadata dokumen (judul, filename, doc_type, hierarchy, bab/pasal/ayat).
- Menjamin format output BM25 konsisten dengan loader runtime.

Dampak:
- Rebuild BM25 berjalan stabil.
- Index BM25 aktif kembali di runtime.

### 2) Perbaikan ingestion dan struktur dokumen (A3-B1-B2)

File:
- backend/app/core/ingestion/document_manager.py
- backend/app/core/ingestion/json_structure_parser.py
- backend/app/core/ingestion/structured_chunker.py

Perbaikan:
- Regex deteksi Pasal diperkuat agar lebih toleran terhadap format heading legal yang bervariasi.
- Splitting chunk panjang diperketat dengan helper append_chunk_with_limit untuk menjaga batas ukuran chunk.
- Tokenisasi BM25 pada document manager diselaraskan ke format lexical + metadata.
- Konsistensi list dokumen diperketat agar hanya menampilkan dokumen dengan status valid dan chunk tersedia.

Dampak:
- Deteksi struktur pasal lebih baik.
- Chunk oversize lebih terkendali.
- Daftar dokumen di aplikasi lebih konsisten dengan kondisi index.

### 3) Tuning retrieval dan rerank untuk query legal spesifik

File:
- backend/app/core/rag/prompts.py
- backend/app/core/rag/langchain_engine.py

Perbaikan:
- Menambahkan aturan khusus domain evaluasi SPBE di prompt agar tidak tercampur dengan domain arsitektur.
- Menambahkan query expansion literal untuk definisi SPBE (frasa "yang dimaksud dengan ...") agar chunk definisi Pasal 1 lebih mudah terangkat.
- Menambahkan query-aware metadata boost pada rerank (termasuk sinyal perpres/nomor/tahun/pasal dan frasa definisi).
- Menyesuaikan final ranking dengan final_score (rerank_score + query_boost).

Dampak:
- Query Pasal 3 lebih konsisten mengangkat sumber Pasal 3.
- Query definisi SPBE lebih stabil mengangkat Pasal 1 sebagai sumber utama.
- Query domain evaluasi lebih terarah ke 4 domain evaluasi.

### 4) Hardening jawaban streaming agar lebih faithful

File:
- backend/app/api/routes/chat.py

Perbaikan:
- Menambahkan sanitasi pasca-validasi untuk menghapus referensi Ayat yang ditandai tidak ada di konteks.

Dampak:
- Mengurangi drift kutipan legal yang tidak didukung konteks.
- Meningkatkan kebersihan output akhir tanpa mengubah isi utama jawaban.

### 5) Pembaruan dokumentasi plan

File:
- edited/12_plan_perbaikan_rag_quality.md

Perbaikan:
- Checklist A1-B2 diubah menjadi selesai dengan catatan verifikasi terbaru (1580 chunk dan uji ulang lewat chat stream).

## Hasil Verifikasi End-to-End (API Stream)

Model default saat uji: qwen3.5:4b

### Query 1
Pertanyaan: Apa definisi SPBE menurut Perpres Nomor 95 Tahun 2018?

Hasil:
- Jawaban mengutip definisi SPBE dari Pasal 1.
- Sumber utama: PERATURAN PRESIDEN TENTANG 95 Tahun 2018 | BAB I > Pasal 1.
- Validasi: is_valid true, warnings kosong.

### Query 2
Pertanyaan: Apa isi Pasal 3 Perpres Nomor 95 Tahun 2018?

Hasil:
- Jawaban memuat ruang lingkup pengaturan Pasal 3 dengan butir a-f.
- Sumber utama: PERATURAN PRESIDEN TENTANG 95 Tahun 2018 | BAB I > Pasal 3.

### Query 3
Pertanyaan: Apa saja domain dalam evaluasi SPBE?

Hasil:
- Jawaban menampilkan 4 domain evaluasi SPBE:
  1. Kebijakan Internal SPBE
  2. Tata Kelola SPBE
  3. Manajemen SPBE
  4. Layanan SPBE

## Kesimpulan

Perbaikan inti sesi ini berhasil memulihkan pipeline hybrid retrieval dan meningkatkan kualitas jawaban pada 3 query benchmark utama. Jalur validasi sudah dilakukan melalui endpoint stream backend yang dipakai aplikasi, sehingga hasil representatif untuk operasional sistem saat ini.
