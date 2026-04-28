# Figure Extraction Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tambah pipeline ekstraksi konten gambar (chart, diagram, tabel-dalam-gambar) ke ingestion SPBE RAG, supaya RAG bisa menjawab pertanyaan dari konten visual yang sebelumnya hilang dari indeks.

**Architecture:** Sidecar approach — Marker tetap menangani text/markdown; PyMuPDF jalan parallel untuk ekstrak file `.png`. Figure classifier route per-figure ke VLM (chart/diagram via `qwen3-vl:4b`) atau PaddleOCR (table-image). Hasil di-merge: summary line di-inject ke text chunk pemanggil, detail jadi figure chunk terpisah.

**Tech Stack:** PyMuPDF (image extraction), Ollama + qwen3-vl:4b (VLM), PaddleOCR (table OCR), existing structured_chunker, SQLite + Qdrant + BM25 (storage). Test via pytest dengan mock untuk VLM/OCR.

**Spec reference:** [docs/superpowers/specs/2026-04-27-figure-extraction-pipeline-design.md](../specs/2026-04-27-figure-extraction-pipeline-design.md)

**Critical model note:** Production chatbot = `qwen3.5:4b` (NOT `qwen2.5:7b-instruct`). VLM = `qwen3-vl:4b` (4.4B params, fits GTX 1650 4GB VRAM after qwen3.5 unload).

---

## File Structure

**New files:**

| File | Responsibility |
|------|----------------|
| `backend/app/core/ingestion/figures/__init__.py` | Package marker; export `FigureExtraction`, `process_figures` |
| `backend/app/core/ingestion/figures/types.py` | `FigureExtraction` dataclass, type literals |
| `backend/app/core/ingestion/figures/image_extractor.py` | PyMuPDF: ekstrak `.png` per halaman + bbox |
| `backend/app/core/ingestion/figures/classifier.py` | Klasifikasi figure type dari caption + dims |
| `backend/app/core/ingestion/figures/vlm_extractor.py` | VLM via Ollama untuk chart/diagram |
| `backend/app/core/ingestion/figures/ocr_extractor.py` | PaddleOCR wrapper untuk table-image |
| `backend/app/core/ingestion/figures/cache.py` | Sidecar `figures.json` baca/tulis |
| `backend/app/core/ingestion/figures/processor.py` | Orchestrator: extract → classify → route → format |
| `backend/tests/test_figure_image_extractor.py` | Test PyMuPDF extraction |
| `backend/tests/test_figure_classifier.py` | Test classifier rules |
| `backend/tests/test_figure_vlm_extractor.py` | Test VLM wrapper (mocked) |
| `backend/tests/test_figure_ocr_extractor.py` | Test OCR wrapper |
| `backend/tests/test_figure_cache.py` | Test sidecar cache |
| `backend/tests/test_figure_processor.py` | Test orchestrator (mocked extractors) |
| `backend/tests/test_chunker_figure_integration.py` | Test summary injection + figure chunk gen |
| `backend/scripts/reingest_doc.py` | Re-process satu dok dengan pipeline figure |
| `backend/scripts/compare_ragas_reports.py` | Diff dua laporan RAGAS |

**Modified files:**

| File | Change |
|------|--------|
| `backend/app/core/ingestion/structured_chunker.py` | Tambah `inject_figure_summaries()` + `make_figure_chunks()` |
| `backend/app/core/ingestion/document_manager.py` | Wire `process_figures()` di flow ingestion (opt-in flag) |
| `backend/scripts/evaluate_rag.py` | Default model → `qwen3.5:4b` |
| `backend/data/ground_truth.json` | Tambah 15 figure-specific GT (id `gt_041`–`gt_055`) |

---

## Task 1: Setup figure package + dataclass

**Files:**
- Create: `backend/app/core/ingestion/figures/__init__.py`
- Create: `backend/app/core/ingestion/figures/types.py`
- Test: `backend/tests/test_figure_types.py`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/test_figure_types.py
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pathlib import Path
from app.core.ingestion.figures.types import FigureExtraction, FIGURE_TYPES


def test_figure_extraction_required_fields():
    fig = FigureExtraction(
        figure_id="fig_p26_01",
        figure_number="Gambar 7",
        caption="Grafik Bobot Penilaian Domain SPBE",
        figure_type="pie_chart",
        page=26,
        image_path=Path("/tmp/x.png"),
        summary="Bobot: Layanan 45,5%, Tata Kelola 25%",
        detail="Pie chart menampilkan...",
        raw_ocr=None,
        extraction_method="vlm",
        extraction_model="qwen3-vl:4b",
    )
    assert fig.figure_id == "fig_p26_01"
    assert fig.figure_type == "pie_chart"
    assert fig.extraction_method == "vlm"


def test_figure_types_enum():
    assert "pie_chart" in FIGURE_TYPES
    assert "bar_chart" in FIGURE_TYPES
    assert "line_chart" in FIGURE_TYPES
    assert "diagram" in FIGURE_TYPES
    assert "timeline_image" in FIGURE_TYPES
    assert "table_image" in FIGURE_TYPES
    assert "photo" in FIGURE_TYPES
    assert len(FIGURE_TYPES) == 7
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && venv/Scripts/python -m pytest tests/test_figure_types.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.core.ingestion.figures'`

- [ ] **Step 3: Create package and types module**

```python
# backend/app/core/ingestion/figures/__init__.py
"""Figure extraction pipeline for SPBE RAG ingestion."""
from app.core.ingestion.figures.types import FigureExtraction, FIGURE_TYPES

__all__ = ["FigureExtraction", "FIGURE_TYPES"]
```

```python
# backend/app/core/ingestion/figures/types.py
"""Type definitions for figure extraction pipeline."""
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


FIGURE_TYPES = frozenset({
    "pie_chart",
    "bar_chart",
    "line_chart",
    "diagram",
    "timeline_image",
    "table_image",
    "photo",
})


@dataclass
class FigureExtraction:
    """Result of processing one figure (image) from a PDF.

    For 'photo' type, summary/detail may be empty (figure skipped from chunks).
    """
    figure_id: str               # "fig_p26_01"
    figure_number: str           # "Gambar 7"
    caption: str                 # "Grafik Bobot Penilaian Domain SPBE"
    figure_type: str             # one of FIGURE_TYPES
    page: int                    # 1-based page number
    image_path: Path
    summary: str                 # 1-2 kalimat untuk inline injection
    detail: str                  # full description for figure chunk
    raw_ocr: Optional[str]       # raw PaddleOCR text (table_image only)
    extraction_method: str       # "vlm" | "ocr" | "skipped"
    extraction_model: Optional[str]  # e.g. "qwen3-vl:4b"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && venv/Scripts/python -m pytest tests/test_figure_types.py -v`
Expected: PASS, 2 tests

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/ingestion/figures/__init__.py backend/app/core/ingestion/figures/types.py backend/tests/test_figure_types.py
git commit -m "feat(ingestion): add figures package with FigureExtraction dataclass"
```

---

## Task 2: PyMuPDF image extractor

**Files:**
- Create: `backend/app/core/ingestion/figures/image_extractor.py`
- Test: `backend/tests/test_figure_image_extractor.py`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/test_figure_image_extractor.py
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pathlib import Path
import pytest
from app.core.ingestion.figures.image_extractor import (
    extract_images_from_pdf,
    ExtractedImage,
)


SPBE_PDF = Path(__file__).parent.parent.parent / "data" / "documents" / "audit" / "20250313_Laporan_Pelaksanaan_Evaluasi_SPBE_2024.pdf"


@pytest.mark.skipif(not SPBE_PDF.exists(), reason="SPBE 2024 PDF not present")
def test_extract_images_from_spbe_2024(tmp_path):
    """SPBE 2024 PDF has many figures (charts, diagrams, photos).
    Expect at least 30 extracted images with valid metadata."""
    images = extract_images_from_pdf(SPBE_PDF, output_dir=tmp_path)

    assert len(images) >= 30, f"expected >= 30 images, got {len(images)}"
    for img in images:
        assert isinstance(img, ExtractedImage)
        assert img.image_path.exists()
        assert img.image_path.suffix == ".png"
        assert img.page >= 1
        assert len(img.bbox) == 4  # x0, y0, x1, y1
        assert img.width > 0 and img.height > 0


def test_extract_images_creates_unique_ids(tmp_path):
    """Each image should have unique figure_id even on same page."""
    if not SPBE_PDF.exists():
        pytest.skip("SPBE 2024 PDF not present")
    images = extract_images_from_pdf(SPBE_PDF, output_dir=tmp_path)
    ids = [img.figure_id for img in images]
    assert len(ids) == len(set(ids)), "figure_ids must be unique"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && venv/Scripts/python -m pytest tests/test_figure_image_extractor.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement image extractor**

```python
# backend/app/core/ingestion/figures/image_extractor.py
"""Extract embedded images from PDF using PyMuPDF.

Returns one ExtractedImage per real image (excludes inline tiny icons < 50x50).
Saves PNGs to output_dir/figures/ with deterministic naming.
"""
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple

import fitz  # PyMuPDF
from loguru import logger


MIN_DIMENSION = 50  # skip icons / decorative dots smaller than this
SUBDIR_NAME = "figures"


@dataclass
class ExtractedImage:
    figure_id: str           # "fig_p{page}_{idx}"
    page: int                # 1-based
    image_path: Path
    bbox: Tuple[float, float, float, float]  # PDF coords on page
    width: int               # pixels
    height: int


