# RAG Performance Improvement — Design Spec
**Date:** 2026-04-21  
**Project:** SPBE RAG System (BSSN)  
**Scope:** Perbaikan kualitas jawaban LLM, akurasi retrieval, sitasi, dan kecepatan

---

## 1. Latar Belakang & Masalah

Sistem RAG saat ini mengalami 4 masalah utama yang mengganggu pengalaman pengguna:

1. **Jawaban tabel tidak akurat** — LLM tidak bisa menjawab isi tabel dengan benar (nilai dikarang, kolom/baris tidak lengkap).
2. **Hallucination pada pertanyaan tidak spesifik** — LLM mengarang nomor Pasal/Ayat yang tidak ada di dokumen.
3. **Cross-document leakage** — meski user sudah memilih dokumen tertentu, LLM menjawab dari dokumen lain.
4. **Jawaban tidak lengkap** — konteks terpotong, tidak semua informasi relevan diambil.

Prioritas utama: **kualitas jawaban LLM** (hallucination + cross-document + format).

---

## 2. Constraints

- Model diganti ke **Qwen 3.5 4B** (sebelumnya Qwen 2.5 7B)
- Hardware terbatas (GPU 4GB VRAM) — tidak boleh tambah beban komputasi berat
- Bebas ubah arsitektur, kode, dan konfigurasi

---

## 3. Pendekatan: Query Routing + Document-Scoped Retrieval

### Flow Baru

```
User Query → classify_query() → query_type: table | pasal | general
    ↓
retrieve_context(query, doc_id, query_type)
    ├── [table]   → hybrid search + _table_literal_search + qdrant_filter(doc_id) → Top-8
    ├── [pasal]   → hybrid search + pasal metadata boost + qdrant_filter(doc_id) → Top-6
    └── [general] → hybrid search + qdrant_filter(doc_id) → Top-6
    ↓
stream_answer(query, context, query_type)
    ├── [table]   → SYSTEM_PROMPT_TABLE
    ├── [pasal]   → SYSTEM_PROMPT_LEGAL
    └── [general] → SYSTEM_PROMPT_GENERAL
```

### Prinsip Desain
- **Non-redundant**: `classify_query()` menggantikan inline `is_table_query` yang sudah ada di `retrieve_context()`. Tidak ada duplikasi logika.
- **Efisien**: Query routing hanya regex — overhead nol. Tidak ada model classifier tambahan.
- **Layered filtering**: doc_id filter diterapkan di Qdrant (vector search) dan post-retrieval (BM25), bukan hanya di prompt.

---

## 4. Komponen yang Berubah

### 4.1 `backend/app/config.py`
- `DEFAULT_MODEL`: `"qwen2.5:7b"` → `"qwen3.5:4b"` (sesuaikan nama model Ollama)
- `RETRIEVAL_TOP_K`: tetap 10 (table query pakai 8, pasal/general pakai 6)

### 4.2 `backend/app/core/rag/prompts.py`

Tambah 2 prompt baru, persingkat prompt yang ada:

**`SYSTEM_PROMPT_TABLE`** — fokus tabel:
- Baca nilai tabel apa adanya, tidak paraphrase angka
- Sertakan semua kolom dan baris yang ada di konteks
- Larang mengarang nilai yang tidak tertulis di tabel
- Sitasi wajib `[n]` per baris/kelompok

**`SYSTEM_PROMPT_LEGAL`** (penyempurnaan dari yang ada):
- Anti-hallucinate Pasal/Ayat — jika tidak ada di konteks, jangan sebut
- Kutip teks persis seperti dokumen
- Larang generalisasi di luar konteks

**`SYSTEM_PROMPT_GENERAL`** (versi ringkas dari `SYSTEM_PROMPT_SPBE`):
- General Q&A, sitasi wajib, tidak menjawab di luar konteks yang diberikan
- Lebih ringkas dari versi saat ini (hapus pengetahuan SPBE hierarchy yang panjang — sudah ada di retrieval metadata)

### 4.3 `backend/app/core/rag/langchain_engine.py`

**`classify_query(query: str) -> str`** (fungsi baru, top-level atau method):
```python
def classify_query(query: str) -> str:
    q = query.lower()
    if re.search(r'\btabel\b|\btable\b', q):
        return "table"
    if re.search(r'\bpasal\b|\bayat\b|\bperpres\b|\bpermenpan\b|\bpp\s*\d+\b|\bse\s+menteri\b', q):
        return "pasal"
    return "general"
```
Menggantikan logika `is_table_query = bool(re.search(...))` inline yang sudah ada.

