# RAG Performance Improvement — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Perbaiki kualitas jawaban RAG dengan menambahkan query routing (table/pasal/general), document-scoped retrieval via Qdrant filter, dan 3 system prompt yang terfokus.

**Architecture:** `classify_query()` mendeteksi tipe query lalu `retrieve_context()` menerapkan Qdrant filter berdasarkan `doc_id` dan menentukan top-k yang tepat per tipe. `stream_answer()` menerima `query_type` dan memilih system prompt yang sesuai dari 3 pilihan (table/legal/general).

**Tech Stack:** Python 3.10+, FastAPI, LangChain, Qdrant (`qdrant_client.models.Filter`), Ollama (qwen3.5:4b), pytest

---

## File Map

| File | Perubahan |
|---|---|
| `backend/app/core/rag/prompts.py` | Tambah `SYSTEM_PROMPT_TABLE`, `SYSTEM_PROMPT_GENERAL`; perbarui `SYSTEM_PROMPT_LEGAL` |
| `backend/app/core/rag/langchain_engine.py` | Tambah `classify_query()`, `_build_doc_filter()`; modifikasi `_vector_search`, `_bm25_search`, `_run_hybrid_retrieval`, `retrieve_context`, `stream_answer` |
| `backend/app/models/schemas.py` | Tambah field `document_id: Optional[str]` ke `ChatRequest` |
| `backend/app/api/routes/chat.py` | Pass `doc_id` ke `retrieve_context`, pass `query_type` ke `stream_answer`, ganti `_is_table_query` dengan `classify_query` |
| `backend/tests/test_rag_routing.py` | Unit test baru untuk `classify_query` dan `_build_doc_filter` |

**Tidak diubah:** `_table_literal_search`, `_filter_table_noise_docs`, table completeness retry, `expand_query`, RRF, Reranker, temperature, `validate_answer`.

---

## Task 1: Tambah 3 System Prompt ke prompts.py

**Files:**
- Modify: `backend/app/core/rag/prompts.py`

- [ ] **Step 1: Tambah `SYSTEM_PROMPT_TABLE` setelah konstanta `SYSTEM_PROMPT_STRICT` yang ada**

Buka `backend/app/core/rag/prompts.py`. Cari baris `SYSTEM_PROMPT_STRICT = """...`. Setelah closing `"""` dari `SYSTEM_PROMPT_STRICT`, tambahkan:

```python
SYSTEM_PROMPT_TABLE = """Anda adalah asisten yang membaca tabel dari dokumen pemerintah Indonesia.

ATURAN WAJIB:
1. Baca nilai tabel PERSIS seperti yang tertulis. JANGAN paraphrase atau ubah angka.
2. Sertakan SEMUA baris dan kolom yang ada di konteks. JANGAN lewati baris.
3. JANGAN mengarang nilai yang tidak tertulis di tabel.
4. Sertakan referensi [n] di setiap baris atau kelompok baris tabel.
5. Jika tabel tidak ada di konteks, katakan: "Tabel tidak ditemukan dalam dokumen yang tersedia."
6. Gunakan bahasa Indonesia formal.

FORMAT JAWABAN:
- Mulai dengan menyebut nama/judul tabel yang ditemukan
- Sajikan isi tabel dalam format yang mudah dibaca (baris per baris atau markdown table)
- Sertakan sitasi [n] di tiap baris"""


SYSTEM_PROMPT_GENERAL = """Anda adalah asisten yang menjawab pertanyaan berdasarkan dokumen pemerintah Indonesia yang diberikan.

ATURAN WAJIB:
1. HANYA jawab berdasarkan dokumen yang diberikan dalam konteks.
2. Sertakan referensi [n] di setiap kalimat yang mengandung informasi dari dokumen.
3. Jika informasi tidak ada dalam konteks, katakan: "Informasi tersebut tidak ditemukan dalam dokumen yang tersedia."
4. Gunakan bahasa Indonesia formal.
5. JANGAN menjawab dari pengetahuan umum di luar konteks yang diberikan.

FORMAT JAWABAN:
- Jawab langsung dan ringkas
- Gunakan referensi [n] konsisten"""
```

- [ ] **Step 2: Perbarui `SYSTEM_PROMPT_LEGAL` — tambah aturan anti-generalisasi**

