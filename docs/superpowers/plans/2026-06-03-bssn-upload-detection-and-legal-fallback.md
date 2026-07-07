# BSSN Upload Detection and Legal Fallback Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:test-driven-development for each behavior change. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ensure uploaded PERKA/BSSN regulation PDFs enter the legal parser/chunker path before addressing metadata-losing fallback behavior.

**Architecture:** Apply small, verified fixes in sequence. First unify upload-preview document type detection so BSSN/PERKA documents are classified as `peraturan`; only after that passes, add guardrails for markdown fallback so regulation chunks do not lose Pasal/Ayat metadata.

**Tech Stack:** Python 3.10+, FastAPI ingestion flow, pytest, existing private venv at `backend/venv/`.

---

## Files

- Modify: `backend/app/core/ingestion/document_manager.py`
  - `detect_document_type()` should recognize BSSN/PERKA legal documents as `peraturan`.
- Test: `backend/tests/test_document_ingestion_detection.py`
  - Regression tests for PERKA/BSSN upload-preview classification.
- Later fix #2 candidate: `backend/app/core/ingestion/structured_chunker.py`
  - Prevent replacing structured legal chunks with markdown fallback chunks that have no Pasal/Ayat metadata.

---

## Task 1: Fix upload-preview document type detection for BSSN/PERKA

**Behavior:** `document_manager.detect_document_type()` must return `peraturan` for BSSN/PERKA regulation filenames and content.

- [ ] **Step 1: Write RED tests**

Create `backend/tests/test_document_ingestion_detection.py`:

```python
from app.core.ingestion.document_manager import detect_document_type


def test_detect_document_type_treats_perka_bssn_filename_as_peraturan():
    text = "PERKA BSSN NOMOR 2 TAHUN 2023 TENTANG PENYELENGGARAAN SPBE"

    assert detect_document_type("PERKA_BSSN_NOMOR_2_TAHUN_2023.pdf", text) == "peraturan"


def test_detect_document_type_treats_bssn_pasal_content_as_peraturan():
    text = """
    PERATURAN BADAN SIBER DAN SANDI NEGARA
    NOMOR 2 TAHUN 2023
    BAB I KETENTUAN UMUM
    Pasal 1
    Dalam Peraturan Kepala Badan ini yang dimaksud dengan...
    """

    assert detect_document_type("dokumen_internal.pdf", text) == "peraturan"
```

- [ ] **Step 2: Verify RED**

Run:

```powershell
cd D:\aqil\pusdatik\backend
& "venv\Scripts\python.exe" -m pytest "tests\test_document_ingestion_detection.py" -q
```

Expected: at least the PERKA/BSSN filename/content detection test fails because current detector only recognizes `perpres`, `pp_`, `permen`, `peraturan`, `se_`, and selected non-BSSN regulation phrases.

- [ ] **Step 3: Minimal implementation**

In `backend/app/core/ingestion/document_manager.py`, update `detect_document_type()` only. Add BSSN/PERKA indicators to filename and text checks:

```python
if any(
    kw in filename_lower
    for kw in ["perpres", "pp_", "permen", "peraturan", "se_", "bssn", "perka"]
):
    return "peraturan"
if any(
    kw in text_lower
    for kw in [
        "peraturan presiden",
        "peraturan pemerintah",
        "peraturan menteri",
        "peraturan badan siber dan sandi negara",
        "peraturan kepala badan",
        "perka bssn",
        "badan siber dan sandi negara",
    ]
):
    return "peraturan"
```

- [ ] **Step 4: Verify GREEN**

Run:

```powershell
cd D:\aqil\pusdatik\backend
& "venv\Scripts\python.exe" -m pytest "tests\test_document_ingestion_detection.py" -q
& "venv\Scripts\python.exe" -m py_compile "app\core\ingestion\document_manager.py"
```

Expected: tests pass and compile succeeds.

- [ ] **Step 5: Regression check**

Run:

```powershell
cd D:\aqil\pusdatik\backend
& "venv\Scripts\python.exe" -m pytest "tests\test_context_ids.py" "tests\test_rag_legal_ranker.py" "tests\test_document_ingestion_detection.py" -q
```

Expected: all targeted tests pass.

---

## Task 2: Only after Task 1 passes, guard legal markdown fallback

**Behavior:** If `chunk_document()` produced structured `peraturan` chunks with Pasal/Ayat metadata, markdown fallback must not replace them with `md_fallback` chunks that clear `pasal` and `ayat`.

- [ ] **Step 1: Write RED tests in `backend/tests/test_document_ingestion_detection.py`**

Add a test that constructs a `peraturan` doc with one structured Pasal chunk and a markdown file that would produce more generic chunks. Assert `chunk_document()` keeps the structured legal chunk metadata.

- [ ] **Step 2: Verify RED**

Run the new test and confirm current behavior replaces structured legal chunks if markdown produces more chunks.

- [ ] **Step 3: Minimal implementation**

In `structured_chunker.chunk_document()`, only allow markdown fallback for `peraturan` when the JSON chunks have no legal metadata at all. Keep structured chunks if any chunk has `metadata.pasal` or `metadata.ayat`.

- [ ] **Step 4: Verify GREEN**

Run targeted tests and compile `structured_chunker.py`.

---

## Completion Criteria

- Task 1 tests pass before Task 2 starts.
- No production code is written before its RED test.
- `document_manager.detect_document_type()` classifies PERKA/BSSN uploads as `peraturan`.
- Existing retrieval/evaluator tests remain green.
