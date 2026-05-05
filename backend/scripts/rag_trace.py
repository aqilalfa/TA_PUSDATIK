"""
Trace RAG retrieval pipeline for a single query.

Usage:
    python backend/scripts/rag_trace.py --query "apa isi tabel 13?" [--doc-id 3] [--json]

Emits 7 structured sections (classify_query, filter_resolution, vector_search,
bm25_search, table_literal_search, rerank, final_context_and_answer).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# Make backend/app importable
_THIS = Path(__file__).resolve()
_BACKEND = _THIS.parents[1]
sys.path.insert(0, str(_BACKEND))

from app.core.rag.langchain_engine import classify_query, langchain_engine  # noqa: E402
from app.core.rag.prompts import expand_query  # noqa: E402


def _get_engine():
    """Return initialized engine singleton. Indirection simplifies test mocking."""
    if not getattr(langchain_engine, "_initialized", False):
        langchain_engine.initialize()
    return langchain_engine


def _doc_brief(doc):
    meta = getattr(doc, "metadata", {}) or {}
    return {
        "filename": meta.get("filename"),
        "section": meta.get("section") or meta.get("context_header"),
        "doc_id": meta.get("doc_id") or meta.get("document_id"),
        "score": meta.get("rerank_score") or meta.get("rrf_score") or meta.get("bm25_score"),
        "table_label": meta.get("table_label"),
    }


def trace(query: str, doc_id: str | None = None) -> dict:
    engine = _get_engine()
    out: dict = {}

    # 1. classify_query
    qt = classify_query(query)
    out["classify_query"] = qt

    # 2. filter_resolution
    resolved = engine._resolve_doc_target(doc_id) if doc_id else None
    qdrant_filter = engine._build_doc_filter(doc_id) if doc_id else None
    hit_count = None
    if qdrant_filter is not None and getattr(engine, "client", None) is not None:
        try:
            hit_count = int(engine.client.count(
                collection_name="document_chunks",
                count_filter=qdrant_filter,
            ).count)
        except Exception as e:  # noqa: BLE001
            hit_count = f"error: {e}"
    out["filter_resolution"] = {
        "doc_id_input": doc_id,
        "resolved": resolved,
        "filter_object": repr(qdrant_filter) if qdrant_filter else None,
        "qdrant_hit_count": hit_count,
    }

    expanded = expand_query(query)[:3]

    # 3. vector_search
    out["vector_search"] = []
    for q in expanded:
        vdocs = engine._vector_search(q, 5, qdrant_filter=qdrant_filter)
        out["vector_search"].append({"query_variant": q, "results": [_doc_brief(d) for d in vdocs]})

    # 4. bm25_search
    out["bm25_search"] = []
    for q in expanded:
        bdocs = engine._bm25_search(q, 5, doc_id=doc_id)
        out["bm25_search"].append({"query_variant": q, "results": [_doc_brief(d) for d in bdocs]})

    # 5. table_literal_search (only for table queries)
    if qt == "table":
        tdocs = engine._table_literal_search(query, 5, doc_id=doc_id)
        out["table_literal_search"] = [_doc_brief(d) for d in tdocs]
    else:
        out["table_literal_search"] = None

    # 6. rerank — take final fused+reranked order from _run_hybrid_retrieval
    fused = engine._run_hybrid_retrieval(
        query=query,
        search_queries=expanded,
        final_top_k=8,
        qdrant_filter=qdrant_filter,
        doc_id=doc_id,
    )
    out["rerank"] = {"final_top_docs": [_doc_brief(d) for d in fused[:8]]}

    # 7. final_context_and_answer
    ctx = engine.retrieve_context(query=query, doc_id=doc_id, use_rag=True)
    out["final_context_and_answer"] = {
        "query_type": ctx.get("query_type"),
        "context_length": len(ctx.get("context", "") or ""),
        "sources_count": len(ctx.get("sources", []) or []),
        "raw_doc_filenames": [
            (d.metadata or {}).get("filename") for d in (ctx.get("raw_docs") or [])
        ],
    }
    return out


def _human(out: dict) -> str:
    lines = []
    for k, v in out.items():
        lines.append(f"\n=== {k} ===")
        lines.append(json.dumps(v, indent=2, ensure_ascii=False, default=str))
    return "\n".join(lines)


def main():
    p = argparse.ArgumentParser(description="Trace RAG pipeline for one query")
    p.add_argument("--query", required=True)
    p.add_argument("--doc-id", default=None)
    p.add_argument("--json", action="store_true", help="Emit JSON instead of human output")
    args = p.parse_args()

    result = trace(args.query, args.doc_id)
    if args.json:
        json.dump(result, sys.stdout, indent=2, ensure_ascii=False, default=str)
        sys.stdout.write("\n")
    else:
        print(_human(result))


if __name__ == "__main__":
    main()