Cari string `SYSTEM_PROMPT_LEGAL = """` di file yang sama. Ganti seluruh nilai string-nya dengan:

```python
SYSTEM_PROMPT_LEGAL = """Anda adalah asisten hukum yang menjawab pertanyaan tentang pasal dan ayat dari dokumen peraturan Indonesia.

ATURAN WAJIB:
1. JANGAN PERNAH mengarang nomor Pasal atau Ayat. Jika konteks tidak memiliki nomor ayat, JANGAN tulis nomor ayat apapun.
2. Kutip teks PERSIS seperti yang tertulis dalam dokumen untuk nomor Pasal, Ayat, dan daftar huruf.
3. Sertakan referensi [n] di setiap kalimat atau poin yang bersumber dari dokumen.
4. Jika ada daftar (a, b, c, d...), tulis LENGKAP semua butir yang ada di konteks.
5. JANGAN generalisasi atau menambahkan interpretasi di luar teks dokumen.
6. Jika informasi tidak ada dalam konteks, katakan: "Informasi tersebut tidak ditemukan dalam dokumen yang tersedia."
7. Gunakan bahasa Indonesia formal pemerintahan.

FORMAT JAWABAN:
- Sebutkan nomor Pasal/Ayat sumber di awal jawaban
- Kutip isi pasal/ayat dengan referensi [n]
- Jika ada daftar huruf, sajikan lengkap dengan referensi per butir"""
```

- [ ] **Step 3: Tambah `SYSTEM_PROMPT_TABLE` dan `SYSTEM_PROMPT_GENERAL` ke `__all__` exports (jika ada) atau pastikan bisa diimport**

Cek apakah ada `__all__` di file tersebut:
```bash
grep -n "__all__" backend/app/core/rag/prompts.py
```
Jika ada, tambahkan kedua nama konstanta baru ke dalamnya. Jika tidak ada `__all__`, tidak perlu tambah apapun — Python akan mengeksport semua nama otomatis.

- [ ] **Step 4: Commit**

```bash
git add backend/app/core/rag/prompts.py
git commit -m "feat(prompts): add SYSTEM_PROMPT_TABLE and SYSTEM_PROMPT_GENERAL, tighten SYSTEM_PROMPT_LEGAL"
```

---

## Task 2: Tulis unit test untuk classify_query dan _build_doc_filter

**Files:**
- Create: `backend/tests/__init__.py` (kosong jika belum ada)
- Create: `backend/tests/test_rag_routing.py`

- [ ] **Step 1: Buat direktori dan file test**

```bash
mkdir -p backend/tests
touch backend/tests/__init__.py
```

- [ ] **Step 2: Tulis test untuk `classify_query`**

Buat file `backend/tests/test_rag_routing.py` dengan isi:

```python
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest


def test_classify_query_imports():
    from app.core.rag.langchain_engine import classify_query
    assert callable(classify_query)


def test_classify_table_queries():
    from app.core.rag.langchain_engine import classify_query
    assert classify_query("apa isi tabel 13?") == "table"
    assert classify_query("tampilkan tabel 3") == "table"
    assert classify_query("table 5 berisi apa?") == "table"
    assert classify_query("isi dari tabel ke-2") == "table"


def test_classify_pasal_queries():
    from app.core.rag.langchain_engine import classify_query
    assert classify_query("apa isi pasal 5?") == "pasal"
    assert classify_query("ayat 2 berbunyi apa?") == "pasal"
    assert classify_query("perpres nomor 95 mengatur apa?") == "pasal"
    assert classify_query("permenpan rb nomor 5") == "pasal"


def test_classify_general_queries():
    from app.core.rag.langchain_engine import classify_query
    assert classify_query("apa itu SPBE?") == "general"
    assert classify_query("jelaskan domain evaluasi") == "general"
    assert classify_query("siapa yang bertanggung jawab?") == "general"


def test_classify_table_wins_over_pasal():
    # Query dengan "tabel" dan "pasal" → table menang
    from app.core.rag.langchain_engine import classify_query
    assert classify_query("tabel di pasal 5 berisi apa?") == "table"


def test_build_doc_filter_with_doc_id():
    from app.core.rag.langchain_engine import LangchainRAGEngine
    engine = LangchainRAGEngine.__new__(LangchainRAGEngine)
    f = engine._build_doc_filter("abc-123")
    assert f is not None
    # Filter harus punya must clause
    assert len(f.must) == 1


def test_build_doc_filter_without_doc_id():
    from app.core.rag.langchain_engine import LangchainRAGEngine
    engine = LangchainRAGEngine.__new__(LangchainRAGEngine)
    assert engine._build_doc_filter(None) is None
    assert engine._build_doc_filter("") is None
```

