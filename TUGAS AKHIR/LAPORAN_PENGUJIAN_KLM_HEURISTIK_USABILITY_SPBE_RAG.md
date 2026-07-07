# Laporan Pengujian KLM dan Heuristik Usability Aplikasi SPBE RAG

Tanggal penyusunan: 2026-06-02

## 1. Tujuan Pengujian

Laporan ini menyusun evaluasi usability aplikasi SPBE RAG berdasarkan kondisi implementasi saat ini. Fokus evaluasi adalah:

1. Mengidentifikasi status role/pengguna yang tersedia saat ini.
2. Menilai antarmuka aplikasi terhadap 10 heuristik usability Nielsen.
3. Mengaitkan temuan dengan konteks KLM (Keystroke-Level Model), khususnya potensi waktu interaksi panjang pada alur chat, manajemen sesi, dan manajemen dokumen.
4. Memberikan rekomendasi perbaikan yang realistis sesuai kondisi aplikasi saat ini.

## 2. Ringkasan Kondisi Role Saat Ini

### 2.1 Apakah hanya ada role Admin PUSDATIK?

Tidak. Secara backend, aplikasi saat ini **tidak hanya memiliki satu role**. Role yang terdefinisi pada mapper adalah:

| Role aplikasi | Asal mapping direktori | Keterangan |
|---|---|---|
| `admin_pusdatik` | `Admin_PUSDATIK` | Role admin; juga mendapat `staf_pusdatik`. |
| `staf_pusdatik` | `Staf_PUSDATIK`, `Admin_PUSDATIK`, `Manager_Evaluasi` | Role staf umum PUSDATIK. |
| `evaluator_spbe` | `Evaluator_SPBE` | Role evaluator SPBE. |
| `manager_evaluasi` | `Manager_Evaluasi` | Role manajer evaluasi; juga mendapat `staf_pusdatik`. |

Bukti kode:

- `backend/app/auth/role_mapper.py` mendefinisikan mapping `Evaluator_SPBE`, `Staf_PUSDATIK`, `Admin_PUSDATIK`, dan `Manager_Evaluasi`.
- `backend/app/main.py` membuat minimal dua user uji: `admin@bssn.go.id` dengan role `admin_pusdatik`, dan `evaluator@bssn.go.id` dengan role `evaluator_spbe`.
- `backend/app/dependencies/auth_dependencies.py` menyediakan dependency `require_roles(...)` untuk membatasi endpoint berbasis role.

### 2.2 Kondisi implementasi role di UI

Frontend saat ini sudah **menampilkan role pengguna**, tetapi belum menerapkan pembatasan menu berbasis role secara eksplisit.

Bukti kode:

- `frontend/src/services/auth.js` menyimpan profil user dan memformat label role, termasuk `Admin PUSDATIK` dan `Evaluator SPBE`.
- `frontend/src/components/layout/AppHeader.vue` menampilkan nama dan role user melalui `currentUserRoleText`.
- `frontend/src/router.js` hanya melakukan guard autentikasi (`requiresAuth`) dan belum memiliki `requiredRoles` per route.

### 2.3 Dampak kondisi role saat ini

Secara backend, operasi sensitif seperti upload, simpan dokumen ke indeks, ubah chunk, hapus chunk, hapus dokumen, sinkronisasi Qdrant, pembuatan user, daftar user, dan pengaturan default model dibatasi ke `admin_pusdatik`.

Namun secara frontend, menu `Dokumen` tetap tampil untuk semua user yang login. Akibatnya, user non-admin dapat masuk ke halaman dokumen dan baru mengetahui pembatasan saat aksi tertentu ditolak oleh backend. Ini berdampak pada heuristik **error prevention**, **user control**, dan **match between system and real world**.

## 3. Ringkasan Hasil Heuristik

Skala status:

