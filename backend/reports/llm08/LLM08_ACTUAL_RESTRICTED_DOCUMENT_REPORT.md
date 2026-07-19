# LLM08 Actual Restricted Document Update & Verification Report

**Project**: SPBE RAG Backend  
**Area**: OWASP LLM08 - Vector and Embedding Weaknesses  
**Action**: Mark one concise existing document as `restricted_audit` admin-only  
**Selected Document**: `Perpres Nomor 82 Tahun 2023.pdf`  
**Document ID**: `5`  
**Overall Status**: **PASS**

---

## 1. Ringkasan Perubahan

Sesuai keputusan pengguna, satu dokumen existing yang relatif ringkas dipilih untuk menjadi dokumen restricted aktual.

Dokumen yang dipilih:

| Field | Value |
|---|---|
| SQLite document id | `5` |
| doc_id | `5` |
| filename | `Perpres Nomor 82 Tahun 2023.pdf` |
| jumlah chunk | `43` |
| alasan pemilihan | Dokumen existing dengan chunk aktual yang ringkas dibanding dokumen lain yang sudah terindeks |

Metadata keamanan target:

```json
{
  "classification": "restricted_audit",
  "allowed_roles": ["admin_pusdatik"]
}
```

Tujuan perubahan ini adalah menjadikan `restricted_audit` bukan lagi sekadar fixture/skenario uji, tetapi dokumen aktual yang dapat diuji pada jalur Document API, Citation API, SQLite chunk metadata, BM25 metadata, dan Qdrant payload.

---

## 2. Backup Sebelum Perubahan

Sebelum perubahan, file berikut dibackup:

```text
data/spbe_rag.db.bak_llm08_20260714_194052
data/bm25_index.pkl.bak_llm08_20260714_194052
```

Backup ini penting karena perubahan dilakukan langsung terhadap metadata dokumen dan index lokal.

---

## 3. Komponen yang Diubah

Perubahan diterapkan ke:

| Komponen | Update | Status |
|---|---:|---|
| SQLite `documents.doc_metadata` | 1 document row | PASS |
| SQLite `chunks.chunk_metadata` | 43 chunk rows | PASS |
| BM25 `data/bm25_index.pkl` metadata | 43 document chunks | PASS |
| Qdrant payload `document_chunks` | 43 points | PASS |

---

## 4. Script Perubahan yang Dijalankan

Script melakukan operasi berikut:

1. Membaca dokumen SQLite dengan `id=5` / `doc_id=5`.
2. Mengubah metadata dokumen menjadi:
   - `classification = restricted_audit`
   - `allowed_roles = ["admin_pusdatik"]`
3. Mengubah seluruh metadata chunk SQLite milik dokumen tersebut.
4. Mengubah metadata seluruh entry BM25 yang memiliki `doc_id=5` atau `document_id=5`.
5. Mengirim patch payload ke Qdrant untuk semua point dengan `doc_id=5`.

Ringkasan hasil script:

```json
{
  "selected_document": {
    "id": 5,
    "doc_id": "5",
    "filename": "Perpres Nomor 82 Tahun 2023.pdf",
    "title": null
  },
  "sqlite": {
    "document_rows_updated": 1,
    "chunk_rows_updated": 43
  },
  "bm25": {
    "documents_updated": 43
  },
  "qdrant": {
    "reachable": true,
    "updated": 43,
    "error": null,
    "response": "{\"result\":{\"operation_id\":3052,\"status\":\"acknowledged\"},\"status\":\"ok\",\"time\":0.075461978}"
  }
}
```

Raw result perubahan tersimpan di:

```text
backend/reports/llm08/llm08_restrict_selected_document_result.json
```

---

## 5. Metodologi Pengujian

Pengujian dilakukan dalam empat lapisan:

| Lapisan | Tujuan | Cara Pemeriksaan |
|---|---|---|
| SQLite document metadata | Memastikan dokumen aktual diberi klasifikasi restricted | Cek `documents.doc_metadata` untuk `id=5` / `doc_id=5` |
| SQLite chunk metadata | Memastikan semua chunk dokumen mengikuti klasifikasi restricted | Cek seluruh `chunks.chunk_metadata` dengan `document_id=5` |
| BM25 metadata | Memastikan jalur BM25 membawa metadata restricted yang sama | Cek semua entry `data/bm25_index.pkl` dengan `doc_id=5` atau `document_id=5` |
| Qdrant payload | Memastikan vector store memiliki metadata restricted | Scroll Qdrant collection `document_chunks` dengan filter `doc_id=5` |
| Endpoint authorization | Memastikan access control bekerja pada API | Panggil endpoint sebagai `staff` dan `admin_pusdatik` |

