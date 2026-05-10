---
phase: comprehensive-code-review
reviewed: 2026-05-06T00:00:00Z
depth: standard
files_reviewed: 3
files_reviewed_list:
  - backend/app/core/rag/langchain_engine.py
  - backend/app/core/ingestion/document_manager.py
  - backend/app/core/ingestion/structured_chunker.py
findings:
  critical: 5
  medium: 2
  low: 3
  total: 10
status: issues_found
---

# SPBE RAG System: Comprehensive Code Review Report

**Reviewed Files:**
1. `backend/app/core/rag/langchain_engine.py` (~61KB) — RAG engine, retrieval, hybrid search
2. `backend/app/core/ingestion/document_manager.py` (~67KB) — Document lifecycle, indexing, BM25
3. `backend/app/core/ingestion/structured_chunker.py` — Chunking strategy, Peraturan/Laporan splitting

**Review Depth:** Standard (per-file analysis + cross-file dependencies)
**Review Date:** May 6, 2026

---

## Executive Summary

The three core SPBE RAG backend files contain **10 findings across severity levels**:
- **5 Critical** issues that can cause incorrect retrieval behavior or security concerns
- **2 Medium** issues affecting data completeness and user feedback
- **3 Low** issues related to robustness and code quality

The most severe issues involve:
1. Cross-document result leakage when document-scoped retrieval fails
2. Missing table metadata in BM25 index (is_table, table_label, table_context)
3. Missing filename in BM25 metadata (breaks doc_id filtering)
4. Peraturan chunker losing Pasal prefix in early buffer flushes
5. Silent 10k chunk truncation during document indexing

**Recommendation:** Fix Critical issues immediately (CR-01 through CR-05) before production deployment. TDD regression tests are specified for each issue.

---

## Critical Issues

### CR-01: Doc-Scoped Retrieval Falls Back to Global Search, Leaking Cross-Document Results

**Severity:** CRITICAL  
**Files:** `backend/app/core/rag/langchain_engine.py` [lines 1343-1350]

**Issue:**
When a `doc_id` is supplied to constrain retrieval to a specific document, the code implements a fallback that silently abandons the constraint:

```python
# Line 1343-1347
if qdrant_filter is not None and not docs:
    logger.warning(
        f"[Retrieval] doc_id filter returned 0 results for doc_id='{doc_id}', "
        "falling back to unscoped retrieval"
    )
    docs = self._run_hybrid_retrieval(
        query=query,
        search_queries=expanded_queries,
        final_top_k=final_top_k,  # <-- NO qdrant_filter, NO doc_id constraint
    )
```

**Root Cause:**
- User supplies `doc_id` expecting results ONLY from that document
- Vector retrieval returns 0 results for that document
- Code falls back to **global search across all documents**, returning results that violate the scope constraint
- No warning to the user that results may come from a different document

**Impact:**
- **Data Leakage:** User requesting "find this in document X" receives results from documents Y, Z
- **Audit Trail Broken:** Cannot trust that scoped queries actually returned scoped results
- **Critical for BSSN:** When querying specific regulatory documents, cross-document leakage is a correctness bug

**Example:**
```
User Query:  "Apa itu SPBE?" dengan doc_id="doc-peraturan-spbe-2023"
Expected:    Results only from Peraturan SPBE 2023
Actual:      Results from ANY document if Peraturan has 0 vector matches
```

**TDD Regression Test Specification:**

```python
# backend/tests/test_rag_doc_scoped_isolation.py

def test_doc_scoped_retrieval_never_leaks_to_other_documents():
    """
    BLOCKING: When doc_id is supplied, results MUST come only from that document.
    If retrieval returns 0 results, FAIL gracefully rather than fallback to global search.
    
    Regression test for CR-01.
    """
    # Setup: Create two documents
    doc_a_id = upload_document("doc_peraturan_spbe.pdf")  # Has content about "SPBE"
    doc_b_id = upload_document("doc_laporan_audit.pdf")    # Doesn't mention "SPBE"
    
    # Index both documents
    index_document(doc_a_id)
    index_document(doc_b_id)
    
    # Query: Ask about SPBE, scoped to Doc A
    response = retrieve_context(
        query="Apa itu SPBE?",
        doc_id=doc_a_id,  # Explicit scope
        top_k=5
    )
    
    # MUST: All results come from doc_a_id
    assert response["retrieved_count"] > 0, "Should find SPBE content in doc_a"
    for chunk in response["chunks"]:
        assert chunk["doc_id"] == doc_a_id, (
            f"Chunk {chunk['id']} from doc {chunk['doc_id']} "
            f"returned for scoped query to {doc_a_id}"
        )
        assert chunk["filename"] == "doc_peraturan_spbe.pdf"


def test_doc_scoped_query_zero_results_doesnt_fallback():
    """
    BLOCKING: When doc_id filter yields 0 results, return empty rather than fallback.
    User must know the result is NOT available in that document.
    
    Regression test for CR-01 fallback behavior.
    """
    doc_id = upload_and_index_document("doc_peraturan_spbe.pdf")
    
    # Query: Ask for something NOT in the document
    response = retrieve_context(
        query="Siapa nama istri presiden?",  # Not in peraturan
        doc_id=doc_id,  # Scoped to this doc
        top_k=5
    )
    
    # MUST: Return empty, NOT fallback to other documents
    assert response["retrieved_count"] == 0, (
        "Scoped query to empty doc should return 0 results, "
        "not fallback to global search"
    )
    assert response.get("fallback_occurred") is False


def test_retrieve_context_respects_doc_id_in_hybrid_search():
    """
    BLOCKING: Both vector and BM25 searches must filter by doc_id when supplied.
    Verify that _run_hybrid_retrieval (called from retrieve_context) respects doc_id.
    """
    doc_a = upload_and_index_document("doc_a.pdf", text="Pasal 1: Tentang SPBE")
    doc_b = upload_and_index_document("doc_b.pdf", text="Pasal 1: Tentang SPBE")
    
    # Query both with same text, but scoped to doc_a
    response = retrieve_context(
        query="Pasal 1 SPBE",
        doc_id=doc_a,
        top_k=5
    )
    
    # All results must be from doc_a
    for chunk in response["chunks"]:
        assert chunk["doc_id"] == doc_a, (
            f"Got doc_id={chunk['doc_id']}, expected {doc_a}"
        )
        assert chunk["filename"].startswith("doc_a"), (
            f"Got filename={chunk['filename']}, expected from doc_a"
        )
```

