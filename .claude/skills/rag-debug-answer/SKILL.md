---
name: rag-debug-answer
description: Use when user reports a RAG answer problem in this SPBE project — wrong sources cited, answer contains content from unexpected document, doc_id scoping leaked, fabricated pasal/ayat, unavailable detector triggered incorrectly, or asks why the retriever returned specific docs. Traces classify_query → doc filter → per-path retrieval (vector / BM25 / table-literal) → rerank → context → answer via backend/scripts/rag_trace.py and reports root cause with file:line recommendations.
---

# RAG Answer Debugging Runbook

Magnetic skill. Auto-invokes when user describes symptoms like:
- "kenapa sumbernya dari dokumen X?"
- "jawabannya ngarang Pasal 99"
- "filter document_id tidak jalan"
- "tabel 13 diambil dari dokumen salah"
- "unavailable detector keliru"

## Steps

### 1. Parse the complaint
- Extract: exact query string, optional `document_id`.
- If ambiguous, ask ONE short question: "Query persisnya apa? Dan ada `document_id` yang Anda kirim?" Don't investigate yet.

### 2. Run the tracer
```
python backend/scripts/rag_trace.py --query "<QUERY>" [--doc-id <ID>] --json
```
Capture the JSON. If the command errors (backend/engine not bootable), fallback: ask user to start the backend or provide the request body; you can also hit `/api/chat/stream` via curl and inspect `sources` directly.

### 3. Analyze with this checklist (in order)

| Hypothesis | Signal in trace | Where to fix |
|---|---|---|
| **H1. doc_id tidak ter-resolve** | `filter_resolution.resolved` is `null` despite user passing `doc_id` | `_resolve_doc_target` in `backend/app/core/rag/langchain_engine.py` — check DB query (doc_id string vs id int) |
| **H2. Qdrant payload key mismatch** | `filter_resolution.qdrant_hit_count == 0` but doc exists in DB | `_build_doc_filter` in same file — inspect Qdrant payload structure with a direct scroll |
| **H3. Satu jalur bocor** | Filenames in one of `vector_search` / `bm25_search` / `table_literal_search` differ from target | That path's scoping: `_vector_search` (qdrant_filter), `_bm25_search` (doc_id), `_table_literal_search` (doc_id) |
| **H4. Fallback terlalu agresif** | `qdrant_hit_count > 0` but final `raw_doc_filenames` includes other docs | `retrieve_context` fallback-no-filter branch in `langchain_engine.py` — fallback should only kick in on 0 docs, not on few |
| **H5. Rerank menenggelamkan target** | `rerank.final_top_docs` top-5 none from target filename but earlier paths had them | Cross-encoder model — usually tuning, not a bug; confirm with user |
| **H6. Unavailable detector over-trigger** | Answer contains deskriptif "tidak tercantum" + `quality_check.has_unavailable_claim=true` while context clearly has numeric evidence | `_contains_unavailable_signal` in `backend/app/api/routes/chat.py` — see Fase 2 plan `sementara-ini-saya-memiliki-playful-kay.md` |

Report format:
- **Symptom** — one line quoting user complaint
- **Trace evidence** — the section(s) that triggered hypothesis
- **Root cause** — pick ONE most likely H#
- **Fix target** — exact file:line
- **Next step** — "Hand off to superpowers:test-driven-development to write a failing test before editing <file>"

### 4. Do NOT apply the fix yourself
This skill only diagnoses. After reporting, wait for user confirmation. When they confirm, invoke `superpowers:test-driven-development` — write the failing test first.

### 5. Escalation
If 2 iterations of H1–H6 don't explain the symptom:
1. Ask user for the commit SHA of the last known-good state.
2. Suggest `git bisect start HEAD <known-good-sha>` with the tracer command as the test.
