# Plan Perbaikan Parser Dokumen SPBE RAG
**Tanggal:** 2026-04-14  
**Tujuan:** Memperbaiki parsing Permenpan RB Nomor 5 Tahun 2020 (10 chunks) dan SE Menteri PAN-RB Nomor 18 Tahun 2022 (9 chunks) agar seluruh konten substantif terparsing dan dapat diambil oleh RAG.

---

## 1. Latar Belakang

Dari hasil benchmark pengujian RAG dengan 6 pertanyaan, ditemukan bahwa dua dokumen menghasilkan jawaban "tidak ditemukan dalam dokumen" meskipun Sources-nya muncul benar. Akar masalahnya terbukti bukan pada retrieval, melainkan pada fase **parsing & chunking**:

| Dokumen | Jumlah Chunk | Masalah |
|---|---|---|
| Permenpan RB Nomor 5 Tahun 2020.pdf | **10 chunks** | Lampiran Pedoman Manajemen Risiko (40+ halaman) tidak masuk |
| SE Menteri PAN-RB Nomor 18 Tahun 2022.pdf | **9 chunks** | Konten isi SE terputus-putus karena format surat tidak terdeteksi dengan benar |

### Dokumen pembanding (sudah baik):
- Pedoman 3/2024 → 254 chunks (kompleksitas serupa tapi terparse lengkap)
- BSSN 8/2024 → 150 chunks
- Laporan Evaluasi SPBE 2024 → 424 chunks

---

## 2. Mekanisme Parser yang Berjalan Sekarang

### 2.1 Alur Pipeline (4 Tahap)

```
PDF File
   │
   ▼
[STEP 1] PDF → Text (pdf_processor.py > _convert_pdf_to_text)
   │  Metode: Marker (GPU) → pdfplumber → PyMuPDF → PyPDF2
   │  Output: string teks mentah
   │
   ▼
[STEP 2] Text → Structured JSON (json_structure_parser.py > parse_document)
   │  Deteksi tipe dokumen → dispatch ke parser yang sesuai:
   │    - "peraturan"      → parse_peraturan()
   │    - "laporan_spbe"   → parse_laporan_spbe()
   │    - "pedoman_spbe"   → parse_pedoman()
   │    - "laporan"        → parse_laporan()
   │
   ▼
[STEP 3] JSON → 600-char Chunks (structured_chunker.py > chunk_document)
   │  Dispatch ke chunker yang sesuai dengan tipe:
   │    - "peraturan"      → chunk_peraturan()
   │    - "pedoman_spbe"   → chunk_pedoman()
   │    - "laporan"        → chunk_laporan()
   │
   ▼
[STEP 4] Chunks → Database + Qdrant + BM25 Index
```

### 2.2 Bagaimana Tipe Dokumen Dideteksi (`detect_doc_type`)

Fungsi `detect_doc_type()` di `json_structure_parser.py` mendeteksi tipe dari nama file dan 2000 karakter pertama:

1. **"pedoman_spbe"**: jika nama file mengandung `pedoman`, `aparatur`, dan `reformasi`
2. **"laporan_spbe"**: jika nama file mengandung `evaluasi spbe`
3. Jika ada `folder_hint` dari saat upload, digunakan sebagai tipe langsung
4. **"peraturan"**: jika nama file mengandung `perpres`, `permen`, `peraturan`, `bssn`, `pp_`
5. **"laporan"**: fallback terakhir

### 2.3 Intermediate Representation: JSON Output

Sebelum proses sudah ada cache JSON di `data/json_output/`. Ini berasal **dari proses ingest sebelumnya**, bukan dari alur saat ini. Alur aktif sekarang (`pdf_processor.py`) **langsung** mengolah text → JSON **tanpa menyimpan** hasil JSON ke file.

---

## 3. Analisis Kekurangan & Kelebihan Parser Saat Ini

### ✅ Kelebihan

| Komponen | Kelebihan |
|---|---|
| **Ekstraksi PDF** | Pipeline berlapis 4 metode (Marker → pdfplumber → PyMuPDF → PyPDF2), sangat robust terhadap PDF bermasalah |
| **Tipe parser spesifik** | Ada parser khusus untuk `peraturan`, `laporan_spbe` (dengan parsing skor per instansi), `pedoman_spbe` (dengan parsing Indikator 1-47) |
| **Chunker struktural** | Chunk per Ayat/Pasal dengan hierarki metadata lengkap (bab → bagian → pasal → ayat) |
| **Linearisasi tabel** | Tabel Markdown diubah menjadi teks `Header: Value` sehingga bisa di-embed dan dicari |
| **BM25 + Vector hybrid** | Setiap chunk memiliki teks BM25 yang diperkaya dari metadata struktural |
| **Caching Marker** | Hasil konversi Marker disimpan ke `.md` file, sehingga re-ingest tidak perlu reconvert |

### ❌ Kekurangan (Yang Menyebabkan Masalah Kini)

#### A. `parse_peraturan()` — Tidak Memproses Lampiran Berisi Teks Substantif