**Fix Strategy:**
1. Remove the fallback that removes the `qdrant_filter` when doc_id is supplied
2. Instead: If scoped search returns 0 results, return 0 results (not fallback)
3. Log clearly: "No results found for query in scoped document"
4. Return empty result set with `fallback_occurred=false`

**Priority:** BLOCKING — Fix before any production deployment

---

### CR-02: BM25 Metadata Missing Table Flags (is_table, table_label, table_context)

**Severity:** CRITICAL  
**Files:**
- `backend/app/core/ingestion/document_manager.py` [lines 1588-1596] — BM25 rebuild
- `backend/app/core/ingestion/document_manager.py` [lines 530-604] — Chunk creation with table metadata

**Issue:**
Table metadata is correctly extracted and stored in SQLite chunks (lines 532-604), but **NOT carried forward to BM25 index** during rebuild (lines 1588-1596).

**Current BM25 Metadata (Missing Fields):**
```python
# document_manager.py lines 1588-1596
"metadata": {
    "document_title": doc.get("document_title", ""),
    "context_header": chunk.get("context_header", ""),
    "pasal": chunk.get("pasal", ""),
    "ayat": chunk.get("ayat", ""),
    "bab": chunk.get("bab", ""),
    "hierarchy": chunk.get("hierarchy", ""),
    "chunk_part": chunk.get("chunk_part"),
    "chunk_parts_total": chunk.get("chunk_parts_total"),
    "parent_pasal_text": chunk.get("parent_pasal_text", ""),
    "is_parent": chunk.get("is_parent", False),
    "doc_id": doc["doc_id"],
    # ❌ MISSING: is_table, table_label, table_context, section
}
```

**What Should Be There:**
```python
"is_table": chunk.get("is_table", False),  # Boolean flag
"table_label": chunk.get("table_label", ""),  # "Tabel 13", etc.
"table_context": chunk.get("table_context", ""),  # Context before/after table
"section": chunk.get("section", ""),  # Header for table section
```

**Root Cause:**
- `_rebuild_bm25_index()` at line 1572 pulls chunks from SQLite using `get_chunks()`
- `get_chunks()` returns dict with all metadata fields including `table_context`, `is_table`
- But the BM25 metadata dict at lines 1588-1596 explicitly cherry-picks only specific fields
- Table fields were added to chunk schema (line 603) but not added to BM25 field list

**Impact:**
- **Table Query Loss:** BM25 cannot filter table chunks by presence (`is_table=true`)
- **Table Search Degradation:** Table-specific queries cannot rank table chunks higher
- **Missing Guardrails:** Cannot identify which chunks are tables for special processing
- **Query Type Routing Broken:** `classify_query()` detects table queries but cannot leverage table metadata in BM25

**Example:**
```
Query: "Apa isi Tabel 13?"
Expected: Chunks marked is_table=true with table_label="Tabel 13" ranked first
Actual:   BM25 has no is_table flag, cannot distinguish table chunks from text
Result:   May return text chunks mentioning "Tabel 13" instead of actual table content
```

**TDD Regression Test Specification:**