- [ ] **Step 3: Jalankan test — pastikan FAIL karena fungsi belum ada**

```bash
cd backend
venv/Scripts/python -m pytest tests/test_rag_routing.py -v 2>&1 | head -30
```

Expected output: `ImportError` atau `AttributeError` karena `classify_query` belum ada.

---

## Task 3: Tambah `classify_query()` dan `_build_doc_filter()` ke langchain_engine.py

**Files:**
- Modify: `backend/app/core/rag/langchain_engine.py`

- [ ] **Step 1: Tambah import `Filter`, `FieldCondition`, `MatchValue` dari qdrant_client**

Cari baris `from qdrant_client import QdrantClient` di bagian atas file. Tambahkan setelahnya:

```python
from qdrant_client.models import Filter, FieldCondition, MatchValue
```

- [ ] **Step 2: Tambah fungsi module-level `classify_query()` sebelum class `LangchainRAGEngine`**

Cari baris `class LangchainRAGEngine:`. Tepat sebelum baris itu, tambahkan:

```python
def classify_query(query: str) -> str:
    """Classify query type for routing: 'table', 'pasal', or 'general'."""
    q = (query or "").lower()
    if re.search(r'\btabel\b|\btable\b', q):
        return "table"
    if re.search(r'\bpasal\b|\bayat\b|\bperpres\b|\bpermenpan\b|\bpp\s*\d+\b|\bse\s+menteri\b', q):
        return "pasal"
    return "general"

```

- [ ] **Step 3: Tambah method `_build_doc_filter()` di dalam class `LangchainRAGEngine`**

Cari method `def _bm25_index_path(self)` di dalam class. Tambahkan method baru tepat sebelumnya:

```python
def _build_doc_filter(self, doc_id: Optional[str]) -> Optional[Filter]:
    """Build Qdrant filter to scope retrieval to a single document."""
    if not doc_id:
        return None
    return Filter(must=[FieldCondition(key="doc_id", match=MatchValue(value=str(doc_id)))])

```

- [ ] **Step 4: Jalankan test — pastikan PASS untuk classify_query dan _build_doc_filter**

```bash
cd backend
venv/Scripts/python -m pytest tests/test_rag_routing.py -v 2>&1 | head -40
```

Expected: semua test `test_classify_*` dan `test_build_doc_filter_*` PASS. Test `test_classify_query_imports` juga PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/rag/langchain_engine.py backend/tests/
git commit -m "feat(rag): add classify_query() and _build_doc_filter() with unit tests"
```

---

## Task 4: Tambah doc_id filter ke _vector_search, _bm25_search, _run_hybrid_retrieval

**Files:**
- Modify: `backend/app/core/rag/langchain_engine.py`

- [ ] **Step 1: Modifikasi `_vector_search()` — tambah parameter `qdrant_filter`**

Cari method:
```python
def _vector_search(self, query: str, top_k: int) -> List[Document]:
    retriever = self.qdrant.as_retriever(search_kwargs={"k": top_k})
    docs = retriever.invoke(query)
    self._enrich_vector_payloads(docs)
    return docs
```

Ganti dengan:
```python
def _vector_search(self, query: str, top_k: int, qdrant_filter: Optional[Filter] = None) -> List[Document]:
    search_kwargs: dict = {"k": top_k}
    if qdrant_filter is not None:
        search_kwargs["filter"] = qdrant_filter
    retriever = self.qdrant.as_retriever(search_kwargs=search_kwargs)
    docs = retriever.invoke(query)
    self._enrich_vector_payloads(docs)
    return docs
