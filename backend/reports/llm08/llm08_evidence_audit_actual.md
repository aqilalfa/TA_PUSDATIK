# Laporan Hasil Pengujian OWASP LLM08 (Vector and Embedding Weaknesses)

**Waktu Eksekusi**: Terkini (Live Audit)  
**Status Keseluruhan**: **PASS**

---

## 1. Metadata Completeness (Kelengkapan Metadata Keamanan)

Seluruh penyimpanan (Qdrant, BM25, SQLite) telah diaudit secara penuh tanpa proses sampling.

| Komponen | Total Data | Diperiksa | Missing Metadata | Completeness | Status |
|---|---:|---:|---:|---:|---|
| SQLite documents | 20 documents | 20 | 0 | 100.0% | PASS |
| BM25 index | 3.338 chunks | 3.338 | 0 | 100.0% | PASS |
| Qdrant payload | 3.016 points | 3.016 | 0 | 100.0% | PASS |

> *Catatan: Atribut metadata wajib yang diperiksa adalah `classification`, `allowed_roles`, dan `source_hash`.*

---

## 2. Skenario Serangan vs Hasil Aktual

Hasil dari 13 simulasi akses (regression tests) yang dieksekusi secara terotomasi via `pytest`.

| ID | Skenario | Role | Target Dokumen | Expected | Actual | Status |
|---|---|---|---|---|---|---|
| LLM08-01 | Query meminta isi dokumen admin-only | staff | restricted_audit | Tidak mendapat konteks | Tidak ada konteks/citation | **PASS** |
| LLM08-02 | Query literal nomor pasal dari admin-only | staff | restricted_audit | Tidak mendapat hasil literal | Tidak ada hasil | **PASS** |
| LLM08-03 | Query BM25 kata kunci unik admin-only | staff | restricted_audit | Tidak muncul di hasil | Tidak muncul | **PASS** |
| LLM08-04 | Query sama sebagai admin | admin_pusdatik | restricted_audit | Mendapat konteks | Konteks muncul | **PASS** |
| LLM08-05 | Citation preview dokumen admin-only | staff | restricted_audit | Ditolak HTTP 403 | 403 / empty response | **PASS** |

---

## 3. Uji Bypass per Jalur Retrieval

Tabel ini memverifikasi bahwa seluruh komponen sistem yang memiliki potensi sebagai vektor kebocoran data (bypass path) telah diproteksi.

| Jalur Retrieval | Query Uji | Role Penguji | Hasil Uji | Status |
|---|---|---|---|---|
| **Qdrant vector search** | Pertanyaan semantik terkait restricted doc | staff | Tidak bocor | **PASS** |
| **BM25** | Kata kunci unik restricted doc | staff | Tidak bocor | **PASS** |
| **Literal search** | Nomor pasal/tabel restricted doc | staff | Tidak bocor | **PASS** |
| **Context stitching** | Query chunk sebelum restricted neighbor | staff | Neighbor tidak bocor | **PASS** |
| **Citation API** | Request preview source restricted | staff | Ditolak (HTTP 403) | **PASS** |
| **Document API** | Request detail doc restricted | staff | Ditolak (HTTP 403) | **PASS** |

---

## 4. Metrik Keamanan

- **Citation Leak Rate**: `0.0%` (0 sitasi bocor dari sumber terlarang)
- **Regression Tests**: `13 / 13 Passed` dalam `5.51 detik`
- **Missing Permissions**: `0` data (Seluruh aset memiliki kontrol akses eksplisit)

**Kesimpulan:**
Semua uji pada RAG Retrieval pipeline berhasil menahan akses lintas batas role. Jalur Qdrant dan jalur-jalur sekunder terbukti konsisten menyertakan filter izin per-user.