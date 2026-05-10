---
phase: manual-code-review
reviewed: 2026-05-06T00:00:00Z
depth: standard
files_reviewed: 5
files_reviewed_list:
  - backend/app/core/rag/langchain_engine.py
  - backend/app/core/ingestion/document_manager.py
  - backend/app/core/rag/prompts.py
  - backend/app/api/routes/chat.py
  - backend/app/core/ingestion/structured_chunker.py
findings:
  critical: 1
  warning: 5
  info: 0
  total: 6
status: issues_found
---
# Phase manual-code-review: Code Review Report

**Reviewed:** 2026-05-06T00:00:00Z  
**Depth:** standard  
**Files Reviewed:** 5  
**Status:** issues_found

## Summary

Reviewed core RAG retrieval, ingestion, prompts, and chat streaming. Found one critical data-scoping bug and multiple retrieval-quality regressions in BM25 metadata and peraturan chunking.

## Critical Issues

### CR-01: Doc-scoped retrieval filter mismatches Qdrant payload

**File:** `backend/app/core/rag/langchain_engine.py:172-182`
**Issue:** `_build_doc_filter` targets `metadata.document_id` (numeric DB id), but ingestion stores `doc_id` as a top-level payload field. The filter matches zero points, triggering the unscoped fallback path (lines 1343-1347) and returning cross-document context when a `doc_id` was provided.
**Fix:**
```python
# Option A: filter by doc_id string (payload top-level)
return Filter(must=[FieldCondition(key="doc_id", match=MatchValue(value=doc_id))])

# Option B: store document_id in payload during ingestion, then keep metadata.document_id
```

## Warnings

### WR-01: BM25 doc-scoped filtering drops all results

**File:** `backend/app/core/rag/langchain_engine.py:167,294`
**Issue:** `_resolve_doc_target` returns the stored filename (`row.filename`), but `_bm25_search` filters chunks by `metadata["filename"]`. BM25 metadata does not include `filename` in `_rebuild_bm25_index`, so doc-scoped BM25 queries always empty out.
**Fix:** Use `doc_id` for BM25 filtering, or include both `filename` and `original_filename` in BM25 metadata and compare against the correct field.

### WR-02: BM25 metadata omits table-specific fields used by ranking

**File:** `backend/app/core/ingestion/document_manager.py:1588-1596`
**Issue:** `_rebuild_bm25_index` only stores a minimal metadata set and drops `chunk_type`, `is_table`, `table_label`, `table_context`, etc. `_table_literal_search` and `_query_metadata_boost` rely on these flags (langchain_engine.py:373,1121), so table boosting never triggers for BM25 docs.
**Fix:** Persist table-related fields into BM25 metadata (at least `chunk_type`, `is_table`, `table_label`, `table_context`).

### WR-03: Inconsistent "Pasal" prefix on peraturan ayat chunks

**File:** `backend/app/core/ingestion/structured_chunker.py:441-462`
**Issue:** Intermediate ayat buffers are flushed without a "Pasal X" prefix, while the final buffer includes it. Early chunks lose explicit Pasal context in their text, reducing retrieval for Pasal-specific queries.
**Fix:** Prepend `Pasal {pasal_nomor}` consistently for all buffer flushes.

### WR-04: Hard 10,000-chunk limits cause silent truncation

**File:** `backend/app/core/ingestion/document_manager.py:1531,1578`
**Issue:** Both `index_document` and `_rebuild_bm25_index` cap chunks at 10,000 without warning. Large documents silently lose tail chunks in Qdrant/BM25.
**Fix:** Paginate chunk retrieval or warn/abort when `total_chunks > limit`.

### WR-05: Unvalidated pickle load of BM25 index

**File:** `backend/app/core/rag/langchain_engine.py:207`
**Issue:** `pickle.load` executes arbitrary code if the BM25 index file is tampered. In a shared environment this is a security risk.
**Fix:** Restrict file permissions and validate file origin/hash, or switch to a safer serialization format.

---

_Reviewed: 2026-05-06T00:00:00Z_  
_Reviewer: the agent (gsd-code-reviewer)_  
_Depth: standard_