- **Baik**: sudah mendukung kebutuhan utama dan konsisten.
- **Cukup**: sudah ada sebagian, tetapi masih ada celah usability.
- **Perlu Perbaikan**: masalah berdampak jelas pada efektivitas, efisiensi, atau kepuasan pengguna.

| No | Heuristik | Status | Catatan / Masalah Utama |
|---:|---|---|---|
| 1 | Visibility of System Status | Cukup | Chat menampilkan status koneksi, loading, retrieval count, streaming, dan dokumen upload menampilkan stepper/progress. Namun status proses RAG belum menjelaskan tahap secara rinci dan error backend kadang masih generik. |
| 2 | Match Between System and Real World | Cukup | Bahasa UI banyak memakai istilah familiar seperti “Dokumen”, “Unggah”, “Pratinjau”, “Simpan ke Indeks”. Namun ada istilah teknis seperti RAG, Qdrant, chunk, dan model yang belum diberi penjelasan awam. |
| 3 | User Control and Freedom | Cukup | User bisa stop generation, hapus chat, buat sesi baru, rename/delete sesi, batal preview dokumen, dan logout. Namun operasi destruktif seperti hapus sesi/dokumen perlu konfirmasi lebih eksplisit. |
| 4 | Consistency and Standards | Cukup | Navigasi dan visual cukup konsisten. Namun ada inkonsistensi izin: frontend menampilkan menu/action admin untuk semua user login, sementara backend membatasi aksi admin. |
| 5 | Error Prevention | Cukup | Upload memiliki validasi format, ukuran, dan warning nama file. Tombol kirim disabled saat kosong/loading. Tetapi role-based menu belum mencegah user non-admin mencoba aksi admin. |
| 6 | Recognition Rather Than Recall | Baik | Ada sample questions, daftar sesi, judul sesi otomatis, source cards, citation popup, dan tombol aksi yang muncul pada jawaban. Ini mengurangi kebutuhan mengingat konteks. |
| 7 | Flexibility and Efficiency of Use | Cukup | Ada shortcut Enter, Shift+Enter, RAG toggle, model selector, regenerate, edit & retry, copy answer, dan session history. Namun belum ada template prompt, pencarian sesi, filter dokumen, atau shortcut lanjutan. |
| 8 | Aesthetic and Minimalist Design | Baik | Layout chat, sidebar, header, dan dokumen relatif bersih. Informasi utama cukup terfokus. Potensi overload muncul pada halaman dokumen/chunk jika data panjang. |
| 9 | Help Users Recognize, Diagnose, and Recover from Errors | Cukup | Error login, upload, timeout, dan chat ditampilkan. Tetapi beberapa pesan masih teknis/generik seperti “Pastikan server backend berjalan” atau detail permission backend mentah. |
| 10 | Help and Documentation | Perlu Perbaikan | Ada hint input dan label UI, tetapi belum ada halaman bantuan, panduan RAG, penjelasan role, panduan upload dokumen, atau tooltip istilah teknis. |

## 4. Analisis Detail Per Heuristik

### 4.1 Visibility of System Status

**Status: Cukup**

Implementasi yang mendukung:

- Header chat menampilkan status koneksi: `Terhubung`, `Terputus`, atau `Menghubungkan...`.
- Saat mengirim pertanyaan, UI menampilkan `Menganalisa pertanyaan...` lalu `Ditemukan X dokumen, sedang menjawab...`.
- Jawaban ditampilkan secara streaming sehingga user melihat progres jawaban secara langsung.
- Halaman dokumen memiliki stepper `UNGGAH → PREVIEW → INDEKS`.
- Upload dokumen memiliki progress bar persentase.
- Halaman dokumen menampilkan state loading seperti `Memuat dokumen...` dan `Mengekstrak chunks...`.

Masalah:

- Status retrieval belum memberi informasi tahap detail seperti “mencari vektor”, “BM25”, “reranking”, atau “menyusun jawaban”.
- Jika backend gagal, pesan sering tidak membedakan apakah masalahnya koneksi, token, izin, database, atau model LLM.
- Untuk KLM/waktu interaksi panjang, user bisa menunggu lama tanpa estimasi waktu atau progres granular.

Rekomendasi:

1. Tambahkan status bertahap pada chat: `Mencari dokumen`, `Menyusun konteks`, `Menghasilkan jawaban`, `Validasi jawaban`.
2. Tambahkan indikator estimasi untuk proses panjang seperti ingestion/preview dokumen.
3. Bedakan pesan error: koneksi, autentikasi, permission, model tidak tersedia, dan database.

### 4.2 Match Between System and Real World

**Status: Cukup**

Implementasi yang mendukung:

- Bahasa antarmuka menggunakan bahasa Indonesia formal dan domain SPBE: `SPBE Asisten`, `Manajemen Dokumen`, `Kelola sumber pengetahuan sistem RAG SPBE`.
- Pertanyaan contoh relevan dengan kebutuhan user: `Apa itu SPBE?`, `Apa saja domain dalam SPBE?`, `Bagaimana prosedur audit keamanan?`.
- Source card dan citation popup mendukung pola kerja pengguna yang membutuhkan bukti dokumen resmi.

Masalah:

- Istilah teknis seperti `RAG`, `Qdrant`, `chunk`, `model`, dan `indeks` belum diberi definisi di UI.
- Untuk pengguna non-teknis, istilah `Sinkronisasi Qdrant` tidak natural; lebih cocok “Sinkronisasi basis pengetahuan”.
- Role backend sudah lebih dari satu, tetapi UI belum menjelaskan perbedaan hak akses admin, evaluator, dan staf.

Rekomendasi:

1. Ubah label teknis menjadi bahasa pengguna, misalnya `Sinkronisasi Qdrant` → `Sinkronisasi Basis Pengetahuan`.
2. Tambahkan tooltip untuk `RAG`, `Chunk`, `Indeks`, dan `Model`.
3. Tambahkan ringkasan hak akses pada profil user atau halaman bantuan.

### 4.3 User Control and Freedom

**Status: Cukup**

Implementasi yang mendukung:

- User dapat menghentikan respons melalui tombol `Stop`.
- User dapat membuat chat baru, memuat sesi lama, menghapus sesi, dan mengganti nama sesi.
- User dapat `Regenerate` dan `Edit & retry` jawaban.
- Pada dokumen, user dapat membatalkan preview dan membersihkan file terpilih.
- Logout tersedia di header.

Masalah:

- Aksi hapus sesi/dokumen/chunk berpotensi destruktif dan perlu konfirmasi jelas.
- Tidak semua aksi role-based disembunyikan dari user yang tidak berhak.
- Belum ada undo untuk penghapusan sesi atau dokumen.

Rekomendasi:

1. Tambahkan dialog konfirmasi untuk hapus sesi, hapus dokumen, hapus chunk, dan clear chat.
2. Tampilkan action sesuai role agar user tidak mencoba tindakan yang akan ditolak backend.
3. Pertimbangkan soft-delete atau undo untuk sesi/dokumen.

### 4.4 Consistency and Standards

**Status: Cukup**

Implementasi yang mendukung:

- Header konsisten di halaman chat dan dokumen.
- Navigasi utama konsisten: Beranda, Chat, Dokumen, Keluar.
- Komponen chat memakai pola konsisten: bubble user, bubble AI, source card, citation popup.
- Upload dokumen memakai stepper yang konsisten dengan alur kerja.

Masalah:

- Frontend route guard hanya mengecek login, bukan role. Backend membatasi beberapa endpoint admin, tetapi frontend tetap menampilkan halaman/aksi dokumen untuk semua user login.
- Backend upload hanya menerima PDF, sementara frontend menyatakan mendukung PDF, DOC, DOCX. Ini inkonsistensi penting:
  - frontend validation menerima `.pdf`, `.doc`, `.docx`.
  - backend `/documents/upload` menolak selain `.pdf` dengan pesan `Hanya file PDF yang didukung`.