```python
# backend/tests/test_bm25_table_metadata.py

def test_bm25_index_includes_is_table_flag():
    """
    BLOCKING: BM25 index must include is_table boolean for each chunk.
    Table detection in SQLite must propagate to BM25.
    """
    doc_id = upload_and_index_document("doc_with_table.pdf")
    
    # Get the raw BM25 data
    bm25_data = load_bm25_index()
    
    # Find chunks from our document
    doc_chunks = [c for c in bm25_data["documents"] if c["metadata"]["doc_id"] == doc_id]
    
    # Check that chunks with is_table=true in SQLite also have it in BM25
    sqlite_chunks = get_chunks(doc_id)
    for sqlite_chunk in sqlite_chunks:
        if sqlite_chunk.get("is_table"):  # If table in SQLite
            # Find corresponding BM25 chunk by text
            bm25_chunk = next(
                (c for c in doc_chunks if c["text"][:100] == sqlite_chunk["text"][:100]),
                None
            )
            assert bm25_chunk is not None, f"Chunk text not found in BM25"
            assert bm25_chunk["metadata"].get("is_table") is True, (
                f"BM25 metadata missing is_table for table chunk"
            )


def test_bm25_index_preserves_table_label():
    """
    BLOCKING: BM25 must include table_label (e.g., "Tabel 13") from SQLite chunks.
    """
    doc_id = upload_and_index_document("doc_audit_with_tables.pdf")
    
    bm25_data = load_bm25_index()
    doc_chunks = [c for c in bm25_data["documents"] if c["metadata"]["doc_id"] == doc_id]
    
    sqlite_chunks = get_chunks(doc_id)
    for sqlite_chunk in sqlite_chunks:
        if sqlite_chunk.get("table_label"):  # If has table label in SQLite
            bm25_chunk = find_bm25_chunk_by_text(doc_chunks, sqlite_chunk["text"])
            assert bm25_chunk is not None
            assert bm25_chunk["metadata"].get("table_label") == sqlite_chunk["table_label"], (
                f"BM25 table_label mismatch: "
                f"SQLite={sqlite_chunk['table_label']}, "
                f"BM25={bm25_chunk['metadata'].get('table_label')}"
            )


def test_table_query_can_filter_bm25_by_is_table():
    """
    BLOCKING: Table queries like "Tabel 13" should be searchable via BM25 is_table flag.
    """
    doc_id = upload_and_index_document("doc_with_table_13.pdf")
    
    # Get BM25 results for a table query
    results = bm25_search(
        query="Tabel 13",
        top_k=5,
        filter_by_is_table=True  # Should filter to table chunks only
    )
    
    # Should find chunks with is_table=true AND table_label containing "13"
    for result in results:
        metadata = result["metadata"]
        assert metadata.get("is_table") is True, (
            "Table-filtered search returned non-table chunk"
        )
        assert "13" in metadata.get("table_label", ""), (
            "Table-filtered search didn't return Tabel 13"
        )


def test_bm25_metadata_includes_all_structural_fields():
    """
    Comprehensive check that BM25 metadata has all fields from SQLite chunks.
    """
    required_fields = [
        "document_title",
        "context_header",
        "pasal",
        "ayat",
        "bab",
        "hierarchy",
        "chunk_part",
        "chunk_parts_total",
        "parent_pasal_text",
        "is_parent",
        "is_table",  # NEW
        "table_label",  # NEW
        "table_context",  # NEW
        "section",  # NEW
        "doc_id",
        "filename",  # See CR-03
    ]
    
    doc_id = upload_and_index_document("test.pdf")
    bm25_data = load_bm25_index()
    
    for chunk in bm25_data["documents"]:
        if chunk["metadata"]["doc_id"] == doc_id:
            for field in required_fields:
                assert field in chunk["metadata"], (
                    f"BM25 chunk missing required field: {field}"
                )
```

**Fix Strategy:**
1. In `_rebuild_bm25_index()` (document_manager.py line 1572), extend metadata dict to include:
   - `is_table`: chunk.get("is_table", False)
   - `table_label`: chunk.get("table_label", "")
   - `table_context`: chunk.get("table_context", "")
   - `section`: chunk.get("section", "") (also used for table headers)
2. Update `_bm25_search_text()` to include table metadata in search tokenization
3. Verify that BM25 rebuild captures these fields from SQLite

**Priority:** CRITICAL — Table queries depend on this

---

### CR-03: BM25 Metadata Missing Filename, Breaking Doc_ID Filtering

**Severity:** CRITICAL  
**Files:**
- `backend/app/core/rag/langchain_engine.py` [lines 290-295, 343] — BM25 filtering by filename
- `backend/app/core/ingestion/document_manager.py` [lines 1588-1596] — BM25 metadata dict

**Issue:**
The BM25 retrieval code attempts to filter by `filename` to enforce document scope, but `filename` is **not included in BM25 metadata**:

**langchain_engine.py line 290-295:**
```python
if target_filename:
    docs = [
        d for d in docs
        if str(d.metadata.get("filename", "")) == target_filename  # ❌ filename always ""
    ]
```

**document_manager.py lines 1588-1596:**
```python
"metadata": {
    "document_title": ...,
    # ❌ NO "filename" FIELD
}
```

**Root Cause:**
- BM25 metadata is constructed from SQLite chunk data
- Chunks contain filename in their metadata (document_manager.py line 603)
- But filename is **not extracted** when rebuilding BM25 index
- `_resolve_doc_target()` returns the correct filename, but BM25 cannot filter by it

**Impact:**
- **BM25 Scoping Broken:** When `doc_id` is supplied, BM25 cannot filter by document
- **Combined with CR-01:** Falls back to global search, leaking cross-document results
- **Amplifies CR-02:** Table queries cannot be scoped to specific documents

**Example:**
```
Query: "Pasal 1" with doc_id="doc-peraturan-spbe"
Expected BM25 filter: filename="PP_SPBE_2023.pdf"
Actual: filename="" (always), so filter matches ALL documents
Result: BM25 returns chunks from any document mentioning "Pasal 1"
```

**TDD Regression Test Specification:**

```python
# backend/tests/test_bm25_filename_metadata.py

def test_bm25_metadata_includes_filename():
    """
    BLOCKING: Every chunk in BM25 must include filename.
    Filename is used to filter results when doc_id is supplied.
    """
    doc_id = upload_and_index_document("pp_95_2018_spbe.pdf")
    
    bm25_data = load_bm25_index()
    doc_chunks = [c for c in bm25_data["documents"] if c["metadata"]["doc_id"] == doc_id]
    
    assert len(doc_chunks) > 0, "No chunks found for document in BM25"
    
    for chunk in doc_chunks:
        filename = chunk["metadata"].get("filename", "")
        assert filename != "", "Chunk has empty filename in BM25"
        assert filename == "pp_95_2018_spbe.pdf", (
            f"Filename mismatch: expected pp_95_2018_spbe.pdf, got {filename}"
        )


def test_bm25_scoped_search_filters_by_filename():
    """
    BLOCKING: When doc_id is supplied, BM25 results must be filtered by filename.
    """
    doc_a = upload_and_index_document("doc_a_pp_95.pdf", text="Pasal 1 tentang definisi")
    doc_b = upload_and_index_document("doc_b_laporan.pdf", text="Pasal 1 hasil audit")
    
    # Both have "Pasal 1" but in different documents
    response = retrieve_context(
        query="Pasal 1",
        doc_id=doc_a,
        search_type="bm25",  # Force BM25 search
        top_k=5
    )
    
    # All results MUST be from doc_a
    for chunk in response["chunks"]:
        assert chunk["filename"] == "doc_a_pp_95.pdf", (
            f"Got filename={chunk['filename']}, expected from doc_a"
        )
        assert chunk["doc_id"] == doc_a


def test_filename_matches_resolved_doc_target():
    """
    Integration test: filename in BM25 matches what _resolve_doc_target returns.
    """
    doc_id = upload_and_index_document("original_filename_pp95.pdf")
    
    # Get resolved target
    db_id, target_filename = _resolve_doc_target(doc_id)
    
    # Check BM25 has same filename
    bm25_data = load_bm25_index()
    bm25_chunk = next(
        (c for c in bm25_data["documents"] if c["metadata"]["doc_id"] == doc_id),
        None
    )
    assert bm25_chunk is not None
    assert bm25_chunk["metadata"]["filename"] == target_filename, (
        f"BM25 filename {bm25_chunk['metadata']['filename']} "
        f"doesn't match resolved {target_filename}"
    )
```

