# Plan: Hybrid MD + JSON Parser untuk SPBE RAG
**Tanggal:** 2026-04-14  
**Versi:** 2.0 (revisi dari Plan 15 — mengganti pendekatan fix-JSON ke hybrid MD fallback)

---

## 1. Latar Belakang & Insight Kritis

### 1.1 Temuan Utama

Dari inspeksi langsung file Marker Output di `backend/data/marker_output/`:

| Dokumen | Ukuran MD | Baris | Status Parser JSON |
|---|---|---|---|
| `SE Menteri PAN-RB Nomor 18 Tahun 2022.md` | **236 KB** | 1.714 | 9 chunks (95% konten hilang) |
| `Permenpan RB Nomor 5 Tahun 2020.md` | **101 KB** | 1.249 | 10 chunks (lampiran 90KB dibuang) |

**Marker sudah berhasil mengekstrak SELURUH konten** dari kedua dokumen ini dengan sempurna. Masalahnya **bukan di konversi PDF** — konten ada, tapi **parser JSON membuangnya**.

### 1.2 Mengapa JSON Parser Gagal (Root Cause)

**Kasus Permenpan 5/2020:**
```
MD (101KB) → parse_peraturan() → JSON
  └─ batang_tubuh: [Pasal 1-6] ← 5KB (tersimpan)
  └─ lampiran.kuesioner_indikator: [] ← KOSONG (90KB Pedoman dibuang)
  
Sebab: Parser lampiran hanya mengenal format "Domain/Aspek/Indikator"
       Lampiran pedoman ini berformat naratif BAB I-V + tabel
```

**Kasus SE 18/2022:**
```
MD (236KB) → detect_doc_type() → "peraturan" → parse_peraturan()
  └─ Mencari "Pasal X"... tidak ditemukan (SE pakai "1. 2. 3. a. b. c.")
  └─ Sebagian besar teks diabaikan → 9 chunks
  
Sebab: parse_surat_edaran() sudah ada di kode tapi tidak pernah dipanggil
       dari parse_document() dispatcher
```

### 1.3 Mengapa Pendekatan Hybrid (Bukan Ganti Total)

| | Refactor Total ke MD | Fix JSON Parser | **Hybrid (Rekomendasi)** |
|---|---|---|---|
| Risiko merusak dokumen lain | Tinggi | Rendah | **Nol** |
| Kompleksitas | Tinggi | Sedang | **Rendah** |
| Waktu implementasi | 2-3 hari | 4-6 jam | **2-3 jam** |
| Metadata hierarki (Bab/Pasal/Ayat) | ❌ Hilang | ✅ Tetap | **✅ Tetap untuk yang sudah baik** |
| Menyelamatkan konten hilang | ✅ | ✅ | **✅** |

**Prinsip Hybrid:** Jika `chunk_document()` menghasilkan kurang dari `MIN_CHUNKS_THRESHOLD` (misal 20), dan file `.md` dari Marker tersedia di cache → gunakan **MD-based chunker** sebagai fallback.

---

## 2. Arsitektur Solusi

### 2.1 Alur Pipeline Baru

```
PDF File
   |
   ▼
[STEP 1] PDF → Markdown (marker_converter.py)
   | Disimpan ke: backend/data/marker_output/<stem>/<stem>.md
   |
   ▼
[STEP 2] Text → Structured JSON (json_structure_parser.py)
   | parse_document() → dispatch sesuai tipe → doc_structure (JSON)
   |
   ▼
[STEP 3A] JSON → Chunks (structured_chunker.py) [EXISTING]
   | hasil: N chunks
   |
   ▼
[STEP 3B] Fallback Check ← NEW
   | if len(chunks) < MIN_THRESHOLD (20) AND md_file_path exists:
   |   → chunk_from_markdown(md_path, filename, doc_title)
   |
   ▼
[STEP 4] Chunks → Database + Qdrant + BM25
```

### 2.2 Fungsi Baru: `chunk_from_markdown()`

Chunker berbasis heading Markdown yang akan dibuat di `structured_chunker.py`:

```python
def chunk_from_markdown(md_text: str, filename: str, doc_title: str) -> List[Dict]:
    """
    Fallback chunker: chunk dokumen langsung dari Markdown Marker output.
    Memecah berdasarkan heading (#, ##, ###) dan paragraf.
    Digunakan ketika JSON parser menghasilkan terlalu sedikit chunk.
    """
```

**Logika chunking MD:**
1. Split teks berdasarkan heading `#`, `##`, `###`, `####`
2. Setiap section heading menjadi konteks (hierarchy) untuk chunk-chunk di bawahnya
3. Teks di bawah heading dipecah dengan `split_text_with_overlap()` (max 600 chars)
4. Baris image `![]()` dan span HTML `<span id=...>` dibuang (noise dari Marker)
5. Tabel Markdown dilinearisasi menjadi pasangan `Kolom: Nilai`

**Metadata yang dihasilkan:**
```python
{
    "doc_type": "md_fallback",   
    "judul_dokumen": doc_title,
    "filename": filename,
    "section": heading_teks,      # H1/H2/H3 terdekat
    "hierarchy": "Judul > H1 > H2 > H3",
    "bab": detected_bab,          # deteksi "BAB I", "BAB II", dll.
    "bagian": detected_bagian,    # sub-section berdasarkan heading
    "pasal": "",
    "ayat": "",
}
```

---

## 3. File yang Dimodifikasi

### 3.1 `backend/app/core/ingestion/structured_chunker.py` ← MODIFY

**Penambahan:**

```python
# TAMBAH di bagian atas (imports):
from pathlib import Path
import re

# TAMBAH fungsi baru sebelum chunk_document():
MIN_JSON_CHUNKS_THRESHOLD = 20   # Jika JSON menghasilkan < 20 chunk, trigger MD fallback

def _clean_marker_noise(text: str) -> str:
    """Buang artefak Marker: image tags, span tags, nomor halaman."""
    text = re.sub(r'!\[.*?\]\(.*?\)', '', text)           # ![]()
    text = re.sub(r'<span[^>]*>.*?</span>', '', text)     # <span>
    text = re.sub(r'\*\*\d+\*\*\s*$', '', text, flags=re.MULTILINE)  # **12**
    return text.strip()

def _linearize_md_table(table_text: str) -> str:
    """Konversi tabel Markdown ke pasangan 'Header: Nilai'."""
    lines = [l.strip() for l in table_text.strip().split('\n') 
             if l.strip() and not re.match(r'^[\|\-\s]+$', l.strip())]
    if len(lines) < 2:
        return table_text
    headers = [h.strip() for h in lines[0].split('|') if h.strip()]
    result = []
    for row_line in lines[1:]:
        cells = [c.strip() for c in row_line.split('|') if c.strip()]
        row_text = '; '.join(
            f"{headers[i]}: {cells[i]}" 
            for i in range(min(len(headers), len(cells)))
        )
        if row_text:
            result.append(row_text)
    return '\n'.join(result)

def chunk_from_markdown(
    md_text: str, 
    filename: str, 
    doc_title: str
) -> List[Dict[str, Any]]:
    """
    Fallback MD-based chunker untuk dokumen yang gagal di JSON parser.
    Memecah berdasarkan heading Markdown dan menghasilkan chunk ≤ 600 chars.
    """
    chunks = []
    md_text = _clean_marker_noise(md_text)
    
    # Regex untuk heading level 1-4
    heading_pattern = re.compile(r'^(#{1,4})\s+(.+)$', re.MULTILINE)
    
    # Split dokumen berdasarkan heading
    splits = re.split(r'(?m)^(#{1,4}\s+.+)$', md_text)
    
    current_h1 = current_h2 = current_h3 = ""
    bab_pattern = re.compile(r'BAB\s+([IVXLCDM]+)', re.IGNORECASE)
    
    i = 0
    while i < len(splits):
        segment = splits[i].strip()
        if not segment:
            i += 1
            continue
        
        # Cek apakah ini heading
        m = heading_pattern.match(segment)
        if m:
            level = len(m.group(1))
            heading_text = m.group(2).strip()
            # Bersihkan bold: **text** → text
            heading_text = re.sub(r'\*\*(.+?)\*\*', r'\1', heading_text)
            
            if level == 1:
                current_h1 = heading_text
                current_h2 = current_h3 = ""
            elif level == 2:
                current_h2 = heading_text
                current_h3 = ""
            elif level == 3:
                current_h3 = heading_text
            # H4 tidak update current context
            
            i += 1
            continue
        
        # Ini konten (bukan heading) — chunk isi di bawah heading saat ini
        # Deteksi BAB dari heading aktif
        bab = ""
        for h_text in [current_h1, current_h2]:
            bm = bab_pattern.search(h_text)
            if bm:
                bab = f"BAB {bm.group(1)}"
                break
        
        # Susun hierarchy
        h_parts = [p for p in [doc_title, current_h1, current_h2, current_h3] if p]
        hierarchy = " > ".join(h_parts)
        section = current_h3 or current_h2 or current_h1 or ""
        
        meta = {
            "doc_type": "md_fallback",
            "judul_dokumen": doc_title,
            "filename": filename,
            "section": section,
            "hierarchy": hierarchy,
            "bab": bab,
            "bagian": current_h2 or current_h1,
            "pasal": "",
            "ayat": "",
        }
        
        # Proses tabel dalam konten
        content = segment
        # Linearisasi tabel Markdown
        table_pattern = re.compile(r'(\|.+\|[\s\S]*?)(?=\n\n|\Z)', re.MULTILINE)
        content = table_pattern.sub(
            lambda m: _linearize_md_table(m.group(0)), content
        )
        
        # Chunk konten
        append_chunk_with_limit(chunks, content, meta)
        i += 1
    
    return chunks
```

