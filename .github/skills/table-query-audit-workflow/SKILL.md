---
name: table-query-audit-workflow
description: "Gunakan saat query RAG berfokus pada tabel (mis. Tabel 13, nilai kolom/baris, perbandingan tabel) untuk membedakan masalah data vs masalah retrieval/ranking."
argument-hint: "Pertanyaan tabel yang ingin diuji (contoh: isi Tabel 13 Permenpan RB 59/2020)"
user-invocable: true
---

# Table Query Audit Workflow

Skill ini adalah runbook praktis untuk mengecek kenapa pertanyaan bertipe tabel sering meleset (contoh: query Tabel 13 justru ditarik ke Pasal 13).

## Kapan Dipakai

- Jawaban RAG untuk pertanyaan tabel berkata "tidak ditemukan" padahal tabel ada di dokumen.
- Source citation mengarah ke pasal/ayat yang tidak relevan dengan tabel yang ditanya.
- Ingin memutuskan cepat: perlu reingest data, sync vektor, atau tuning retrieval.

## Referensi

- Standard command repo: `.github/instructions/project-standard-commands.instructions.md`
- Audit dokumen vs chunk: `.github/skills/document-chunk-alignment-workflow/SKILL.md`
- Workflow end-to-end: `.github/skills/spbe-rag-workflow/SKILL.md`

## Input Minimal

1. Pertanyaan tabel utama (contoh: "Pada Permenpan RB 59/2020, apa isi Tabel 13?")
2. Dokumen target (jika diketahui)
3. Ekspektasi minimum jawaban (contoh: menyebut nilai Domain 2/Tata Kelola)

## Prosedur

### 1) Validasi layanan dasar

- Backend health: `GET /api/health`
- Qdrant collection aktif dan point count masuk akal

Jika service belum sehat, selesaikan ini dulu sebelum audit kualitas.

### 2) Validasi data tabel benar-benar ada di chunk SQLite

Gunakan query SQLite `LIKE '%tabel X%'` pada tabel `chunks`.

Tujuan:
- Membuktikan apakah sumber data ada atau memang tidak ada.

Keputusan:
- Jika tidak ada di SQLite: fokus ke parser/chunker/reingest.
- Jika ada di SQLite: lanjut ke audit retrieval.

### 3) Validasi sinkronisasi SQLite vs Qdrant

Jika ada indikasi stale index, jalankan:
- `backend/scripts/sync_vectors.py --force`

Lalu cek ulang `points_count` koleksi target.

### 4) Uji endpoint chat streaming dengan 3 level pertanyaan

Gunakan `POST /api/chat/stream` untuk:

1. Pertanyaan generik tabel
- "Apa isi Tabel 13?"

2. Pertanyaan bertarget dokumen
- "Pada Permenpan RB 59/2020, apa isi Tabel 13?"

3. Pertanyaan nilai konkret tabel
- "Pada tabel perhitungan indeks domain, berapa nilai Domain 2 Tata Kelola?"

Catat output:
- jumlah source
- dokumen/section source teratas
- apakah jawaban menjawab nilai/isi tabel dengan benar

### 5) Diagnosis akar masalah

Klasifikasi hasil:

- Data Missing:
  SQLite tidak mengandung tabel target.

- Index Stale:
  SQLite ada, Qdrant/source chat belum sesuai sampai dilakukan sync/rebuild.

- Retrieval Drift:
  Data ada dan index sinkron, tetapi source dominan salah konteks (mis. Pasal 13 vs Tabel 13).

### 6) Tindakan per kategori

- Data Missing:
  perbaiki parser/chunker, reprocess dokumen target, lalu sync Qdrant.

- Index Stale:
  jalankan sync/rebuild collection.

- Retrieval Drift:
  terapkan table-aware retrieval:
  - query expansion khusus pola `tabel <angka>`
  - metadata/query boost untuk chunk yang memuat `tabel <angka>`
  - penalti ringan untuk chunk pasal saat query tidak meminta pasal

### 7) Periksa metadata `is_table` pada chunk

Setelah retrieval OK, periksa apakah chunk tabel sudah punya metadata `is_table=True`:

```sql
SELECT id, chunk_metadata FROM chunks WHERE chunk_metadata LIKE '%"is_table": true%' LIMIT 10;
```

Jika chunk tabel tidak punya flag ini, jalankan backfill:

- `DATABASE_URL="sqlite:///./backend/data/spbe_rag.db" venv\Scripts\python.exe scripts\backfill_table_metadata.py`
- Lalu rebuild BM25 + sync Qdrant (lihat instructions standard commands).

Metadata `is_table=True` dan `table_label` dipakai oleh `_table_literal_search` dan `_query_metadata_boost` di `langchain_engine.py` untuk boost score chunk tabel secara eksplisit (bukan hanya regex teks).

### 8) Periksa quality gate — apakah jawaban ditandai unavailable secara salah?

Jika retrieval sudah OK tetapi jawaban tetap buruk, periksa apakah detector unavailable over-trigger:

1. Set `QUALITY_DEBUG=1` sebelum start backend.
2. Kirim query tabel.
3. Lihat di payload SSE event `complete`: field `quality_check.unavailable_triggers_active`.
   - Jika ada trigger tapi `local_evidence_present=True` → sudah disupress otomatis (aman).
   - Jika ada trigger dengan `local_evidence_present=False` → genuine unavailable claim; model perlu diretry.
4. Jalankan batch audit untuk cross-check: `venv\Scripts\python.exe scripts\_tmp_table_batch.py`
5. Kolom `Triggers` di report menampilkan frasa yang aktif (tidak disupress) per tabel.

## Output Skill

- Ringkasan status 3 lapis: data, index, retrieval.
- Bukti uji pertanyaan tabel (jawaban + source utama).
- Status metadata `is_table` pada chunk target.
- Status quality gate (trigger aktif vs disupress).
- Rekomendasi aksi berikutnya paling kecil dan berdampak.

## Definition of Done

- Pertanyaan tabel menghasilkan source yang relevan ke tabel target.
- Jawaban tidak lagi default "tidak ditemukan" jika data sebenarnya ada.
- Chunk tabel punya metadata `is_table=True` di SQLite + BM25 + Qdrant.
- Quality gate tidak memunculkan false-positive `conflicting_unavailable_claim` pada frasa deskriptif tabel.
- Rekomendasi lanjutan jelas (jika masih ada gap).