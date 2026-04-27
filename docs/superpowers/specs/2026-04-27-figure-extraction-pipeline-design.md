# Figure Extraction Pipeline — Design Spec

**Status:** Approved (brainstorming phase) — pending implementation plan
**Date:** 2026-04-27
**Scope:** POC pada `data/documents/audit/20250313_Laporan_Pelaksanaan_Evaluasi_SPBE_2024.pdf` (95 hal)
**Goal:** Memungkinkan RAG menjawab pertanyaan tentang konten gambar (chart, diagram, tabel-dalam-gambar) yang saat ini hilang dari indeks.

---

## 1. Latar Belakang & Problem

Dokumen audit BSSN dan laporan SPBE banyak mengandung konten visual:

| Tipe | Contoh di SPBE 2024 | Status saat ini |
|------|---------------------|-----------------|
| Tabel teks-native | Tabel 1, 4 (tertangkap markdown) | ✅ OK |
| Pie chart | Gambar 7 (Bobot Domain), Gambar 8 (Aspek) | ❌ Hilang |
| Bar chart | Gambar 1 (Capaian Indeks 2018-2024) | ❌ Hilang |
| Diagram alur/hierarki | Gambar 4, 5, 6 | ❌ Hilang |
| Tabel dalam gambar | Daftar instansi (D1-D4 scores) | ⚠️ Sebagian |
| Foto | Foto Presiden, Tim Koordinasi | ❌ Hilang (tidak relevan untuk skip) |

**Bukti masalah dari Marker output:**
- `data/marker_output/.../SPBE_2024.md` punya **223 referensi `![](image.jpeg)`**
- TAPI **0 file gambar** disimpan
- Caption tertinggal di markdown, konten visual tidak pernah masuk OCR/VLM
- 114 chunks di DB untuk dok ini, semuanya `chunk_type='text'`

**Dampak ke RAG:**
- Pertanyaan tentang bobot domain, kriteria kematangan, capaian historis → tidak bisa dijawab dari context retrieved
- Saat RAGAS evaluation dijalankan: `faithfulness ≈ 0` karena LLM kadang menebak benar dari training data tapi context yang di-retrieve tidak mendukung

---

## 2. Keputusan Desain

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Goal | Ekstrak konten visual untuk RAG (no UI display) | Pragmatis; UI multimodal di luar scope POC |
| Pendekatan ekstraksi | Hybrid: PaddleOCR (table-image) + VLM (chart/diagram) | OCR cepat untuk tabel; VLM perlu untuk interpretasi chart |
| Storage representation | Hybrid: text chunk dengan summary line + figure chunk terpisah | Retrieval optimal untuk query naratif maupun spesifik |
| Scope POC | Single document — SPBE 2024 audit | Validasi quality dulu, full rollout di iterasi berikutnya |
| Validation | RAGAS regression (40 GT existing) + figure GT khusus (15 baru) | Pastikan tidak ada regresi + buktikan improvement |
| Pipeline integration | Marker tetap (text), PyMuPDF parallel (image) | Minimal disruption pipeline existing |

---

## 3. Arsitektur

### 3.1 Modul

**Modul baru:**

| File | Tanggung jawab |
|------|----------------|
| `backend/app/core/ingestion/figure_processor.py` | Orkestrasi: extract → classify → route → format |
| `backend/app/core/ingestion/figure_classifier.py` | Klasifikasi tipe figure berdasarkan caption + heuristik |
| `backend/app/core/ingestion/vlm_extractor.py` | Wrapper VLM via Ollama (default `qwen2.5vl:7b`) |
| `backend/app/core/ingestion/figure_image_extractor.py` | PyMuPDF wrapper untuk ekstrak `.png` per halaman |

**Modul yang dimodifikasi:**

| File | Perubahan |
|------|-----------|
| `backend/app/core/ingestion/marker_converter.py` | Pastikan Marker save image files; fallback ke PyMuPDF |
| `backend/app/core/ingestion/structured_chunker.py` | Handle `chunk_type='figure'`; injeksi summary ke text chunk |
| `backend/app/core/ingestion/document_manager.py` | Wire pipeline baru di flow ingestion |

Schema `chunks` table tidak berubah — `chunk_type` dan `chunk_metadata` (JSON) sudah ada.

### 3.2 Interface

