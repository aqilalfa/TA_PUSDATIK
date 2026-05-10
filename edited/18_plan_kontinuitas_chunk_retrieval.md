# 18 - Plan Kontinuitas Chunk Retrieval (Quick Win)

Tanggal: 2026-04-19
Status: Planned -> Execution in progress
Scope: Quick Win sesuai keputusan user

## Tujuan
Meningkatkan kesinambungan konteks antar chunk pada alur retrieval dan tampilan UI tanpa refactor besar atau re-ingest massal.

## Masalah Utama
1. Chunk yang dipilih retrieval kadang berdiri sendiri tanpa tetangga konteks.
2. Informasi parent_pasal_text belum dimanfaatkan optimal saat format konteks ke LLM.
3. Metadata continuity (hierarchy, chunk_part, chunk_parts_total) belum konsisten dibawa lintas layer.
4. UI detail dokumen menampilkan chunk secara flat sehingga hubungan antar bagian kurang terlihat.

## Strategi Quick Win

### A. Backend Retrieval Continuity
- Tambahkan neighbor expansion pada hasil retrieval utama berbasis doc_id + chunk_index (ambil i-1 dan i+1).
- Terapkan context stitching agar potongan berurutan digabung secara lebih natural sebelum diprompt ke LLM.
- Gunakan parent_pasal_text jika tersedia untuk memperkuat konteks ayat.

### B. Metadata Continuity End-to-End
- Pastikan field berikut konsisten dari chunker -> DB -> API -> Qdrant:
  - hierarchy
  - chunk_part
  - chunk_parts_total
- Expose field continuity tersebut di endpoint chunks untuk kebutuhan UI.

### C. UI Continuity di Document Detail
- Stabilkan sorting dengan tie-break chunk_part setelah chunk_index.
- Tampilkan indikator parent chunk dan part chunk (Bagian n/m) bila tersedia.
- Jaga agar label ayat tidak terduplikasi jika value sudah berprefix.

## File Target
1. backend/app/core/rag/langchain_engine.py
2. backend/app/core/ingestion/document_manager.py
3. backend/app/api/documents.py
4. frontend/src/views/DocumentDetailView.vue

## Checklist Eksekusi
- [ ] Patch retrieval continuity (neighbor + stitching)
- [ ] Patch parent context enrichment
- [ ] Patch metadata propagation ke DB/API/Qdrant
- [ ] Patch UI continuity rendering + sorting
- [ ] Verifikasi smoke_check dan uji retrieval stream
- [ ] Verifikasi tampilan /documents dan /documents/:doc_id

## Kriteria Sukses
1. Jawaban untuk query regulasi beruntun tidak lagi terkesan terpotong di batas chunk.
2. Metadata continuity tersedia di API chunks dan tampil di UI detail dokumen.
3. Tidak ada regresi pada endpoint utama dan startup stack.

## Verifikasi Akhir
1. smoke_check.bat --json lulus semua check.
2. GET /api/documents/{doc_id}/chunks menampilkan chunk_part/chunk_parts_total/hierarchy.
3. POST /api/chat/stream memunculkan retrieval event dan jawaban lebih koheren antar bagian.
4. UI Document Detail memperlihatkan urutan chunk yang stabil dan indikator continuity.