```

- [ ] **Step 2: Modifikasi `_bm25_search()` — tambah parameter `doc_id` untuk post-filter**

Cari method:
```python
def _bm25_search(self, query: str, top_k: int) -> List[Document]:
```

Ganti signature-nya dan tambah filter setelah loop:
```python
def _bm25_search(self, query: str, top_k: int, doc_id: Optional[str] = None) -> List[Document]:
    self._load_bm25()
    if self._bm25 is None or not self._bm25_docs:
        return []

    tokens = re.findall(r"\b\w+\b", query.lower())
    if not tokens:
        return []

    scores = self._bm25.get_scores(tokens)
    top_idx = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]

    docs: List[Document] = []
    for idx in top_idx:
        raw = self._bm25_docs[idx]
        text = raw.get("text", "")
        metadata = dict(raw.get("metadata", {}))
        metadata["bm25_score"] = float(scores[idx])
        docs.append(Document(page_content=text, metadata=metadata))

    if doc_id:
        docs = [d for d in docs if str(d.metadata.get("doc_id", "")) == str(doc_id)]

    return docs
```

- [ ] **Step 3: Modifikasi `_run_hybrid_retrieval()` — tambah parameter `qdrant_filter` dan `doc_id`**

Cari signature:
```python
def _run_hybrid_retrieval(
    self,
    query: str,
    search_queries: List[str],
    final_top_k: int,
    vector_top_k: Optional[int] = None,
    bm25_top_k: Optional[int] = None,
    literal_table_top_k: Optional[int] = None,
) -> List[Document]:
```

Tambah 2 parameter baru:
```python
def _run_hybrid_retrieval(
    self,
    query: str,
    search_queries: List[str],
    final_top_k: int,
    vector_top_k: Optional[int] = None,
    bm25_top_k: Optional[int] = None,
    literal_table_top_k: Optional[int] = None,
    qdrant_filter: Optional[Filter] = None,
    doc_id: Optional[str] = None,
) -> List[Document]:
```

Di dalam body method, cari:
```python
            vdocs = self._vector_search(q, v_top_k)
```
Ganti dengan:
```python
            vdocs = self._vector_search(q, v_top_k, qdrant_filter=qdrant_filter)
```

Cari:
```python
            bdocs = self._bm25_search(q, b_top_k)
```
Ganti dengan:
```python
            bdocs = self._bm25_search(q, b_top_k, doc_id=doc_id)
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/core/rag/langchain_engine.py
git commit -m "feat(rag): add doc_id scoped filtering to _vector_search and _bm25_search"
```

---

## Task 5: Update retrieve_context() — gunakan classify_query, terima doc_id, tambah fallback

**Files:**
- Modify: `backend/app/core/rag/langchain_engine.py`

- [ ] **Step 1: Ubah signature `retrieve_context()`**

Cari:
```python
    def retrieve_context(
        self,
        query: str,
        top_k: Optional[int] = None,
        use_rag: bool = True,
    ) -> Dict[str, Any]:
```

Ganti dengan:
```python
    def retrieve_context(
        self,
        query: str,
        top_k: Optional[int] = None,
        use_rag: bool = True,
        doc_id: Optional[str] = None,
    ) -> Dict[str, Any]:
```

- [ ] **Step 2: Ganti logika `is_table_query` inline dengan `classify_query()` dan tambah doc_id filter**

Di dalam body `retrieve_context()`, cari blok:
```python
        final_top_k = max(1, int(top_k or self.top_k))

        # Table queries benefit from a slightly wider final set to avoid false negatives.
        is_table_query = bool(
            re.search(r"\b(?:tabel|table)\s*(?:ke[-\s]*)?\d{1,3}\b", query.lower())
        )
        if is_table_query:
            final_top_k = max(final_top_k, 8)
```

Ganti dengan:
```python
        query_type = classify_query(query)
        is_table_query = query_type == "table"

        base_top_k = max(1, int(top_k or self.top_k))
        if query_type == "table":
            final_top_k = max(base_top_k, 8)
        else:
            final_top_k = min(base_top_k, 6)

        qdrant_filter = self._build_doc_filter(doc_id)