**Fix Strategy:**
1. In `_rebuild_bm25_index()` at line 1572, add filename to metadata dict:
   ```python
   "filename": doc.get("original_filename") or doc.get("filename") or "",
   ```
2. Verify that `_table_literal_search()` at line 343 can now correctly filter by filename

**Priority:** CRITICAL — Dependent on CR-01, CR-02

---

### CR-04: Peraturan Chunker Loses "Pasal N" Prefix in Early Buffer Flushes

**Severity:** CRITICAL  
**Files:** `backend/app/core/ingestion/structured_chunker.py` [lines 437-462]

**Issue:**
When chunking Peraturan documents with multiple Ayat, the buffer fills and flushes early. Early flushes **omit the "Pasal N" prefix**, while only the final flush includes it.

**Current Logic (Lines 437-462):**

```python
# Line 437: Buffer fills, flush early
if len(buffer_text) + len(candidate) + 1 <= MAX_CHUNK_SIZE_PERATURAN:
    # Add to buffer
    buffer_text += (...candidate...)
else:
    # BUFFER FULL: Flush without Pasal prefix
    if buffer_text:
        complete_text = f"{pasal_isi}\n{buffer_text}"  # ❌ No "Pasal N"
        for piece in split_text_with_overlap(complete_text, ...):
            chunks.append({
                "text": piece,  # ❌ Missing "Pasal N" header
                ...
            })
    buffer_text = candidate

# Line 453-462: Final flush WITH Pasal prefix
if buffer_text:
    complete_text = f"{pasal_isi}\n{buffer_text}"
    if pasal_nomor and pasal_nomor != "intro":
        complete_text = f"Pasal {pasal_nomor}\n{complete_text}"  # ✅ Has "Pasal N"
    for piece in split_text_with_overlap(complete_text, ...):
        chunks.append({
            "text": piece,  # ✅ Has "Pasal N"
            ...
        })
```

**Root Cause:**
- Early buffer flushes at line 447 construct `complete_text` WITHOUT "Pasal {pasal_nomor}" prefix
- Final flush at line 461 adds the prefix explicitly
- Inconsistency: First chunk of a Pasal might have no prefix, last chunk has it

**Impact:**
- **Context Loss:** Early chunks appear orphaned (no Pasal number in text)
- **Query Loss:** Queries like "Pasal 5 ayat 2" may miss early chunks if they don't contain "Pasal 5"
- **User Confusion:** Retrieved chunks lack structural context
- **Table of Contents:** Cannot reliably extract "Pasal N" from chunk text

**Example:**
```
Pasal 5 has 10 Ayats. Buffer fills after Ayat 5.

Chunk 1: (early flush, NO prefix)
"(1) Definisi SPBE adalah...
(2) Sistem pemerintah...
(3) Elektronik adalah..."
❌ No "Pasal 5" header

Chunk 2: (final flush, WITH prefix)
"Pasal 5
(6) Integrasi adalah...
(7) Data adalah..."
✅ Has "Pasal 5" header
```

**TDD Regression Test Specification:**

