---
name: document-chunk-alignment-workflow
description: "Gunakan saat perlu memeriksa kesesuaian dokumen PDF sumber dengan chunk yang tersimpan (SQLite/API) sebelum sinkronisasi atau rebuild vektor."
argument-hint: "Doc ID target atau daftar dokumen yang ingin diaudit"
user-invocable: true
---

# Document-Chunk Alignment Workflow

Skill ini adalah alur standar untuk mengecek apakah isi dokumen asli sudah terwakili dengan benar pada chunk yang dipakai UI/retrieval.

## Kapan Dipakai
- Saat user melihat struktur penting hilang di preview chunk (contoh: BAB I, BAB II, dst).
- Saat hasil retrieval terasa tidak sesuai isi dokumen sumber.
- Sebelum menjalankan full rebuild index vektor.

## Prasyarat
- Backend aktif di `http://localhost:8000`.
- Jalankan command dari folder `backend` dengan interpreter `venv\\Scripts\\python.exe`.

## Input Wajib
1. `doc_id` SQLite dokumen target.
2. Konteks mismatch yang ingin diverifikasi (contoh: "BAB tidak muncul").

## Alur Kerja Standar

### 1) Validasi service dan endpoint
- `curl -s http://localhost:8000/api/health`
- Pastikan endpoint chunk tersedia: `GET /api/documents/{doc_id}/chunks`

### 2) Jalankan audit alignment dokumen
Gunakan script audit:

- `venv\\Scripts\\python.exe scripts\\check_document_chunk_alignment.py --doc-id <DOC_ID>`

Opsional simpan report:

- `venv\\Scripts\\python.exe scripts\\check_document_chunk_alignment.py --doc-id <DOC_ID> --output ..\\data\\evaluation\\alignment_doc_<DOC_ID>.json`

### 3) Interpretasi hasil
Fokus field berikut di output JSON:
- `source_marker_counts`
- `chunk_text_marker_counts`
- `chunk_metadata_non_empty`
- `missing_bab_labels`
- `assessment`

Aturan cepat:
- Jika `source_marker_counts.bab > 0` tetapi `chunk_metadata_non_empty.bab == 0` → mismatch kritis parser/chunker.
- Jika `missing_bab_labels` tidak kosong → mismatch parsial (sebagian struktur hilang).
- Jika `assessment.overall = ok` → chunk representatif, lanjut ke sinkronisasi vektor bila diperlukan.

### 4) Remediasi saat mismatch
Urutan tindakan:
1. Perbaiki parser/chunker (jangan langsung rebuild vektor).
2. Reprocess dokumen target di SQLite.
3. Ulangi audit alignment sampai `assessment.overall = ok`.

### 5) Sinkronisasi vektor setelah data chunk benar
Jika chunk di SQLite sudah benar, jalankan rebuild index:

- `venv\\Scripts\\python.exe scripts\\sync_vectors.py --force`

### 6) Verifikasi pasca-rebuild
- Bandingkan jumlah chunk DB vs jumlah vector Qdrant.
- Uji retrieval/chat untuk pertanyaan yang sebelumnya gagal.

## Output Skill (yang harus dilaporkan)
1. Status alignment dokumen (`ok`, `partial`, `missing`).
2. Bukti mismatch utama (contoh label BAB yang hilang).
3. Tindakan perbaikan yang dijalankan.
4. Hasil akhir pasca-reprocess dan pasca-rebuild.

## Catatan Operasional
- Jangan jalankan full rebuild sebelum memastikan chunk SQLite sudah benar.
- Untuk kasus parser lama vs parser baru, prioritaskan perbaikan parser agar masalah tidak berulang di dokumen lain.
