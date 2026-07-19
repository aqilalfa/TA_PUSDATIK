"""Compare the 64-candidate reranker baseline with adaptive candidate pruning."""
from __future__ import annotations

import argparse
import json
import math
import re
import statistics
import sys
import time
from pathlib import Path
from typing import Any

_BACKEND = Path(__file__).resolve().parents[1]
_ROOT = _BACKEND.parent
sys.path.insert(0, str(_BACKEND))

from app.core.rag.langchain_engine import langchain_engine  # noqa: E402


def _normalize(value: Any) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).split())


def _evidence_markers(entry: dict[str, Any]) -> list[str]:
    evidence = entry.get("evidence") or {}
    table = _normalize(evidence.get("table"))
    if table:
        match = re.search(r"tabel\s+\d+", table)
        return [match.group(0) if match else table]

    article = _normalize(evidence.get("article"))
    if article:
        match = re.search(r"pasal\s+\d+", article)
        return [match.group(0) if match else article]

    chapter = _normalize(evidence.get("chapter"))
    indicator = re.search(r"indikator\s+\d+", chapter)
    if indicator:
        return [indicator.group(0)]

    primary_keywords = [_normalize(item) for item in entry.get("primary_keywords", [])]
    return [item for item in primary_keywords if len(item) >= 4][:3]


def _document_haystack(doc: Any) -> str:
    metadata = getattr(doc, "metadata", {}) or {}
    return _normalize(f"{json.dumps(metadata, ensure_ascii=False, default=str)} {doc.page_content}")


def _relevant_rank(docs: list[Any], entry: dict[str, Any]) -> int | None:
    markers = _evidence_markers(entry)
    for rank, doc in enumerate(docs, 1):
        haystack = _document_haystack(doc)
        source_matches = "59" in haystack and "2020" in haystack
        if source_matches and markers and any(marker in haystack for marker in markers):
            return rank
    return None


def _identity(doc: Any) -> str:
    metadata = getattr(doc, "metadata", {}) or {}
    return str(
        metadata.get("canonical_context_id")
        or metadata.get("citation_id")
        or metadata.get("chunk_id")
        or metadata.get("id")
        or ""
    )


def _run_query(entry: dict[str, Any], candidate_limit: int | None, top_k: int) -> dict[str, Any]:
    started = time.perf_counter()
    result = langchain_engine.retrieve_context(
        entry["question"],
        top_k=top_k,
        rerank_candidate_limit_override=candidate_limit,
    )
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    docs = list(result.get("raw_docs") or [])
    metadata = docs[0].metadata if docs else {}
    relevant_rank = _relevant_rank(docs, entry)
    return {
        "relevant_rank": relevant_rank,
        "hit": relevant_rank is not None,
        "reciprocal_rank": 1.0 / relevant_rank if relevant_rank else 0.0,
        "ndcg": 1.0 / math.log2(relevant_rank + 1) if relevant_rank else 0.0,
        "rerank_ms": float(metadata.get("rerank_elapsed_ms") or 0.0),
        "pipeline_ms": elapsed_ms,
        "candidate_limit": metadata.get("rerank_candidate_limit"),
        "candidate_count": metadata.get("rerank_candidate_count"),
        "candidate_policy": metadata.get("rerank_candidate_policy"),
        "top_ids": [_identity(doc) for doc in docs],
    }


def _summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    count = len(rows)
    rerank_times = [row["rerank_ms"] for row in rows]
    pipeline_times = [row["pipeline_ms"] for row in rows]
    return {
        "queries": count,
        "hit_rate_at_5": sum(row["hit"] for row in rows) / count,
        "mrr_at_5": sum(row["reciprocal_rank"] for row in rows) / count,
        "ndcg_at_5": sum(row["ndcg"] for row in rows) / count,
        "mean_rerank_ms": statistics.fmean(rerank_times),
        "median_rerank_ms": statistics.median(rerank_times),
        "mean_pipeline_ms": statistics.fmean(pipeline_times),
        "candidate_counts": [row["candidate_count"] for row in rows],
        "candidate_policies": [row["candidate_policy"] for row in rows],
    }


def benchmark(ground_truth_path: Path, top_k: int = 5) -> dict[str, Any]:
    payload = json.loads(ground_truth_path.read_text(encoding="utf-8"))
    entries = payload["ground_truths"]
    if not langchain_engine._initialized:
        langchain_engine.initialize()

    # Warm the model without biasing either measured configuration.
    langchain_engine.retrieve_context(
        entries[0]["question"],
        top_k=top_k,
        rerank_candidate_limit_override=8,
    )

    baseline_rows: list[dict[str, Any]] = []
    adaptive_rows: list[dict[str, Any]] = []
    details = []
    for index, entry in enumerate(entries):
        if index % 2 == 0:
            baseline = _run_query(entry, 64, top_k)
            adaptive = _run_query(entry, None, top_k)
        else:
            adaptive = _run_query(entry, None, top_k)
            baseline = _run_query(entry, 64, top_k)
        baseline_rows.append(baseline)
        adaptive_rows.append(adaptive)
        overlap = len(set(baseline["top_ids"]) & set(adaptive["top_ids"])) / max(
            1, len(set(baseline["top_ids"]) | set(adaptive["top_ids"]))
        )
        details.append(
            {
                "id": entry.get("id"),
                "question": entry["question"],
                "markers": _evidence_markers(entry),
                "baseline": baseline,
                "adaptive": adaptive,
                "top5_jaccard": overlap,
            }
        )

    baseline_summary = _summary(baseline_rows)
    adaptive_summary = _summary(adaptive_rows)
    latency_reduction = 1.0 - (
        adaptive_summary["mean_rerank_ms"] / baseline_summary["mean_rerank_ms"]
    )
    hit_rate_drop = baseline_summary["hit_rate_at_5"] - adaptive_summary["hit_rate_at_5"]
    mrr_drop = baseline_summary["mrr_at_5"] - adaptive_summary["mrr_at_5"]
    return {
        "ground_truth": str(ground_truth_path),
        "acceptance_thresholds": {
            "minimum_rerank_latency_reduction": 0.50,
            "maximum_hit_rate_drop": 0.02,
            "maximum_mrr_drop": 0.02,
        },
        "baseline_64": baseline_summary,
        "adaptive": adaptive_summary,
        "comparison": {
            "rerank_latency_reduction": latency_reduction,
            "hit_rate_drop": hit_rate_drop,
            "mrr_drop": mrr_drop,
            "mean_top5_jaccard": statistics.fmean(row["top5_jaccard"] for row in details),
            "accepted": latency_reduction >= 0.50 and hit_rate_drop <= 0.02 and mrr_drop <= 0.02,
        },
        "details": details,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--ground-truth",
        type=Path,
        default=_ROOT / "data" / "ground_truth" / "ground_truth_rag_permenpan59_2020.json",
    )
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    report = benchmark(args.ground_truth, args.top_k)
    rendered = json.dumps(report, indent=2, ensure_ascii=False)
    if args.output:
        args.output.write_text(f"{rendered}\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
