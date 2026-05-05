#!/usr/bin/env python3
"""Collect RAG answers via HTTP SSE API (avoids HuggingFaceEmbeddings segfault on Windows).

Usage:
    python scripts/collect_via_api.py [--sample N] [--api-url URL]
"""
import sys
import json
import time
import argparse
from pathlib import Path

import httpx
from loguru import logger

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

GROUND_TRUTH_PATH = Path(__file__).parent.parent / "data" / "ground_truth.json"
RESULTS_PATH = Path(__file__).parent.parent / "data" / "eval_results.json"

DEFAULT_API_URL = "http://localhost:8000"
DEFAULT_MODEL = "qwen3.5:4b"


def collect_one(question: str, api_url: str, model: str) -> dict:
    """Call the SSE stream endpoint, collect the 'complete' event."""
    payload = {
        "message": question,
        "model": model,
        "use_rag": True,
        "top_k": 5,
        "max_quality_retries": 0,
    }

    raw_lines = []
    with httpx.Client(timeout=600.0) as client:
        with client.stream("POST", f"{api_url}/api/chat/stream", json=payload) as resp:
            resp.raise_for_status()
            raw_lines = list(resp.iter_lines())

    # Find 'event: complete' and its data line in the SSE response
    complete_data = None
    for i, line in enumerate(raw_lines):
        if line == "event: complete" and i + 1 < len(raw_lines):
            data_line = raw_lines[i + 1]
            if data_line.startswith("data: "):
                complete_data = json.loads(data_line[6:])
                break

    if not complete_data:
        raise ValueError("No 'complete' event received from stream")

    answer = complete_data.get("answer", "")
    sources = complete_data.get("sources", [])
    contexts = [
        s.get("content", s.get("text", s.get("snippet", "")))
        for s in sources
        if s
    ]
    return {"answer": answer, "contexts": contexts}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample", type=int, default=None)
    parser.add_argument("--api-url", default=DEFAULT_API_URL)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--figure-only", action="store_true",
                        help="Only run figure GT questions (gt_041 and above)")
    args = parser.parse_args()

    ground_truth = json.loads(GROUND_TRUTH_PATH.read_text(encoding="utf-8"))

    if args.figure_only:
        items = [g for g in ground_truth
                 if int(g["id"].replace("gt_0", "").replace("gt_", "")) >= 41]
    else:
        items = ground_truth[: args.sample] if args.sample else ground_truth
    logger.info(f"Collecting {len(items)} answers via {args.api_url} (model={args.model})")

    results = []
    for i, gt in enumerate(items, 1):
        logger.info(f"[{i}/{len(items)}] {gt['question'][:70]}...")
        t0 = time.perf_counter()
        try:
            out = collect_one(gt["question"], args.api_url, args.model)
            elapsed = time.perf_counter() - t0
            results.append(
                {
                    "id": gt["id"],
                    "source_doc": gt["source_doc"],
                    "doc_type": gt["doc_type"],
                    "question": gt["question"],
                    "ground_truth": gt["ground_truth"],
                    "answer": out["answer"],
                    "contexts": out["contexts"],
                    "latency_s": round(elapsed, 2),
                }
            )
            logger.success(
                f"  answer {len(out['answer'])} chars, {len(out['contexts'])} ctx, {elapsed:.1f}s"
            )
        except Exception as e:
            logger.error(f"  FAILED: {e}")
            results.append(
                {
                    "id": gt["id"],
                    "source_doc": gt["source_doc"],
                    "doc_type": gt["doc_type"],
                    "question": gt["question"],
                    "ground_truth": gt["ground_truth"],
                    "answer": "",
                    "contexts": [],
                    "latency_s": -1,
                    "error": str(e),
                }
            )

    RESULTS_PATH.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.success(f"Saved {len(results)} results to {RESULTS_PATH}")


if __name__ == "__main__":
    main()