**Modifikasi `chunk_document()`:**

```python
def chunk_document(
    doc: Dict[str, Any], 
    md_file_path: str = None   # ← TAMBAH parameter
) -> List[Dict[str, Any]]:
    doc_type = doc.get("type", "laporan")

    if doc_type == "peraturan":
        chunks = chunk_peraturan(doc)
    elif doc_type == "laporan_spbe":
        chunks = chunk_laporan_spbe(doc)
    elif doc_type == "pedoman_spbe":
        chunks = chunk_pedoman_spbe(doc)
    else:
        chunks = chunk_laporan(doc)

    # ── HYBRID FALLBACK ── NEW
    if len(chunks) < MIN_JSON_CHUNKS_THRESHOLD and md_file_path:
        md_path = Path(md_file_path)
        if md_path.exists():
            logger.warning(
                f"JSON parser hanya menghasilkan {len(chunks)} chunks "
                f"(threshold: {MIN_JSON_CHUNKS_THRESHOLD}). "
                f"Beralih ke MD fallback chunker dari: {md_path.name}"
            )
            try:
                with open(md_path, "r", encoding="utf-8") as f:
                    md_text = f.read()
                doc_title = (
                    doc.get("metadata_dokumen", {}).get("tentang", "") or
                    doc.get("judul", "") or
                    Path(doc.get("source_filename", "")).stem
                )
                filename = doc.get("source_filename", "")
                md_chunks = chunk_from_markdown(md_text, filename, doc_title)
                if len(md_chunks) > len(chunks):
                    logger.success(
                        f"MD fallback menghasilkan {len(md_chunks)} chunks "
                        f"(vs {len(chunks)} dari JSON)"
                    )
                    chunks = md_chunks
            except Exception as e:
                logger.error(f"MD fallback gagal: {e}. Menggunakan JSON chunks.")
    # ── END HYBRID FALLBACK ──

    # ... (rest of existing filter & logging code unchanged)
```

---

### 3.2 `backend/app/core/ingestion/pdf_processor.py` ← MODIFY

**Lokasi:** Fungsi `DocumentProcessor.process_document()`, STEP 3

```python
# STEP 3: JSON → Chunks (≤600 chars) — DIMODIFIKASI
logger.info("STEP 3: Structured chunking (max 600 chars)...")

# Tentukan path MD dari Marker output (jika ada)
md_fallback_path = None
if markdown_path:
    md_fallback_path = markdown_path   # Marker sudah menyimpan path-nya
else:
    # Coba cari cache MD secara manual
    from app.core.ingestion.marker_converter import marker_converter
    stem = Path(filename).stem
    candidate = marker_converter.output_dir / stem / f"{stem}.md"
    if candidate.exists():
        md_fallback_path = str(candidate)

# ← PASS md_fallback_path ke chunk_document
chunks = chunk_document(doc_structure, md_file_path=md_fallback_path)
```