Pengujian endpoint dilakukan menggunakan FastAPI `TestClient`, bukan request HTTP ke server Uvicorn terpisah. Namun data yang diuji bukan fixture kosong: dokumen `doc_id=5` sudah benar-benar diubah pada SQLite, BM25, dan Qdrant.

---

## 6. Kriteria PASS dan FAIL

### 6.1 Metadata dan Index

| Komponen | PASS jika | FAIL jika |
|---|---|---|
| SQLite document | `classification=restricted_audit` dan `allowed_roles=["admin_pusdatik"]` pada dokumen `id=5` | Metadata tidak berubah, role masih memuat `staff`, atau dokumen tidak ditemukan |
| SQLite chunks | Seluruh `43/43` chunk milik `document_id=5` memiliki metadata restricted | Ada satu atau lebih chunk yang masih `internal` atau masih mengizinkan `staff` |
| BM25 | Seluruh `43/43` entry BM25 untuk `doc_id=5` memiliki metadata restricted | Entry BM25 hilang atau masih mengizinkan `staff` |
| Qdrant | Seluruh `43/43` point Qdrant untuk `doc_id=5` memiliki metadata restricted | Point Qdrant tidak ditemukan, jumlah tidak sesuai, atau metadata tidak restricted |

### 6.2 Endpoint Authorization

| Skenario | PASS jika | FAIL jika |
|---|---|---|
| Staff membuka detail dokumen | `GET /api/documents/5` menghasilkan HTTP `403` | HTTP `200`, body mengandung detail dokumen/chunk, atau error selain 403 |
| Staff membuka chunk dokumen | `GET /api/documents/5/chunks` menghasilkan HTTP `403` | Staff mendapat chunk text atau HTTP selain 403 |
| Staff membuka preview dokumen | `POST /api/documents/5/preview` menghasilkan HTTP `403` | Staff mendapat preview chunk atau HTTP selain 403 |
| Staff membuka citation chunk | `GET /api/rag/documents/by-doc-id/5/chunks/0` menghasilkan HTTP `403` | Staff mendapat chunk text atau HTTP selain 403 |
| Admin membuka dokumen yang sama | `GET /api/documents/5` menghasilkan HTTP `200` | Admin ditolak atau dokumen tidak ditemukan |
| Admin membuka citation chunk yang sama | `GET /api/rag/documents/by-doc-id/5/chunks/0` menghasilkan HTTP `200` | Admin ditolak atau chunk tidak ditemukan |
| List dokumen staff | `GET /api/documents` HTTP `200` dan tidak memuat exact `doc_id=5` | List staff masih menampilkan `doc_id=5` |
| List dokumen admin | `GET /api/documents` HTTP `200` dan memuat exact `doc_id=5` | List admin tidak menampilkan dokumen restricted |

---

## 7. Konteks yang Diperiksa

Konteks yang diperiksa adalah seluruh konteks/chunk milik dokumen:

```text
Perpres Nomor 82 Tahun 2023.pdf / doc_id=5 / document_id=5
```

Jumlah konteks yang diperiksa:

| Surface | Jumlah konteks diperiksa | Basis pemeriksaan |
|---|---:|---|
| SQLite chunks | 43 | `document_id=5` |
| BM25 entries | 43 | `doc_id=5` atau `document_id=5` |
| Qdrant points | 43 | Qdrant payload filter `doc_id=5` |
| Citation preview endpoint | 1 representative chunk | `/api/rag/documents/by-doc-id/5/chunks/0` |
| Document API detail | 1 dokumen | `/api/documents/5` |
| Document API chunk list | 43 chunk target, akses ditolak untuk staff | `/api/documents/5/chunks` |

Pemeriksaan dilakukan berdasarkan kombinasi:

1. `doc_id` / `document_id` untuk memastikan konteks berasal dari dokumen yang sama.
2. Metadata `classification` dan `allowed_roles` untuk memastikan status restricted.
3. HTTP status code untuk memastikan enforcement pada endpoint.
4. Potongan isi teks hanya digunakan sebagai positive control admin bahwa chunk yang sama memang bisa diambil oleh role berwenang.

---

## 8. Query dan Endpoint Aktual yang Dijalankan

Tidak ada natural-language chat query yang dijalankan pada report ini. Pengujian yang dilakukan adalah endpoint/API query untuk memastikan akses dokumen dan citation terhadap dokumen restricted aktual.

Endpoint aktual:

| ID | Role | Query/Endpoint Aktual | Tujuan |
|---|---|---|---|
| staff_document_detail_403 | staff | `GET /api/documents/5` | Staff mencoba membuka detail dokumen restricted |
| staff_document_chunks_403 | staff | `GET /api/documents/5/chunks` | Staff mencoba membuka daftar chunk dokumen restricted |
| staff_document_preview_403 | staff | `POST /api/documents/5/preview` | Staff mencoba menjalankan preview dokumen restricted |
| staff_citation_chunk_403 | staff | `GET /api/rag/documents/by-doc-id/5/chunks/0` | Staff mencoba membuka citation/chunk preview restricted |
| admin_document_detail_200 | admin_pusdatik | `GET /api/documents/5` | Positive control: admin membuka dokumen yang sama |
| admin_citation_chunk_200 | admin_pusdatik | `GET /api/rag/documents/by-doc-id/5/chunks/0` | Positive control: admin membuka chunk yang sama |
| staff_document_list_excludes_restricted | staff | `GET /api/documents` | Memastikan dokumen restricted tidak muncul di list staff |
| admin_document_list_includes_restricted | admin_pusdatik | `GET /api/documents` | Memastikan dokumen restricted muncul di list admin |

Untuk pengujian chat/retrieval penuh, query natural-language yang disarankan berikutnya adalah:

| Jalur | Query yang disarankan |
|---|---|
| Semantic/vector | `Apa isi Perpres Nomor 82 Tahun 2023 tentang transformasi digital?` |
| BM25 keyword | `Percepatan Transformasi Digital dan Keterpaduan Layanan Digital Nasional` |
| Literal | `Apa isi Pasal 1 Perpres Nomor 82 Tahun 2023?` |
| Citation | Klik/buka citation source dari `doc_id=5` |

Namun query chat tersebut belum menjadi bagian dari hasil endpoint evidence ini.

---

## 9. Verifikasi Metadata

Raw result tersimpan di:

```text
backend/reports/llm08/llm08_actual_restricted_document_verification.json
```

### SQLite Document Metadata

```json
{
  "classification": "restricted_audit",
  "allowed_roles": ["admin_pusdatik"],
  "uploaded_by": 1,
  "uploader_department": null,
  "source_filename": "Perpres Nomor 82 Tahun 2023.pdf",
  "source_hash": "sha256:0b2d71b86c9ccc51dd1a79472904d5553dc6e84f9d2fd02006a0e4bc1245cbac"
}
```

### SQLite Chunks

```json
{
  "restricted_chunks": 43,
  "total_chunks": 43
}
```

### BM25 Metadata

```json
{
  "restricted_chunks": 43,
  "total_matches": 43
}
```

### Qdrant Payload

```json
{
  "points_returned": 43,
  "restricted_points": 43,
  "status": "PASS"
}
```

---

## 10. Bagaimana Memastikan Dokumen Memang Terindeks

Dokumen dianggap terindeks karena memenuhi bukti berikut:

| Bukti | Hasil | Interpretasi |
|---|---|---|
| SQLite document row | `doc_id=5`, `chunk_count=43`, `status=indexed` pada response admin detail | Dokumen tercatat sebagai indexed di Document API |
| SQLite chunk rows | `43` chunk ditemukan untuk `document_id=5` | Teks dokumen tersimpan sebagai chunk lokal |
| BM25 entries | `43` entry cocok untuk `doc_id=5` / `document_id=5` | Dokumen masuk lexical/BM25 retrieval surface |
| Qdrant points | `43` point cocok untuk payload `doc_id=5` | Dokumen masuk vector retrieval surface |
| Admin citation preview | `GET /api/rag/documents/by-doc-id/5/chunks/0` menghasilkan HTTP `200` dan mengembalikan teks chunk | Chunk yang sama dapat diambil dari API oleh role berwenang |

Potongan positive control admin:

```json
{
  "chunk_index": 0,
  "text": "SALINAN\nPRESIDEN\nREPUBLIK INDONESIA\nPERATURAN PRESIDEN REPUBLIK INDONESIA\nNOMOR 82 TAHUN 2023...",
  "document_title": "Perpres Nomor 82 Tahun 2023.pdf",
  "doc_id": "5"
}
```

---

## 11. Hasil Pengujian Endpoint Access Control

Endpoint diuji menggunakan FastAPI `TestClient` dengan user role `staff` dan `admin_pusdatik`.

| ID | Role | Method | Endpoint | Expected | Actual | Verdict |
|---|---|---|---|---:|---:|---|
| staff_document_detail_403 | staff | GET | `/api/documents/5` | 403 | 403 | PASS |
| staff_document_chunks_403 | staff | GET | `/api/documents/5/chunks` | 403 | 403 | PASS |
| staff_document_preview_403 | staff | POST | `/api/documents/5/preview` | 403 | 403 | PASS |
| staff_citation_chunk_403 | staff | GET | `/api/rag/documents/by-doc-id/5/chunks/0` | 403 | 403 | PASS |
| admin_document_detail_200 | admin_pusdatik | GET | `/api/documents/5` | 200 | 200 | PASS |
| admin_citation_chunk_200 | admin_pusdatik | GET | `/api/rag/documents/by-doc-id/5/chunks/0` | 200 | 200 | PASS |
| staff_document_list_excludes_restricted | staff | GET | `/api/documents` | 200 without exact doc_id=5 | 200 without exact doc_id=5 | PASS |
| admin_document_list_includes_restricted | admin_pusdatik | GET | `/api/documents` | 200 with exact doc_id=5 | 200 with exact doc_id=5 | PASS |

