# Legal Hierarchical Chunking and Safe Reindex Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Preserve complete legal context across chunk boundaries and rebuild the active corpus with correct heading ownership, parent-child relationships, neighbor links, and legal cross-reference metadata.

**Architecture:** Keep ayat-level chunks searchable, attach the complete Pasal as parent context, and store structural IDs plus previous/next/reference edges in chunk metadata. Retrieval expands each anchor independently so another primary hit may still serve as its neighbor, then reranks the stitched windows. Reindexing uses backups and validation gates; destructive replacement is not accepted unless SQLite, BM25, and Qdrant align.

**Tech Stack:** Python 3.10, FastAPI, SQLAlchemy/SQLite, Qdrant, rank_bm25, LangChain Documents, pytest, Docker Compose.

---

### Task 1: Fix primary-candidate neighbor stitching

**Files:**
- Modify: `backend/app/core/rag/engine/context_stitching.py`
- Test: `backend/tests/test_rag_modular_regression.py`

- [ ] Add a failing test with adjacent primary chunks 28 and 29 plus mocked Qdrant payloads proving each anchor receives the other primary chunk in its ordered window.
- [ ] Run `docker compose -f docker-compose.dev.yml -f docker-compose.gpu.yml exec -T backend pytest tests/test_rag_modular_regression.py -q`; expect the new test to fail because `doc_neighbors -= indices` removes adjacent primary candidates.
- [ ] Replace document-global neighbor subtraction with per-anchor windows. Include primary documents in the local candidate map, fetch only missing indices from Qdrant, and build each anchor from `anchor-1`, `anchor`, `anchor+1` without shared mutable state.
- [ ] Preserve role filters, `doc_id`, `chunk_index`, ordering, and overlap-aware text merging.
- [ ] Run the focused test and the full context-stitching regression suite; expect all tests to pass.

### Task 2: Parse heading ownership and legal references

**Files:**
- Modify: `backend/app/core/ingestion/json_structure_parser.py`
- Test: `backend/tests/test_legal_hierarchical_chunking.py`

- [ ] Add a failing parser test for `Pasal 8 ... Bagian Keempat\nKriteria Audit Keamanan SPBE\nPasal 9 ...`; assert the new Bagian belongs to Pasal 9 and is absent from Pasal 8 text.
- [ ] Add failing tests for split Bagian titles on the next non-empty line and references such as `sebagaimana dimaksud dalam Pasal 8 ayat (3)`.
- [ ] Run focused tests; expect failures from absent heading-title carry and reference extraction.
- [ ] Update `parse_peraturan` so a Bagian marker flushes the preceding Pasal, captures its title from either the same line or the next heading line, and applies it only to subsequent Pasal records.
- [ ] Add a small pure helper that extracts normalized legal targets (`pasal-8`, `pasal-8/ayat-3`, local `ayat-2`) from Pasal/ayat content without inventing targets.
- [ ] Run focused parser tests; expect all to pass.

### Task 3: Emit hierarchical searchable chunks

**Files:**
- Modify: `backend/app/core/ingestion/structured_chunker.py`
- Test: `backend/tests/test_legal_hierarchical_chunking.py`

- [ ] Add failing tests asserting each regulation child has `section_id`, `pasal_id`, `ayat_id`, `parent_id`, `parent_pasal_text`, `reference_targets`, and a stable structural key.
- [ ] Assert ayat children remain searchable separately while `parent_pasal_text` contains the complete Pasal exactly once.
- [ ] Implement deterministic slugs from document title/BAB/Bagian/Pasal/Ayat using existing `slug_text`; do not add DB columns because `chunk_metadata` already stores JSON.
- [ ] Build complete Pasal parent text once, attach it to every child, and keep the child text as the embedding/BM25 unit.
- [ ] After final chunk ordering, attach `previous_chunk_id` and `next_chunk_id` using deterministic canonical IDs; first/last edges are null.
- [ ] Preserve existing table, lampiran, access, and citation metadata.
- [ ] Run focused chunker tests and existing `test_spbe_chunker.py`, `test_chunker_sizes.py`, and figure integration tests.

### Task 4: Persist and index hierarchy metadata