---

### 3.3 `backend/app/core/ingestion/marker_converter.py` ← MODIFY (minor)

**Masalah:** `convert()` mengembalikan `(text, md_path, used_marker)` tapi `md_path` adalah `None` ketika menggunakan cache. Pastikan cache path juga dikembalikan:

```python
# Di blok check cache (sekitar baris 354-363):
if not force_reconvert and output_md_path.exists():
    logger.info(f"Menggunakan cache Marker: {output_md_path}")
    with open(output_md_path, "r", encoding="utf-8") as f:
        result.text = f.read()
    result.success = True
    result.output_path = str(output_md_path)   # ← Sudah ada, pastikan tidak None
    result.method = "marker_cached"
    return result
```

Di `pdf_processor.py`, saat mengambil `markdown_path`:
```python
text, markdown_path, used_marker = marker_converter.convert(pdf_path, save_output=True)
# markdown_path sekarang selalu terisi (cache atau baru)
```

Cek apakah `convert()` mengembalikan `result.output_path` dengan benar untuk kasus cache.

---

## 4. Urutan Implementasi

| # | Langkah | File | Estimasi |
|---|---|---|---|
| 1 | Tambah `_clean_marker_noise()` & `_linearize_md_table()` | `structured_chunker.py` | 20 menit |
| 2 | Tambah `chunk_from_markdown()` | `structured_chunker.py` | 40 menit |
| 3 | Modifikasi `chunk_document()` — tambah param & fallback logic | `structured_chunker.py` | 20 menit |
| 4 | Pastikan `convert()` mengembalikan `output_path` dari cache | `marker_converter.py` | 10 menit |
| 5 | Modifikasi STEP 3 di `process_document()` — pass md_path | `pdf_processor.py` | 15 menit |
| 6 | Test lokal dengan script `check_chunks.py` (tanpa re-ingest) | Script | 15 menit |
| 7 | Re-ingest Permenpan 5/2020 dan SE 18/2022 dari UI | UI | 20 menit |
| 8 | Benchmark 6 pertanyaan dari Plan 15 | Browser | 20 menit |

**Total estimasi: ~2.5 jam**

---

## 5. Script Pengujian Lokal (Sebelum Re-ingest)

Buat script `backend/scripts/test_md_chunker.py` untuk validasi cepat tanpa menyentuh database:

```python
"""Test chunk_from_markdown() terhadap kedua file bermasalah."""
import sys
sys.path.insert(0, r"d:\aqil\pusdatik\backend")

from app.core.ingestion.structured_chunker import chunk_from_markdown

# Test SE 18/2022
md_path = r"d:\aqil\pusdatik\backend\data\marker_output\SE Menteri PAN-RB Nomor 18 Tahun 2022\SE Menteri PAN-RB Nomor 18 Tahun 2022.md"
with open(md_path, encoding="utf-8") as f:
    md_text = f.read()

chunks = chunk_from_markdown(md_text, "SE Menteri PAN-RB Nomor 18 Tahun 2022.pdf", "SE 18 Tahun 2022")
print(f"SE 18/2022: {len(chunks)} chunks")
for i, c in enumerate(chunks[:5]):
    print(f"  [{i}] hierarchy={c['metadata']['hierarchy'][:80]}")
    print(f"       text={c['text'][:100]}")

# Test Permenpan 5/2020
md_path2 = r"d:\aqil\pusdatik\backend\data\marker_output\1ffe96f1_Permenpan_RB_Nomor_5_Tahun_2020\1ffe96f1_Permenpan_RB_Nomor_5_Tahun_2020.md"
with open(md_path2, encoding="utf-8") as f:
    md_text2 = f.read()

chunks2 = chunk_from_markdown(md_text2, "Permenpan RB Nomor 5 Tahun 2020.pdf", "Permenpan 5 Tahun 2020")
print(f"\nPermenpan 5/2020: {len(chunks2)} chunks")
for i, c in enumerate(chunks2[:5]):
    print(f"  [{i}] section={c['metadata']['section'][:60]}")
    print(f"       text={c['text'][:100]}")
```