def extract_images_from_pdf(pdf_path: Path, output_dir: Path) -> List[ExtractedImage]:
    """Extract all embedded images, save as PNG, return metadata list."""
    pdf_path = Path(pdf_path)
    figures_dir = Path(output_dir) / SUBDIR_NAME
    figures_dir.mkdir(parents=True, exist_ok=True)

    results: List[ExtractedImage] = []
    doc = fitz.open(pdf_path)
    try:
        for page_idx in range(len(doc)):
            page = doc[page_idx]
            page_no = page_idx + 1
            for img_idx, img_info in enumerate(page.get_images(full=True), start=1):
                xref = img_info[0]
                try:
                    pix = fitz.Pixmap(doc, xref)
                    if pix.width < MIN_DIMENSION or pix.height < MIN_DIMENSION:
                        pix = None
                        continue
                    if pix.colorspace and pix.colorspace.n >= 4:
                        # CMYK or other → convert to RGB
                        pix = fitz.Pixmap(fitz.csRGB, pix)

                    figure_id = f"fig_p{page_no:03d}_{img_idx:02d}"
                    image_path = figures_dir / f"{figure_id}.png"
                    pix.save(str(image_path))

                    # bbox: best-effort via image rects on page
                    rects = page.get_image_rects(xref)
                    bbox = tuple(rects[0]) if rects else (0.0, 0.0, 0.0, 0.0)

                    results.append(ExtractedImage(
                        figure_id=figure_id,
                        page=page_no,
                        image_path=image_path,
                        bbox=bbox,
                        width=pix.width,
                        height=pix.height,
                    ))
                    pix = None
                except Exception as e:
                    logger.warning(f"Failed extracting image {xref} on page {page_no}: {e}")
    finally:
        doc.close()

    logger.info(f"Extracted {len(results)} images from {pdf_path.name}")
    return results
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && venv/Scripts/python -m pytest tests/test_figure_image_extractor.py -v`
Expected: PASS, both tests

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/ingestion/figures/image_extractor.py backend/tests/test_figure_image_extractor.py
git commit -m "feat(ingestion): add PyMuPDF-based figure image extractor"
```

---

## Task 3: Figure classifier

**Files:**
- Create: `backend/app/core/ingestion/figures/classifier.py`
- Test: `backend/tests/test_figure_classifier.py`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/test_figure_classifier.py
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from app.core.ingestion.figures.classifier import classify


CASES = [
    # (caption, dims, expected_type)
    ("Gambar 7. Grafik Bobot Penilaian Domain SPBE",        (800, 600), "bar_chart"),
    ("Gambar 8. Grafik Bobot Penilaian Aspek SPBE",         (800, 600), "bar_chart"),
    ("Gambar 1. Capaian Indeks SPBE Nasional 2018-2024",    (1000, 500), "line_chart"),
    ("Gambar X. Pie chart distribusi instansi",             (600, 600), "pie_chart"),
    ("Gambar X. Diagram lingkaran komposisi",               (600, 600), "pie_chart"),
    ("Gambar X. Diagram batang capaian",                    (800, 500), "bar_chart"),
    ("Gambar 4. Kriteria Tingkat Kematangan Proses",        (900, 700), "diagram"),
    ("Gambar 6. Struktur Penilaian Tingkat Kematangan SPBE",(900, 700), "diagram"),
    ("Gambar 3. Tim Koordinasi SPBE",                       (900, 700), "diagram"),
    ("Gambar 10. Lini Masa Pelaksanaan Evaluasi SPBE 2024", (1500, 400), "timeline_image"),
    ("Tabel 5. Daftar Instansi (sebagai gambar)",           (900, 1200), "table_image"),
    ("Foto Presiden saat penyerahan award",                 (800, 600), "photo"),
    ("Gambar X. Tim pelaksanaan",                           (800, 600), "photo"),
    ("Gambar tanpa caption deskriptif",                     (3000, 800), "timeline_image"),  # aspect-ratio fallback
    ("Gambar tanpa caption deskriptif",                     (800, 600), "diagram"),  # default
]


@pytest.mark.parametrize("caption,dims,expected", CASES)
def test_classify(caption, dims, expected):
    assert classify(caption, dims) == expected
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && venv/Scripts/python -m pytest tests/test_figure_classifier.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement classifier**

```python
# backend/app/core/ingestion/figures/classifier.py
"""Classify figure type from caption text + image dimensions.

Output is one of FIGURE_TYPES. Returned subtype determines downstream routing:
- pie/bar/line_chart, diagram, timeline_image → VLM
- table_image                                  → PaddleOCR
- photo                                        → skipped (no chunk)
"""
import re
from typing import Tuple


def classify(caption: str, image_dims: Tuple[int, int]) -> str:
    """Return one of FIGURE_TYPES based on caption + dims heuristics."""
    text = (caption or "").lower()

    # Pass 1: chart subtypes (most specific first)
    if re.search(r"\b(pie|lingkaran)\b", text):
        return "pie_chart"
    if re.search(r"\b(bar|batang)\b", text):
        return "bar_chart"
    if re.search(r"\b(line|garis|tren|capaian.*tahun|indeks.*\d{4})\b", text):
        return "line_chart"
    if re.search(r"\b(grafik|chart)\b", text):
        return "bar_chart"  # default chart subtype

    # Pass 2: structural diagrams
    if re.search(r"\b(lini masa|timeline|kronologi)\b", text):
        return "timeline_image"
    if re.search(r"\b(diagram|struktur|alur|hierarki|kriteria|peta|tingkat)\b", text):
        return "diagram"

    # Pass 3: photos (check before generic "tabel" since photo caption can mention things)
    if re.search(r"\b(foto|presiden|tim koordinasi|tim pelaksanaan)\b", text):
        return "photo"

    # Pass 4: tables
    if re.search(r"\btabel\b", text):
        return "table_image"

    # Fallback: aspect-ratio heuristic
    w, h = image_dims
    if h > 0 and w / h > 2.5:
        return "timeline_image"  # very wide → likely banner / timeline

    return "diagram"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && venv/Scripts/python -m pytest tests/test_figure_classifier.py -v`
Expected: PASS, all 15 parametrized cases

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/ingestion/figures/classifier.py backend/tests/test_figure_classifier.py
git commit -m "feat(ingestion): add figure classifier with caption + dims heuristics"
```

---

## Task 4: VLM extractor (mocked tests)

**Files:**
- Create: `backend/app/core/ingestion/figures/vlm_extractor.py`
- Test: `backend/tests/test_figure_vlm_extractor.py`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/test_figure_vlm_extractor.py
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

from app.core.ingestion.figures.vlm_extractor import (
    extract_with_vlm,
    parse_vlm_output,
    VLM_MODEL,
)


def test_vlm_default_model_is_qwen3_vl_4b():
    assert VLM_MODEL == "qwen3-vl:4b"


def test_parse_vlm_output_with_summary_and_detail():
    raw = (
        "SUMMARY: Bobot domain SPBE: Layanan 45,5%, Tata Kelola 25%, "
        "Kebijakan 16,5%, Manajemen 13%.\n"
        "DETAIL: Pie chart yang menampilkan distribusi bobot 4 domain SPBE. "
        "Layanan SPBE memiliki bobot terbesar (45,5%), diikuti Tata Kelola (25%), "
        "Kebijakan Internal (16,5%), dan Manajemen (13%)."
    )
    summary, detail = parse_vlm_output(raw)
    assert "45,5%" in summary
    assert "Layanan" in summary
    assert "Pie chart" in detail
    assert "distribusi bobot" in detail


def test_parse_vlm_output_missing_labels_falls_back_to_split():
    raw = "Bobot domain: Layanan 45,5%, Manajemen 13%.\nDeskripsi pie chart penuh dengan 4 segmen."
    summary, detail = parse_vlm_output(raw)
    assert summary  # non-empty
    assert detail   # non-empty


def test_extract_with_vlm_calls_ollama(tmp_path):
    img = tmp_path / "test.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)  # fake PNG header

    fake_response = MagicMock()
    fake_response.status_code = 200
    fake_response.json.return_value = {
        "response": "SUMMARY: Test.\nDETAIL: Test detail."
    }
    fake_response.raise_for_status = MagicMock()

    with patch("app.core.ingestion.figures.vlm_extractor.httpx.Client") as MockClient:
        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.post.return_value = fake_response
        MockClient.return_value = mock_client

        summary, detail, model = extract_with_vlm(
            image_path=img,
            figure_type="pie_chart",
            caption="Gambar 7. Grafik Bobot Penilaian Domain SPBE",
        )

    assert summary == "Test."
    assert detail == "Test detail."
    assert model == "qwen3-vl:4b"
    mock_client.post.assert_called_once()
    # Verify the prompt includes caption
    call_kwargs = mock_client.post.call_args.kwargs
    assert "Bobot Penilaian" in call_kwargs["json"]["prompt"]
    assert call_kwargs["json"]["model"] == "qwen3-vl:4b"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && venv/Scripts/python -m pytest tests/test_figure_vlm_extractor.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement VLM extractor**

```python
# backend/app/core/ingestion/figures/vlm_extractor.py
"""VLM-based figure extraction via Ollama.

Uses qwen3-vl:4b (4.4B params, fits 4GB VRAM) by default.
Different prompt templates per figure_type for chart vs diagram.
"""
import base64
import re
from pathlib import Path
from typing import Tuple

import httpx
from loguru import logger

from app.config import settings


VLM_MODEL = "qwen3-vl:4b"
VLM_TIMEOUT = 180.0  # seconds per inference