```python
# backend/tests/test_peraturan_chunker_pasal_prefix.py

def test_all_peraturan_ayat_chunks_include_pasal_prefix():
    """
    BLOCKING: Every chunk containing Ayats from a Pasal MUST include "Pasal N" prefix.
    All chunks, not just the final one.
    """
    json_doc = parse_peraturan_pdf("PP_95_2018_SPBE.pdf")
    chunks = chunk_document(json_doc)
    
    # Extract all chunks with Ayat content
    ayat_chunks = [c for c in chunks if c["metadata"].get("ayat")]
    
    assert len(ayat_chunks) > 0, "No Ayat chunks generated"
    
    for chunk in ayat_chunks:
        text = chunk["text"]
        pasal_num = chunk["metadata"].get("pasal", "")
        
        if pasal_num and pasal_num != "intro":
            # MUST: Text includes "Pasal N" where N matches metadata
            assert re.search(rf"^Pasal\s+{re.escape(pasal_num)}", text, re.MULTILINE), (
                f"Chunk with pasal={pasal_num} missing 'Pasal {pasal_num}' prefix: {text[:100]}"
            )


def test_buffer_overflow_flushes_include_pasal_prefix():
    """
    BLOCKING: When buffer overflows and flushes early, include "Pasal N" prefix.
    This tests the specific case at line 447 where early flush happens.
    """
    # Create a Pasal with many large Ayats that cause buffer overflow
    json_doc = {
        "batang_tubuh": [
            {
                "pasal_nomor": "5",
                "pasal_isi": "Tentang Definisi",
                "ayat_list": [
                    # 10 large ayats that will cause buffer to overflow
                    {"nomor": str(i), "isi": f"Lorem ipsum dolor sit amet consectetur adipiscing elit. " * 20}
                    for i in range(1, 11)
                ]
            }
        ]
    }
    
    chunks = chunk_document(json_doc)
    
    # Find chunks from Pasal 5
    pasal_5_chunks = [c for c in chunks if c["metadata"].get("pasal") == "Pasal 5"]
    
    assert len(pasal_5_chunks) > 1, "Should have multiple chunks for Pasal 5"
    
    # ALL chunks must start with "Pasal 5"
    for i, chunk in enumerate(pasal_5_chunks):
        text = chunk["text"]
        assert text.startswith("Pasal 5\n") or "Pasal 5" in text.split("\n")[0], (
            f"Chunk {i} of Pasal 5 missing prefix: {text[:80]}"
        )


def test_peraturan_chunks_have_consistent_hierarchy():
    """
    BLOCKING: Hierarchy metadata must match actual text structure.
    If chunk contains "Pasal N", then hierarchy must start with "Pasal N".
    """
    json_doc = parse_peraturan_pdf("PERATURAN_KOMPLEKS.pdf")
    chunks = chunk_document(json_doc)
    
    for chunk in chunks:
        text = chunk["text"]
        hierarchy = chunk["metadata"].get("hierarchy", "")
        
        # Extract Pasal from text
        text_pasal_match = re.search(r"^Pasal\s+(\d+)", text, re.MULTILINE)
        meta_pasal = chunk["metadata"].get("pasal", "")
        
        if text_pasal_match:
            text_pasal = f"Pasal {text_pasal_match.group(1)}"
            assert meta_pasal == text_pasal, (
                f"Text has {text_pasal}, metadata has {meta_pasal}"
            )
            # Hierarchy must reference this Pasal
            assert text_pasal in hierarchy, (
                f"Hierarchy '{hierarchy}' doesn't match Pasal in text"
            )


def test_final_pasal_buffer_flush_consistent_with_intermediate():
    """
    Verify that final buffer flush (line 461) applies same prefix logic as intermediate flushes.
    """
    # Create Peraturan where ONLY the last Pasal fits entirely in one chunk
    json_doc = {
        "batang_tubuh": [
            {
                "pasal_nomor": "99",
                "pasal_isi": "",
                "ayat_list": [
                    {"nomor": "1", "isi": "Short"}  # Won't cause overflow
                ]
            }
        ]
    }
    
    chunks = chunk_document(json_doc)
    final_chunk = chunks[-1]
    
    # Should start with "Pasal 99"
    assert final_chunk["text"].startswith("Pasal 99\n"), (
        f"Final chunk missing Pasal prefix: {final_chunk['text'][:50]}"
    )
```

**Fix Strategy:**
1. At line 447 (early buffer flush), add the "Pasal N" prefix:
   ```python
   if pasal_nomor and pasal_nomor != "intro":
       complete_text = f"Pasal {pasal_nomor}\n{complete_text}"
   ```
2. Extract this logic into a shared function to ensure consistency
3. Verify all buffer flushes follow the same pattern

**Priority:** CRITICAL — Affects query retrieval and context quality

---

### CR-05: BM25 Pickle Deserialization Without Integrity Check

**Severity:** CRITICAL (Low probability, High impact)  
**Files:** `backend/app/core/rag/langchain_engine.py` [lines 207-215]

**Issue:**
The BM25 index is loaded via `pickle.load()` without any integrity verification:

```python
# Line 207-215
def _load_bm25(self, force: bool = False):
    """Load pre-built BM25 index from disk."""
    path = Path(settings.BM25_INDEX_PATH)
    
    # No mtime check if already loaded
    current_mtime = path.stat().st_mtime
    if not force and self._bm25_loaded and self._bm25_mtime == current_mtime:
        return

    try:
        with path.open("rb") as f:
            data = pickle.load(f)  # ❌ No integrity check
        self._bm25 = data.get("bm25")
        self._bm25_docs = data.get("documents", [])
        self._bm25_loaded = True
        self._bm25_mtime = current_mtime
        logger.info(f"BM25 loaded ({len(self._bm25_docs)} chunks)")
    except Exception as e:
        logger.warning(f"Failed to load BM25 index: {e}")
        self._bm25 = None
        self._bm25_docs = []
        self._bm25_loaded = True
        self._bm25_mtime = None
```

**Root Cause:**
- Pickle format allows arbitrary Python code execution during deserialization
- No checksum or signature validation of the pickle file
- If BM25 index file is corrupted or tampered, could execute malicious code
- File path is controlled via `settings.BM25_INDEX_PATH`

**Attack Scenario (Low Probability but High Impact):**
1. Attacker gains write access to `/data/bm25_index.pkl`
2. Replaces pickle file with malicious payload
3. Next time RAG engine loads BM25, arbitrary code executes with app privileges
4. For BSSN internal system: If network is compromised, this is a pivot point

**Impact:**
- **Security Vulnerability:** Arbitrary code execution via malicious pickle
- **Not Exploitable in Current Setup:** File is on local filesystem, not exposed
- **But:** Good practice to validate file integrity before unpickling

**TDD Regression Test Specification:**

