---
description: "Use when: running retrieval-quality regression evaluation with the repo’s fixed ground-truth CSV and the built-in evaluator script. Produces HitRate/MRR summary and a structured failure report."
name: "SPBE RAG Retrieval Quality Eval (Fixed Query Set)"
argument-hint: "What changed? (chunking, ingestion, embeddings, vector/bm25 settings, reranker, Qdrant sync)"
agent: "agent"
---

# Retrieval Quality Eval — Fixed Query Set (Ground Truth CSV)

Tujuan: melakukan regression test kualitas retrieval menggunakan **query set tetap** dan **ground truth** yang tersimpan di repo ini.

## Scope (apa yang diuji)

- Query set: `data/ground_truth/ground_truth_evaluasi_spbe.csv`
- Evaluator: `backend/scripts/evaluate_retrieval.py`
- Output detail: `data/evaluation_report.json`

Catatan:

- Evaluator saat ini menguji retrieval dari Qdrant (vector retriever) dan mencocokkan hasil dengan:
  - `chunk_index` (jika tersedia di metadata dokumen yang di-retrieve), dan/atau
  - `metadata_konteks` dari CSV (pencocokan fleksibel substring).
- Script evaluator masih memakai path absolut untuk CSV dan output. Jika repo dipindah folder, update konstanta `CSV_PATH` dan `output_path` di `backend/scripts/evaluate_retrieval.py`.

## Preconditions (wajib)

1) Qdrant harus running (Docker/compose) dan koleksi berisi vektor.

2) Dataset dokumen harus sudah ter-ingest + ter-index.

3) Jika baru saja edit/delete chunk di SQLite atau mengubah pipeline ingestion, sync ulang vector index agar Qdrant tidak “stale”:

- Dari folder `backend`:
  - `venv\Scripts\python.exe scripts\sync_vectors.py --force`

## Jalankan evaluasi (reproducible)

Dari folder `backend`:

1) (Opsional) aktifkan venv:

- `call venv\Scripts\activate.bat`

2) Jalankan evaluator:

- `venv\Scripts\python.exe scripts\evaluate_retrieval.py`

Yang diharapkan:

- Terminal menampilkan ringkasan metrik:
  - `K=1,3,5,10 | Hit Rate | MRR`
- File report detail ditulis ke: `data/evaluation_report.json`

## Cara membaca hasil

Di `data/evaluation_report.json`, per item query umumnya ada field:

- `no` (nomor query dari CSV)
- `question`
- `gt_ids` (list chunk index target)
- `found_at` (rank pertama yang match; `null` jika tidak ketemu)
- `hits` (list semua rank yang match)

Interpretasi cepat:

- Hit Rate @K: proporsi query dengan `found_at <= K`
- MRR @K: rata-rata `1/found_at` (untuk query yang ketemu di ≤K)

## Failure triage (kalau metrik turun / banyak miss)

Fokus cek berurutan (dari yang paling sering):

1) **Index stale**
- Gejala: perubahan chunk/metadata di SQLite tidak tercermin di retrieval.
- Action: jalankan `scripts/sync_vectors.py --force`.

2) **Dokumen belum ter-index / koleksi kosong**
- Cek Qdrant: `curl -s http://localhost:6333/collections`
- Pastikan ingestion sudah dijalankan (lihat instructions “Standard Commands”).

3) **Perubahan chunking menyebabkan chunk_index bergeser**
- Ground truth mengacu ke `chunk_index`. Jika pipeline chunking berubah besar, GT bisa jadi tidak kompatibel.
- Action: (a) kunci pipeline chunking untuk regression, atau (b) update ground truth secara eksplisit (hanya jika memang diinginkan).

4) **Metadata mismatch**
- Jika `chunk_index` tidak match, evaluator coba pakai `metadata_konteks` (substring match).
- Pastikan metadata penting (mis. `pasal`, `ayat`, `bagian`, `indikator`, dsb) benar-benar ikut tersimpan di payload Qdrant.

## Deep dive per-query (opsional, untuk query yang gagal)

Untuk query yang `found_at == null` atau `found_at > 10`, lakukan inspeksi retrieval manual.

Gunakan `backend/scripts/debug_q6.py` sebagai template:

- Ubah string pertanyaan di bagian `debug_query("...")` menjadi pertanyaan dari CSV.
- Jalankan dari folder `backend`:
  - `venv\Scripts\python.exe scripts\debug_q6.py`

Script ini mencetak top-10 retrieved docs beserta `chunk_index` dan snippet, sehingga kamu bisa lihat kenapa target tidak naik ke atas.

## Output (format laporan)

Keluarkan laporan ringkas seperti ini:

**Context**
- Change focus: <isi dari argument-hint>
- Ground truth: `data/ground_truth/ground_truth_evaluasi_spbe.csv`
- Evaluator: `backend/scripts/evaluate_retrieval.py`

**Metrics (copy dari terminal)**
- K=1: HitRate=<...> MRR=<...>
- K=3: HitRate=<...> MRR=<...>
- K=5: HitRate=<...> MRR=<...>
- K=10: HitRate=<...> MRR=<...>

**Failures / Repro**
- Q<no>: found_at=<null/angka> — ringkas dugaan penyebab
- (Jika perlu) lampirkan output `debug_q6.py` untuk 1-3 query terburuk

**Actions**
- <1-3 tindakan konkret yang paling mungkin memperbaiki metrik>

**Notes**
- Apakah perubahan ini acceptable untuk regression? (ya/tidak) + alasan