**Masalah:** Untuk `Permenpan RB 5/2020`, fungsi `parse_peraturan()` hanya memproses bagian `batang_tubuh` (Pasal 1-5). Lampiran dokumen ini berisi **Pedoman Manajemen Risiko SPBE** — dokumen panjang 40+ halaman yang adalah inti dari peraturan tersebut.

Di kode `json_structure_parser.py`, lampiran diekstraksi dengan pola:
```python
lampiran_match = re.search(
    r"LAMPIRAN\s+PERATURAN.*?(?=LAMPIRAN\s+PERATURAN|\Z)",
    text, re.DOTALL | re.IGNORECASE | re.MULTILINE
)
```

Namun field yang diisi hanya `kuesioner_indikator` (format Domain/Aspek/Indikator yang spesifik untuk Pedoman kuesioner). Untuk lampiran berbentuk **naratif dan tabel** seperti Permenpan 5/2020 (yang berisi metodologi manajemen risiko, tabel kategori risiko, dll.), seluruh isi dibuang karena tidak cocok format kuesioner.

**Bukti:** Di `data/json_output/Permenpan RB Nomor 5 Tahun 2020.json`:
```json
"lampiran": {
    "judul_lampiran": "LAMPIRAN",
    "kuesioner_indikator": []  ← KOSONG!
}
```

#### B. `parse_surat_edaran()` vs `parse_peraturan()` — Routing Salah

**Masalah:** File `SE Menteri PAN-RB Nomor 18 Tahun 2022.pdf` berisi nama file yang mengandung `se` di depannya. Fungsi `detect_doc_type()` cocok dengan kondisi `"peraturan"` (melalui pattern `permen`), bukan ke `parse_surat_edaran()` yang sudah tersedia di kode.

Akibatnya, SE diparsing oleh `parse_peraturan()` yang mencari `Pasal X`. Karena SE tidak memiliki `Pasal` (menggunakan format huruf `a. b. c.`), hasilnya adalah dokumen tanpa struktur, dan sebagian besar teks isi diabaikan.

**Bukti:** `parse_surat_edaran()` sudah ada di `json_structure_parser.py` baris 254 namun **tidak pernah dipanggil** dari `parse_document()`. Fungsi ini sudah dipersiapkan tapi tidak terhubung ke dispatcher utama.

#### C. Metadata Salah pada JSON Output Permenpan 5/2020

Dari inspeksi `json_output/Permenpan RB Nomor 5 Tahun 2020.json`:
```json
"metadata_dokumen": {
    "jenis_peraturan": "(5) Peraturan Presiden Nomor 95 Tahun 2018 tentang",
    "nomor": "95",
    "tahun": "2018",
    "tentang": "PEDOMAN MANAJEMEN RISIKO"
}
```

Parser mengekstrak metadata yang salah — teridentifikasi sebagai `Perpres 95/2018` padahal seharusnya `Permenpan 5/2020`. Ini menyebabkan UI menampilkan judul dokumen yang keliru.

#### D. Tidak Ada Penyimpanan JSON Intermediate secara Otomatis

Pipeline saat ini **tidak menyimpan JSON ke disk** otomatis (vs. proses lama yang menyimpan ke `data/json_output/`). Ini mempersulit debugging karena kita tidak bisa dengan mudah melihat hasil parsing setiap dokumen tanpa menjalankan ulang.

---

## 4. Rencana Perbaikan (Fase-Fase)

### FASE 1: Fix Routing SE ke `parse_surat_edaran()` *(Prioritas Tinggi)*

**File:** `backend/app/core/ingestion/json_structure_parser.py`  
**Fungsi:** `detect_doc_type()` dan `parse_document()`

**Perubahan:**
1. Tambah kondisi deteksi SE di `detect_doc_type()`:
   ```python
   # Sebelum cek peraturan:
   if re.search(r"\bse[\s_-]?\w+|surat.edaran", lower_name):
       return "surat_edaran"
   ```
2. Tambah dispatch ke `parse_surat_edaran()` di `parse_document()`:
   ```python
   elif dtype == "surat_edaran":
       result = parse_surat_edaran(cleaned, metadata_dokumen, filename)
   ```
3. Tambah chunker untuk `surat_edaran` di `structured_chunker.py` — atau re-use `chunk_laporan()` dengan enrichment field SE.

**Ekspektasi:** SE 18/2022 akan naik dari 9 chunks menjadi ~30-50 chunks dengan struktur yang tepat.

---

### FASE 2: Fix Lampiran Naratif Permenpan 5/2020 *(Prioritas Tinggi)*

**File:** `backend/app/core/ingestion/json_structure_parser.py`  
**Fungsi:** `parse_peraturan()` → blok lampiran

**Perubahan:**
1. Setelah mencoba `parse_spbe_lampiran()` (kuesioner), tambah fallback untuk lampiran naratif:
   ```python
   if not lampiran_data["kuesioner_indikator"]:
       # Fallback: simpan teks lampiran sebagai blok naratif
       lampiran_data["isi_naratif"] = lampiran_text.strip()
   ```