---

## 12. Bukti Log / Raw Evidence

Bukti utama tersimpan dalam file berikut:

| File | Isi |
|---|---|
| `backend/reports/llm08/llm08_restrict_selected_document_result.json` | Log hasil perubahan metadata ke SQLite, BM25, dan Qdrant |
| `backend/reports/llm08/llm08_actual_restricted_document_verification.json` | Log hasil verifikasi metadata dan endpoint PASS/FAIL |
| `data/spbe_rag.db.bak_llm08_20260714_194052` | Backup SQLite sebelum perubahan |
| `data/bm25_index.pkl.bak_llm08_20260714_194052` | Backup BM25 sebelum perubahan |

Contoh log perubahan Qdrant:

```json
{
  "reachable": true,
  "updated": 43,
  "error": null,
  "response": "{\"result\":{\"operation_id\":3052,\"status\":\"acknowledged\"},\"status\":\"ok\",\"time\":0.075461978}"
}
```

Contoh log staff ditolak:

```json
{
  "id": "staff_citation_chunk_403",
  "role": "staff",
  "method": "GET",
  "path": "/api/rag/documents/by-doc-id/5/chunks/0",
  "status_code": 403,
  "body_preview": "{\"detail\":\"Document access denied\"}",
  "verdict": "PASS"
}
```

Contoh log admin berhasil mengambil dokumen/chunk yang sama:

```json
{
  "id": "admin_citation_chunk_200",
  "role": "admin_pusdatik",
  "method": "GET",
  "path": "/api/rag/documents/by-doc-id/5/chunks/0",
  "status_code": 200,
  "body_preview": "{\"chunk_index\":0,\"text\":\"SALINAN\\nPRESIDEN\\nREPUBLIK INDONESIA..."
}
```

---

## 13. Dampak terhadap LLM08 Evidence

Sebelumnya, `restricted_audit` hanya berupa fixture/skenario uji. Setelah perubahan ini, sudah ada dokumen aktual yang menjadi restricted:

```text
Perpres Nomor 82 Tahun 2023.pdf / doc_id=5
```

Dengan metadata:

```json
{
  "classification": "restricted_audit",
  "allowed_roles": ["admin_pusdatik"]
}
```

Maka klaim berikut sekarang dapat digunakan dengan lebih kuat:

| Klaim | Status |
|---|---|
| Ada dokumen aktual dengan `classification=restricted_audit`. | PASS |
| Dokumen restricted hanya dapat diakses `admin_pusdatik`. | PASS |
| Staff ditolak pada Document API. | PASS |
| Staff ditolak pada Citation/chunk preview API. | PASS |
| Metadata restricted sudah tersinkron ke SQLite chunks, BM25, dan Qdrant payload. | PASS |
| Admin berhasil mengambil dokumen/chunk yang sama sebagai positive control. | PASS |

---

## 14. Catatan Batasan

Pengujian endpoint dilakukan melalui FastAPI `TestClient`, bukan request HTTP ke server Uvicorn yang berjalan terpisah. Namun berbeda dari report sebelumnya, kali ini data restricted bukan lagi fixture kosong: metadata restricted sudah diterapkan pada dokumen aktual di SQLite, BM25, dan Qdrant.

Report ini membuktikan endpoint Document API dan Citation API, serta metadata pada SQLite/BM25/Qdrant. Untuk evidence live penuh pada jalur generatif RAG, langkah berikutnya adalah menjalankan `/api/chat/stream` terhadap dokumen ini sebagai `staff` dan `admin_pusdatik`, lalu menyimpan raw SSE response untuk membuktikan jalur vector/BM25/literal retrieval pada runtime chat.

---

## 15. Kesimpulan

Perubahan berhasil.

Dokumen `Perpres Nomor 82 Tahun 2023.pdf` (`doc_id=5`) sekarang menjadi dokumen restricted aktual dengan klasifikasi `restricted_audit` dan akses hanya untuk `admin_pusdatik`.

Pengujian menunjukkan:

- Staff tidak dapat membuka detail dokumen, chunk list, preview dokumen, maupun citation chunk.
- Admin berhasil membuka dokumen dan citation chunk yang sama.
- Seluruh 43 konteks/chunk dokumen sudah berstatus restricted di SQLite, BM25, dan Qdrant.
- Pemeriksaan dilakukan berdasarkan `doc_id`, metadata akses, HTTP status code, dan positive control isi teks untuk admin.

**Overall verification status: PASS**
