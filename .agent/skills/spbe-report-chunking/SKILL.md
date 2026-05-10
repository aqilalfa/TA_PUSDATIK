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
