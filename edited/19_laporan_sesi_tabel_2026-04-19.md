# 19 - Laporan Sesi Perbaikan Query Tabel dan Rencana Lanjutan

Tanggal: 2026-04-19  
Status: Core fix selesai, regression lintas tabel masih dilanjutkan

## Tujuan Sesi

1. Menstabilkan jawaban untuk query sederhana berbasis tabel (khususnya pola `apa isi dari Tabel X`).
2. Menurunkan kasus jawaban "tidak tersedia/tidak tercantum" saat data tabel sebenarnya ada.
3. Menyiapkan baseline uji untuk tabel lain setelah Tabel 14.

## Perubahan yang Sudah Dibuat

### 1) Hardening retrieval untuk query tabel

File:
- `backend/app/core/rag/langchain_engine.py`

Perubahan utama:
- Menambahkan penalti lebih kuat untuk chunk "mention-only" seperti daftar tabel (noise index).
- Menambahkan boost untuk chunk yang memuat isi tabel aktual (termasuk marker tahap untuk tabel perbandingan).
- Menambahkan helper filter noise tabel agar hasil context lebih fokus ke isi tabel, bukan daftar.
- Menyesuaikan metadata boost agar ranking lebih sensitif ke sinyal isi tabel.

Dampak:
- Source retrieval lebih relevan untuk pertanyaan tabel.
- Risiko konteks didominasi "Daftar Tabel" berkurang.

### 2) Quality control jawaban tabel di layer streaming chat

File:
- `backend/app/api/routes/chat.py`

Perubahan utama:
- Menambahkan evaluasi kualitas jawaban tabel (stage coverage dan deteksi frasa unavailable).
- Menambahkan retry satu kali dengan instruksi lebih ketat jika kualitas jawaban awal belum memadai.
- Memperluas trigger retry: bukan hanya saat heading tahap hilang, tapi juga saat ada klaim "tidak tersedia/tidak tercantum".

Dampak:
- Jawaban akhir lebih lengkap dan lebih sedikit caveat yang tidak perlu.
- Stabilitas output meningkat untuk query tabel sederhana.

### 3) Catatan runtime/testing

File:
- `memories/repo/runtime_facts.md`

Perubahan utama:
- Menambahkan catatan soal prompt keamanan PowerShell saat web request dan penggunaan mode parsing yang aman untuk menghindari interupsi.

## Hasil Uji yang Sudah Terkonfirmasi

### Query target utama

1. Tabel 14 (simple query)
- `STAGE_HITS`: Tahap Persiapan, Tahap Pelaksanaan, Tahap Pelaporan
- `NEGATIVE_PHRASES`: kosong
- Hasil: lulus (coverage 3 tahap + tanpa frasa unavailable)

2. Tabel 13 (simple query)
- `EXPECT_HITS`: 4/4 (Memuaskan, Sangat Baik, Baik, Cukup)
- `NEGATIVE_PHRASES`: kosong
- Hasil: lulus

### Batch lanjutan yang sempat berjalan

1. T7 simple
- `EXPECT_HITS`: 3/3
- `NEGATIVE`: masih muncul "tidak tercantum"
- Status: perlu tuning lanjutan

2. T9 simple
- `EXPECT_HITS`: 3/3
- `NEGATIVE`: kosong
- Status: lulus

3. T11 simple
- `EXPECT_HITS`: 3/3
- `NEGATIVE`: kosong
- Status: lulus

## Kendala yang Muncul di Sesi Ini

1. Batch test sempat terputus (interrupt pada proses streaming yang panjang).
2. Variasi environment Python menyebabkan modul `requests` tidak selalu tersedia di interpreter aktif.
3. Ada percobaan parser SSE yang sempat gagal karena escape regex tidak tepat (menghasilkan `NO_COMPLETE_EVENT`).

## Pekerjaan yang Belum Selesai

1. Menuntaskan rerun stabil untuk tabel yang belum konsisten tervalidasi (minimal T8, T10, T12) dalam satu runner yang sama.
2. Menyatukan runner regression query tabel agar output metrik konsisten dan tersimpan ke file laporan.
3. Menurunkan residual kasus frasa unavailable di tabel selain 13/14 (contoh: T7).

## Rencana Eksekusi Berikutnya

1. Buat satu script regression tabel (SSE) dengan output ringkas per query:
   - negative phrases
   - expected keyword hits
   - source count
   - answer length
2. Jalankan regression set untuk T7-T14 (simple + targeted document query).
3. Jika masih ada miss:
   - tambah aturan ranking khusus tabel yang gagal,
   - validasi ulang tanpa mengubah makna query user.
4. Simpan hasil regression ke dokumen evaluasi berkala agar bisa dibandingkan antar sesi.

## Kesimpulan Sementara

Perbaikan inti untuk query tabel sudah berjalan efektif pada kasus prioritas (Tabel 13 dan Tabel 14). Fokus sesi berikutnya adalah menutup gap konsistensi pada tabel lain dan menstandarkan regression test supaya perbaikan dapat dipantau repeatable.