2. Update `structured_chunker.py` → `chunk_peraturan()` → blok lampiran:
   ```python
   # Jika bukan kuesioner, chunk lampiran sebagai laporan biasa
   elif "isi_naratif" in lampiran:
       for piece in split_text_with_overlap(lampiran["isi_naratif"]):
           chunks.append({...})
   ```

**Ekspektasi:** Permenpan 5/2020 akan naik dari 10 chunks menjadi ~60-100 chunks (mencakup seluruh Pedoman Manajemen Risiko).

---

### FASE 3: Fix Metadata Ekstraksi Permenpan 5/2020 *(Prioritas Sedang)*

**File:** `backend/app/core/ingestion/json_structure_parser.py`  
**Fungsi:** `parse_peraturan()` → blok metadata (`metadata_dokumen`)

**Masalah saat ini:** Regex nomor/tahun menangkap kata "95" dari kalimat "Pasal 47 ayat (5) Peraturan Presiden Nomor 95 Tahun 2018" di bagian Menimbang, bukan dari judul utama peraturan.

**Perubahan:**
- Perkuat regex ekstraksi metadata agar mencari dari 300 karakter pertama (judul), bukan dari seluruh teks `Menimbang`:
  ```python
  # Scan judul terlebih dahulu
  header_text = text[:500]
  m_nomor = re.search(r"NOMOR\s+(\d+)\s+TAHUN\s+(\d+)", header_text, re.IGNORECASE)
  ```

**Ekspektasi:** UI akan menampilkan `Permenpan 5 Tahun 2020` bukan `Perpres 95 Tahun 2018`.

---

### FASE 4: Aktifkan Penyimpanan JSON Intermediate Otomatis *(Prioritas Rendah)*

**File:** `backend/app/core/ingestion/pdf_processor.py`

**Perubahan:**
- Setelah `parse_document()`, simpan JSON ke `data/json_output/<filename>.json` untuk setiap dokumen yang berhasil diparsing.
- Ini memungkinkan debugging parser dengan membuka file.

---

## 5. Urutan Pekerjaan & Prioritas

| # | Perbaikan | File | Dampak | Estimasi |
|---|---|---|---|---|
| 1 | Fix routing SE ke `parse_surat_edaran` | `json_structure_parser.py` | SE 18/2022: +30 chunks | 1-2 jam |
| 2 | Fix lampiran naratif Permenpan 5/2020 | `json_structure_parser.py`, `structured_chunker.py` | Permenpan: +50 chunks | 2-3 jam |
| 3 | Fix metadata nomor/tahun peraturan | `json_structure_parser.py` | UI title akurat | 30 menit |
| 4 | Aktifkan simpan JSON intermediate | `pdf_processor.py` | Debug lebih mudah | 30 menit |
| 5 | Re-ingest kedua dokumen | Script/UI | Verifikasi semua fix | 30 menit |
| 6 | Benchmark ulang 6 pertanyaan | Browser | Validasi hasil | 30 menit |

---

## 6. Verifikasi Pasca-Perbaikan

Setelah perbaikan selesai, benchmark dengan pertanyaan berikut yang sebelumnya gagal:

1. **SE 18/2022:** *"Apa isi Surat Edaran Menteri PAN-RB Nomor 18 Tahun 2022 tentang kewajiban penggunaan aplikasi?"*
   - Target: Jawaban berisi penjelasan keterpaduan layanan digital dan kewajiban penyusunan Arsitektur SPBE sebelum Desember 2022

2. **Permenpan 5/2020:** *"Jelaskan ruang lingkup penerapan Permenpan RB Nomor 5 Tahun 2020 dan siapa saja yang wajib menerapkannya?"*
   - Target: Jawaban berisi penjelasan Manajemen Risiko SPBE untuk Instansi Pusat dan Pemerintah Daerah

3. **Permenpan 5/2020:** *"Apa saja kategori risiko dalam Manajemen Risiko SPBE?"*
   - Target: Jawaban berisi tabel/daftar kategori risiko dari lampiran pedoman

---

## 7. Catatan Teknis Penting

### Format SE yang Tidak Memiliki "Pasal"
SE menggunakan format `a. ... b. ... c. ...` bukan `Pasal X`. Parser yang benar (`parse_surat_edaran`) telah dibuat dengan logika ini namun belum terhubung ke dispatcher.

### Lampiran Permenpan 5/2020 Berformat Naratif
Bukan matriks kuesioner seperti Pedoman 3/2024. Isinya meliputi:
- Bab I: Pendahuluan Manajemen Risiko
- Bab II: Proses Manajemen Risiko (identifikasi, analisis, evaluasi, mitigasi)
- Tabel-tabel kategori risiko, likelihood, impact
- Lampiran Form pengisian

Ini **harus** diparsing sebagai laporan biasa, bukan kuesioner indikator.

### Backward Compatibility
Semua perubahan bersifat **additive** — hanya menambah kondisi/fallback, tidak mengubah logika yang sudah benar untuk Perpres 95, PP 71, BSSN 8, Permenpan 59, Perpres 82, dan Pedoman 3.