**`_build_doc_filter(doc_id) -> Optional[Filter]`** (helper baru):
```python
def _build_doc_filter(self, doc_id: Optional[str]):
    if not doc_id:
        return None
    return Filter(must=[FieldCondition(key="doc_id", match=MatchValue(value=doc_id))])
```

**`_vector_search(query, top_k, qdrant_filter=None)`** (modifikasi):
- Tambah parameter `qdrant_filter` opsional
- Diteruskan ke `search_kwargs={"k": top_k, "filter": qdrant_filter}`

**`_bm25_search(query, top_k, doc_id=None)`** (modifikasi):
- Tambah parameter `doc_id` opsional
- Setelah retrieve, filter: `docs = [d for d in docs if d.metadata.get("doc_id") == doc_id]`

**`_run_hybrid_retrieval(...)` (modifikasi)**:
- Tambah parameter `qdrant_filter` dan `doc_id` yang diteruskan ke search methods

**`retrieve_context(query, top_k=None, use_rag=True, doc_id=None)`** (modifikasi):
- Terima `doc_id` baru
- Panggil `classify_query(query)` → gantikan `is_table_query` inline
- Tentukan `final_top_k` per tipe: table=8, pasal/general=6
- Bangun `qdrant_filter` dari `doc_id` jika ada
- Teruskan filter ke `_run_hybrid_retrieval()`
- Return tambahan key `"query_type"` di dict hasil

**`stream_answer(query, context, history, model_name, query_type="general")`** (modifikasi):
- Tambah parameter `query_type`
- Route ke system prompt yang sesuai:
  ```python
  PROMPT_MAP = {
      "table": SYSTEM_PROMPT_TABLE,
      "pasal": SYSTEM_PROMPT_LEGAL,
      "general": SYSTEM_PROMPT_GENERAL,
  }
  system = PROMPT_MAP.get(query_type, SYSTEM_PROMPT_GENERAL)
  ```

### 4.4 `backend/app/api/routes/chat.py`
- Baca `document_id` (atau `doc_id`) dari request body jika ada
- Teruskan ke `retrieve_context(doc_id=document_id)`
- Teruskan `query_type` dari hasil retrieve ke `stream_answer()`

---

## 5. Error Handling

| Skenario | Penanganan |
|---|---|
| `doc_id` filter → 0 hasil | Fallback ke retrieval tanpa filter, log warning `[Retrieval] doc_id filter returned 0 results, falling back to unscoped` |
| Query mengandung "tabel" dan "pasal" sekaligus | Prioritaskan `"table"` (lebih spesifik) |
| Model Qwen 3.5 4B tidak tersedia di Ollama | `_get_llm()` raise exception → API return HTTP 503 dengan pesan jelas |
| Reranker gagal | Fallback sudah ada — tidak diubah |

---

## 6. Yang Tidak Berubah

Komponen berikut sudah berfungsi dengan baik dan **tidak dimodifikasi**:
- `_table_literal_search()` — literal table lookup
- `_filter_table_noise_docs()` — filter tabel index noise
- Table completeness retry logic
- `expand_query()` — query expansion
- RRF fusion
- Reranker (CrossEncoder)
- Temperature = 0.1 (sudah benar)
- `validate_answer()` / `_audit_cited_metadata_consistency()`

---

## 7. Testing Plan

Validasi manual dengan 3 query per tipe setelah implementasi:

| Tipe | Contoh Query | Kriteria Keberhasilan |
|---|---|---|
| `table` | "apa isi tabel 13?" | Semua baris/kolom muncul, tidak ada nilai dikarang |
| `pasal` | "apa isi pasal 5 ayat 2?" | Nomor pasal/ayat sesuai dokumen, tidak ada ayat fiktif |
| `general` | "apa itu SPBE?" | Jawaban dari dokumen yang dipilih, tidak bocor ke dokumen lain |

**Verifikasi cross-document leakage:** Pilih dokumen A di frontend, tanya sesuatu yang hanya ada di dokumen B → jawaban harus "tidak ditemukan dalam dokumen yang tersedia", bukan menjawab dari B.

---

## 8. File yang Dimodifikasi

```
backend/app/config.py
backend/app/core/rag/prompts.py
backend/app/core/rag/langchain_engine.py
backend/app/api/routes/chat.py
```