```python
# figure_processor.py — main entry
def process_figures(
    pdf_path: Path,
    marker_md: str,
    output_dir: Path,
    use_cache: bool = True,
) -> list[FigureExtraction]:
    """Extract and process all figures in a PDF.
    Returns one FigureExtraction per real figure (skips photos).
    Cached output to {output_dir}/figures.json for idempotent re-runs.
    """

@dataclass
class FigureExtraction:
    figure_id: str           # "fig_p26_01"
    figure_number: str       # "Gambar 7"
    caption: str             # "Grafik Bobot Penilaian Domain SPBE"
    figure_type: str         # "pie_chart" | "bar_chart" | "line_chart" | "diagram" | "timeline_image" | "table_image" | "photo"
    page: int                # 26
    image_path: Path         # absolute path to extracted PNG
    summary: str             # 1-2 kalimat untuk inline injection
    detail: str              # full description (200-500 kata) untuk figure chunk
    raw_ocr: str | None      # raw PaddleOCR text (untuk table_image)
    extraction_method: str   # "vlm" | "ocr" | "skipped"
    extraction_model: str | None  # "qwen2.5vl:7b" jika VLM
```

---

## 4. Data Flow

```
PDF
 ├──→ Marker → markdown.md (with image refs)
 └──→ PyMuPDF → page_X_fig_Y.png + bbox metadata
                          ↓
                  figure_classifier
              (caption text + dims + position)
                          ↓
        ┌─────────────────┼──────────────────┐
        ↓                 ↓                  ↓
     CHART            DIAGRAM            TABLE-IMAGE
     (VLM)             (VLM)              (PaddleOCR)
        │                 │                  │
        └─────────────────┼──────────────────┘
                          ↓
                  FigureExtraction
                          ↓
                  structured_chunker
                  ├── Inject summary into text chunk (where caption found)
                  └── Create separate figure chunk
                          ↓
                  SQLite + Qdrant + BM25
```

**Kunci flow:**

1. **Parallel extraction.** Marker (text) dan PyMuPDF (image) jalan paralel; di-merge berdasarkan page + bbox overlap.
2. **Photo skip-list.** Foto presiden / tim → skip, hemat ~30% waktu pada dok BSSN.
3. **VLM batching.** Kumpulkan semua chart+diagram dulu, panggil VLM dalam batch (1 model load × N inferensi).
4. **Sidecar cache.** Hasil extract di `figures.json` per dok; re-chunk tanpa re-extract.
5. **Caption matching.** Match summary ke text chunk via regex caption (`Gambar 7. Grafik Bobot...`); fallback ke chunk page-terdekat.

---

## 5. Storage Schema

### 5.1 Text chunk dengan figure references

`chunk_type='text'`, `chunk_metadata`:
```json
{
  "section": "Bobot Penilaian dan Predikat Indeks SPBE",
  "page_start": 25,
  "page_end": 26,
  "has_figure_refs": true,
  "figure_refs": ["fig_p26_01", "fig_p26_02"],
  "hierarchy_path": "Pemantauan dan Evaluasi SPBE > Bobot Penilaian"
}
```

`chunk_text` berisi prosa asli + summary line di-inject:
```
...Penetapan bobot penilaian Indeks SPBE dilakukan pada setiap level...

[Gambar 7] Grafik Bobot Penilaian Domain SPBE menunjukkan: Layanan SPBE
45,5% (terbesar), Tata Kelola SPBE 25%, Kebijakan Internal 16,5%,
Manajemen SPBE 13%.
```

### 5.2 Figure chunk

`chunk_type='figure'`, `chunk_metadata`:
```json
{
  "figure_id": "fig_p26_01",
  "figure_number": "Gambar 7",
  "caption": "Grafik Bobot Penilaian Domain SPBE",
  "figure_type": "pie_chart",
  "page": 26,
  "source_image": "data/marker_output/SPBE_2024/figures/page_26_fig_01.png",
  "extraction_method": "vlm",
  "extraction_model": "qwen2.5vl:7b",
  "parent_section": "Bobot Penilaian dan Predikat Indeks SPBE"
}
```

