"""Trace the modular RAG retrieval pipeline without invoking an LLM by default."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_BACKEND))

from app.core.rag.langchain_engine import classify_query, langchain_engine  # noqa: E402
from app.core.rag.observability import RagTrace  # noqa: E402
from app.core.rag.prompts import expand_query  # noqa: E402
from app.core.rag.query_profile import classify_query_profile  # noqa: E402


def _get_engine():
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
        "canonical_context_id": meta.get("canonical_context_id"),
        "rrf_score": meta.get("rrf_score"),
        "rrf_contributions": meta.get("rrf_contributions", []),
        "rerank_base_score": meta.get("rerank_base_score"),
        "query_boost": meta.get("query_boost"),
        "rerank_score": meta.get("rerank_score"),
        "table_label": meta.get("table_label"),
    }


def _build_filter(engine, doc_id):
    if not doc_id:
        return None, None
    if hasattr(engine, "_build_qdrant_filter"):
        return doc_id, engine._build_qdrant_filter(doc_id)
    resolved = engine._resolve_doc_target(doc_id) if hasattr(engine, "_resolve_doc_target") else None
    return resolved, engine._build_doc_filter(doc_id) if hasattr(engine, "_build_doc_filter") else None


def trace(query: str, doc_id: str | None = None, *, enable_llm: bool = False) -> dict:
    engine = _get_engine()
    query_profile = classify_query_profile(query)
    query_type = classify_query(query)
    pipeline_trace = RagTrace.create(session_id=None, user_id=None, query=query)
    resolved, qdrant_filter = _build_filter(engine, doc_id)
    hit_count = None
    client = getattr(engine, "client", None)
    if qdrant_filter is not None and client is not None:
        try:
            count_result = client.count(
                collection_name=getattr(engine, "collection_name", "document_chunks"),
                count_filter=qdrant_filter,
            )
            hit_count = int(getattr(count_result, "count", 0))
        except Exception as exc:
            hit_count = f"error: {type(exc).__name__}"

    expanded = expand_query(query)[:3]
    retriever = getattr(engine, "retriever", None)
    vector_sections = []
    bm25_sections = []
    for variant in expanded:
        if retriever is not None:
            vector_docs = retriever.vector_search(variant, 5, qdrant_filter)
            bm25_docs = retriever.bm25_search(
                variant, 5, getattr(engine, "_bm25_docs", []), doc_id
            )
        else:
            vector_docs = getattr(engine, "_vector_search")(variant, 5, qdrant_filter=qdrant_filter)
            bm25_docs = getattr(engine, "_bm25_search")(variant, 5, doc_id=doc_id)
        vector_sections.append({"query_variant": variant, "results": [_doc_brief(doc) for doc in vector_docs]})
        bm25_sections.append({"query_variant": variant, "results": [_doc_brief(doc) for doc in bm25_docs]})

    if query_type == "table":
        if retriever is not None:
            table_docs = retriever.table_literal_search(
                query, getattr(engine, "collection_name", "document_chunks"), doc_id
            )
        else:
            table_docs = getattr(engine, "_table_literal_search")(query, 5, doc_id=doc_id)
        table_section = [_doc_brief(doc) for doc in table_docs]
    else:
        table_section = None

    result = engine.retrieve_context(
        query=query,
        doc_id=doc_id,
        use_rag=True,
        trace=pipeline_trace,
    )
    final_docs = result.get("raw_docs") or []
    return {
        "classify_query": query_type,
        "query_profile": {
            "retrieval_type": query_profile.retrieval_type,
            "answer_type": query_profile.answer_type,
            "scope": query_profile.scope,
        },
        "expanded_queries": expanded,
        "filter_resolution": {
            "doc_id_input": doc_id,
            "resolved": resolved,
            "filter_object": repr(qdrant_filter) if qdrant_filter else None,
            "qdrant_hit_count": hit_count,
        },
        "vector_search": vector_sections,
        "bm25_search": bm25_sections,
        "table_literal_search": table_section,
        "rerank": {"final_top_docs": [_doc_brief(doc) for doc in final_docs[:8]]},
        "retrieval_outcome": {
            "status": result.get("retrieval_status"),
            "failed_retrievers": result.get("failed_retrievers", []),
        },
        "pipeline_trace": pipeline_trace.snapshot(),
        "final_context_and_answer": {
            "query_type": result.get("query_type"),
            "context_length": len(result.get("context", "") or ""),
            "sources_count": len(result.get("sources", []) or []),
            "raw_doc_filenames": [(doc.metadata or {}).get("filename") for doc in final_docs],
            "llm_enabled": bool(enable_llm),
        },
    }


def _human(output: dict) -> str:
    lines = []
    for key, value in output.items():
        lines.extend((f"\n=== {key} ===", json.dumps(value, indent=2, ensure_ascii=False, default=str)))
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Trace RAG pipeline for one query")
    parser.add_argument("--query", required=True)
    parser.add_argument("--doc-id", default=None)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = trace(args.query, args.doc_id)
    if args.json:
        json.dump(result, sys.stdout, indent=2, ensure_ascii=False, default=str)
        sys.stdout.write("\n")
    else:
        print(_human(result))


if __name__ == "__main__":
    main()