CHART_PROMPT = """Anda adalah asisten yang mendeskripsikan chart/grafik dalam bahasa Indonesia.

Caption gambar: "{caption}"

Tugas: deskripsikan chart pada gambar ini dengan AKURAT. Sebutkan:
1. Tipe chart (pie/bar/line)
2. Semua label dan nilai numerik secara EKSAK (jangan dibulatkan)
3. Trend atau pola jika ada

Format output (wajib pakai label SUMMARY dan DETAIL):
SUMMARY: [1-2 kalimat ringkas berisi list label+nilai]
DETAIL: [paragraf 100-300 kata, deskripsi lengkap]
"""

DIAGRAM_PROMPT = """Anda adalah asisten yang mendeskripsikan diagram dalam bahasa Indonesia.

Caption gambar: "{caption}"

Tugas: deskripsikan struktur dan konten diagram. Sebutkan:
1. Tipe diagram (alur, hierarki, struktur, kriteria, dll)
2. Semua label, level, dan kriteria yang tertulis di gambar
3. Hubungan antar elemen (jika ada panah / koneksi)

Format output (wajib pakai label SUMMARY dan DETAIL):
SUMMARY: [1-2 kalimat]
DETAIL: [paragraf, mention setiap level/kriteria yang terlihat]
"""


def _select_prompt(figure_type: str, caption: str) -> str:
    if figure_type in ("pie_chart", "bar_chart", "line_chart"):
        return CHART_PROMPT.format(caption=caption)
    return DIAGRAM_PROMPT.format(caption=caption)


def parse_vlm_output(raw: str) -> Tuple[str, str]:
    """Split raw VLM output into (summary, detail).

    Expects 'SUMMARY: ...' and 'DETAIL: ...' labels.
    Falls back to first-line vs rest if labels missing.
    """
    summary_match = re.search(r"SUMMARY\s*:\s*(.+?)(?=DETAIL\s*:|$)", raw, re.DOTALL | re.IGNORECASE)
    detail_match  = re.search(r"DETAIL\s*:\s*(.+)$", raw, re.DOTALL | re.IGNORECASE)

    if summary_match and detail_match:
        return summary_match.group(1).strip(), detail_match.group(1).strip()

    # Fallback: first non-empty paragraph as summary, rest as detail
    parts = [p.strip() for p in raw.split("\n\n") if p.strip()]
    if len(parts) >= 2:
        return parts[0], "\n\n".join(parts[1:])
    if parts:
        return parts[0], parts[0]
    return "", ""


def extract_with_vlm(
    image_path: Path,
    figure_type: str,
    caption: str,
    model: str = VLM_MODEL,
) -> Tuple[str, str, str]:
    """Call Ollama VLM, return (summary, detail, model_used).

    Raises httpx.HTTPError on transport failure (caller should catch and skip).
    """
    image_path = Path(image_path)
    image_b64 = base64.b64encode(image_path.read_bytes()).decode("ascii")
    prompt = _select_prompt(figure_type, caption)

    payload = {
        "model": model,
        "prompt": prompt,
        "images": [image_b64],
        "stream": False,
        "options": {"temperature": 0.1, "num_predict": 800},
    }

    url = f"{settings.OLLAMA_BASE_URL}/api/generate"
    logger.debug(f"VLM request: {model} for {image_path.name} ({figure_type})")

    with httpx.Client(timeout=VLM_TIMEOUT) as client:
        response = client.post(url, json=payload)
        response.raise_for_status()
        raw = response.json().get("response", "")

    summary, detail = parse_vlm_output(raw)
    logger.debug(f"VLM result: summary={len(summary)}ch, detail={len(detail)}ch")
    return summary, detail, model
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && venv/Scripts/python -m pytest tests/test_figure_vlm_extractor.py -v`
Expected: PASS, 4 tests

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/ingestion/figures/vlm_extractor.py backend/tests/test_figure_vlm_extractor.py
git commit -m "feat(ingestion): add VLM extractor using qwen3-vl:4b via Ollama"
```

---

## Task 5: PaddleOCR table extractor

**Files:**
- Create: `backend/app/core/ingestion/figures/ocr_extractor.py`
- Test: `backend/tests/test_figure_ocr_extractor.py`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/test_figure_ocr_extractor.py
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pathlib import Path
from unittest.mock import patch, MagicMock

from app.core.ingestion.figures.ocr_extractor import (
    extract_table_with_ocr,
    format_ocr_as_summary,
)


def test_format_ocr_as_summary_short_text():
    raw = "No\tNama\tNilai\n1\tA\t100\n2\tB\t200"
    summary, detail = format_ocr_as_summary(raw, caption="Tabel 1. Daftar Skor")
    assert "Tabel 1" in summary
    assert "100" in detail or "200" in detail


def test_extract_table_with_ocr_returns_text(tmp_path):
    img = tmp_path / "table.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

    fake_ocr_result = [[
        [[[0, 0], [100, 0], [100, 30], [0, 30]], ("Header A", 0.99)],
        [[[0, 30], [100, 30], [100, 60], [0, 60]], ("Cell 1", 0.95)],
    ]]

    with patch("app.core.ingestion.figures.ocr_extractor._get_paddle_ocr") as mock_get:
        mock_engine = MagicMock()
        mock_engine.ocr.return_value = fake_ocr_result
        mock_get.return_value = mock_engine

        summary, detail, raw = extract_table_with_ocr(
            image_path=img,
            caption="Tabel X. Test"
        )

    assert "Header A" in raw
    assert "Cell 1" in raw
    assert "Tabel X" in summary
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && venv/Scripts/python -m pytest tests/test_figure_ocr_extractor.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement OCR extractor**

```python
# backend/app/core/ingestion/figures/ocr_extractor.py
"""PaddleOCR-based extraction for table-image figures.

Lazy-load PaddleOCR engine to avoid loading at import time
(saves ~200MB RAM when not needed).
"""
from pathlib import Path
from typing import Tuple, Optional

import cv2
import numpy as np
from loguru import logger


_paddle_ocr_engine = None


def _get_paddle_ocr():
    """Lazy initialize PaddleOCR engine. Reuse existing OCRProcessor if available."""
    global _paddle_ocr_engine
    if _paddle_ocr_engine is None:
        from paddleocr import PaddleOCR
        _paddle_ocr_engine = PaddleOCR(
            lang="id",        # Indonesian
            use_angle_cls=True,
            use_gpu=False,    # CPU to avoid GPU contention with VLM
            show_log=False,
        )
        logger.info("PaddleOCR engine initialized for figure extraction")
    return _paddle_ocr_engine


def extract_table_with_ocr(
    image_path: Path,
    caption: str,
) -> Tuple[str, str, str]:
    """OCR a table image, return (summary, detail, raw_ocr_text)."""
    image_path = Path(image_path)
    img = cv2.imread(str(image_path))
    if img is None:
        logger.warning(f"OCR: cannot read {image_path}")
        return "", "", ""

    engine = _get_paddle_ocr()
    result = engine.ocr(img, cls=True)

    lines = []
    if result and result[0]:
        for line in result[0]:
            text = line[1][0] if line[1] else ""
            if text:
                lines.append(text)

    raw = "\n".join(lines)
    summary, detail = format_ocr_as_summary(raw, caption)
    return summary, detail, raw


def format_ocr_as_summary(raw: str, caption: str) -> Tuple[str, str]:
    """Convert raw OCR output → (summary, detail).

    Summary: caption + first 200 chars hint.
    Detail: caption + full OCR text.
    """
    raw = raw.strip()
    if not raw:
        return f"{caption}: (kosong)", caption

    snippet = raw[:200].replace("\n", " ")
    summary = f"{caption}: {snippet}"
    detail = f"{caption}\n\n{raw}"
    return summary, detail
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && venv/Scripts/python -m pytest tests/test_figure_ocr_extractor.py -v`
Expected: PASS, 2 tests

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/ingestion/figures/ocr_extractor.py backend/tests/test_figure_ocr_extractor.py
git commit -m "feat(ingestion): add PaddleOCR-based table-image extractor"
```

---

## Task 6: Sidecar cache module

**Files:**
- Create: `backend/app/core/ingestion/figures/cache.py`
- Test: `backend/tests/test_figure_cache.py`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/test_figure_cache.py
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pathlib import Path
from app.core.ingestion.figures.cache import save_cache, load_cache, image_hash
from app.core.ingestion.figures.types import FigureExtraction


def _make_fig(tmp_path, fid="fig_p01_01"):
    img = tmp_path / f"{fid}.png"
    img.write_bytes(b"PNGDATA" * 50)
    return FigureExtraction(
        figure_id=fid,
        figure_number="Gambar 1",
        caption="Test",
        figure_type="diagram",
        page=1,
        image_path=img,
        summary="sum",
        detail="det",
        raw_ocr=None,
        extraction_method="vlm",
        extraction_model="qwen3-vl:4b",
    )


def test_image_hash_stable(tmp_path):
    img = tmp_path / "a.png"
    img.write_bytes(b"hello world")
    h1 = image_hash(img)
    h2 = image_hash(img)
    assert h1 == h2
    assert h1.startswith("sha256:")


def test_save_and_load_cache_roundtrip(tmp_path):
    figs = [_make_fig(tmp_path, "fig_p01_01"), _make_fig(tmp_path, "fig_p02_01")]
    cache_path = tmp_path / "figures.json"

    save_cache(cache_path, figs)
    loaded = load_cache(cache_path)

    assert len(loaded) == 2
    assert loaded[0].figure_id == "fig_p01_01"
    assert loaded[0].extraction_method == "vlm"
    assert loaded[0].image_path.exists()


def test_load_cache_returns_empty_when_missing(tmp_path):
    assert load_cache(tmp_path / "missing.json") == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && venv/Scripts/python -m pytest tests/test_figure_cache.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement cache module**

```python
# backend/app/core/ingestion/figures/cache.py
"""Sidecar JSON cache for FigureExtraction results.

Idempotent: re-running pipeline does not re-extract figures whose
image hash matches the cached entry. Cache file is per-document at
data/marker_output/<doc>/figures.json.
"""
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from loguru import logger