**Target hasil test:**
- SE 18/2022: > 50 chunks (vs. sebelumnya 9)
- Permenpan 5/2020: > 80 chunks (vs. sebelumnya 10)

---

## 6. Pertanyaan Benchmark Pasca-Implementasi

Setelah re-ingest, uji dengan pertanyaan berikut (sebelumnya gagal):

| Pertanyaan | Dokumen Target | Ekspektasi |
|---|---|---|
| "Apa tujuan SE 18/2022 tentang keterpaduan layanan digital?" | SE 18/2022 Bagian 2 | Jawaban tentang Arsitektur SPBE + deadline Desember 2022 |
| "Sebutkan isi edaran pada poin 5 SE 18/2022" | SE 18/2022 Bagian 5 | 6 poin kewajiban instansi (a-f) |
| "Apa itu Manajemen Risiko SPBE menurut Permenpan 5/2020?" | Permenpan 5/2020 Pasal 1 + BAB I | Definisi + tujuan |
| "Sebutkan 16 kategori Risiko SPBE" | Permenpan 5/2020 BAB III B.6 | Daftar a sampai p |
| "Apa itu level risiko dalam Permenpan 5/2020?" | Permenpan 5/2020 Tabel 10-11 | Sangat Rendah-Sangat Tinggi + rentang besaran |
| "Apa perbedaan Risiko SPBE Positif dan Negatif?" | Permenpan 5/2020 BAB III | Definisi + opsi penanganan berbeda |

---

## 7. Pertimbangan Teknis

### 7.1 Backward Compatibility
- Semua dokumen yang sudah bekerja baik (Perpres 95, BSSN 8, Pedoman 3/2024, Permenpan 59) **tidak terpengaruh** karena mereka sudah menghasilkan >20 chunks — fallback tidak akan aktif.
- Parameter `md_file_path` di `chunk_document()` bersifat **opsional** (default `None`), sehingga memanggil `chunk_document(doc)` tetap valid.

### 7.2 Deteksi Path MD dari Marker Cache
Marker menyimpan file di: `backend/data/marker_output/<stem>/<stem>.md`  
Namun `stem` bisa memiliki prefix hash (contoh: `1ffe96f1_Permenpan_RB_Nomor_5_Tahun_2020`).

**Solusi pencarian path MD:**
```python
def find_marker_cache(filename: str, output_dir: Path) -> Optional[Path]:
    """Cari file MD di marker_output folder, termasuk folder dengan prefix hash."""
    stem = Path(filename).stem
    # Exact match dulu
    exact = output_dir / stem / f"{stem}.md"
    if exact.exists():
        return exact
    # Cari folder yang mengandung nama file (dengan prefix hash)
    for folder in output_dir.iterdir():
        if folder.is_dir() and stem.lower() in folder.name.lower():
            candidate = folder / f"{folder.name}.md"
            if candidate.exists():
                return candidate
    return None
```

### 7.3 Ukuran Chunk MD vs JSON
File MD SE 18/2022 = 236KB. Dengan MAX_CHUNK_SIZE=600 dan teks rata-rata 400 char per heading section:
- Estimasi: ~180-250 chunks untuk SE 18/2022 (dokumen kompleks dengan banyak tabel)
- Target minimum: 50 chunks yang bermakna (setelah filter tabel noise dan gambar)

### 7.4 Linearisasi Tabel
Tabel dalam MD Marker menggunakan format `| col | col |` dengan baris separator `|---|---|`.
Perlu dilinearisasi agar tidak memenuhi satu chunk dengan separator yang tidak bermakna.

---

## 8. Tidak Perlu Dilakukan (Scope Reduction)

Dibandingkan Plan 15, **hal-hal ini TIDAK lagi diperlukan** karena sudah diatasi oleh hybrid approach:

- ~~Fix routing SE ke `parse_surat_edaran()`~~ → MD fallback menangani ini
- ~~Fix lampiran naratif Permenpan~~ → MD fallback menangani ini
- ~~Fix metadata nomor/tahun peraturan~~ → Deprioritasi (bisa dilakukan terpisah nanti)

Yang **tetap perlu** dilakukan tapi diluar scope sesi ini:
- Frontend fix: Model dropdown state (issue terpisah, tidak blockin)