```

- [ ] **Step 3: Teruskan `qdrant_filter` dan `doc_id` ke semua pemanggilan `_run_hybrid_retrieval()`**

Cari semua baris `docs = self._run_hybrid_retrieval(` di dalam `retrieve_context()`. Ada 2 pemanggilan (initial + retry). Tambahkan `qdrant_filter=qdrant_filter, doc_id=doc_id` ke keduanya:

Pemanggilan pertama:
```python
        docs = self._run_hybrid_retrieval(
            query=query,
            search_queries=expanded_queries,
            final_top_k=final_top_k,
            qdrant_filter=qdrant_filter,
            doc_id=doc_id,
        )
```

Pemanggilan retry (di dalam blok `if is_table_query:`):
```python
                retry_docs = self._run_hybrid_retrieval(
                    query=query,
                    search_queries=retry_queries,
                    final_top_k=final_top_k,
                    vector_top_k=max(self.vector_top_k, final_top_k * 4),
                    bm25_top_k=max(self.bm25_top_k, final_top_k * 4),
                    literal_table_top_k=max(6, final_top_k * 2),
                    qdrant_filter=qdrant_filter,
                    doc_id=doc_id,
                )
```

- [ ] **Step 4: Tambah fallback jika doc_id filter menghasilkan 0 docs**

Setelah baris `docs = self._run_hybrid_retrieval(...)` pertama dan sebelum blok `if is_table_query:`, tambahkan:

```python
        # Fallback: jika filter doc_id menghasilkan 0 hasil, coba tanpa filter
        if qdrant_filter is not None and not docs:
            logger.warning(
                f"[Retrieval] doc_id filter returned 0 results for doc_id='{doc_id}', "
                "falling back to unscoped retrieval"
            )
            docs = self._run_hybrid_retrieval(
                query=query,
                search_queries=expanded_queries,
                final_top_k=final_top_k,
            )
```

- [ ] **Step 5: Tambah `query_type` ke return dict**

Cari baris `return {"context": context, "sources": sources, "raw_docs": docs}` di akhir `retrieve_context()`. Ganti dengan:

```python
        return {"context": context, "sources": sources, "raw_docs": docs, "query_type": query_type}
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/core/rag/langchain_engine.py
git commit -m "feat(rag): update retrieve_context() with classify_query routing, doc_id scoping, and fallback"
```

---

## Task 6: Update stream_answer() — tambah query_type, route ke 3 system prompt

**Files:**
- Modify: `backend/app/core/rag/langchain_engine.py`

- [ ] **Step 1: Tambah import prompt baru di bagian atas file**

Cari baris:
```python
from app.core.rag.prompts import SYSTEM_PROMPT_SPBE, expand_query
```

Ganti dengan:
```python
from app.core.rag.prompts import (
    SYSTEM_PROMPT_SPBE,
    SYSTEM_PROMPT_TABLE,
    SYSTEM_PROMPT_LEGAL,
    SYSTEM_PROMPT_GENERAL,
    expand_query,
)
```

- [ ] **Step 2: Ubah signature `stream_answer()` dan tambah prompt routing**

Cari:
```python
    async def stream_answer(
        self, query: str, context: str, history: List, model_name: str
    ) -> AsyncIterator[str]:
```

Ganti dengan:
```python
    async def stream_answer(
        self, query: str, context: str, history: List, model_name: str, query_type: str = "general"
    ) -> AsyncIterator[str]:
```

Di dalam body method, cari:
```python
        system_content = SYSTEM_PROMPT_SPBE + "\n\nKonteks Referensi:\n" + context
```

Ganti dengan:
```python
        _PROMPT_MAP = {
            "table": SYSTEM_PROMPT_TABLE,
            "pasal": SYSTEM_PROMPT_LEGAL,
            "general": SYSTEM_PROMPT_GENERAL,
        }
        system_prompt = _PROMPT_MAP.get(query_type, SYSTEM_PROMPT_GENERAL)
        system_content = system_prompt + "\n\nKonteks Referensi:\n" + context
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/core/rag/langchain_engine.py
git commit -m "feat(rag): route stream_answer() to typed system prompts via query_type param"
```

---

## Task 7: Update ChatRequest schema dan chat.py — wire doc_id dan query_type end-to-end

**Files:**
- Modify: `backend/app/models/schemas.py`
- Modify: `backend/app/api/routes/chat.py`

- [ ] **Step 1: Tambah field `document_id` ke `ChatRequest` di schemas.py**

Buka `backend/app/models/schemas.py`. Cari:
```python
class ChatRequest(BaseModel):
    session_id: Optional[str] = None
    message: str
    model: Optional[str] = None
    use_rag: bool = True
    top_k: int = 5
    max_tokens: int = 2048
```

Tambah field baru setelah `use_rag`:
```python
class ChatRequest(BaseModel):
    session_id: Optional[str] = None
    message: str
    model: Optional[str] = None
    use_rag: bool = True
    top_k: int = 5
    max_tokens: int = 2048
    document_id: Optional[str] = None
```

- [ ] **Step 2: Update `chat.py` — import `classify_query` dan ganti `_is_table_query`**

Buka `backend/app/api/routes/chat.py`. Cari baris import:
```python
from app.core.rag.langchain_engine import langchain_engine
```

Ganti dengan:
```python
from app.core.rag.langchain_engine import langchain_engine, classify_query
```

Kemudian cari semua penggunaan `_is_table_query(request.message)` di file ini (ada 2 kemunculan). Ganti keduanya dengan `classify_query(request.message) == "table"`.

Contoh — cari:
```python
                if _is_table_query(request.message)
```
Ganti dengan:
```python
                if classify_query(request.message) == "table"
```

- [ ] **Step 3: Teruskan `doc_id` ke `retrieve_context()` di chat.py**

Cari blok:
```python
            retrieval = await asyncio.get_event_loop().run_in_executor(
                None,
                partial(
                    langchain_engine.retrieve_context,
                    query=request.message,
                    top_k=request.top_k,
                    use_rag=request.use_rag,
                ),
            )
```

Ganti dengan:
```python
            retrieval = await asyncio.get_event_loop().run_in_executor(
                None,
                partial(
                    langchain_engine.retrieve_context,
                    query=request.message,
                    top_k=request.top_k,
                    use_rag=request.use_rag,
                    doc_id=request.document_id,
                ),
            )
```

- [ ] **Step 4: Ambil `query_type` dari hasil retrieval dan teruskan ke `stream_answer()`**

Cari baris:
```python
            sources_for_response = retrieval["sources"]
            context = retrieval["context"]
```

Tambah baris baru setelahnya:
```python
            sources_for_response = retrieval["sources"]
            context = retrieval["context"]
            query_type = retrieval.get("query_type", "general")
```

Cari pemanggilan `langchain_engine.stream_answer(` di dalam `collect_answer()`:
```python
                async for token in langchain_engine.stream_answer(
                    query=user_query,
                    context=context,
                    history=history,
                    model_name=model,
                ):
```

Ganti dengan:
```python
                async for token in langchain_engine.stream_answer(
                    query=user_query,
                    context=context,
                    history=history,
                    model_name=model,
                    query_type=query_type,
                ):
```

- [ ] **Step 5: Jalankan semua unit test**

```bash
cd backend
venv/Scripts/python -m pytest tests/test_rag_routing.py -v
```

Expected output: semua test PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/models/schemas.py backend/app/api/routes/chat.py
git commit -m "feat(api): wire document_id and query_type end-to-end from request to stream_answer"
```

---

## Task 8: Verifikasi manual end-to-end

**Files:** Tidak ada perubahan kode — verifikasi saja.

- [ ] **Step 1: Pastikan backend berjalan**

```bash
cd backend
venv/Scripts/python -m uvicorn app.main:app --reload --port 8000
```

Pastikan tidak ada error import di startup log.

- [ ] **Step 2: Test query tipe TABLE**

Kirim request:
```bash
curl -X POST http://localhost:8000/api/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"message": "apa isi tabel 13?", "use_rag": true}'
```

Cek log backend: harus ada baris `[Retrieval] Query type: table` (atau sesuai log yang ada) dan jawaban berisi isi tabel tanpa nilai dikarang.

- [ ] **Step 3: Test query tipe PASAL**

```bash
curl -X POST http://localhost:8000/api/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"message": "apa isi pasal 5?", "use_rag": true}'
```

Jawaban harus menyebutkan nomor pasal persis dari dokumen, tidak ada ayat fiktif.

- [ ] **Step 4: Test cross-document leakage**

Cari `doc_id` dokumen A dari endpoint dokumen:
```bash
curl http://localhost:8000/api/documents/
```

Kirim pertanyaan yang hanya ada di dokumen B, dengan `document_id` dokumen A:
```bash
curl -X POST http://localhost:8000/api/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"message": "apa itu SPBE?", "use_rag": true, "document_id": "<id_dokumen_A>"}'
```

Jawaban harus tidak memuat informasi dari dokumen B.

- [ ] **Step 5: Commit final**

```bash
git add -A
git commit -m "chore: RAG improvement complete — query routing, doc-scoped retrieval, typed prompts"
```
