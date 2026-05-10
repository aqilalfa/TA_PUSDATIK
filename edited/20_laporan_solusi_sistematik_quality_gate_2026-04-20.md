# 20 - Laporan Solusi Sistematik Quality Gate RAG (Selesai vs Belum Selesai)

Tanggal: 2026-04-20  
Status: In progress (fondasi sistematik sudah aktif, masih ada 1 gap lintas-konteks)

## 1) Permasalahan Utama

Masalah yang ingin diselesaikan bukan sekadar kualitas jawaban untuk satu query tabel tertentu, melainkan pola yang berulang:

1. Jawaban kadang memunculkan klaim `tidak tersedia/tidak tercantum` padahal konteks relevan ada.
2. Kualitas jawaban tidak konsisten antar jenis query (tabel vs non-tabel).
3. Pendekatan perbaikan yang terlalu spesifik berisiko hanya bekerja pada satu konteks dan tidak reusable.

## 2) Tujuan Sistematik

Tujuan sesi ini difokuskan ke perbaikan arsitektur kualitas jawaban yang reusable lintas kasus:

1. Membangun **quality gate generik** pada jalur streaming chat.
2. Memilih jawaban terbaik berbasis skor kualitas (bukan 1x retry sempit).
3. Menjaga agar evaluasi dapat dipakai lintas konteks melalui regression terstruktur:
   - query tabel,
   - query non-tabel.

## 3) Yang Sudah Dilakukan

### A. Implementasi inti (backend)

Perubahan inti telah berjalan pada layer API streaming:

1. `backend/app/api/routes/chat.py`
   - Menambahkan quality signal generik: coverage istilah fokus query, struktur list, sitasi, panjang jawaban, source count, dan deteksi klaim unavailable.
   - Menambahkan quality score dan `needs_retry` sebagai dasar keputusan.
   - Menambahkan candidate pool + best-of selection (jawaban final dipilih dari kandidat terbaik, bukan sekadar jawaban pertama).
   - Menambahkan retry query builder berbasis alasan kualitas (reason-aware retry instruction).
   - Mengekspor ringkasan quality check ke payload event `complete` agar bisa diaudit dari script.

2. Refinement deteksi unavailable (sudah dipatch hari ini)
   - Memisahkan pola unavailable keras vs pola parsial kontekstual.
   - Mengurangi false positive dari frasa parsial yang deskriptif (tidak selalu berarti data hilang).

### B. Penguatan retrieval/guardrail yang sudah ada

1. `backend/app/core/rag/langchain_engine.py`
   - Tetap memakai fondasi retrieval-aware untuk query tabel (literal table retrieval, table-noise filter, dan metadata boost) agar konteks awal lebih relevan.

### C. Script evaluasi/regression

1. `backend/scripts/_tmp_table_batch.py`
   - Audit tabel dengan output terstruktur: benar/lengkap, negative phrase, sumber, panjang jawaban, kesimpulan.

2. `backend/scripts/_tmp_generic_quality_sanity.py`
   - Sanity check non-tabel lintas tipe query (definisi, daftar, perbandingan, indikator) dengan metrik quality gate.

### D. Hasil validasi terbaru

1. Tabel kritis (yang sebelumnya bermasalah) sekarang lulus:
   - Report: `data/evaluation/permenpan59_tabel_1_14_audit_20260420_144718.md`
   - Ringkasan: T6-T9 = PASS semua.

2. Non-tabel belum 100% stabil:
   - Report: `data/evaluation/generic_quality_sanity_20260420_150520.md`
   - Ringkasan: 3 PASS, 1 FAIL (`Q3_PERBANDINGAN`).

## 4) Yang Belum Dilakukan (Outstanding)

Berikut pekerjaan yang belum selesai penuh dan masih diperlukan agar target “solusi sistematik lintas konteks” benar-benar tercapai:

1. Menuntaskan root-cause final untuk fail `Q3_PERBANDINGAN` pada non-tabel sanity.
   - Gejala: quality gate masih mendeteksi konflik unavailable pada jawaban yang secara konten terlihat cukup lengkap.
   - Dampak: false-positive retry/fail pada sebagian query perbandingan.

2. Menyetel ulang calibration rule pada detector unavailable agar:
   - tetap sensitif untuk false-negative nyata,
   - tetapi tidak over-trigger pada kalimat pembatas yang faktual.

3. Menambahkan regression guard yang lebih formal agar tidak regress saat tuning:
   - threshold pass/fail lintas kategori query,
   - baseline report pembanding antar run.

4. Menyatukan script sanity ke alur evaluasi sesi (semi-standar) agar evaluasi tidak bergantung eksekusi manual ad-hoc.

## 5) Hal yang Sengaja Belum Dianggap Selesai

Agar tujuan tetap sistematik (bukan patch satu kasus), hal-hal berikut **belum** ditandai selesai:

1. Belum meng-hardcode aturan spesifik untuk query `Q3_PERBANDINGAN`.
2. Belum melakukan tuning prompt yang hanya memperbaiki satu query tapi berpotensi menurunkan generalisasi.
3. Belum menutup sesi sebagai “final” sebelum non-tabel sanity mencapai pass konsisten.

## 6) Rencana Eksekusi Lanjutan (Prioritas)

1. Tambahkan observability debug khusus quality detector (capture trigger phrase + window konteks) untuk query fail.
2. Finalisasi rule unavailable detector berbasis evidence lokal, lalu rerun `backend/scripts/_tmp_generic_quality_sanity.py`.
3. Jalankan ulang paket tabel + non-tabel dalam satu siklus, kemudian bandingkan dengan baseline report hari ini.
4. Jika hasil stabil, tandai quality gate sebagai reusable lintas konteks dan dokumentasikan sebagai standar kerja.

## 7) Kesimpulan Sementara

Fondasi solusi sistematik sudah terbentuk dan terbukti memperbaiki kasus tabel kritis, tetapi target lintas konteks belum 100% karena masih ada 1 fail pada sanity non-tabel. Fokus berikutnya bukan menambah patch spesifik kasus, melainkan menyelesaikan calibration detector agar quality gate benar-benar robust dan reusable.
