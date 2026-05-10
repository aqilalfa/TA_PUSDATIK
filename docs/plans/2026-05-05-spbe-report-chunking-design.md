# SPBE Evaluation Report Chunking Design

## 1. Objective
Enable 100% accurate, hallucination-free retrieval and cross-year comparison (2023 vs 2024) of SPBE index scores for specific government agencies (Kementerian, LPNK, Pemerintah Daerah).

## 2. Approach: Hybrid Entity-Centric & Metadata Injection (Option A + C)
We will implement a specialized parsing and chunking pipeline strictly for documents identified as `laporan_spbe`. This completely bypasses the standard `MarkdownChunker` used for regulations (UU/PP/SE), ensuring **zero negative impact** on the existing accuracy of legal document retrieval.

### Isolation Strategy (Why it won't break other documents):
- **Routing:** In the chunking logic (e.g., `chunker.py`), we will add a type check:
  ```python
  if parsed_json.get("type") == "laporan_spbe":
      return LaporanSPBEChunker.chunk(parsed_json)
  else:
      # Use the existing chunker for normal documents
      return StandardChunker.chunk(parsed_json)
  ```

### 3. Chunking Implementation Details
For each object inside the `data_capaian_instansi` array:
1. **Text Payload Generation (Entity-Centric)**
   Generate a highly explicit paragraph:
   > "Laporan Pelaksanaan Evaluasi SPBE Tahun {Tahun}. Instansi: {Nama Instansi} ({Jenis Instansi}, Kategori Wilayah: {Kategori}). Indeks SPBE Akhir: {Indeks} (Predikat: {Predikat}). Rincian Nilai Domain: Kebijakan Internal ({Nilai}), Tata Kelola ({Nilai}), Manajemen SPBE ({Nilai}), Layanan SPBE ({Nilai})."
2. **Metadata Injection**
   Inject strict, filterable fields into the Qdrant payload:
   ```json
   {
     "doc_type": "laporan_spbe",
     "tahun_evaluasi": 2024,
     "nama_instansi": "Badan Kepegawaian Negara",
     "jenis_instansi": "Kementerian",
     "indeks_spbe": 4.06,
     "predikat": "Sangat Baik"
   }
   ```

### 4. Implementation Steps
1. **Create Skill Document:** Write `.agent/skills/spbe-report-chunking/SKILL.md` to document the exact payload structure and routing mechanism so the standard is codified.
2. **Refactor Ingestion/Chunker:** Update the backend chunking logic to support the new `LaporanSPBEChunker`.
3. **Database Reingestion:** Run the ingestion pipeline on the 2023 and 2024 PDF/JSON files to populate Qdrant with the new structured chunks.
4. **Retriever Updates (Optional):** If needed, update the retrieval logic (`backend/app/core/retrieval/`) to apply Qdrant payload filters when it detects "Tahun" dan "Instansi" in the user's prompt.