- Beberapa label masih campuran teknis dan user-facing.

Rekomendasi:

1. Samakan frontend dan backend terkait format upload: pilih PDF-only atau benar-benar dukung DOC/DOCX.
2. Tambahkan meta `requiredRoles` pada router frontend.
3. Standardisasi label teknis menjadi bahasa domain pengguna.

### 4.5 Error Prevention

**Status: Cukup**

Implementasi yang mendukung:

- Tombol kirim disabled jika input kosong.
- Input disabled saat sistem sedang loading.
- Upload memvalidasi ukuran maksimal 50 MB.
- Upload memvalidasi ekstensi file.
- Nama file dengan karakter tidak umum diberi warning dan saran nama file.

Masalah:

- Karena frontend menerima DOC/DOCX tapi backend menolak, user bisa tetap mengalami error yang seharusnya dicegah dari awal.
- User non-admin masih dapat melihat/mencoba aksi yang membutuhkan admin.
- Belum ada validasi khusus untuk pertanyaan terlalu panjang, kosong setelah normalisasi ekstrem, atau pertanyaan di luar domain.

Rekomendasi:

1. Sesuaikan validasi upload dengan backend.
2. Sembunyikan/disable aksi admin untuk role non-admin.
3. Tambahkan guard input untuk pertanyaan sangat panjang dan beri saran mempersempit pertanyaan.

### 4.6 Recognition Rather Than Recall

**Status: Baik**

Implementasi yang mendukung:

- Welcome screen menyediakan contoh pertanyaan.
- Sidebar menyimpan daftar sesi dan mengelompokkan sesi berdasarkan waktu.
- Judul sesi dapat dibuat otomatis dari pesan pertama.
- Source cards menampilkan sumber jawaban.
- Citation popup membantu melihat rujukan tanpa harus mengingat dokumen.
- Input hint menjelaskan `Enter untuk kirim · Shift+Enter untuk baris baru`.

Masalah:

- Belum ada pencarian sesi atau dokumen di UI.
- Belum ada daftar pertanyaan populer atau template prompt untuk tugas umum.
- Belum ada breadcrumb detail dokumen yang kuat untuk membantu orientasi saat membuka chunk panjang.

Rekomendasi:

1. Tambahkan pencarian sesi dan filter dokumen.
2. Tambahkan prompt template: definisi, pasal, perbandingan, ringkasan dokumen, audit keamanan.
3. Tambahkan breadcrumb pada halaman detail dokumen.

### 4.7 Flexibility and Efficiency of Use

**Status: Cukup**

Implementasi yang mendukung:

- Enter mengirim pesan; Shift+Enter membuat baris baru.
- User dapat toggle RAG.
- User dapat memilih model dan admin dapat mengubah default model lewat backend.
- User dapat regenerate dan edit & retry.
- User dapat copy jawaban.
- User dapat mengelola sesi.

Masalah:

- Belum ada shortcut keyboard selain input chat.
- Belum ada command palette atau pencarian cepat.
- Belum ada mode advanced yang menjelaskan parameter seperti `top_k`, model, atau RAG toggle.
- Alur pengujian KLM untuk pertanyaan panjang masih dapat memakan waktu karena user harus mengetik manual dan menunggu retrieval/LLM tanpa estimasi.

Rekomendasi:

1. Tambahkan template prompt dan history prompt.
2. Tambahkan shortcut: `/` fokus input, `Ctrl+K` cari sesi/dokumen, `Esc` stop generation.
3. Tambahkan opsi advanced yang tersembunyi untuk parameter teknis.

### 4.8 Aesthetic and Minimalist Design

**Status: Baik**

Implementasi yang mendukung:

- Layout chat bersih: sidebar, area pesan, input bawah.
- Header menampilkan navigasi utama, akun, role, dan status koneksi.
- Source cards dan citation popup tidak langsung memenuhi layar sebelum dibutuhkan.
- Upload dokumen menggunakan stepper dan card, sehingga alur terlihat jelas.

Masalah:

- Pada halaman dokumen, preview chunk panjang dapat membuat UI padat.
- Source cards yang banyak dapat memperpanjang jawaban.
- Label teknis seperti Qdrant dan chunk dapat mengganggu minimalisme untuk user non-teknis.

Rekomendasi:

1. Gunakan collapse/expand untuk source cards dan chunk preview panjang.
2. Tampilkan ringkasan sumber terlebih dahulu, detail dibuka saat diklik.
3. Kurangi istilah teknis di label utama.

### 4.9 Help Users Recognize, Diagnose, and Recover from Errors

**Status: Cukup**

Implementasi yang mendukung:

- Login test mencakup tampilan error saat login gagal.
- Chat menampilkan error saat event SSE error atau request gagal.
- API client menangani token expired dan redirect ke login dengan pesan sesi berakhir.
- Upload dan dokumen menampilkan toast error.
- Copy action memberi feedback `Tersalin` atau `Gagal`.

Masalah:

- Pesan error chat masih umum: `Pastikan server backend berjalan` meskipun penyebab bisa permission, model, database, timeout, atau token.
- Error permission backend dapat muncul sebagai pesan teknis `Operation not permitted. Required roles: [...]`.
- Belum ada rekomendasi langkah pemulihan yang spesifik per error.

Rekomendasi:

1. Map error backend menjadi pesan user-facing:
   - 401: sesi berakhir, login ulang.
   - 403: akun tidak memiliki izin; hubungi admin.
   - 429: terlalu banyak request; tunggu beberapa saat.
   - 503: model/layanan AI belum tersedia.
   - timeout: proses lama; coba ulang atau sederhanakan pertanyaan.
2. Tambahkan tombol aksi pemulihan: `Coba lagi`, `Login ulang`, `Hubungi Admin`, atau `Lihat status sistem`.

### 4.10 Help and Documentation

**Status: Perlu Perbaikan**

Implementasi yang mendukung:

- Ada hint penggunaan input chat.
- Ada label dan status pada upload dokumen.
- Ada source citation yang membantu kepercayaan jawaban.

Masalah:

- Belum ada halaman bantuan pengguna.
- Belum ada dokumentasi singkat tentang cara bertanya yang efektif.
- Belum ada penjelasan RAG aktif/nonaktif.
- Belum ada dokumentasi role dan hak akses.
- Belum ada panduan upload/preview/index dokumen di UI.

Rekomendasi:

1. Tambahkan halaman `Bantuan` atau panel onboarding.
2. Tambahkan dokumentasi ringkas:
   - Cara bertanya tentang pasal/ayat.
   - Cara membaca sumber dan sitasi.
   - Kapan RAG harus aktif.
   - Perbedaan role Admin PUSDATIK, Evaluator SPBE, Staf PUSDATIK, dan Manager Evaluasi.
   - Cara upload dan indeks dokumen.
3. Tambahkan tooltip pada istilah teknis.

## 5. Analisis KLM: Waktu Interaksi Panjang

KLM pada konteks laporan ini dipakai untuk mengidentifikasi alur yang berpotensi memerlukan banyak aksi, banyak keputusan, atau waktu tunggu panjang. Karena belum dilakukan observasi stopwatch terhadap pengguna nyata, analisis ini bersifat evaluasi awal berbasis alur UI.

### 5.1 Alur Chat Pertanyaan Panjang

Alur umum:

1. User memilih halaman Chat.
2. User mengetik pertanyaan panjang.
3. User memastikan RAG aktif/nonaktif.
4. User menekan Enter/kirim.
5. Sistem mencari dokumen.
6. Sistem streaming jawaban.
7. User membaca jawaban dan sumber.
8. User membuka citation/source bila perlu.
9. Jika tidak puas, user memilih regenerate atau edit & retry.

Potensi waktu panjang:

- Mengetik pertanyaan panjang secara manual.
- Menunggu retrieval dan LLM.
- Membuka banyak sumber satu per satu.
- Mengulang pertanyaan karena hasil belum sesuai.

Perbaikan KLM:

- Tambahkan template prompt.
- Tambahkan saran pertanyaan lanjutan.
- Tambahkan ringkasan sumber utama.
- Tambahkan status proses yang lebih rinci agar waktu tunggu terasa terkendali.

### 5.2 Alur Manajemen Dokumen

Alur umum:

1. User membuka halaman Dokumen.
2. User memilih atau drag file.
3. Sistem validasi file.
4. User klik Unggah Dokumen.
5. User menunggu upload.
6. User klik Pratinjau Chunks.
7. User membaca chunk.
8. User klik Simpan ke Indeks.
9. User menunggu indexing.

Potensi waktu panjang:

- Preview chunk panjang membuat scanning lama.
- Jika format file frontend/backend tidak sinkron, user membuang waktu mencoba file yang ditolak.
- Jika user bukan admin, user dapat masuk alur tapi gagal pada aksi yang membutuhkan role admin.

Perbaikan KLM:

- Samakan validasi format frontend/backend.
- Sembunyikan upload/index/delete untuk non-admin.
- Tambahkan ringkasan preview: jumlah chunk, jenis dokumen, pasal utama, estimasi waktu indexing.
- Tambahkan pencarian/filter dalam preview chunk.

## 6. Prioritas Rekomendasi Perbaikan

| Prioritas | Rekomendasi | Alasan |
|---|---|---|
| Tinggi | Tambahkan role-based route/action guard di frontend | Backend sudah role-based, tetapi UI belum. Ini mencegah error dan mengurangi waktu interaksi sia-sia. |
| Tinggi | Samakan dukungan format upload frontend/backend | Saat ini frontend menerima DOC/DOCX, backend upload hanya PDF. Ini inkonsistensi langsung. |
| Tinggi | Perbaiki pesan error berdasarkan kode status | Membantu user memahami dan memulihkan error. |
| Sedang | Tambahkan halaman/panel bantuan | Saat ini help/documentation masih lemah. |
| Sedang | Tambahkan tooltip istilah teknis | Mengurangi beban kognitif pengguna non-teknis. |
| Sedang | Tambahkan pencarian sesi/dokumen dan template prompt | Mengurangi waktu interaksi panjang pada KLM. |
| Rendah | Tambahkan shortcut lanjutan | Meningkatkan efisiensi pengguna mahir. |

## 7. Kesimpulan

1. Aplikasi saat ini **bukan hanya memiliki role Admin PUSDATIK**. Backend sudah mengenal beberapa role: `admin_pusdatik`, `staf_pusdatik`, `evaluator_spbe`, dan `manager_evaluasi`.
2. Namun dari sisi pengalaman pengguna, role yang paling nyata tampak di UI adalah label role pada header. Frontend belum menerapkan pembatasan menu/aksi berbasis role secara menyeluruh.
3. Usability aplikasi secara umum sudah cukup baik untuk chat RAG: ada status loading, streaming, source citation, session history, regenerate, edit & retry, dan upload stepper.
4. Masalah utama saat ini adalah inkonsistensi role frontend-backend, inkonsistensi format upload, pesan error yang masih generik, dan belum adanya dokumentasi bantuan pengguna.
5. Untuk pengujian KLM waktu interaksi panjang, alur yang perlu diprioritaskan adalah chat pertanyaan panjang dan manajemen dokumen, karena keduanya mengandung banyak aksi, waktu tunggu, dan potensi pengulangan.