`chunk_text` berisi deskripsi penuh (caption + detail VLM):
```
Gambar 7. Grafik Bobot Penilaian Domain SPBE

Pie chart yang menampilkan distribusi bobot 4 domain SPBE:
- Layanan SPBE: 45,5% (slice terbesar)
- Tata Kelola SPBE: 25%
- Kebijakan Internal SPBE: 16,5%
- Manajemen SPBE: 13% (slice terkecil)

Total bobot = 100%. Domain Layanan SPBE memiliki bobot tertinggi karena
merepresentasikan output langsung pemerintahan digital.
```

### 5.3 Qdrant payload tambahan

```json
{
  "chunk_type": "figure",
  "figure_type": "pie_chart",
  "page": 26,
  "figure_number": "Gambar 7"
}
```

→ Mengizinkan filtering query masa depan tanpa schema migration.

### 5.4 Sidecar cache `figures.json`

Disimpan per dok di `data/marker_output/<doc>/figures.json`:
```json
[
  {
    "figure_id": "fig_p26_01",
    "page": 26,
    "image_path": "figures/page_26_fig_01.png",
    "image_hash": "sha256:...",
    "caption": "Gambar 7. Grafik Bobot Penilaian Domain SPBE",
    "figure_type": "pie_chart",
    "summary": "Bobot domain SPBE: Layanan 45,5%, Tata Kelola 25%, Kebijakan 16,5%, Manajemen 13%",
    "detail": "...full VLM output...",
    "extraction_method": "vlm",
    "extraction_model": "qwen2.5vl:7b",
    "extracted_at": "2026-04-27T20:00:00"
  }
]
```

Idempotent: re-run tidak re-extract jika `image_hash` cocok.

---

## 6. Classifier Logic

`figure_classifier.py` menggunakan caption text sebagai signal utama dengan fallback heuristic. Output langsung subtype konkret (sesuai dengan `FigureExtraction.figure_type`):

```python
def classify(caption: str, image_dims: tuple[int, int]) -> str:
    """Return one of: pie_chart, bar_chart, line_chart, diagram,
    table_image, timeline_image, photo."""
    text = caption.lower()

    # Pass 1: chart subtypes (most specific first)
    if re.search(r"\b(pie|lingkaran)\b", text):
        return "pie_chart"
    if re.search(r"\b(bar|batang)\b", text):
        return "bar_chart"
    if re.search(r"\b(line|garis|tren)\b", text):
        return "line_chart"
    if re.search(r"\b(grafik|chart)\b", text):
        return "bar_chart"  # default chart subtype when not specified

    # Pass 2: structural diagrams
    if re.search(r"\b(lini masa|timeline|kronologi)\b", text):
        return "timeline_image"
    if re.search(r"\b(diagram|struktur|alur|hierarki|kriteria|peta|tingkat)\b", text):
        return "diagram"

    # Pass 3: tables and photos
    if re.search(r"\btabel\b", text):
        return "table_image"
    if re.search(r"\b(foto|presiden|tim koordinasi|tim pelaksanaan)\b", text):
        return "photo"

    # Fallback: aspect-ratio heuristic
    w, h = image_dims
    if w / h > 2.5:
        return "timeline_image"  # very wide → likely timeline/banner

    return "diagram"  # safe default
```

Routing per output:

| `figure_type` | Pipeline |
|---------------|----------|
| `pie_chart`, `bar_chart`, `line_chart` | VLM dengan **chart prompt** |
| `diagram`, `timeline_image` | VLM dengan **diagram prompt** |
| `table_image` | PaddleOCR |
| `photo` | skip (no figure chunk, caption tetap di parent text chunk) |

---

## 7. VLM Prompts

Prompt template berbeda per `figure_type`:

**Chart prompt:**
```
Anda adalah asisten yang mendeskripsikan chart/grafik dalam bahasa Indonesia.

Tugas: deskripsikan chart berikut dengan akurat. Sebutkan:
1. Tipe chart (pie/bar/line)
2. Semua label dan nilainya secara eksak (jangan dibulatkan)
3. Trend atau pola jika ada

Output dalam 2 bagian:
SUMMARY: [1-2 kalimat ringkas, list nilai jika ada]
DETAIL: [paragraf deskripsi lengkap]
```

**Diagram prompt:**
```
Anda adalah asisten yang mendeskripsikan diagram dalam bahasa Indonesia.

Tugas: deskripsikan struktur dan konten diagram berikut. Sebutkan:
1. Tipe diagram (alur, hierarki, struktur, kriteria, dll)
2. Semua label, level, dan kriteria yang tertulis
3. Hubungan antar elemen

Output:
SUMMARY: [1-2 kalimat]
DETAIL: [paragraf, mention setiap level/kriteria]
```

