# Perbaikan Parser 2024 & Penambahan Fitur Ranking Query

> **For Antigravity:** REQUIRED WORKFLOW: Use `.agent/workflows/execute-plan.md` to execute this plan in single-flow mode.

**Goal:** Memperbaiki parser laporan SPBE 2024 agar dapat mengekstrak data capaian instansi dari tabel rekapitulasi, dan menambahkan dukungan *ranking query* agar RAG dapat menjawab pertanyaan nilai "tertinggi/terendah" secara akurat.

**Architecture:** 
1. `json_structure_parser.py` akan dimodifikasi untuk mendeteksi tabel hasil evaluasi (Tabel 9 dst) dalam laporan 2024 dan merestrukturisasinya menjadi *array* `data_capaian_instansi` yang setara dengan laporan 2023.
2. `langchain_engine.py` akan dimodifikasi untuk menambahkan tipe query `ranking`. Jika terdeteksi, *engine* akan melakukan *scroll* dokumen di Qdrant, mengurutkannya berdasarkan `indeks_spbe`, dan menyuntikkan data *top/bottom* ke dalam konteks LLM, sehingga LLM tidak lagi bergantung pada *vector search* untuk menjawab pertanyaan analitik.

**Tech Stack:** Python, Regex, QdrantClient

---

### Task 1: Update Parser untuk Ekstrak Tabel Laporan 2024

**Files:**
- Modify: `backend/app/core/ingestion/json_structure_parser.py`
- Test: `backend/tests/test_parser_2024.py` (Create)

**Step 1: Write the failing test**

```python
import pytest
import os
import json
from app.core.ingestion.json_structure_parser import parse_document

def test_parse_laporan_2024_extracts_capaian():
    # Simulasikan isi markdown Laporan 2024
    md_content = """# Laporan Evaluasi SPBE Tahun 2024
    
Tabel 9. Hasil Evaluasi SPBE Kementerian
| No | Nama Instansi | D1 | D2 | D3 | D4 | Indeks | Predikat |
|---|---|---|---|---|---|---|---|
| 1 | Kementerian A | 4.0 | 3.0 | 2.0 | 4.0 | 3.25 | Baik |
| 2 | Kementerian B | 5.0 | 4.0 | 3.0 | 5.0 | 4.25 | Memuaskan |

Tabel 10. Hasil Evaluasi SPBE Lembaga Pemerintah Non Kementerian (LPNK)
| No | Nama Instansi | D1 | D2 | D3 | D4 | Indeks | Predikat |
|---|---|---|---|---|---|---|---|
| 1 | Badan X | 3.0 | 2.0 | 1.0 | 3.0 | 2.25 | Cukup |
"""
    doc = parse_document(md_content, "Laporan_Evaluasi_SPBE_2024.pdf", "laporan")
    
    assert doc.get("type") == "laporan"
    capaian = doc.get("data_capaian_instansi", [])
    assert len(capaian) == 3
    assert capaian[0]["nama_instansi"] == "Kementerian A"
    assert capaian[0]["indeks_spbe"] == "3.25"
    assert capaian[0]["tahun_evaluasi"] == "2024"
    assert capaian[0]["jenis_instansi"] == "Kementerian"
    
    assert capaian[2]["nama_instansi"] == "Badan X"
    assert capaian[2]["jenis_instansi"] == "Lembaga Pemerintah Non Kementerian (LPNK)"
```

**Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_parser_2024.py -v`
Expected: FAIL (len(capaian) == 0 instead of 3)

**Step 3: Write minimal implementation**

Modify `backend/app/core/ingestion/json_structure_parser.py`:
Tambahkan logika di fungsi `_extract_laporan_metadata` atau setelahnya untuk mem-parsing tabel-tabel evaluasi (Tabel 9 - Tabel 54) menggunakan regex, khusus jika tahun evaluasi adalah 2024 atau jika dokumen memuat "Tabel 9. Hasil Evaluasi SPBE Kementerian".

**Step 4: Run test to verify it passes**

Run: `pytest backend/tests/test_parser_2024.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/core/ingestion/json_structure_parser.py backend/tests/test_parser_2024.py
git commit -m "feat(ingestion): extract capaian instansi from 2024 report tables"
```

### Task 2: Re-ingest Laporan 2024

**Step 1: Execute re-ingestion script**

Run command: `venv/Scripts/python.exe scripts/reingest_single.py "D:\aqil\pusdatik\data\documents\audit\LAPORAN EVALUASI SPBE NASIONAL TAHUN 2024.pdf"`

**Step 2: Verify Qdrant indexing**

Gunakan script `scratch_rank_inspect.py` yang sebelumnya dibuat untuk memastikan bahwa "Tahun 2024" sekarang memiliki data dan chunk *Kementerian* untuk tahun 2024 tidak lagi 0.

### Task 3: Tambahkan Deteksi Ranking Query

**Files:**
- Modify: `backend/app/core/rag/langchain_engine.py`

**Step 1: Modify `classify_query`**

Di dalam `backend/app/core/rag/langchain_engine.py`, modifikasi fungsi `classify_query` untuk mendeteksi *intent* "ranking".

```python
    ranking_patterns = [
        r"\b(?:tertinggi|terendah|peringkat|ranking|top|bottom|urutan)\b",
    ]
    if any(re.search(p, text_lower) for p in ranking_patterns):
        return "ranking"
```

**Step 2: Tambahkan fungsi agregasi Qdrant**

Buat metode privat baru di `LangchainRAGEngine`, misalnya `_get_ranking_context(self, query: str) -> str`, yang akan:
1. Mengidentifikasi tahun dan jenis instansi dari *query* (jika ada).
2. Melakukan *scroll* `document_chunks` di Qdrant yang bertipe `laporan_spbe`.
3. Mengumpulkan nama instansi, indeks SPBE, dan predikat.
4. Mengurutkan berdasarkan indeks SPBE secara numerik.
5. Menghasilkan *string* berisi *Top 10* dan *Bottom 10* untuk disuntikkan ke konteks.

**Step 3: Integrasikan ke `retrieve_context`**

Di dalam `retrieve_context`, tambahkan logika khusus untuk `query_type == "ranking"`. Tambahkan hasil dari `_get_ranking_context` ke bagian atas `context_text`, dan lewati *vector search* standar jika diperlukan, atau gabungkan dengan hasil *vector search* agar mendapat informasi kualitatif lainnya.

**Step 4: Commit**

```bash
git add backend/app/core/rag/langchain_engine.py
git commit -m "feat(rag): add ranking query handler for highest/lowest evaluation scores"
```