from app.core.ingestion.figures.types import FigureExtraction


def image_hash(image_path: Path) -> str:
    """SHA-256 hash of image bytes, prefixed with 'sha256:' for clarity."""
    h = hashlib.sha256()
    h.update(Path(image_path).read_bytes())
    return f"sha256:{h.hexdigest()}"


def save_cache(cache_path: Path, figures: List[FigureExtraction]) -> None:
    """Serialize figures to JSON sidecar."""
    cache_path = Path(cache_path)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    payload = []
    for f in figures:
        payload.append({
            "figure_id": f.figure_id,
            "figure_number": f.figure_number,
            "caption": f.caption,
            "figure_type": f.figure_type,
            "page": f.page,
            "image_path": str(f.image_path),
            "image_hash": image_hash(f.image_path) if f.image_path.exists() else None,
            "summary": f.summary,
            "detail": f.detail,
            "raw_ocr": f.raw_ocr,
            "extraction_method": f.extraction_method,
            "extraction_model": f.extraction_model,
            "cached_at": datetime.now().isoformat(),
        })
    cache_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(f"Saved {len(figures)} figure entries to {cache_path}")


def load_cache(cache_path: Path) -> List[FigureExtraction]:
    """Load cached figures. Returns [] if file missing or invalid."""
    cache_path = Path(cache_path)
    if not cache_path.exists():
        return []
    try:
        data = json.loads(cache_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        logger.warning(f"Invalid cache JSON: {cache_path} — treating as empty")
        return []

    return [
        FigureExtraction(
            figure_id=e["figure_id"],
            figure_number=e["figure_number"],
            caption=e["caption"],
            figure_type=e["figure_type"],
            page=e["page"],
            image_path=Path(e["image_path"]),
            summary=e["summary"],
            detail=e["detail"],
            raw_ocr=e.get("raw_ocr"),
            extraction_method=e["extraction_method"],
            extraction_model=e.get("extraction_model"),
        )
        for e in data
    ]


def get_cached_for_image(cache: List[FigureExtraction], image_path: Path) -> Optional[FigureExtraction]:
    """Find cached entry matching the given image by hash. Returns None if not cached."""
    if not image_path.exists():
        return None
    target_hash = image_hash(image_path)
    cache_path = Path(image_path)
    for entry in cache:
        if entry.image_path == cache_path and entry.image_path.exists():
            if image_hash(entry.image_path) == target_hash:
                return entry
    return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && venv/Scripts/python -m pytest tests/test_figure_cache.py -v`
Expected: PASS, 3 tests

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/ingestion/figures/cache.py backend/tests/test_figure_cache.py
git commit -m "feat(ingestion): add sidecar JSON cache for figure extractions"
```

---

## Task 7: Caption matching helper

**Files:**
- Create: `backend/app/core/ingestion/figures/caption_matcher.py`
- Test: `backend/tests/test_figure_caption_matcher.py`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/test_figure_caption_matcher.py
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.core.ingestion.figures.caption_matcher import (
    find_caption_for_image,
    extract_figure_number,
)


SAMPLE_MD = """\
Beberapa paragraf intro.

![](_page_25_Picture_3.jpeg)

Bobot Penilaian Domain SPBE
16,50% 13% 25% 45,50%

Gambar 7. Grafik Bobot Penilaian Domain SPBE

Selanjutnya pada Gambar 8 ditampilkan...

![](_page_25_Picture_5.jpeg)

Gambar 8. Grafik Bobot Penilaian Aspek SPBE
"""


def test_extract_figure_number():
    assert extract_figure_number("Gambar 7. Grafik Bobot Penilaian Domain SPBE") == "Gambar 7"
    assert extract_figure_number("Tabel 5. Daftar Indeks") == "Tabel 5"
    assert extract_figure_number("No caption here") == ""


def test_find_caption_for_image_picks_nearest_after():
    """Caption right after image ref should match."""
    caption = find_caption_for_image(SAMPLE_MD, page=25, image_index=1)
    assert "Gambar 7" in caption
    assert "Grafik Bobot Penilaian Domain SPBE" in caption


def test_find_caption_for_image_second_image():
    caption = find_caption_for_image(SAMPLE_MD, page=25, image_index=2)
    assert "Gambar 8" in caption


def test_find_caption_returns_empty_when_no_match():
    caption = find_caption_for_image("only text\nno images", page=1, image_index=1)
    assert caption == ""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && venv/Scripts/python -m pytest tests/test_figure_caption_matcher.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement caption matcher**

```python
# backend/app/core/ingestion/figures/caption_matcher.py
"""Match figure captions to extracted images.

Marker outputs markdown with image references like:
    ![](_page_25_Picture_3.jpeg)
    Gambar 7. Caption text...

We match by finding image refs by page number and pairing each with
the nearest "Gambar N." or "Tabel N." caption that follows it.
"""
import re
from typing import List, Tuple


IMG_REF_RE = re.compile(r"!\[\]\(_page_(\d+)_Picture_(\d+)\.jpeg\)")
CAPTION_RE = re.compile(r"^(Gambar|Tabel)\s+\d+[\.\s]", re.MULTILINE)
FIG_NUMBER_RE = re.compile(r"^(Gambar|Tabel)\s+\d+", re.MULTILINE)


def extract_figure_number(line: str) -> str:
    """Extract 'Gambar N' or 'Tabel N' from start of a line."""
    m = FIG_NUMBER_RE.match((line or "").strip())
    return m.group(0) if m else ""


def _find_image_refs(markdown: str) -> List[Tuple[int, int, int]]:
    """Return list of (page, image_index, char_offset)."""
    refs = []
    for m in IMG_REF_RE.finditer(markdown):
        page = int(m.group(1))
        idx = int(m.group(2))
        refs.append((page, idx, m.start()))
    return refs


def _find_captions(markdown: str) -> List[Tuple[int, str]]:
    """Return list of (char_offset, full_caption_line)."""
    captions = []
    for m in CAPTION_RE.finditer(markdown):
        line_start = m.start()
        line_end = markdown.find("\n", line_start)
        line_end = line_end if line_end != -1 else len(markdown)
        captions.append((line_start, markdown[line_start:line_end].strip()))
    return captions


def find_caption_for_image(markdown: str, page: int, image_index: int) -> str:
    """Find caption that follows the image ref for (page, image_index).

    Marker uses 0-based page numbers in image refs, but PyMuPDF uses 1-based.
    We try both: page-1 (Marker convention) first, then page.

    Returns caption string, or "" if no match.
    """
    refs = _find_image_refs(markdown)
    captions = _find_captions(markdown)

    # Try Marker convention (0-based) first
    for marker_page in (page - 1, page):
        match = next(
            (offset for p, idx, offset in refs if p == marker_page and idx == image_index),
            None,
        )
        if match is not None:
            # Find first caption AFTER this image offset, within 500 chars
            for cap_offset, cap_text in captions:
                if 0 <= cap_offset - match <= 500:
                    return cap_text
            return ""
    return ""
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && venv/Scripts/python -m pytest tests/test_figure_caption_matcher.py -v`
Expected: PASS, 4 tests

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/ingestion/figures/caption_matcher.py backend/tests/test_figure_caption_matcher.py
git commit -m "feat(ingestion): add caption matcher to pair Marker image refs with figure numbers"
```

---

## Task 8: Figure processor (orchestrator)

**Files:**
- Create: `backend/app/core/ingestion/figures/processor.py`
- Test: `backend/tests/test_figure_processor.py`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/test_figure_processor.py
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

from app.core.ingestion.figures.processor import process_figures
from app.core.ingestion.figures.image_extractor import ExtractedImage


SAMPLE_MD = """\
Pendahuluan.

![](_page_25_Picture_3.jpeg)

Gambar 7. Grafik Bobot Penilaian Domain SPBE

Lalu paragraf lain.

![](_page_30_Picture_1.jpeg)

Foto Presiden saat penyerahan

![](_page_45_Picture_2.jpeg)

Tabel 12. Daftar instansi peserta evaluasi
"""


def _make_extracted_image(page, idx, tmp_path):
    fid = f"fig_p{page:03d}_{idx:02d}"
    p = tmp_path / f"{fid}.png"
    p.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
    return ExtractedImage(
        figure_id=fid,
        page=page,
        image_path=p,
        bbox=(0, 0, 100, 100),
        width=800,
        height=600,
    )


def test_process_figures_routes_chart_to_vlm_and_skips_photo(tmp_path):
    images = [
        _make_extracted_image(26, 1, tmp_path),  # page 25 marker → page 26 fitz; chart
        _make_extracted_image(31, 1, tmp_path),  # page 30 marker → page 31 fitz; photo
        _make_extracted_image(46, 1, tmp_path),  # page 45 marker → page 46 fitz; table
    ]

    with patch("app.core.ingestion.figures.processor.extract_images_from_pdf", return_value=images), \
         patch("app.core.ingestion.figures.processor.extract_with_vlm", return_value=("VLM summary", "VLM detail", "qwen3-vl:4b")) as vlm_mock, \
         patch("app.core.ingestion.figures.processor.extract_table_with_ocr", return_value=("OCR summary", "OCR detail", "raw text")) as ocr_mock:

        results = process_figures(
            pdf_path=tmp_path / "fake.pdf",
            marker_md=SAMPLE_MD,
            output_dir=tmp_path,
            use_cache=False,
        )

    by_id = {r.figure_id: r for r in results}
    assert "fig_p026_01" in by_id
    assert "fig_p046_01" in by_id
    # Photo should be present but extraction_method == "skipped"
    photo = by_id["fig_p031_01"]
    assert photo.extraction_method == "skipped"
    assert photo.figure_type == "photo"

    chart = by_id["fig_p026_01"]
    assert chart.extraction_method == "vlm"
    assert chart.figure_type == "bar_chart"
    assert chart.figure_number == "Gambar 7"
    assert "VLM summary" in chart.summary

    table = by_id["fig_p046_01"]
    assert table.extraction_method == "ocr"
    assert table.figure_type == "table_image"
    assert table.figure_number == "Tabel 12"

    assert vlm_mock.call_count == 1
    assert ocr_mock.call_count == 1


def test_process_figures_uses_cache_on_second_run(tmp_path):
    images = [_make_extracted_image(26, 1, tmp_path)]

    # First call — VLM is called
    with patch("app.core.ingestion.figures.processor.extract_images_from_pdf", return_value=images), \
         patch("app.core.ingestion.figures.processor.extract_with_vlm", return_value=("S", "D", "qwen3-vl:4b")) as vlm:
        process_figures(
            pdf_path=tmp_path / "fake.pdf",
            marker_md=SAMPLE_MD,
            output_dir=tmp_path,
            use_cache=True,
        )
        assert vlm.call_count == 1

    # Second call — cache hit, VLM not called
    with patch("app.core.ingestion.figures.processor.extract_images_from_pdf", return_value=images), \
         patch("app.core.ingestion.figures.processor.extract_with_vlm") as vlm2:
        results = process_figures(
            pdf_path=tmp_path / "fake.pdf",
            marker_md=SAMPLE_MD,
            output_dir=tmp_path,
            use_cache=True,
        )
        assert vlm2.call_count == 0
        assert results[0].summary == "S"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && venv/Scripts/python -m pytest tests/test_figure_processor.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement processor**

```python
# backend/app/core/ingestion/figures/processor.py
"""Orchestrator: extract images → classify → route to VLM/OCR → cache.

Main entry: process_figures(pdf_path, marker_md, output_dir, use_cache=True)
Returns list[FigureExtraction] (one per real figure, including skipped photos).
"""
from pathlib import Path
from typing import List

from loguru import logger

from app.core.ingestion.figures.types import FigureExtraction
from app.core.ingestion.figures.image_extractor import (
    extract_images_from_pdf,
    ExtractedImage,
)
from app.core.ingestion.figures.classifier import classify
from app.core.ingestion.figures.caption_matcher import (
    find_caption_for_image,
    extract_figure_number,
)
from app.core.ingestion.figures.vlm_extractor import extract_with_vlm
from app.core.ingestion.figures.ocr_extractor import extract_table_with_ocr
from app.core.ingestion.figures.cache import (
    save_cache,
    load_cache,
    image_hash,
)


CACHE_FILENAME = "figures.json"
VLM_TYPES = {"pie_chart", "bar_chart", "line_chart", "diagram", "timeline_image"}
OCR_TYPES = {"table_image"}


def _image_idx_from_id(figure_id: str) -> int:
    """fig_p026_01 → 1"""
    return int(figure_id.rsplit("_", 1)[-1])


def _build_extraction(
    img: ExtractedImage,
    caption: str,
    figure_type: str,
) -> FigureExtraction:
    """Run the right extractor based on figure_type, build FigureExtraction."""
    figure_number = extract_figure_number(caption)

    if figure_type == "photo":
        return FigureExtraction(
            figure_id=img.figure_id,
            figure_number=figure_number,
            caption=caption,
            figure_type=figure_type,
            page=img.page,
            image_path=img.image_path,
            summary="",
            detail="",
            raw_ocr=None,
            extraction_method="skipped",
            extraction_model=None,
        )

    summary = ""
    detail = ""
    raw_ocr = None
    method = "skipped"
    model = None

    try:
        if figure_type in VLM_TYPES:
            summary, detail, model = extract_with_vlm(
                image_path=img.image_path,
                figure_type=figure_type,
                caption=caption or f"Gambar pada halaman {img.page}",
            )
            method = "vlm"
        elif figure_type in OCR_TYPES:
            summary, detail, raw_ocr = extract_table_with_ocr(
                image_path=img.image_path,
                caption=caption or f"Tabel pada halaman {img.page}",
            )
            method = "ocr"
    except Exception as e:
        logger.warning(f"Extraction failed for {img.figure_id} ({figure_type}): {e}")
        method = "failed"

    return FigureExtraction(
        figure_id=img.figure_id,
        figure_number=figure_number,
        caption=caption,
        figure_type=figure_type,
        page=img.page,
        image_path=img.image_path,
        summary=summary,
        detail=detail,
        raw_ocr=raw_ocr,
        extraction_method=method,
        extraction_model=model,
    )


def process_figures(
    pdf_path: Path,
    marker_md: str,
    output_dir: Path,
    use_cache: bool = True,
) -> List[FigureExtraction]:
    """Extract & process all figures from a PDF.

    output_dir: where extracted PNGs + figures.json sidecar are saved.
    Returns one FigureExtraction per image, including skipped photos.
    """
    pdf_path = Path(pdf_path)
    output_dir = Path(output_dir)
    cache_path = output_dir / CACHE_FILENAME

    cached = load_cache(cache_path) if use_cache else []
    cache_by_hash = {}
    for c in cached:
        if c.image_path.exists():
            cache_by_hash[image_hash(c.image_path)] = c

    images = extract_images_from_pdf(pdf_path, output_dir=output_dir)
    logger.info(f"Processing {len(images)} extracted images")

    results: List[FigureExtraction] = []
    for img in images:
        h = image_hash(img.image_path)
        if h in cache_by_hash:
            logger.debug(f"Cache hit: {img.figure_id}")
            results.append(cache_by_hash[h])
            continue

        idx = _image_idx_from_id(img.figure_id)
        caption = find_caption_for_image(
            markdown=marker_md,
            page=img.page,
            image_index=idx,
        )
        figure_type = classify(caption, (img.width, img.height))
        logger.info(f"  {img.figure_id} → {figure_type} (caption: {caption[:60]!r})")

        extraction = _build_extraction(img, caption, figure_type)
        results.append(extraction)

    save_cache(cache_path, results)
    return results
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && venv/Scripts/python -m pytest tests/test_figure_processor.py -v`
Expected: PASS, 2 tests

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/ingestion/figures/processor.py backend/tests/test_figure_processor.py
git commit -m "feat(ingestion): add figure processor orchestrator with caching"
```

---

## Task 9: Update package exports

**Files:**
- Modify: `backend/app/core/ingestion/figures/__init__.py`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/test_figure_types.py — append to existing file

def test_package_exports_processor():
    from app.core.ingestion.figures import process_figures, FigureExtraction
    assert callable(process_figures)
    assert FigureExtraction.__name__ == "FigureExtraction"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && venv/Scripts/python -m pytest tests/test_figure_types.py::test_package_exports_processor -v`
Expected: FAIL — `process_figures` not exported

- [ ] **Step 3: Update package init**

```python
# backend/app/core/ingestion/figures/__init__.py
"""Figure extraction pipeline for SPBE RAG ingestion."""
from app.core.ingestion.figures.types import FigureExtraction, FIGURE_TYPES
from app.core.ingestion.figures.processor import process_figures

__all__ = ["FigureExtraction", "FIGURE_TYPES", "process_figures"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && venv/Scripts/python -m pytest tests/test_figure_types.py -v`
Expected: PASS, 3 tests

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/ingestion/figures/__init__.py backend/tests/test_figure_types.py
git commit -m "feat(ingestion): export process_figures from figures package"
```

---

## Task 10: Chunker integration — inject summary lines

**Files:**
- Modify: `backend/app/core/ingestion/structured_chunker.py`
- Test: `backend/tests/test_chunker_figure_integration.py`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/test_chunker_figure_integration.py
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pathlib import Path
from app.core.ingestion.structured_chunker import (
    inject_figure_summaries,
    make_figure_chunks,
)
from app.core.ingestion.figures.types import FigureExtraction


def _fig(fid, num, ftype, summary, detail, page=26, method="vlm"):
    return FigureExtraction(
        figure_id=fid,
        figure_number=num,
        caption=f"{num}. Caption",
        figure_type=ftype,
        page=page,
        image_path=Path(f"/tmp/{fid}.png"),
        summary=summary,
        detail=detail,
        raw_ocr=None,
        extraction_method=method,
        extraction_model="qwen3-vl:4b" if method == "vlm" else None,
    )


def test_inject_figure_summaries_adds_line_after_caption():
    md = """\
Lorem ipsum dolor sit amet.

Gambar 7. Caption

Paragraf berikutnya.
"""
    figs = [_fig("fig_p026_01", "Gambar 7", "pie_chart",
                 "Bobot: Layanan 45,5%, Manajemen 13%",
                 "Pie chart penuh deskripsi.")]
    out = inject_figure_summaries(md, figs)
    assert "[Gambar 7] Bobot: Layanan 45,5%, Manajemen 13%" in out
    # Original markdown structure preserved
    assert "Lorem ipsum" in out
    assert "Paragraf berikutnya." in out


def test_inject_skips_photos():
    md = "Foto Presiden\n"
    figs = [_fig("fig_p031_01", "", "photo", "", "", method="skipped")]
    out = inject_figure_summaries(md, figs)
    assert out == md  # unchanged


def test_make_figure_chunks_creates_one_chunk_per_extracted_figure():
    figs = [
        _fig("fig_p026_01", "Gambar 7", "pie_chart", "Bobot: ...", "Pie chart...", page=26),
        _fig("fig_p031_01", "", "photo", "", "", page=31, method="skipped"),
        _fig("fig_p046_01", "Tabel 12", "table_image", "Tabel: ...", "Tabel rincian...", page=46, method="ocr"),
    ]
    chunks = make_figure_chunks(
        figs,
        doc_title="Laporan Evaluasi SPBE 2024",
        filename="spbe.pdf",
        doc_type="laporan",
    )

    # Photo skipped — only 2 chunks
    assert len(chunks) == 2

    chart_chunk = next(c for c in chunks if "Gambar 7" in c["text"])
    assert chart_chunk["chunk_type"] == "figure"
    assert "Pie chart" in chart_chunk["text"]
    # document_manager-compatible format — metadata smuggled in standard fields
    assert chart_chunk["context_header"] == "Figure: Gambar 7"
    assert chart_chunk["section"] == "Gambar 7. Caption"  # full caption
    assert chart_chunk["filename"] == "spbe.pdf"
    assert chart_chunk["doc_type"] == "laporan"
    assert chart_chunk["table_context"] == "pie_chart|fig_p026_01|page:26|vlm"

    table_chunk = next(c for c in chunks if "Tabel 12" in c["text"])
    assert "table_image" in table_chunk["table_context"]
    assert "ocr" in table_chunk["table_context"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && venv/Scripts/python -m pytest tests/test_chunker_figure_integration.py -v`
Expected: FAIL — `inject_figure_summaries` and `make_figure_chunks` don't exist

- [ ] **Step 3: Add functions to structured_chunker.py**

Append to end of `backend/app/core/ingestion/structured_chunker.py`:

```python
# ===========================================================================
# Figure pipeline integration
# ===========================================================================

def inject_figure_summaries(markdown: str, figures: "list") -> str:
    """Inject 1-line summary after each figure's caption in markdown.

    For each figure with summary text, finds the caption line in markdown
    and inserts an inline summary line immediately after it. Photos
    (method='skipped') are not injected.

    Returns modified markdown.
    """
    if not figures:
        return markdown

    out = markdown
    for f in figures:
        if f.extraction_method in ("skipped", "failed") or not f.summary:
            continue
        if not f.figure_number:
            continue
        # Match the line starting with "Gambar 7." or "Tabel 7." (escape dots)
        import re
        pattern = re.compile(
            rf"^({re.escape(f.figure_number)}\.[^\n]*)$",
            re.MULTILINE,
        )
        injection = f"\\1\n\n[{f.figure_number}] {f.summary.strip()}"
        out, n = pattern.subn(injection, out, count=1)
        if n == 0:
            # Caption not found — append summary at end
            out += f"\n\n[{f.figure_number}] {f.summary.strip()}\n"
    return out


def make_figure_chunks(
    figures: "list",
    doc_title: str = "",
    filename: str = "",
    doc_type: str = "",
) -> "list":
    """Create chunk dicts (document_manager-compatible format) for each
    successfully-extracted figure.

    Skips photos (extraction_method='skipped') and failed extractions.
    Output shape matches structured_chunks transformed format used by
    DocumentManager.preview_chunks (see save_chunks meta dict).

    Figure-specific metadata smuggled into standard fields:
      - context_header: "Figure: <figure_number>"
      - section:        full caption ("Gambar 7. Grafik Bobot ...")
      - table_context:  "<figure_type>|<figure_id>|page:<n>|<method>"
                        — pipe-delimited for downstream parsing
    """
    chunks = []
    for f in figures:
        if f.extraction_method in ("skipped", "failed"):
            continue
        if not f.detail.strip():
            continue
        text = f"{f.caption}\n\n{f.detail}".strip() if f.caption else f.detail
        fig_num = f.figure_number or "Figure"
        chunks.append({
            "text": text,
            "raw_text": text,
            "context_header": f"Figure: {fig_num}",
            "hierarchy": "",
            "document_title": doc_title,
            "filename": filename,
            "doc_type": doc_type,
            "bab": "",
            "bagian": "",
            "pasal": "",
            "ayat": "",
            "chunk_part": None,
            "chunk_parts_total": None,
            "parent_pasal_text": "",
            "is_parent": True,
            "chunk_type": "figure",
            "section": f.caption,
            "table_context": f"{f.figure_type}|{f.figure_id}|page:{f.page}|{f.extraction_method}",
            "original_table": f.raw_ocr or "",
        })
    return chunks
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && venv/Scripts/python -m pytest tests/test_chunker_figure_integration.py -v`
Expected: PASS, 3 tests

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/ingestion/structured_chunker.py backend/tests/test_chunker_figure_integration.py
git commit -m "feat(ingestion): integrate figure summaries into chunker output"
```

---

## Task 11: Wire figure pipeline into DocumentManager.preview_chunks

**Files:**
- Modify: `backend/app/core/ingestion/document_manager.py`
- Test: smoke import test below + integration via Task 12 reingest

The integration point is `DocumentManager.preview_chunks(doc_id)` at ~line 958, specifically right after `structured_chunks = chunk_document(...)` returns at line 1027 and chunks list is built at line 1063.

- [ ] **Step 1: Add `use_figure_pipeline` parameter to preview_chunks signature**

Locate `def preview_chunks(self, doc_id: str)` at line 958. Change signature to:

```python
def preview_chunks(self, doc_id: str, use_figure_pipeline: bool = False) -> Dict[str, Any]:
```

- [ ] **Step 2: Add helper method `_apply_figure_pipeline`**

Add this NEW method just before `preview_chunks` (around line 957) inside the `DocumentManager` class:

```python
    def _apply_figure_pipeline(
        self,
        pdf_path: Path,
        chunks: List[Dict[str, Any]],
        doc_title: str,
        filename: str,
        doc_type: str,
    ) -> List[Dict[str, Any]]:
        """Run figure extraction pipeline; append figure chunks to existing list.

        Also rewrites Marker markdown with injected summary lines so future
        re-chunks see the enriched text. Idempotent via figures.json cache.
        """
        from app.core.ingestion.figures import process_figures
        from app.core.ingestion.structured_chunker import (
            inject_figure_summaries,
            make_figure_chunks,
        )
        from app.core.ingestion.pdf_processor import DocumentProcessor

        # Locate existing Marker markdown for this PDF
        md_path_str = DocumentProcessor._find_marker_markdown_path(pdf_path.name)
        if not md_path_str:
            md_path_str = DocumentProcessor._find_marker_markdown_path(filename)
        if not md_path_str:
            logger.warning("Figure pipeline skipped: no Marker markdown found")
            return chunks

        md_path = Path(md_path_str)
        output_dir = md_path.parent
        marker_md = md_path.read_text(encoding="utf-8")

        figures = process_figures(
            pdf_path=pdf_path,
            marker_md=marker_md,
            output_dir=output_dir,
            use_cache=True,
        )

        enriched_md = inject_figure_summaries(marker_md, figures)
        if enriched_md != marker_md:
            md_path.write_text(enriched_md, encoding="utf-8")
            logger.info(f"Updated markdown with figure summaries: {md_path}")

        figure_chunks = make_figure_chunks(
            figures,
            doc_title=doc_title,
            filename=filename,
            doc_type=doc_type,
        )
        logger.info(
            f"Figure pipeline: {len(figures)} figures processed, "
            f"{len(figure_chunks)} figure chunks added"
        )
        return chunks + figure_chunks
```

- [ ] **Step 3: Call helper inside preview_chunks**

In `preview_chunks`, locate the line `logger.info(f"Using structured chunker pipeline for document: ...")` at ~line 1061. Right AFTER the `if structured_chunks:` block ends (i.e. after line 1063, but still within the try block at the same indent level), add:

```python
            # Apply figure extraction pipeline (opt-in)
            if use_figure_pipeline and chunks:
                chunks = self._apply_figure_pipeline(
                    pdf_path=file_path,
                    chunks=chunks,
                    doc_title=doc_title,
                    filename=doc["original_filename"],
                    doc_type=detected_type,
                )
```

- [ ] **Step 4: Update save_chunks meta dict to preserve figure metadata**

Locate `save_chunks` at line 748. Inside the meta dict at lines 765-783, add this line just before the closing `}`:

```python
                    # additional metadata (figure pipeline + future use)
                    "table_context": chunk.get("table_context", ""),
```

(Note: `table_context` is already there at line 778. No change needed if already present. Just verify.)

- [ ] **Step 5: Smoke test the wiring**

Run:
```bash
cd backend && venv/Scripts/python -c "
from app.core.ingestion.document_manager import DocumentManager
m = DocumentManager()
assert hasattr(m, '_apply_figure_pipeline')
import inspect
sig = inspect.signature(m.preview_chunks)
assert 'use_figure_pipeline' in sig.parameters
print('OK: preview_chunks(use_figure_pipeline=...) and _apply_figure_pipeline available')
"
```
Expected: `OK: preview_chunks(use_figure_pipeline=...) and _apply_figure_pipeline available`

- [ ] **Step 6: Commit**

```bash
git add backend/app/core/ingestion/document_manager.py
git commit -m "feat(ingestion): wire figure pipeline into DocumentManager.preview_chunks (opt-in)"
```

---

## Task 12: Reingest script

**Files:**
- Create: `backend/scripts/reingest_doc.py`

This script uses the existing `DocumentManager.preview_chunks(use_figure_pipeline=True)` + `save_chunks` + `index_document` methods.

- [ ] **Step 1: Implement script**

```python
# backend/scripts/reingest_doc.py
#!/usr/bin/env python3
"""Re-process a single document with the figure extraction pipeline.

This calls DocumentManager.preview_chunks(use_figure_pipeline=True) which:
  1. Re-extracts text via Marker
  2. Runs figure extraction (PyMuPDF + classifier + VLM/OCR)
  3. Appends figure chunks to the chunk list
Then save_chunks() persists to SQLite, and index_document() refreshes Qdrant + BM25.

Prerequisites:
  - Ollama running with qwen3-vl:4b model pulled
  - Qdrant running on localhost:6333
  - Document already exists in DB (was ingested before)

Usage:
    python scripts/reingest_doc.py --doc-id 1
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

from loguru import logger


def main():
    parser = argparse.ArgumentParser(description="Re-ingest one document with figure pipeline")
    parser.add_argument("--doc-id", required=True, help="Document ID (numeric) in SQLite")
    args = parser.parse_args()

    from app.core.ingestion.document_manager import get_document_manager
    manager = get_document_manager()

    doc = manager.get_document(args.doc_id)
    if not doc:
        logger.error(f"Doc id {args.doc_id} not found")
        sys.exit(1)

    logger.info(f"Re-ingesting doc {args.doc_id}: {doc.get('original_filename')}")

    # Step 1: preview chunks with figure pipeline
    preview = manager.preview_chunks(args.doc_id, use_figure_pipeline=True)
    chunks = preview.get("chunks", [])
    figure_chunks = [c for c in chunks if c.get("chunk_type") == "figure"]
    logger.info(f"Generated {len(chunks)} chunks total, {len(figure_chunks)} figure chunks")

    # Step 2: save chunks (replaces existing)
    saved = manager.save_chunks(args.doc_id, chunks)
    logger.info(f"Saved {saved} chunks to SQLite")

    # Step 3: index in Qdrant + BM25
    result = manager.index_document(args.doc_id)
    logger.success(f"Indexing result: {result}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify preview_chunks returns dict with 'chunks' key**

Run:
```bash
grep -n "return\s*{.*chunks" backend/app/core/ingestion/document_manager.py | head -5
```
Expected: shows return statement at end of preview_chunks. If the key is different (e.g. `"preview_chunks"` instead of `"chunks"`), update the script accordingly.

- [ ] **Step 3: Smoke run**

Pre-check Ollama:
```bash
curl -s http://localhost:11434/api/tags | python -c "import json,sys; m=[x['name'] for x in json.load(sys.stdin)['models']]; print('qwen3-vl:4b' in m)"
```
Expected: `True` (pull with `ollama pull qwen3-vl:4b` if False)

Then:
```bash
cd backend && venv/Scripts/python scripts/reingest_doc.py --doc-id 1
```
Expected: takes 5-15 minutes for VLM calls; ends with success log.

- [ ] **Step 4: Commit**

```bash
git add backend/scripts/reingest_doc.py
git commit -m "feat(scripts): add reingest_doc.py for figure pipeline re-processing"
```

---

## Task 13: Update evaluate_rag.py default model

**Files:**
- Modify: `backend/scripts/evaluate_rag.py:42`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/test_eval_default_model.py
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import importlib.util
from pathlib import Path

def test_evaluate_rag_default_model_is_qwen3_5_4b():
    spec = importlib.util.spec_from_file_location(
        "evaluate_rag",
        Path(__file__).parent.parent / "scripts" / "evaluate_rag.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.DEFAULT_MODEL == "qwen3.5:4b"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && venv/Scripts/python -m pytest tests/test_eval_default_model.py -v`
Expected: FAIL — `DEFAULT_MODEL == "qwen2.5:7b-instruct"`

- [ ] **Step 3: Update DEFAULT_MODEL**

In `backend/scripts/evaluate_rag.py`, change:

```python
DEFAULT_MODEL = "qwen2.5:7b-instruct"
```

to:

```python
DEFAULT_MODEL = "qwen3.5:4b"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && venv/Scripts/python -m pytest tests/test_eval_default_model.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/scripts/evaluate_rag.py backend/tests/test_eval_default_model.py
git commit -m "fix(eval): use production chatbot model qwen3.5:4b for answer generation"
```

---

## Task 14: Add 15 figure-specific ground truth questions

**Files:**
- Modify: `backend/data/ground_truth.json`

- [ ] **Step 1: Read existing GT to find next id**

Run:
```bash
cd backend && venv/Scripts/python -c "
import json
gt = json.load(open('data/ground_truth.json', encoding='utf-8'))
print('Total:', len(gt))
print('Last id:', gt[-1]['id'])
"
```
Expected: `Total: 40, Last id: gt_040` (or similar — note the count and last id)

- [ ] **Step 2: Append 15 figure-specific entries**

Append to `backend/data/ground_truth.json` (insert before the closing `]` of the JSON array):

```json
,
{
  "id": "gt_041",
  "source_doc": "20250313_Laporan_Pelaksanaan_Evaluasi_SPBE_2024.pdf",
  "doc_type": "laporan",
  "question": "Berapa bobot Domain Layanan SPBE dalam penilaian Indeks SPBE?",
  "ground_truth": "Bobot Domain Layanan SPBE adalah 45,5%, merupakan bobot terbesar dari 4 domain SPBE."
},
{
  "id": "gt_042",
  "source_doc": "20250313_Laporan_Pelaksanaan_Evaluasi_SPBE_2024.pdf",
  "doc_type": "laporan",
  "question": "Berapa bobot Domain Manajemen SPBE dalam penilaian Indeks SPBE?",
  "ground_truth": "Bobot Domain Manajemen SPBE adalah 13%, merupakan bobot terkecil dari 4 domain SPBE."
},
{
  "id": "gt_043",
  "source_doc": "20250313_Laporan_Pelaksanaan_Evaluasi_SPBE_2024.pdf",
  "doc_type": "laporan",
  "question": "Apa kriteria Tingkat Kematangan Optimum dalam kapabilitas proses SPBE?",
  "ground_truth": "Tingkat Optimum: kriteria Tingkat Terpadu dan Terukur telah terpenuhi, dan proses penerapan SPBE telah dilakukan peningkatan kualitas secara berkesinambungan berdasarkan hasil reviu dan evaluasi."
},
{
  "id": "gt_044",
  "source_doc": "20250313_Laporan_Pelaksanaan_Evaluasi_SPBE_2024.pdf",
  "doc_type": "laporan",
  "question": "Pada tingkat kematangan kapabilitas proses berapa SPBE diukur kontribusinya pada kinerja organisasi?",
  "ground_truth": "Pada Tingkat 4 (Terpadu dan Terukur): proses penerapan SPBE yang terpadu telah berkontribusi pada kinerja organisasi dan dapat diukur melalui kegiatan reviu dan evaluasi."
},
{
  "id": "gt_045",
  "source_doc": "20250313_Laporan_Pelaksanaan_Evaluasi_SPBE_2024.pdf",
  "doc_type": "laporan",
  "question": "Apa kriteria Tingkat Kematangan Layanan SPBE pada level Transaksi?",
  "ground_truth": "Tingkat Transaksi: kriteria Tingkat Interaksi telah terpenuhi, dan layanan SPBE diberikan melalui satu kesatuan transaksi operasi dengan menggunakan beberapa sumber daya SPBE, mencakup validasi data, analitik data, dan mekanisme persetujuan."
},
{
  "id": "gt_046",
  "source_doc": "20250313_Laporan_Pelaksanaan_Evaluasi_SPBE_2024.pdf",
  "doc_type": "laporan",
  "question": "Bagaimana hierarki Struktur Penilaian Tingkat Kematangan SPBE?",
  "ground_truth": "Struktur penilaian SPBE terdiri atas 3 level: (1) domain — area penerapan SPBE yang dinilai; (2) aspek — area spesifik dalam domain; (3) indikator — informasi spesifik dari aspek yang dinilai. Sebuah domain terdiri dari satu atau beberapa aspek, dan sebuah aspek terdiri dari beberapa indikator."
},
{
  "id": "gt_047",
  "source_doc": "20250313_Laporan_Pelaksanaan_Evaluasi_SPBE_2024.pdf",
  "doc_type": "laporan",
  "question": "Berapa bobot Aspek Penerapan Manajemen SPBE?",
  "ground_truth": "Bobot Aspek Penerapan Manajemen SPBE adalah 12%."
},
{
  "id": "gt_048",
  "source_doc": "20250313_Laporan_Pelaksanaan_Evaluasi_SPBE_2024.pdf",
  "doc_type": "laporan",
  "question": "Mana yang lebih besar bobotnya antara Aspek Layanan Administrasi Pemerintahan dan Aspek Layanan Publik berbasis Elektronik?",
  "ground_truth": "Aspek Layanan Administrasi Pemerintahan Berbasis Elektronik mempunyai bobot 27,5%, lebih besar dari Aspek Layanan Publik Berbasis Elektronik yang berbobot 18%."
},
{
  "id": "gt_049",
  "source_doc": "20250313_Laporan_Pelaksanaan_Evaluasi_SPBE_2024.pdf",
  "doc_type": "laporan",
  "question": "Berapa nilai Indeks SPBE Nasional pada tahun 2018?",
  "ground_truth": "Nilai Indeks SPBE Nasional pada tahun 2018 adalah 1,98."
},
{
  "id": "gt_050",
  "source_doc": "20250313_Laporan_Pelaksanaan_Evaluasi_SPBE_2024.pdf",
  "doc_type": "laporan",
  "question": "Pada tahun berapa Indeks SPBE Nasional pertama kali melampaui nilai 3?",
  "ground_truth": "Tahun 2024 adalah pertama kalinya Indeks SPBE Nasional mencapai nilai di atas 3, yaitu 3,12."
},
{
  "id": "gt_051",
  "source_doc": "20250313_Laporan_Pelaksanaan_Evaluasi_SPBE_2024.pdf",
  "doc_type": "laporan",
  "question": "Berapa target peringkat EGDI Indonesia pada periode 2025-2029 dan 2045?",
  "ground_truth": "Indonesia menargetkan masuk ke dalam 50 besar peringkat EGDI pada periode 2025-2029 dan 20 besar pada 2045."
},
{
  "id": "gt_052",
  "source_doc": "20250313_Laporan_Pelaksanaan_Evaluasi_SPBE_2024.pdf",
  "doc_type": "laporan",
  "question": "Siapa saja anggota Tim Koordinasi SPBE Nasional?",
  "ground_truth": "Tim Koordinasi SPBE Nasional terdiri dari Kementerian PPN/Bappenas, Kementerian Kominfo, Kementerian Keuangan, Kementerian Dalam Negeri, Badan Siber dan Sandi Negara (BSSN), dan Badan Riset dan Inovasi Nasional (BRIN)."
},
{
  "id": "gt_053",
  "source_doc": "20250313_Laporan_Pelaksanaan_Evaluasi_SPBE_2024.pdf",
  "doc_type": "laporan",
  "question": "Domain mana yang mencapai indeks tertinggi pada Indeks SPBE Nasional 2024?",
  "ground_truth": "Domain Layanan mencapai indeks tertinggi pada tahun 2024 dengan skor 3,78."
},
{
  "id": "gt_054",
  "source_doc": "20250313_Laporan_Pelaksanaan_Evaluasi_SPBE_2024.pdf",
  "doc_type": "laporan",
  "question": "Bagaimana tren capaian Domain Manajemen SPBE Nasional dari 2021 hingga 2024?",
  "ground_truth": "Capaian Domain Manajemen SPBE Nasional menunjukkan tren peningkatan dari 1,23 (2021), 1,32 (2022), 1,66 (2023), hingga 1,86 (2024). Domain ini konsisten berada di posisi terendah dibanding domain lainnya."
},
{
  "id": "gt_055",
  "source_doc": "20250313_Laporan_Pelaksanaan_Evaluasi_SPBE_2024.pdf",
  "doc_type": "laporan",
  "question": "Berapa banyak Instansi Pusat dan Pemerintah Daerah yang dievaluasi dalam Evaluasi SPBE 2024?",
  "ground_truth": "Evaluasi SPBE 2024 dilaksanakan terhadap 615 IPPD yang terdiri dari 92 Instansi Pusat dan 523 Pemerintah Daerah."
}
```

- [ ] **Step 2 (continued): Verify JSON is valid**

Run:
```bash
cd backend && venv/Scripts/python -c "
import json
gt = json.load(open('data/ground_truth.json', encoding='utf-8'))
print(f'Total: {len(gt)}')
print(f'Last 3 ids: {[g[chr(34)+chr(105)+chr(100)+chr(34)] for g in gt[-3:]]}')
new_questions = [g for g in gt if g['id'].startswith('gt_04') or g['id'].startswith('gt_05')]
assert len(new_questions) == 15, f'expected 15 figure GT, got {len(new_questions)}'
print('OK: 15 figure-specific GT added')
"
```
Expected: `Total: 55`, `OK: 15 figure-specific GT added`

- [ ] **Step 3: Commit**

```bash
git add backend/data/ground_truth.json
git commit -m "test(eval): add 15 figure-specific ground truth for SPBE 2024 audit"
```

---

## Task 15: RAGAS report comparison script

**Files:**
- Create: `backend/scripts/compare_ragas_reports.py`

- [ ] **Step 1: Implement script**

```python
# backend/scripts/compare_ragas_reports.py
#!/usr/bin/env python3
"""Compare two RAGAS evaluation reports and print delta.

Usage:
    python scripts/compare_ragas_reports.py data/eval_baseline.json data/eval_after.json
"""
import argparse
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")


METRICS = ["faithfulness", "answer_relevancy", "context_precision", "context_recall"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("baseline", help="Path to baseline RAGAS report JSON")
    parser.add_argument("after", help="Path to post-change RAGAS report JSON")
    parser.add_argument("--threshold", type=float, default=0.0,
                        help="Min delta to flag (default: 0.0 = any change)")
    args = parser.parse_args()

    baseline = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
    after = json.loads(Path(args.after).read_text(encoding="utf-8"))

    print("=" * 70)
    print(f"RAGAS Report Comparison")
    print(f"  Baseline: {args.baseline}  ({baseline.get('total_evaluated')} questions)")
    print(f"  After:    {args.after}  ({after.get('total_evaluated')} questions)")
    print("=" * 70)
    print()
    print(f"{'Metric':<22} {'Baseline':>10} {'After':>10} {'Delta':>10} {'Status':>10}")
    print("-" * 70)

    regressions = 0
    for m in METRICS:
        b = baseline.get("averages", {}).get(m)
        a = after.get("averages", {}).get(m)
        if b is None or a is None:
            print(f"{m:<22} {'-':>10} {'-':>10} {'-':>10}")
            continue
        delta = a - b
        if delta > 0.001:
            status = "↑ improve"
        elif delta < -0.05:
            status = "❌ REGRESS"
            regressions += 1
        elif delta < -0.001:
            status = "↓ minor"
        else:
            status = "= same"
        print(f"{m:<22} {b:>10.4f} {a:>10.4f} {delta:>+10.4f} {status:>10}")

    print()
    # Per-question breakdown for figure GT (gt_041 onwards)
    after_pq = {pq["id"]: pq for pq in after.get("per_question", [])}
    figure_ids = [pid for pid in after_pq if pid.startswith("gt_04") or pid.startswith("gt_05")]
    if figure_ids:
        print(f"Figure-specific GT ({len(figure_ids)} questions):")
        passed = 0
        for fid in sorted(figure_ids):
            pq = after_pq[fid]
            faith = pq["scores"].get("faithfulness", 0)
            mark = "✓" if faith >= 0.7 else "✗"
            if faith >= 0.7:
                passed += 1
            print(f"  {mark} {fid}: faithfulness={faith:.3f}  Q: {pq['question'][:60]}")
        print(f"\nFigure GT pass rate: {passed}/{len(figure_ids)} (target: ≥10/15)")

    print()
    if regressions > 0:
        print(f"❌ FAIL: {regressions} metric(s) regressed > 0.05")
        sys.exit(1)
    print("✅ No regressions exceeding threshold")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Smoke test the script**

Run:
```bash
cd backend && venv/Scripts/python scripts/compare_ragas_reports.py --help
```
Expected: shows argparse help

- [ ] **Step 3: Commit**

```bash
git add backend/scripts/compare_ragas_reports.py
git commit -m "feat(scripts): add RAGAS report comparison utility"
```

---

## Task 16: End-to-end validation run

**Files:** none (execution only)

This task runs the full validation pipeline. Each step is a manual execution + observation.

- [ ] **Step 1: Verify Ollama VLM is available**

Run:
```bash
curl -s http://localhost:11434/api/tags | python -c "import json,sys; m=[x['name'] for x in json.load(sys.stdin)['models']]; assert 'qwen3-vl:4b' in m; print('OK: qwen3-vl:4b available')"
```
Expected: `OK: qwen3-vl:4b available`

If missing: `ollama pull qwen3-vl:4b`

- [ ] **Step 2: Capture baseline (current pipeline, no figure extraction)**

```bash
cd backend
venv/Scripts/python scripts/evaluate_rag.py --phase collect
venv/Scripts/python scripts/evaluate_ragas.py --sample 5
cp data/eval_ragas_report.json data/eval_baseline_sample5.json
```
Expected: `eval_baseline_sample5.json` created with averages for 5 questions.

- [ ] **Step 3: Re-ingest SPBE 2024 with figure pipeline**

```bash
cd backend
venv/Scripts/python scripts/reingest_doc.py --doc-id 1
```
Expected: Logs show "Extracted N images", "process figures", "Figure pipeline: N figures processed". Takes 5-15 minutes for VLM calls.

- [ ] **Step 4: Run RAGAS evaluation on combined GT (40 + 15 = 55 questions)**

```bash
cd backend
venv/Scripts/python scripts/evaluate_rag.py --phase collect
venv/Scripts/python scripts/evaluate_ragas.py
cp data/eval_ragas_report.json data/eval_after.json
```
Expected: 55 questions evaluated; report saved.

- [ ] **Step 5: Compare baseline vs after**

```bash
cd backend
venv/Scripts/python scripts/compare_ragas_reports.py data/eval_baseline_sample5.json data/eval_after.json
```
Expected output (target):
- No metric regression > 0.05 on the 40 existing GT
- Figure GT pass rate ≥ 10/15 with faithfulness ≥ 0.7
- Script exits with status 0 (no regressions)

- [ ] **Step 6: Document results**

Create `data/eval_figure_pipeline_results.md` with:
- Date of run
- Baseline vs after table from comparison script
- Per-figure pass/fail
- Manual review notes on figure summary accuracy (target: 80%+ accurate)

- [ ] **Step 7: Final commit**

```bash
git add backend/data/eval_baseline_sample5.json backend/data/eval_after.json backend/data/eval_figure_pipeline_results.md
git commit -m "test(eval): figure pipeline POC validation results — SPBE 2024"
```

---

## Definition of Done

- [ ] All 15 tasks above complete
- [ ] All tests pass: `cd backend && venv/Scripts/python -m pytest tests/ -v` — green
- [ ] 16+ figures from SPBE 2024 extracted and indexed
- [ ] Figure GT pass rate ≥10/15 with faithfulness ≥ 0.7
- [ ] No regression > 0.05 on existing 40 GT metrics
- [ ] Sidecar `figures.json` allows re-chunking without re-extraction
- [ ] Manual review: 80%+ figure summaries factually accurate