VLM via Ollama:
```python
import httpx
async with httpx.AsyncClient(timeout=120.0) as client:
    response = await client.post(
        f"{settings.OLLAMA_BASE_URL}/api/generate",
        json={
            "model": "qwen2.5vl:7b",
            "prompt": prompt,
            "images": [base64_image],
            "stream": False,
            "options": {"temperature": 0.1}
        }
    )
```

Fallback chain jika qwen2.5vl OOM: `llava:7b` → `moondream:1.8b`.

---

## 8. Validation Strategy

### 8.1 Baseline (state sekarang)

- 40 ground truth pertanyaan existing (di `backend/data/ground_truth.json`)
- Skor RAGAS sebelum perubahan dijadikan baseline

### 8.2 Target POC

1. **Regression check:** skor RAGAS untuk 40 GT existing **tidak turun**
2. **Improvement nyata:** **≥10/15 figure-specific GT terjawab** dengan `faithfulness ≥ 0.7`

### 8.3 Figure-specific ground truth (15 pertanyaan baru)

| # | Pertanyaan | Source | Tipe |
|---|------------|--------|------|
| 1 | Berapa bobot Domain Layanan SPBE? | Gambar 7 | pie_chart |
| 2 | Berapa bobot Domain Manajemen SPBE? | Gambar 7 | pie_chart |
| 3 | Apa kriteria Tingkat Kematangan Optimum (proses)? | Gambar 4 | diagram |
| 4 | Pada tingkat berapa SPBE diukur kontribusinya pada kinerja organisasi? | Gambar 4 | diagram |
| 5 | Apa kriteria layanan tingkat Transaksi? | Gambar 5 | diagram |
| 6 | Bagaimana hierarki Struktur Penilaian Tingkat Kematangan SPBE? | Gambar 6 | diagram |
| 7 | Berapa bobot Aspek Penerapan Manajemen SPBE? | Gambar 8 | pie_chart |
| 8 | Berapa bobot Aspek Layanan Administrasi vs Layanan Publik? | Gambar 8 | pie_chart |
| 9 | Berapa Indeks SPBE Nasional 2018? | Gambar 1 | bar_chart |
| 10 | Tahun berapa Indeks SPBE pertama melampaui 3? | Gambar 1 + Tabel 4 | hybrid |
| 11 | Berapa proyeksi peringkat EGDI Indonesia di 2030? | Gambar 2 | line_chart |
| 12 | Siapa anggota Tim Koordinasi SPBE? | Gambar 3 | diagram |
| 13 | Domain mana yang capai indeks tertinggi 2024? | Tabel 4 (text-native) | **control** |
| 14 | Tren Domain Manajemen 2018-2024 menunjukkan apa? | Tabel 4 + Gambar 1 | hybrid |
| 15 | Lini masa Evaluasi SPBE 2024 dimulai dan selesai kapan? | Gambar 10 | timeline_image |

#13 sengaja dari tabel text-native sebagai **control**: harus pass di sistem lama maupun baru.

### 8.4 Eksekusi validasi

```bash
# Step 1: Baseline (sebelum perubahan kode pipeline ingestion)
python scripts/evaluate_rag.py --phase collect --doc-id 1
python scripts/evaluate_ragas.py
mv data/eval_ragas_report.json data/eval_baseline.json

# Step 2: Apply pipeline baru, re-ingest doc 1
python scripts/reingest_doc.py --doc-id 1 --use-figure-pipeline

# Step 3: Re-evaluate dengan combined GT (40 existing + 15 figure)
python scripts/evaluate_rag.py --phase collect
python scripts/evaluate_ragas.py
mv data/eval_ragas_report.json data/eval_after.json

# Step 4: Compare
python scripts/compare_ragas_reports.py data/eval_baseline.json data/eval_after.json
```

---

## 9. Implementation Phases

TDD-friendly, frequent commits. Total estimasi **13-19 jam** (~2-3 hari).

### Phase 1: Foundation — Image extraction (~2-3 jam)