```python
# backend/tests/test_bm25_pickle_security.py

def test_bm25_pickle_loading_validates_structure():
    """
    BLOCKING: BM25 pickle must validate that loaded data has expected structure.
    """
    engine = LangchainRAGEngine()
    
    # Load valid BM25
    engine._load_bm25(force=True)
    
    # Verify loaded data has expected keys
    assert engine._bm25 is not None or engine._bm25_loaded, (
        "BM25 load failed or not marked as attempted"
    )
    
    if engine._bm25_docs:
        # If docs loaded, verify structure
        for doc in engine._bm25_docs:
            assert "text" in doc, f"BM25 doc missing 'text': {doc.keys()}"
            assert "metadata" in doc, f"BM25 doc missing 'metadata': {doc.keys()}"
            assert isinstance(doc["metadata"], dict), (
                f"BM25 metadata not dict: {type(doc['metadata'])}"
            )


def test_bm25_corrupted_pickle_fails_safely():
    """
    BLOCKING: If pickle file is corrupted, catch exception and fallback gracefully.
    """
    import tempfile
    
    # Create corrupted pickle file
    with tempfile.NamedTemporaryFile(suffix=".pkl", delete=False) as f:
        corrupted_path = f.name
        f.write(b"this is not valid pickle data")
    
    try:
        # Attempt to load corrupted file
        engine = LangchainRAGEngine()
        
        # Mock the BM25_INDEX_PATH
        original_path = settings.BM25_INDEX_PATH
        settings.BM25_INDEX_PATH = corrupted_path
        
        # Should catch exception and set _bm25 = None
        engine._load_bm25(force=True)
        
        assert engine._bm25 is None, "Should fail gracefully and set _bm25=None"
        assert engine._bm25_loaded is True, "Should mark load as attempted"
        
    finally:
        settings.BM25_INDEX_PATH = original_path
        os.unlink(corrupted_path)


def test_bm25_pickle_file_must_exist():
    """
    BLOCKING: If BM25 pickle file doesn't exist, should log warning and continue.
    """
    engine = LangchainRAGEngine()
    
    # Mock non-existent path
    original_path = settings.BM25_INDEX_PATH
    settings.BM25_INDEX_PATH = "/nonexistent/path/bm25.pkl"
    
    try:
        # Should handle missing file gracefully
        engine._load_bm25(force=True)
        
        assert engine._bm25 is None
        assert engine._bm25_loaded is True
        
    finally:
        settings.BM25_INDEX_PATH = original_path
```

**Fix Strategy:**
1. After `pickle.load()`, validate loaded data structure:
   ```python
   assert isinstance(data, dict), "BM25 pickle must be dict"
   assert "bm25" in data, "Missing 'bm25' key"
   assert "documents" in data, "Missing 'documents' key"
   ```
2. Consider using `pickle.loads()` with restricted unpickler (e.g., `RestrictedUnpickler`)
3. Add checksum validation (optional, for defense-in-depth)

**Priority:** CRITICAL (security, though low probability)

---

## Medium-Severity Issues

### M-01: Silent 10K Chunk Truncation During Document Indexing

**Severity:** MEDIUM  
**Files:** `backend/app/core/ingestion/document_manager.py` [line 1531, 1578]

**Issue:**
When indexing a document, chunks are retrieved with `limit=10000`:

```python
# Line 1531
chunks = self.get_chunks(doc_id, limit=10000)
```

If a document has **more than 10,000 chunks**, the excess chunks are **silently truncated**:
- Only first 10k chunks are indexed
- No warning logged
- No indication that the document is incomplete
- User receives no feedback about truncation

```python
# Line 1578: Same issue in _rebuild_bm25_index
chunks = self.get_chunks(doc["doc_id"], limit=10000)
```

**Root Cause:**
- `get_chunks()` at line 901 uses `.limit(limit)` where limit defaults to 100
- When called with `limit=10000`, SQLAlchemy `.limit(10000)` truncates silently
- No check whether `chunk_count` exceeds the limit

**Impact:**
- **Data Loss:** Large documents (>10k chunks) are partially indexed
- **Silent Failure:** No user warning about incomplete indexing
- **Audit Trail Broken:** Cannot know if a query failed due to missing chunks or no match
- **For BSSN:** Regulatory documents might be large; truncation is a compliance issue

**Example:**
```
Document: "Laporan Audit BSSN 2024.pdf" has 15,000 chunks
Result: Only chunks 1-10,000 indexed, chunks 10,001-15,000 silently skipped
User: Queries might not find content in chunks 10,001-15,000
System: No warning that indexing was incomplete
```

**TDD Regression Test Specification:**

```python
# backend/tests/test_chunk_truncation_warning.py

def test_document_with_more_than_10k_chunks_logs_warning():
    """
    BLOCKING: If a document has >10k chunks, log clear warning during indexing.
    """
    # Create a document that will have >10k chunks
    # (requires a very large file or artificial setup)
    
    # Option 1: Mock the get_chunks to return 10001 chunks
    with patch.object(DocumentManager, 'get_chunks') as mock_get_chunks:
        mock_get_chunks.return_value = [
            {"id": i, "text": f"Chunk {i}" * 10}
            for i in range(10001)  # 10,001 chunks
        ]
        
        with patch('app.core.ingestion.document_manager.logger') as mock_logger:
            doc_mgr = DocumentManager()
            result = doc_mgr.index_document("test_doc_id")
            
            # MUST log warning about truncation
            mock_logger.warning.assert_called()
            warning_call = [c for c in mock_logger.warning.call_args_list 
                           if "10000" in str(c) or "truncat" in str(c).lower()]
            assert warning_call, "No truncation warning logged"


def test_index_document_respects_chunk_count_limit():
    """
    BLOCKING: index_document must explicitly check if chunk_count > 10000.
    """
    doc_id = upload_document("large_doc.pdf")
    
    # Mock: Set chunk_count > 10000
    with patch.object(DocumentManager, 'get_chunk_count') as mock_count:
        mock_count.return_value = 15000
        
        # Index should warn or raise
        result = doc_mgr.index_document(doc_id)
        
        # Either warn or raise, but not silently truncate
        assert result.get("warning_truncated") is True, (
            "Should indicate truncation in result"
        )
        assert result.get("chunks_indexed") <= 10000


def test_chunk_retrieval_pagination_for_large_documents():
    """
    BLOCKING: If document has >10k chunks, use pagination to index all.
    """
    doc_id = create_document_with_exactly(11000)  # 11k chunks
    
    result = doc_mgr.index_document(doc_id)
    
    # Should handle pagination internally
    assert result.get("chunks_indexed") == 11000, (
        f"Expected 11000 chunks indexed, got {result.get('chunks_indexed')}"
    )
    # OR if intentional limit, must warn
    if result.get("chunks_indexed") < 11000:
        assert "truncated" in result.get("warning", "").lower()
```

