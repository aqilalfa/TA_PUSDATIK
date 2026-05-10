# Plan Perbaikan Chunking Semantik dan Tabel
**Tanggal:** 2026-04-17
**Status:** Dieksekusi

## 1) Latar Belakang Masalah
Temuan audit sebelumnya menunjukkan:
1. Chunk kadang dimulai di tengah kata (contoh potongan seperti "eks ND x BD ...").
2. Struktur tabel yang sudah dilinearisasi tetap bisa terpotong antar baris/kolom saat split berbasis karakter.
3. Ada indikasi drift data lama (sebagian dokumen memiliki chunk jauh di atas batas target).

## 2) Tujuan Perbaikan
1. Menghindari awal chunk jatuh di tengah kata.
2. Menjaga baris tabel tetap utuh sebisa mungkin (table-aware chunking).
3. Menjaga kompatibilitas pipeline ingest yang sudah ada.
4. Menyediakan langkah verifikasi objektif pasca perubahan.

## 3) Strategi Implementasi
### A. Boundary-aware overlap
Perbaiki fungsi split utama agar posisi start chunk berikutnya disesuaikan ke batas kata terdekat.

Rencana teknis:
1. Tambah helper internal untuk menyesuaikan indeks start ke boundary kata.
2. Tetap gunakan overlap, tetapi geser start ke kanan/kiri terkontrol agar tidak memotong token.
3. Tambah guard agar overlap tidak melebihi max size.

### B. Table-aware chunking
Tambah jalur split khusus untuk teks table-like (hasil linearisasi markdown table).

Rencana teknis:
1. Deteksi teks table-like (indikator pola ": ...; ..." per baris atau marker tabel).
2. Split berbasis baris dengan overlap berbasis ekor baris, bukan karakter mentah.
3. Jika ada baris sangat panjang, fallback ke splitter umum secara aman.

### C. Hygiene fix kecil
Hapus duplikasi penambahan header Pasal yang terulang pada satu blok chunking peraturan.

## 4) File yang Akan Diubah
1. backend/app/core/ingestion/structured_chunker.py

## 5) Langkah Eksekusi
1. Implement helper boundary-aware di splitter.
2. Implement splitter table-like berbasis baris.
3. Integrasi splitter table-like ke append_chunk_with_limit.
4. Fix duplikasi header Pasal.
5. Jalankan validasi syntax.
6. Jalankan uji fungsi cepat dengan contoh teks tabel dan contoh teks overlap.

## 6) Kriteria Sukses
1. Tidak ada chunk baru yang diawali fragmen tengah kata pada skenario uji.
2. Chunk table-like mempertahankan baris tabel utuh (kecuali baris tunggal sangat panjang).
3. File target lolos py_compile.
4. Tidak ada error runtime baru di area yang diubah.

## 7) Rencana Verifikasi
1. py_compile untuk file chunker.
2. Snippet test: split teks legal panjang untuk cek boundary awal chunk.
3. Snippet test: split teks table-like untuk cek pemisahan per baris.

## 8) Catatan Operasional
1. Perubahan ini fokus pada kualitas chunking saat ingest berikutnya.
2. Data lama yang sudah terlanjur tersimpan tetap perlu reprocess/reingest terarah bila ingin ikut membaik.

## 9) Checklist Eksekusi
- [x] Plan dibuat di folder edited
- [x] Patch boundary-aware overlap
- [x] Patch table-aware split
- [x] Fix duplikasi header Pasal
- [x] Validasi compile
- [x] Uji fungsi cepat
- [x] Ringkas hasil dan next step

## 10) Hasil Eksekusi Singkat
Perubahan yang sudah diterapkan:
1. `split_text_with_overlap` dibuat boundary-aware agar start chunk baru tidak jatuh di tengah kata.
2. Ditambahkan jalur table-aware (`_is_table_like_text`, `_split_table_like_text`) untuk menjaga split per baris tabel.
3. Dihapus duplikasi injeksi header `Pasal` pada blok ayat peraturan.

Hasil verifikasi:
1. `py_compile` untuk `backend/app/core/ingestion/structured_chunker.py`: OK.
2. Uji splitter teks umum: chunk start tidak lagi menunjukkan fragmen token acak.
3. Uji splitter teks tabel: table-like text diproses melalui jalur row-aware.

Catatan:
1. Perbaikan ini berlaku untuk proses ingest berikutnya.
2. Data lama yang sudah tersimpan perlu reprocess/reingest terarah bila ingin ikut membaik.

## 11) Lanjutan Eksekusi (Upload Baru + Sinkronisasi)
Perbaikan lanjutan yang sudah diselesaikan:
1. Rechunk terarah untuk dokumen terdampak (`doc_id=2`) selesai, lalu audit alignment pasca-rechunk lulus (`overall=ok`).
2. Sinkronisasi vector dari SQLite ke Qdrant selesai kembali (koleksi `document_chunks` terisi ulang).
3. Alur upload baru diperbaiki pada `backend/app/core/ingestion/document_manager.py`:
	- `preview_chunks` sekarang memprioritaskan pipeline yang sama dengan `DocumentProcessor` (`parse_document + chunk_document`).
	- Jika pipeline terstruktur gagal, fallback lama tetap dipakai agar endpoint tetap robust.
	- Fallback splitter default tidak lagi mengunci `max_chunk_size=1500`, sehingga mengikuti konfigurasi splitter.

Validasi upload baru:
1. Uji jalur `upload_file -> preview_chunks` dengan PDF sampel berhasil.
2. Log menunjukkan pipeline terstruktur dipakai: `Using structured chunker pipeline...`.
3. Instrumentasi call counter menunjukkan:
	- `parse_document`: 1x
	- `chunk_document`: 1x
4. Hasil preview: `total_chunks=147`, `max_chunk_len_preview_slice=594`.
5. Data uji sementara dibersihkan kembali (`delete_document`) setelah verifikasi.