- Tambah PyMuPDF dep (jika belum ada via Marker transitively)
- Implementasi `figure_image_extractor.py` + tests:
  - Test: extract semua gambar dari SPBE_2024.pdf, expect ≥ 50 image files
  - Test: setiap image punya `page` + `bbox` metadata yang valid
- Commit: `feat(ingestion): add PyMuPDF-based image extractor`

### Phase 2: Classifier (~2-3 jam)

- Implementasi `figure_classifier.py`
- Test: 16 figure dari SPBE_2024 → klasifikasi benar minimal 14/16
- Commit: `feat(ingestion): add figure classifier with caption rules`

### Phase 3: VLM extractor (~3-4 jam)

- Pull `qwen2.5vl:7b` via Ollama (atau fallback `llava:7b`)
- Implementasi `vlm_extractor.py`:
  - Prompt template per figure_type
  - Output parser (SUMMARY/DETAIL split)
  - Sidecar cache di `figures.json`
- Test: 5 chart manual → bandingkan output vs expected facts
- Commit: `feat(ingestion): add VLM-based figure extractor with caching`

### Phase 4: PaddleOCR integration (~1-2 jam)

- Sambungkan PaddleOCR existing untuk `table_image` type
- Test: 1 tabel-dalam-gambar dari SPBE_2024 → cek struktur tabel ter-extract
- Commit: `feat(ingestion): wire PaddleOCR to table-image figures`

### Phase 5: Orchestrator + chunker integration (~3-4 jam)

- Implementasi `figure_processor.py` (orkestrasi)
- Modifikasi `structured_chunker.py`:
  - Inject summary line ke text chunk yang punya caption matching
  - Generate figure chunk dengan metadata
- Test: end-to-end dengan SPBE_2024.pdf, expect chunks `figure` di DB
- Commit: `feat(ingestion): integrate figure pipeline into chunker`

### Phase 6: Re-ingest script + validation (~2-3 jam)

- `scripts/reingest_doc.py` (re-process satu dok dengan pipeline baru)
- 15 figure-specific GT di `data/ground_truth.json`
- `scripts/compare_ragas_reports.py`
- Test: re-ingest SPBE_2024, run RAGAS, verifikasi target tercapai
- Commit: `feat(eval): add figure-specific ground truth + comparison`

---

## 10. Definition of Done (POC)

- [ ] 16 unique figure dari SPBE_2024.pdf ter-ekstrak dan ter-index
- [ ] **≥10/15 figure-specific GT pass** dengan `faithfulness ≥ 0.7`
- [ ] **Skor RAGAS untuk 40 existing GT tidak turun** (boleh naik karena Qdrant payload bersih)
- [ ] Sidecar cache `figures.json` mengizinkan re-chunk tanpa re-extract
- [ ] Manual review: 80%+ figure summary akurat secara faktual
- [ ] Tidak ada regresi pada tipe dokumen lain (peraturan, surat edaran) — pipeline baru opt-in via flag

---

## 11. Constraints & Risks

| Constraint | Mitigasi |
|------------|----------|
| GPU 4GB VRAM tidak cukup load Qwen 2.5 7B + VLM 7B sekaligus | VLM dipanggil via Ollama dengan model swap; ingestion offline (tidak block server) |
| Ingestion time bertambah ~10-30s/figure × 16 figure ≈ 5-8 menit/dok | Acceptable untuk one-time ingestion; cached via figures.json |
| VLM hallucination (output tidak matching gambar) | Prompt menekankan akurasi; manual review 80%+ sebagai DoD; fallback OCR raw text untuk verifikasi |
| Marker tidak save image files reliably | PyMuPDF parallel extraction; idempotent — kedua source dimerge by page+bbox |
| Caption matching gagal (figure tanpa "Gambar X" prefix) | Fallback: append summary ke chunk page-terdekat; figure chunk tetap created |
| Regresi pada existing pipeline | Pipeline baru opt-in via flag `--use-figure-pipeline`; test 40 existing GT memastikan tidak regress |

---

## 12. Out of Scope (POC)

- Multimodal UI (display gambar di chat) — design terpisah jika dibutuhkan
- Full re-ingest semua 7 dokumen — separate task setelah POC sukses
- VLM fine-tuning untuk konten SPBE/audit Indonesia — gunakan model out-of-the-box
- Chart-to-data structured extraction (CSV) — hanya text description
- Real-time figure ingestion (saat upload) — pipeline tetap offline/batch
