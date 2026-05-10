---
date: 2026-05-06
task: comprehensive-code-review
status: complete
---

# Session Summary: Comprehensive Code Review — SPBE RAG Backend

## Reviewed Files
1. `backend/app/core/rag/langchain_engine.py` (~61KB) — RAG engine, hybrid search, retrieval
2. `backend/app/core/ingestion/document_manager.py` (~67KB) — Document lifecycle, BM25 indexing
3. `backend/app/core/ingestion/structured_chunker.py` — Chunking strategy, Peraturan/Laporan splitting

## Findings Summary

### Critical Issues (5) — BLOCKING

**CR-01: Doc-Scoped Retrieval Falls Back to Global Search**
- When `doc_id` supplied, expects results only from that document
- Falls back to global search if vector retrieval returns 0 results
- **Impact:** Cross-document result leakage, violates scope constraint
- **TDD Test:** `test_doc_scoped_retrieval_never_leaks_to_other_documents()`

**CR-02: BM25 Metadata Missing Table Flags**
- Table metadata (is_table, table_label, table_context) extracted in SQLite but NOT carried to BM25
- Chunks saved with table_context, section, but lost during BM25 rebuild (lines 1588-1596)
- **Impact:** Table queries cannot filter by table presence, degraded search quality
- **TDD Test:** `test_bm25_index_includes_is_table_flag()`

**CR-03: BM25 Metadata Missing Filename**
- Filename not included in BM25 metadata dict (critical issue causing CR-01)
- Code at langchain_engine.py:294 tries to filter by filename but field is always ""
- **Impact:** Document-scoped BM25 filtering broken
- **TDD Test:** `test_bm25_metadata_includes_filename()`

**CR-04: Peraturan Chunker Loses "Pasal N" Prefix in Early Buffer Flushes**
- When ayat buffer fills and flushes early (line 447), "Pasal N" prefix is missing
- Only final flush (line 461) includes prefix
- **Impact:** Early chunks appear orphaned, query context loss
- **TDD Test:** `test_all_peraturan_ayat_chunks_include_pasal_prefix()`

**CR-05: BM25 Pickle Deserialization Without Integrity Check**
- `pickle.load()` at line 207 has no validation
- No checksum, signature, or structure verification
- **Impact:** Low probability but high-impact security vulnerability
- **TDD Test:** `test_bm25_pickle_loading_validates_structure()`

### Medium Issues (2) — SHOULD FIX SOON

**M-01: Silent 10K Chunk Truncation During Indexing**
- Documents with >10,000 chunks silently truncate at line 1531, 1578
- No warning to user about incomplete indexing
- **Impact:** Data loss for very large documents
- **TDD Test:** `test_document_with_more_than_10k_chunks_logs_warning()`

**M-02: Missing Test Coverage for BM25 Search Text Construction**
- `_bm25_search_text()` has important business logic but no direct unit tests
- Only indirect testing through corpus-level tests
- **Impact:** Hidden bug risk for field composition changes
- **TDD Test:** `test_bm25_search_text_includes_all_structural_fields()`

### Low Issues (3) — NICE TO HAVE

**L-01:** Missing filename in `_table_literal_search()` metadata (symptom of CR-03)  
**L-02:** Query classification doesn't validate document content constraints  
**L-03:** Reranker failure logging lacks detail  

## Execution Order (Phase Breakdown)

### Phase 1: Critical Fixes (Blocking)
1. **CR-03:** Add filename to BM25 metadata (prerequisite for CR-01)
2. **CR-02:** Add table metadata to BM25
3. **CR-04:** Add Pasal prefix to early buffer flushes
4. **CR-01:** Remove fallback for doc-scoped retrieval (depends on CR-03)
5. **CR-05:** Add pickle integrity checks

### Phase 2: Medium Fixes
6. **M-01:** Add truncation warning and pagination
7. **M-02:** Add direct unit tests for `_bm25_search_text()`

### Phase 3: Low Improvements
8. **L-03:** Improve reranker failure logging

## Key Findings

**Root Causes:**
- BM25 metadata dict was added at line 1588 with hardcoded field list
- When new fields (table metadata, filename) were added to chunks, BM25 wasn't updated
- Peraturan chunker has inconsistent buffer flushing logic (early vs final)
- Pickle loading lacks defensive programming

**Cross-File Dependencies:**
```
langchain_engine.py:294 (BM25 filename filter)
    ↑ depends on
document_manager.py:1588 (BM25 metadata dict)
```

**Impact on SPBE RAG:**
- Table queries may return wrong results due to missing table metadata
- Document-scoped queries leak cross-document results (CR-01)
- Regulatory documents may be partially indexed (M-01)
- Peraturan chunks lose structural context (CR-04)

## Validation Gates

**Before Implementation:**
- [ ] Run existing test suite: `pytest backend/tests/ -v`
- [ ] Verify no current test failures

**After Each Fix:**
- [ ] Run specific regression test suite
- [ ] Run full test suite for side effects
- [ ] Manual smoke test with `backend/scripts/rag_trace.py`

**Before Merge:**
- [ ] All Critical fixes pass TDD tests
- [ ] Full test suite green
- [ ] Code review by senior engineer

## Deliverables

- ✅ COMPREHENSIVE_CODE_REVIEW.md — Full detailed report with TDD specs
- ✅ This session summary — Quick reference
- ✅ TDD Regression Test Specifications — Exact test function signatures
- ✅ Fix Strategies — Code-level recommendations
- ✅ Execution Plan — Ordered, dependency-aware phases

## Next Steps

1. Implement CR-03 (filename in BM25) first — it's a prerequisite for other fixes
2. For each fix, follow Red-Green-Refactor TDD cycle
3. Run regression tests before and after each fix
4. Merge only after all Critical fixes pass validation gates

---

**Duration:** Comprehensive standard-depth review of 3 critical files  
**Method:** GSD code-review skill + superpowers:code-review + TDD specifications  
**Evidence-Based:** All issues verified by direct code inspection and cross-file dependency analysis  
