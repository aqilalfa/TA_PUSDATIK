# SPBE Report Chunking Implementation Plan

> **For Antigravity:** REQUIRED WORKFLOW: Use `.agent/workflows/execute-plan.md` to execute this plan in single-flow mode.

**Goal:** Isolate SPBE Evaluation reports into Entity-Centric text chunks and inject 2023/2024 metric data heavily into the vector metadata without affecting other regulatory documents.

**Architecture:** Create a specialized `LaporanSPBEChunker` class and route all documents with `type == "laporan_spbe"` to it inside `structured_chunker.py`. This ensures perfect isolation from legal documents.

**Tech Stack:** Python, Pytest

---

### Task 1: Setup Worktree

**Files:**
- Worktree creation

**Step 1: Create isolated environment**
Run: `git diff` to ensure working tree is clean.
Run: `git branch -D feature/spbe-report-chunking` (ignore error if it doesn't exist).
Run: `git worktree add ~/.config/superpowers/worktrees/pusdatik/spbe-report-chunking -b feature/spbe-report-chunking`
Expected: Worktree created successfully.

**Step 2: Change directory**
Execute the rest of the plan from `~/.config/superpowers/worktrees/pusdatik/spbe-report-chunking`.

### Task 2: Create Agent Skill Document

**Files:**
- Create: `.agent/skills/spbe-report-chunking/SKILL.md`

**Step 1: Create the file**
Write the following content to `.agent/skills/spbe-report-chunking/SKILL.md`:
```markdown
---
name: spbe-report-chunking
description: Use when chunking or parsing "Laporan Evaluasi SPBE" to maintain Entity-Centric patterns and strict metadata injection.
---

# SPBE Report Chunking Protocol

## Overview
Laporan Evaluasi SPBE (SPBE Audit Reports) are structured differently from legal documents (UU/PP/SE). They contain arrays of `data_capaian_instansi`. We must parse these using an **Entity-Centric Chunking** strategy combined with **Metadata Injection**.

## Rules for Chunking SPBE Reports
1. **Routing Isolation:** Documents tagged with `"type": "laporan_spbe"` MUST bypass the standard `MarkdownChunker` and use `LaporanSPBEChunker`.
2. **One Chunk Per Agency:** Each object inside `data_capaian_instansi` becomes exactly ONE chunk.
3. **Chunk Content Format:**
   `Laporan Pelaksanaan Evaluasi SPBE Tahun {Tahun}. Instansi: {Nama Instansi} ({Jenis Instansi}, Kategori Wilayah: {Kategori}). Indeks SPBE Akhir: {Indeks} (Predikat: {Predikat}). Rincian Nilai Domain: Kebijakan Internal ({Nilai}), Tata Kelola ({Nilai}), Manajemen SPBE ({Nilai}), Layanan SPBE ({Nilai}).`
4. **Metadata Injection:** The payload MUST include:
   - `doc_type`: "laporan_spbe"
   - `tahun_evaluasi`: (from metadata_dokumen)
   - `nama_instansi`: (exact string)
   - `jenis_instansi`: (e.g., Kementerian)
   - `indeks_spbe`: (float)
   - `predikat`: (string)

This ensures zero cross-contamination with legal documents while providing 100% accurate RAG retrieval for cross-year index comparisons.
```

**Step 2: Commit**
Run: `git add .agent/skills/spbe-report-chunking/SKILL.md`
Run: `git commit -m "docs(agent): add spbe-report-chunking skill"`

### Task 3: Write Failing Test for SPBE Chunker

**Files:**
- Create: `backend/tests/test_spbe_chunker.py`

**Step 1: Write the failing test**
Create `backend/tests/test_spbe_chunker.py`:
```python
import pytest
from app.core.ingestion.structured_chunker import DocumentChunker

def test_laporan_spbe_chunking():
    mock_json = {
        "type": "laporan_spbe",
        "metadata_dokumen": {
            "tahun_evaluasi": "2024",
            "penerbit": "Kementerian PANRB"
        },
        "data_capaian_instansi": [
            {
                "nama_instansi": "Badan Kepegawaian Negara",
                "jenis_instansi": "Kementerian",
                "kategori_wilayah": "Nasional",
                "skor_domain": {
                    "kebijakan_internal": 4.4,
                    "tata_kelola": 4.0,
                    "manajemen_spbe": 3.55,
                    "layanan_spbe": 4.19
                },
                "indeks_spbe_akhir": 4.06,
                "predikat": "Sangat Baik"
            }
        ]
    }
    
    chunker = DocumentChunker()
    chunks = chunker.chunk_document(mock_json)
    
    # We expect 1 chunk for the agency (we can ignore ringkasan for now or expect 1 total)
    # The minimum required is that the agency is extracted as a specific chunk
    agency_chunks = [c for c in chunks if c.get("metadata", {}).get("doc_type") == "laporan_spbe"]
    assert len(agency_chunks) == 1
    
    chunk = agency_chunks[0]
    assert "Badan Kepegawaian Negara" in chunk["text"]
    assert "4.06" in chunk["text"]
    assert "Sangat Baik" in chunk["text"]
    
    # Check Metadata Injection
    assert chunk["metadata"]["tahun_evaluasi"] == "2024"
    assert chunk["metadata"]["nama_instansi"] == "Badan Kepegawaian Negara"
    assert chunk["metadata"]["indeks_spbe"] == 4.06
```

**Step 2: Verify test fails**
Run: `pytest backend/tests/test_spbe_chunker.py -v`
Expected: FAIL (because `DocumentChunker` currently does not properly route or generate the required metadata for `laporan_spbe`).

**Step 3: Commit**
Run: `git add backend/tests/test_spbe_chunker.py`
Run: `git commit -m "test: add failing test for laporan_spbe routing and chunking"`

### Task 4: Implement LaporanSPBEChunker

**Files:**
- Modify: `backend/app/core/ingestion/structured_chunker.py`

**Step 1: Write implementation**
Modify `structured_chunker.py` to add the new logic and route it. Look for `class DocumentChunker:` and its `chunk_document` method. Add the routing logic for `laporan_spbe`:

```python
    def chunk_document(self, parsed_json: dict) -> list[dict]:
        """Main entry point for chunking a parsed document."""
        doc_type = parsed_json.get("type", "peraturan")
        
        if doc_type == "laporan_spbe":
            return self._chunk_laporan_spbe(parsed_json)
            
        # ... existing logic for peraturan / pedoman ...
```

Add the private method `_chunk_laporan_spbe`:
```python
    def _chunk_laporan_spbe(self, parsed_json: dict) -> list[dict]:
        chunks = []
        tahun = parsed_json.get("metadata_dokumen", {}).get("tahun_evaluasi", "")
        
        for instansi in parsed_json.get("data_capaian_instansi", []):
            nama = instansi.get("nama_instansi", "")
            jenis = instansi.get("jenis_instansi", "")
            kategori = instansi.get("kategori_wilayah", "")
            indeks = instansi.get("indeks_spbe_akhir", 0.0)
            predikat = instansi.get("predikat", "")
            skor = instansi.get("skor_domain", {})
            
            text = (
                f"Laporan Pelaksanaan Evaluasi SPBE Tahun {tahun}. "
                f"Instansi: {nama} ({jenis}, Kategori Wilayah: {kategori}). "
                f"Indeks SPBE Akhir: {indeks} (Predikat: {predikat}). "
                f"Rincian Nilai Domain: Kebijakan Internal ({skor.get('kebijakan_internal', 0)}), "
                f"Tata Kelola ({skor.get('tata_kelola', 0)}), "
                f"Manajemen SPBE ({skor.get('manajemen_spbe', 0)}), "
                f"Layanan SPBE ({skor.get('layanan_spbe', 0)})."
            )
            
            metadata = {
                "doc_type": "laporan_spbe",
                "tahun_evaluasi": tahun,
                "nama_instansi": nama,
                "jenis_instansi": jenis,
                "indeks_spbe": indeks,
                "predikat": predikat
            }
            
            chunks.append({
                "text": text,
                "metadata": metadata
            })
            
        return chunks
```

*(Note for executor: You may need to adapt the structure slightly depending on how `DocumentChunker` builds metadata and chunk objects (e.g. `DocumentChunk` object vs `dict`)).*

**Step 2: Verify test passes**
Run: `pytest backend/tests/test_spbe_chunker.py -v`
Expected: PASS

**Step 3: Commit**
Run: `git add backend/app/core/ingestion/structured_chunker.py`
Run: `git commit -m "feat(ingestion): implement specialized chunker for laporan_spbe"`
