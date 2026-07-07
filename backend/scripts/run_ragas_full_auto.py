#!/usr/bin/env python3
"""Run RAGAS evaluation in small Groq batches with automatic model fallback.

The runner is intentionally conservative: it evaluates small batches, retries failed
or null metrics per question, switches Groq judge model on rate-limit failures, and
regenerates the aggregate JSON/Markdown report after each successful batch.
"""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
import time
from pathlib import Path


DEFAULT_METRICS = [
    "context_precision",
    "context_recall",
    "faithfulness",
    "answer_relevancy",
]

DEFAULT_MODELS = [
    "qwen/qwen3-32b",
    "meta-llama/llama-4-scout-17b-16e-instruct",
    "openai/gpt-oss-120b",
    "groq/compound",
]

RATE_LIMIT_MARKERS = [
    "rate limit",
    "ratelimit",
    "tokens per minute",
    "tokens per day",
    "tpm",
    "tpd",
    "429",
]


def finite_number(value) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(value)


def load_total(results_path: Path) -> int:
    results = json.loads(results_path.read_text(encoding="utf-8"))
    return len([item for item in results if item.get("answer") and not item.get("error")])


def run_command(command: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    print("\n$ " + " ".join(command), flush=True)
    return subprocess.run(
        command,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        encoding="utf-8",
        errors="replace",
    )


def command_hit_rate_limit(output: str) -> bool:
    lowered = output.lower()
    return any(marker in lowered for marker in RATE_LIMIT_MARKERS)


def missing_metrics(report_path: Path, metrics: list[str]) -> list[dict]:
    if not report_path.exists():
        return [{"id": None, "offset": None, "metrics": metrics}]

    report = json.loads(report_path.read_text(encoding="utf-8"))
    missing = []
    for index, item in enumerate(report.get("per_question", [])):
        scores = item.get("scores", {})
        null_metrics = [metric for metric in metrics if not finite_number(scores.get(metric))]
        if null_metrics:
            missing.append({"id": item.get("id"), "offset": index, "metrics": null_metrics})
    return missing


def build_report_path(data_dir: Path, start: int, end: int, model: str, suffix: str = "") -> Path:
    safe_model = model.replace("/", "_").replace(":", "_").replace("-", "_")
    suffix_part = f"_{suffix}" if suffix else ""
    return data_dir / f"eval_ragas_batch_{start:02d}_{end:02d}{suffix_part}_4metrics_groq_{safe_model}.json"


def run_ragas_batch(
    backend_dir: Path,
    model: str,
    start: int,
    limit: int,
    metrics: list[str],
    results_path: Path,
    report_path: Path,
    timeout: int,
) -> tuple[bool, str, bool]:
    command = [
        sys.executable,
        "scripts/evaluate_ragas.py",
        "--provider",
        "groq",
        "--model",
        model,
        "--start",
        str(start),
        "--limit",
        str(limit),
        "--metrics",
        *metrics,
        "--results-path",
        str(results_path),
        "--report-path",
        str(report_path),
        "--timeout",
        str(timeout),
        "--max-workers",
        "1",
    ]
    completed = run_command(command, backend_dir)
    print(completed.stdout, flush=True)
    rate_limited = command_hit_rate_limit(completed.stdout)
    return completed.returncode == 0 and report_path.exists(), completed.stdout, rate_limited


def regenerate_aggregate(backend_dir: Path, data_dir: Path, metrics: list[str]) -> None:
    command = [
        sys.executable,
        "scripts/aggregate_ragas_batches.py",
        "--pattern",
        str(data_dir / "eval_ragas_batch_*_4metrics_groq_*.json"),
        "--output-json",
        str(data_dir / "eval_ragas_aggregate_4metrics_groq_auto.json"),
        "--output-md",
        str(data_dir / "eval_ragas_aggregate_4metrics_groq_auto.md"),
        "--metrics",
        *metrics,
    ]
    completed = run_command(command, backend_dir)
    print(completed.stdout, flush=True)
    completed.check_returncode()


def append_manifest(manifest_path: Path, event: dict) -> None:
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    else:
        manifest = {"events": []}
    manifest["events"].append(event)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run full RAGAS evaluation with Groq fallback")
    parser.add_argument("--start", type=int, default=0, help="0-based start index")
    parser.add_argument("--batch-size", type=int, default=2, help="Questions per batch")
    parser.add_argument("--results-path", type=Path, default=Path("data/eval_results_spbe_rag_after_precision_tuning_round2.json"))
    parser.add_argument("--metrics", nargs="+", default=DEFAULT_METRICS)
    parser.add_argument("--models", nargs="+", default=DEFAULT_MODELS)
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--sleep-on-rate-limit", type=int, default=30)
    parser.add_argument("--max-batches", type=int, default=None)
    args = parser.parse_args()

    backend_dir = Path(__file__).resolve().parent.parent
    data_dir = backend_dir / "data"
    results_path = args.results_path if args.results_path.is_absolute() else backend_dir / args.results_path
    total = load_total(results_path)
    manifest_path = data_dir / "eval_ragas_full_auto_manifest.json"

    model_index = 0
    batches_run = 0
    start = args.start

    while start < total:
        if args.max_batches is not None and batches_run >= args.max_batches:
            break

        limit = min(args.batch_size, total - start)
        end = start + limit
        success = False

        for offset in range(len(args.models)):
            model = args.models[(model_index + offset) % len(args.models)]
            report_path = build_report_path(data_dir, start, end, model)
            ok, output, rate_limited = run_ragas_batch(
                backend_dir=backend_dir,
                model=model,
                start=start,
                limit=limit,
                metrics=args.metrics,
                results_path=results_path,
                report_path=report_path,
                timeout=args.timeout,
            )
            append_manifest(
                manifest_path,
                {
                    "start": start,
                    "end": end,
                    "model": model,
                    "report_path": str(report_path),
                    "ok": ok,
                    "rate_limited": rate_limited,
                },
            )

            if rate_limited:
                model_index = (args.models.index(model) + 1) % len(args.models)
                print(f"Rate limit detected for {model}; switching to {args.models[model_index]}", flush=True)
                time.sleep(args.sleep_on_rate_limit)
                continue

            if ok:
                for missing in missing_metrics(report_path, args.metrics):
                    if missing["offset"] is None:
                        continue
                    retry_start = start + int(missing["offset"])
                    retry_path = build_report_path(data_dir, retry_start, retry_start + 1, model, "retry")
                    run_ragas_batch(
                        backend_dir=backend_dir,
                        model=model,
                        start=retry_start,
                        limit=1,
                        metrics=args.metrics,
                        results_path=results_path,
                        report_path=retry_path,
                        timeout=args.timeout,
                    )
                regenerate_aggregate(backend_dir, data_dir, args.metrics)
                success = True
                break

            print(output[-2000:], flush=True)

        if not success:
            raise RuntimeError(f"Batch {start}:{end} failed on all configured models")

        batches_run += 1
        start = end

    regenerate_aggregate(backend_dir, data_dir, args.metrics)
    print("Full automatic RAGAS run finished.", flush=True)


if __name__ == "__main__":
    main()