**Fix Strategy:**
1. Before indexing, check `chunk_count` against limit:
   ```python
   total_chunks = self.get_chunk_count(doc_id)
   if total_chunks > 10000:
       logger.warning(f"Document has {total_chunks} chunks, will index only 10000 (pagination not yet implemented)")
   ```
2. Better: Implement pagination to index all chunks in batches
3. Add `truncated=true` flag to result if chunks were truncated

**Priority:** MEDIUM — Data loss risk, but only for very large documents

---

### M-02: Missing Test Coverage for BM25 Search Text Construction

**Severity:** MEDIUM  
**Files:** `backend/app/core/ingestion/document_manager.py` [lines 315-329]

**Issue:**
The `_bm25_search_text()` function constructs search text from chunk metadata, but **only tested indirectly** (test_bm25_corpus.py tests the output, not the input-output mapping):

```python
def _bm25_search_text(text: str, metadata: Dict[str, Any]) -> str:
    """Compose BM25 search text from chunk content + structural metadata only."""
    fields = [
        metadata.get("hierarchy", ""),
        metadata.get("context_header", ""),
        metadata.get("bab", ""),
        metadata.get("bagian", ""),
        metadata.get("pasal", ""),
        metadata.get("ayat", ""),
        text or "",
    ]
    return " ".join(str(v).strip() for v in fields if str(v).strip())
```

**Root Cause:**
- Function has important business logic (field priority, exclusion of document-level fields)
- No direct unit test of field composition
- test_bm25_corpus.py tests that document-level fields ARE excluded, but not completeness

**Impact:**
- **Hidden Bug Risk:** Changes to field list could break search without test failure
- **Regression Risk:** If field order changes, BM25 IDF scores shift unpredictably
- **Maintenance Risk:** Difficult to verify that new fields are handled correctly

**TDD Regression Test Specification:**

```python
# backend/tests/test_bm25_search_text_unit.py

def test_bm25_search_text_includes_all_structural_fields():
    """
    BLOCKING: _bm25_search_text must include pasal, ayat, bab, bagian.
    """
    metadata = {
        "hierarchy": "BAB I > Pasal 5",
        "context_header": "BAB I - KETENTUAN UMUM",
        "bab": "BAB I",
        "bagian": "Bagian Pertama",
        "pasal": "Pasal 5",
        "ayat": "Ayat (2)",
    }
    text = "Isi chunk teks"
    
    result = _bm25_search_text(text, metadata)
    
    assert "BAB I" in result
    assert "Pasal 5" in result
    assert "Ayat (2)" in result
    assert "Isi chunk teks" in result


def test_bm25_search_text_excludes_document_level_fields():
    """
    BLOCKING: _bm25_search_text must NOT include judul_dokumen, filename, doc_type.
    """
    metadata = {
        "judul_dokumen": "PP Nomor 95 Tahun 2018",
        "filename": "PP_95_2018.pdf",
        "doc_type": "peraturan",
        "pasal": "Pasal 1",
    }
    text = "Isi chunk"
    
    result = _bm25_search_text(text, metadata)
    
    # Document-level fields should NOT be in result
    assert "PP Nomor 95 Tahun 2018" not in result
    assert "PP_95_2018.pdf" not in result
    assert result.count("peraturan") == 0  # Not as standalone field


def test_bm25_search_text_field_order_consistency():
    """
    Field order in search text should be consistent for reproducibility.
    """
    metadata = {...}
    
    result1 = _bm25_search_text("text", metadata)
    result2 = _bm25_search_text("text", metadata)
    
    # Same input should produce same output
    assert result1 == result2


def test_bm25_search_text_handles_empty_fields():
    """
    Empty metadata fields should not create double spaces.
    """
    metadata = {
        "hierarchy": "BAB I",
        "context_header": "",  # Empty
        "bab": "",  # Empty
        "pasal": "Pasal 5",
        "ayat": "",  # Empty
    }
    
    result = _bm25_search_text("text", metadata)
    
    assert "  " not in result, "Should not have double spaces"
    assert result.strip() != "", "Should not be empty"
```

**Fix Strategy:**
1. Add unit tests for `_bm25_search_text()` with edge cases
2. Document the intended field composition
3. Add test to verify that chunks with new fields (is_table, table_label) are included correctly

**Priority:** MEDIUM — Prevents future regressions

---

## Low-Severity Issues

### L-01: Missing Filename in BM25 _table_literal_search Metadata

**Severity:** LOW  
**Files:** `backend/app/core/rag/langchain_engine.py` [lines 324-350]

**Issue:**
The `_table_literal_search()` function filters BM25 results by document scope (if `doc_id` supplied), but the filtering code checks for `metadata.get("filename", "")`:

```python
# Line 343
if target_filename and str(metadata.get("filename", "")) != target_filename:
    continue
```

However, as noted in CR-03, BM25 metadata doesn't include filename. This filter always fails silently.