**Files:**
- Modify: `backend/app/core/ingestion/document_manager.py`
- Modify: `backend/app/core/rag/context_ids.py`
- Modify: `backend/scripts/rebuild_bm25.py`
- Modify: `backend/scripts/sync_vectors.py`
- Test: `backend/tests/test_legal_hierarchical_chunking.py`
- Test: `backend/tests/test_context_ids.py`

- [ ] Add failing tests proving all hierarchy/edge fields survive structured mapping, `save_chunks`, SQLite JSON, BM25 documents, and Qdrant payload construction.
- [ ] Make canonical context IDs prefer the deterministic structural key while retaining the old `doc<id>:idx<n>` fallback for legacy chunks.
- [ ] Propagate hierarchy fields through every structured chunk mapping and payload builder; preserve `allowed_roles`, uploader, document identity, and citation fields.
- [ ] Replace random Qdrant point IDs with deterministic UUID5 values derived from canonical context IDs so repeated indexing is idempotent.
- [ ] Include structural labels in BM25 search text without indexing full parent text, preventing term-frequency inflation.
- [ ] Run focused persistence/identity tests and retrieval access-control tests.

### Task 5: Add safe backup and staged rebuild tooling

**Files:**
- Create: `backend/scripts/reindex_hierarchical.py`
- Test: `backend/tests/test_reindex_hierarchical.py`

- [ ] Add tests for preflight refusal when source PDFs are missing, backup creation failure, count mismatch, failed document processing, and rollback metadata.
- [ ] Implement `--preflight`, `--backup-only`, `--rebuild`, and `--validate` modes.
- [ ] Back up the configured SQLite database and BM25 pickle with timestamped copies; request a Qdrant snapshot and record snapshot name, collection, counts, model, and timestamp in a JSON manifest.
- [ ] Refuse destructive rebuild unless every active document source exists and backups verify readable.
- [ ] Reuse the production parser/chunker/embedding paths; do not duplicate ingestion logic.
- [ ] Build a staging BM25 file and staging Qdrant collection. Validate staged counts and required metadata before swapping collection alias/file.
- [ ] Keep the SQLite backup and Qdrant snapshot after success for explicit rollback.
- [ ] Run focused script tests without mutating production services.

### Task 6: Back up and reindex the complete corpus

**Files:**
- Runtime artifacts only; do not commit backups or Qdrant storage.

- [ ] Run preflight and record active document/source/chunk counts.
- [ ] Run backup-only mode and verify SQLite copy, BM25 copy, Qdrant snapshot, and manifest.
- [ ] Run the hierarchical rebuild over all active documents in the backend container.
- [ ] Abort and restore if any document fails, any required access metadata is absent, or staged SQLite/BM25/Qdrant counts differ.
- [ ] Activate the rebuilt collection/index only after all validation gates pass.

### Task 7: Validate behavior and quality

**Files:**
- Test: `backend/tests/test_legal_hierarchical_chunking.py`
- Runtime report: `data/evaluation_report_hierarchical_reindex.json`

- [ ] Confirm the Peraturan BSSN 8/2024 Pasal 8 chunk no longer contains `Bagian Keempat`.
- [ ] Confirm Pasal 9 owns `Bagian Keempat - Kriteria Audit Keamanan SPBE`, has complete parent text, valid prev/next edges, and resolves the Pasal 8 reference when present.
- [ ] Run a retrieval-only trace for the Pasal 8–9 query; verify no dangling context and primary/supporting citations remain distinct.
- [ ] Compare SQLite, BM25, and Qdrant counts and canonical ID sets; require exact equality.
- [ ] Verify non-admin filters still exclude unauthorized chunks and admin retrieval remains complete.
- [ ] Run retrieval benchmark before/after; reject if Hit@5 or MRR drops more than 0.02.
- [ ] Run full backend tests, readiness, and a no-LLM retrieval canary.

### Task 8: Review and rollback readiness

**Files:**
- No new source files unless review finds a defect.

- [ ] Run post-implementation goal, code, security, QA, and context review.
- [ ] Fix introduced blockers and rerun affected tests.
- [ ] Record backup manifest and exact rollback commands in the final report.
- [ ] Do not delete backups or push/commit unless explicitly requested.
