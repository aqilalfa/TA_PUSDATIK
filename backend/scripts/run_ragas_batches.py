#!/usr/bin/env python3
"""Run RAGAS evaluation in small batches with Groq model fallback.

This wrapper keeps the expensive judge run resumable:
- skips questions that already have all requested metrics in the aggregate report,
- runs small batches through scripts/evaluate_ragas.py,
- retries null metrics per question,
- rotates to fallback Groq models when rate/token-limit failures appear,
- regenerates aggregate JSON/Markdown after every successful batch.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
EVALUATE_SCRIPT = ROOT / "scripts" / "evaluate_ragas.py"
AGGREGATE_SCRIPT = ROOT / "scripts" / "aggregate_ragas_batches.py"

DEFAULT_RESULTS_PATH = DATA_DIR / "eval_results_spbe_rag_after_precision_tuning_round2.json"
DEFAULT_AGGREGATE_JSON = DATA_DIR / "eval_ragas_aggregate_4metrics_groq_qwen3_32b.json"
DEFAULT_AGGREGATE_MD = DATA_DIR / "eval_ragas_aggregate_4metrics_groq_qwen3_32b.md"
DEFAULT_BATCH_PATTERN = "data/eval_ragas_batch_*_4metrics_groq_*.json"
DEFAULT_METRICS = [
    "context_precision",
    "context_recall",
    "faithfulness",
    "answer_relevancy",
]

# Ordered for judge quality + rate-limit practicality. All are substantially larger
# than the local qwen3.5:4b answer model used for the evaluated RAG answers.
DEFAULT_MODELS = [
    "qwen/qwen3-32b",
    "meta-llama/llama-4-scout-17b-16e-instruct",
    "openai/gpt-oss-120b",
    "groq/compound",
    "llama-3.3-70b-versatile",
    "openai/gpt-oss-20b",
    "llama-3.1-8b-instant",
    "allam-2-7b",
]

RATE_LIMIT_PATTERNS = [
    "rate limit",
    "ratelimit",
    "tokens per minute",
    "tokens per day",
    "tpm",
    "tpd",
    "429",
]


@dataclass
class CommandResult:
    returncode: int
    output: str


def finite_number(value: object) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(value)


def model_slug(model: str) -> str:
    slug = model.lower().replace("/", "_")
    return re.sub(r"[^a-z0-9_.-]+", "_", slug).strip("_")


def load_valid_results(results_path: Path) -> list[dict]:
    results = json.loads(results_path.read_text(encoding="utf-8"))
    return [item for item in results if item.get("answer") and not item.get("error")]


def load_completed_ids(aggregate_path: Path, metrics: list[str]) -> set[str]:
    if not aggregate_path.exists():
        return set()
    report = json.loads(aggregate_path.read_text(encoding="utf-8"))
    completed = set()
    for item in report.get("per_question", []):
        scores = item.get("scores", {})
        if all(finite_number(scores.get(metric)) for metric in metrics):
            completed.add(str(item.get("id")))
    return completed


def missing_metrics(report_path: Path, metrics: list[str]) -> dict[str, list[str]]:
    if not report_path.exists():
        return {}
    report = json.loads(report_path.read_text(encoding="utf-8"))
    missing = {}
    for item in report.get("per_question", []):
        item_id = str(item.get("id"))
        scores = item.get("scores", {})
        null_metrics = [metric for metric in metrics if not finite_number(scores.get(metric))]
        if null_metrics:
            missing[item_id] = null_metrics
    return missing


def has_rate_limit(output: str) -> bool:
    lowered = output.lower()
    return any(pattern in lowered for pattern in RATE_LIMIT_PATTERNS)


def run_command(command: list[str], cwd: Path) -> CommandResult:
    print("\n$ " + " ".join(command), flush=True)
    process = subprocess.run(
        command,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=os.environ.copy(),
    )
    print(process.stdout, flush=True)
    return CommandResult(returncode=process.returncode, output=process.stdout)


def aggregate_reports(args: argparse.Namespace) -> CommandResult:
    command = [
        sys.executable,
        str(AGGREGATE_SCRIPT),
        "--pattern",
        args.batch_pattern,
        "--output-json",
        str(args.aggregate_json),
        "--output-md",
        str(args.aggregate_md),
        "--metrics",
        *args.metrics,
    ]
    return run_command(command, ROOT)


def evaluate_batch(
    *,
    args: argparse.Namespace,
    model: str,
    start: int,
    limit: int,
    suffix: str = "",
) -> tuple[CommandResult, Path]:
    end = start + limit
    suffix_part = f"_{suffix}" if suffix else ""
    report_path = DATA_DIR / (
        f"eval_ragas_batch_{start:02d}_{end:02d}{suffix_part}_4metrics_groq_{model_slug(model)}.json"
    )
    command = [
        sys.executable,
        str(EVALUATE_SCRIPT),
        "--provider",
        "groq",
        "--model",
        model,
        "--start",
        str(start),
        "--limit",
        str(limit),
        "--metrics",
        *args.metrics,
        "--results-path",
        str(args.results_path),
        "--report-path",
        str(report_path),
        "--timeout",
        str(args.timeout),
        "--max-workers",
        str(args.max_workers),
    ]
    return run_command(command, ROOT), report_path


def record_run_event(path: Path, event: dict) -> None:
    events = []
    if path.exists():
        events = json.loads(path.read_text(encoding="utf-8"))
    events.append(event)
    path.write_text(json.dumps(events, ensure_ascii=False, indent=2), encoding="utf-8")


def choose_next_model(models: list[str], current_index: int) -> int:
    return min(current_index + 1, len(models) - 1)


def run_batch_with_fallback(
    *,
    args: argparse.Namespace,
    start: int,
    limit: int,
    model_index: int,
    retry_suffix: str = "",
) -> tuple[int, Path | None, bool]:
    attempts = 0
    current_index = model_index
    last_report_path = None

    while attempts < args.max_model_attempts and current_index < len(args.models):
        model = args.models[current_index]
        suffix = retry_suffix or f"attempt{attempts + 1}"
        if attempts == 0 and not retry_suffix:
            suffix = ""

        result, report_path = evaluate_batch(
            args=args,
            model=model,
            start=start,
            limit=limit,
            suffix=suffix,
        )
        last_report_path = report_path
        rate_limited = has_rate_limit(result.output)
        missing = missing_metrics(report_path, args.metrics)
        success = result.returncode == 0 and report_path.exists() and not missing and not rate_limited

        record_run_event(
            args.run_log,
            {
                "time": datetime.now().isoformat(),
                "start": start,
                "limit": limit,
                "model": model,
                "report_path": str(report_path),
                "returncode": result.returncode,
                "rate_limited": rate_limited,
                "missing_metrics": missing,
            },
        )

        if success:
            return current_index, report_path, True

        if rate_limited or result.returncode != 0:
            next_index = choose_next_model(args.models, current_index)
            if next_index == current_index:
                break
            print(f"Switching Groq judge model: {model} -> {args.models[next_index]}", flush=True)
            current_index = next_index
            attempts += 1
            time.sleep(args.sleep_on_fallback)
            continue

        # Parser/finish instability: retry the same batch once, then move to next model.
        attempts += 1
        if attempts >= args.same_model_retries + 1:
            next_index = choose_next_model(args.models, current_index)
            if next_index == current_index:
                break
            print(f"Retry still has null metrics; switching model: {model} -> {args.models[next_index]}", flush=True)
            current_index = next_index
            time.sleep(args.sleep_on_fallback)
        else:
            print(f"Retrying batch {start}:{start + limit} with same model due null metrics", flush=True)
            time.sleep(args.sleep_between_batches)

    return current_index, last_report_path, False


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run RAGAS batches with Groq fallback models")
    parser.add_argument("--results-path", type=Path, default=DEFAULT_RESULTS_PATH)
    parser.add_argument("--aggregate-json", type=Path, default=DEFAULT_AGGREGATE_JSON)
    parser.add_argument("--aggregate-md", type=Path, default=DEFAULT_AGGREGATE_MD)
    parser.add_argument("--batch-pattern", default=DEFAULT_BATCH_PATTERN)
    parser.add_argument("--run-log", type=Path, default=DATA_DIR / "eval_ragas_autorun_log.json")
    parser.add_argument("--metrics", nargs="+", default=DEFAULT_METRICS)
    parser.add_argument("--models", nargs="+", default=DEFAULT_MODELS)
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--batch-size", type=int, default=2)
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--max-workers", type=int, default=1)
    parser.add_argument("--max-model-attempts", type=int, default=4)
    parser.add_argument("--same-model-retries", type=int, default=1)
    parser.add_argument("--sleep-between-batches", type=int, default=10)
    parser.add_argument("--sleep-on-fallback", type=int, default=30)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    valid_results = load_valid_results(args.results_path)
    stop = len(valid_results) if args.limit is None else min(len(valid_results), args.start + args.limit)

    aggregate_reports(args)
    completed_ids = load_completed_ids(args.aggregate_json, args.metrics)
    model_index = 0

    index = args.start
    while index < stop:
        batch_end = min(index + args.batch_size, stop)
        batch_results = valid_results[index:batch_end]
        if batch_results and all(str(item.get("id")) in completed_ids for item in batch_results):
            print(f"Skipping {index}:{batch_end}; already complete", flush=True)
            index = batch_end
            continue

        model_index, report_path, success = run_batch_with_fallback(
            args=args,
            start=index,
            limit=batch_end - index,
            model_index=model_index,
        )

        aggregate_reports(args)
        completed_ids = load_completed_ids(args.aggregate_json, args.metrics)

        # If the batch still has missing values, retry individual missing questions.
        if report_path and report_path.exists():
            missing = missing_metrics(report_path, args.metrics)
            id_to_offset = {str(item.get("id")): offset for offset, item in enumerate(valid_results)}
            for item_id in missing:
                retry_start = id_to_offset.get(item_id)
                if retry_start is None:
                    continue
                model_index, _, _ = run_batch_with_fallback(
                    args=args,
                    start=retry_start,
                    limit=1,
                    model_index=model_index,
                    retry_suffix="retry",
                )
                aggregate_reports(args)
                completed_ids = load_completed_ids(args.aggregate_json, args.metrics)

        if not success:
            incomplete = [str(item.get("id")) for item in batch_results if str(item.get("id")) not in completed_ids]
            if incomplete:
                print(f"WARNING: incomplete after retries: {incomplete}", flush=True)

        index = batch_end
        time.sleep(args.sleep_between_batches)

    aggregate_reports(args)
    final_completed = load_completed_ids(args.aggregate_json, args.metrics)
    print(
        f"Completed {len(final_completed)} / {len(valid_results)} valid questions. "
        f"Aggregate: {args.aggregate_json} and {args.aggregate_md}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
