---
name: rag-debug-answer
description: Use when user reports a RAG answer problem in this SPBE project, such as wrong sources cited, answer containing content from unexpected document, doc_id scoping leaked, fabricated pasal/ayat, unavailable detector triggered incorrectly, or asks why the retriever returned specific docs.
---

# RAG Answer Debugging Runbook

## Overview
A systematic diagnosis approach to identify exactly where in the pipeline (retrieval, filtering, reranking, or generation) a RAG answer failed.

## When to Use

- "kenapa sumbernya dari dokumen X?"
- "jawabannya ngarang Pasal 99"
- "filter document_id tidak jalan"
- "tabel 13 diambil dari dokumen salah"
- "unavailable detector keliru"

## Diagnosis Steps

### 1. Parse the Complaint
- Extract the exact query string and the optional `document_id`.
- If ambiguous, ask ONE short question: "Query persisnya apa? Dan ada `document_id` yang Anda kirim?". Do not investigate until you have this.

### 2. Run the Tracer
Execute the tracing script to capture pipeline states:
```bash
python backend/scripts/rag_trace.py --query "<QUERY>" [--doc-id <ID>] --json
```
*If the backend is not bootable, fall back to asking the user for the request body or use curl against `/api/chat/stream` to inspect `sources`.*

### 3. Analyze Trace Data (In Order)

| Hypothesis | Signal in trace | Where to fix |
|---|---|---|
| **H1. doc_id tidak ter-resolve** | `filter_resolution.resolved` is `null` despite user passing `doc_id` | `_resolve_doc_target` in `backend/app/core/rag/langchain_engine.py` |
| **H2. Qdrant payload key mismatch** | `filter_resolution.qdrant_hit_count == 0` but doc exists in DB | `_build_doc_filter` in same file |
| **H3. Satu jalur bocor** | Filenames in one of `vector_search` / `bm25_search` / `table_literal_search` differ from target | That path's scoping: `_vector_search`, `_bm25_search`, `_table_literal_search` |
| **H4. Fallback terlalu agresif** | `qdrant_hit_count > 0` but final `raw_doc_filenames` includes other docs | `retrieve_context` fallback-no-filter branch in `langchain_engine.py` |
| **H5. Rerank menenggelamkan target** | `rerank.final_top_docs` top-5 none from target filename | Cross-encoder model (tuning issue, confirm with user) |
| **H6. Unavailable detector over-trigger** | Answer contains "tidak tercantum" + `quality_check.has_unavailable_claim=true` while context has evidence | `_contains_unavailable_signal` in `backend/app/api/routes/chat.py` |

### 4. Report Format

Output your findings exactly like this:
- **Symptom:** [Quote user]
- **Trace evidence:** [What triggered the hypothesis]
- **Root cause:** [H1-H6]
- **Fix target:** [File and Line]
- **Next step:** Hand off to systematic-debugging and test-driven-development skills to write a failing test before editing.

## Red Flags - STOP and Start Over
- Trying to apply a fix before reporting the diagnosis.
- Editing files without writing a failing test first.

**All of these mean: Stop. Report the diagnosis. Wait for approval. Invoke TDD.**

## Escalation
If 2 iterations of H1–H6 don't explain the symptom:
1. Ask user for the commit SHA of the last known-good state.
2. Suggest `git bisect start HEAD <known-good-sha>` with the tracer command as the test.
