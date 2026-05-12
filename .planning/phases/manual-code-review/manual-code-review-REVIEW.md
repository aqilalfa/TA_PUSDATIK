---
phase: manual-code-review
reviewed: 2026-05-11T00:00:00Z
depth: standard
files_reviewed: 7
files_reviewed_list:
  - backend/app/core/rag/langchain_engine.py
  - backend/app/core/rag/engine/retrievers.py
  - backend/app/core/rag/engine/context_stitching.py
  - backend/app/core/rag/engine/rankers.py
  - backend/app/core/ingestion/document_manager.py
  - backend/app/api/routes/chat.py
  - backend/app/core/rag/prompts.py
findings:
  critical: 1
  warning: 4
  info: 0
  total: 5
status: issues_found
---
# Phase manual-code-review: Code Review Report

**Reviewed:** 2026-05-11T00:00:00Z  
**Depth:** standard  
**Files Reviewed:** 7  
**Status:** issues_found

## Summary

Reviewed retrieval and citation flow after modularization. Found one critical doc scoping mismatch plus four warning-level issues that can cause table retrieval drift, citation mislabeling after stitching, missing neighbors in multi-doc pools, and citation validation false negatives.

## Critical Issues

### CR-01: Doc-scoped filters target the wrong payload field

**File:** `backend/app/core/rag/langchain_engine.py:143-148`  
**File:** `backend/app/core/rag/engine/retrievers.py:81-86`  
**File:** `backend/app/core/rag/engine/retrievers.py:140-142`  
**File:** `backend/app/core/ingestion/document_manager.py:1540-1557`

**Issue:** Retrieval filters use `document_id`, while Qdrant payloads store `doc_id`. When a document filter is requested, the filter matches zero points, letting cross-document candidates into RRF and producing incorrect citations for scoped queries.

**Fix:**
```python
# Align filters to payload keys and allow legacy fallback if needed.
Filter(must=[FieldCondition(key="doc_id", match=MatchValue(value=str(doc_id)))])
# Optionally add a should-condition for document_id to support legacy payloads.
```

## Warnings

### WR-01: Table metadata is computed but not persisted; literal search targets the wrong field

**File:** `backend/app/core/ingestion/document_manager.py:535-608`  
**File:** `backend/app/core/ingestion/document_manager.py:335-352`  
**File:** `backend/app/core/ingestion/document_manager.py:1539-1560`  
**File:** `backend/app/core/rag/engine/retrievers.py:81-84`  
**File:** `backend/app/core/rag/engine/rankers.py:116-129`

**Issue:** `table_label` and `is_table` are derived but never persisted into chunk metadata or Qdrant payloads, so the table-aware boost in `RAGRanker` never triggers. Additionally, `table_literal_search` tries an exact match against `table_context`, which is stored as surrounding prose, not the literal label (for example, `Tabel 13`). This combination makes table queries drift into non-table chunks and can produce missing or wrong citations.

**Fix:**
- Persist `is_table` and `table_label` in chunk dicts, `chunk_metadata`, BM25 metadata, and Qdrant payloads.
- Change literal search to match `table_label` (or use `MatchText` on `text`/`context_header`).

### WR-02: Neighbor stitching can merge cross-section text under a single citation

**File:** `backend/app/core/rag/engine/context_stitching.py:143-164`

**Issue:** Neighbor chunks are merged into one document while retaining only the center metadata. If a neighboring chunk crosses into another Pasal/section, citations in the merged context can point to the wrong Pasal or hierarchy label.

**Fix:**
- Only stitch neighbors that share the same `pasal`/`context_header`/`hierarchy`.
- Or keep neighbors as separate docs and update sources accordingly.

### WR-03: Global neighbor index pruning can drop valid neighbors across multiple docs

**File:** `backend/app/core/rag/engine/context_stitching.py:26-36`

**Issue:** Neighbor indices are computed globally and center indices are removed across all documents. When one doc's center index matches another doc's neighbor index, the neighbor is removed for both, reducing context coverage and potentially omitting citations.

**Fix:**
- Track neighbor indices per `doc_id` or filter per document rather than using a global set.

### WR-04: Citation validation counts duplicate source lines, masking invalid citations

**File:** `backend/app/core/rag/langchain_engine.py:212-234`  
**File:** `backend/app/core/rag/prompts.py:556`

**Issue:** Context formatting prints `[n]` entries in both the summary and detail sections. `validate_answer` counts these lines to determine `context_sources`, which effectively doubles the source count and can allow out-of-range citations to pass validation.

**Fix:**
- Use `len(sources)` directly for validation, or de-duplicate source indices from context before counting.

## Missing Tests

- Doc-scoped retrieval: verify that vector, table-literal, and indicator-literal searches honor `doc_id` and never return cross-document chunks.
- Table queries: ensure `table_label`/`is_table` are persisted and that table literal search hits the intended chunks.
- Stitching boundaries: confirm that stitched contexts do not mix Pasal/section metadata, and that sources remain accurate.
- Citation validation: assert that citations beyond the real source count are flagged even when context contains multiple `[n]` sections.

---

_Reviewed: 2026-05-11T00:00:00Z_  
_Reviewer: the agent (gsd-code-reviewer)_  
_Depth: standard_