**Root Cause:**
- This is a symptom of CR-03 (missing filename in BM25)
- Low severity because it's in a table-specific search function
- Will be fixed when CR-03 is fixed

**TDD Note:**
- Covered by CR-03 tests
- No separate test needed

**Priority:** LOW — Will be fixed by CR-03

---

### L-02: Query Classification Doesn't Check Metadata Constraints

**Severity:** LOW  
**Files:** `backend/app/core/rag/langchain_engine.py` [lines 38-52]

**Issue:**
The `classify_query()` function returns query type ("table", "pasal", "ranking", "general") but doesn't validate whether the document actually contains that content type:

```python
def classify_query(query: str) -> str:
    q = (query or "").lower()
    if re.search(r'\btabel\b|\btable\b', q):
        return "table"  # Assumes document has tables
    # ...
    return "general"
```

If user asks "Apa isi Tabel 13?" but the scoped document has no tables, the router will try table-specific retrieval and fail.

**Root Cause:**
- Classification is text-based only, doesn't check document metadata
- Would require passing `doc_id` to `classify_query()` and checking document properties
- Current implementation is pragmatic; tables should be tagged in metadata

**Impact:**
- **Inefficiency:** May attempt table-specific retrieval on documents without tables
- **Fallback:** Router will retry with generic search, so functionally correct
- **Performance:** Extra round-trip for table queries on non-table documents

**Priority:** LOW — Fallback mechanism works, just not optimal

---

### L-03: Reranker Failure Logging Lacks Detail

**Severity:** LOW  
**Files:** `backend/app/core/rag/langchain_engine.py` [line 816]

**Issue:**
When reranker fails to load, the warning logs the exception but doesn't capture model name or device:

```python
# Line 815-817
except Exception as e:
    self._reranker_failed = True
    logger.warning(f"Reranker unavailable, fallback to RRF-only: {e}")
```

**Improvement:**
Include more context in the warning:

```python
logger.warning(
    f"Reranker unavailable (model={settings.RERANKER_MODEL_NAME}, "
    f"device={settings.RERANKER_DEVICE}), fallback to RRF-only: {e}"
)
```

**Priority:** LOW — Informational improvement only

---

## Summary: TDD Execution Plan

### Phase 1: Critical Fixes (Blocking)

**Order of Execution:**
1. **Fix CR-03 First:** Add filename to BM25 metadata
   - Prerequisite for CR-01 (doc-scoped filtering)
   - Enable CR-02 (table metadata) fields
   - TDD: test_bm25_filename_metadata.py

2. **Fix CR-02:** Add table metadata (is_table, table_label, table_context) to BM25
   - Builds on CR-03
   - Enables table-specific retrieval
   - TDD: test_bm25_table_metadata.py

3. **Fix CR-04:** Add Pasal prefix to early buffer flushes
   - Independent of other fixes
   - TDD: test_peraturan_chunker_pasal_prefix.py

4. **Fix CR-01:** Remove fallback for doc-scoped retrieval
   - Depends on CR-03 (filename filtering)
   - Return empty results instead of global search
   - TDD: test_rag_doc_scoped_isolation.py

5. **Fix CR-05:** Add integrity checks to pickle loading
   - Independent
   - Low probability but important for security
   - TDD: test_bm25_pickle_security.py

### Phase 2: Medium Fixes

6. **Fix M-01:** Add truncation warning and implement pagination
   - TDD: test_chunk_truncation_warning.py

7. **Add M-02:** Direct unit tests for `_bm25_search_text()`
   - TDD: test_bm25_search_text_unit.py

### Phase 3: Low Improvements

8. **Add L-03:** Improve reranker failure logging

---

## Execution Gates & Validation

### Before Implementing Any Fix:
- [ ] Run existing test suite: `pytest backend/tests/ -v --tb=short`
- [ ] Verify no regressions from current tests

### After Each Fix:
- [ ] Run the corresponding TDD regression test suite
- [ ] Run full test suite to verify no side effects
- [ ] Manual smoke test with `backend/scripts/rag_trace.py`

### Before Merging:
- [ ] All Critical fixes pass regression tests
- [ ] All Medium fixes pass regression tests
- [ ] Full test suite passes
- [ ] Code review by senior engineer

---

## Cross-Cutting Concerns

### Dependency Graph:
```
CR-03 (filename)
  ↓
CR-01 (doc-scoped isolation)
  ↓
CR-02 (table metadata)  ← Also depends on CR-03

CR-04 (pasal prefix) — Independent

CR-05 (pickle security) — Independent

M-01 (chunk truncation) — Independent

M-02 (BM25 search text) — Independent
```

### Backward Compatibility:
- **CR-01, CR-02, CR-03:** No breaking changes to API; improves behavior
- **CR-04:** Chunk text format changes; may affect downstream processing (verify)
- **CR-05:** No API changes; improves robustness
- **M-01:** No API changes; adds warning
- **M-02:** Tests only; no code changes

---

## Deliverables

✅ **This Review Document** — Comprehensive finding inventory with root causes  
✅ **TDD Specifications** — Exact test function signatures and assertions  
✅ **Fix Strategies** — Code-level recommendations for each issue  
✅ **Execution Plan** — Ordered, dependency-aware phase breakdown  
✅ **Validation Gates** — Testing and review checkpoints  

**Next Step:** Implement critical fixes in Phase 1 using TDD (Red-Green-Refactor).

---

_Code Review completed: 2026-05-06_  
_Reviewer: GitHub Copilot (Haiku 4.5)_  
_Methodology: GSD Code Review Skill + Superpowers:code-review_  
_Depth: Standard (per-file analysis + cross-file dependencies)_
