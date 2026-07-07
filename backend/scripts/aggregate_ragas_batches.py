#!/usr/bin/env python3
"""Aggregate multiple RAGAS batch reports into one JSON and Markdown report."""

import argparse
import glob
import json
import math
from datetime import datetime
from pathlib import Path


DEFAULT_METRICS = [
    "context_precision",
    "context_recall",
    "faithfulness",
    "answer_relevancy",
]


def finite_number(value) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(value)


def aggregate(pattern: str, metrics: list[str]) -> dict:
    files = sorted(glob.glob(pattern))
    items_by_id = {}
    batches = []

    for file_path in files:
        report = json.loads(Path(file_path).read_text(encoding="utf-8"))
        batches.append(
            {
                "file": file_path,
                "total_evaluated": report.get("total_evaluated"),
                "judge_provider": report.get("judge_provider"),
                "llm_judge": report.get("llm_judge"),
                "averages": report.get("averages", {}),
            }
        )
        for item in report.get("per_question", []):
            item_id = item.get("id")
            if not item_id:
                continue

            current = items_by_id.setdefault(
                item_id,
                {
                    "id": item_id,
                    "question": item.get("question"),
                    "source_doc": item.get("source_doc"),
                    "doc_type": item.get("doc_type"),
                    "scores": {},
                    "batch_files": [],
                },
            )
            current["batch_files"].append(file_path)

            for metric, value in item.get("scores", {}).items():
                if finite_number(value) or current["scores"].get(metric) is None:
                    current["scores"][metric] = value

    items = list(items_by_id.values())

    summary = {}
    for metric in metrics:
        values = [item["scores"].get(metric) for item in items]
        valid = [value for value in values if finite_number(value)]
        summary[metric] = {
            "avg": round(sum(valid) / len(valid), 4) if valid else None,
            "valid": len(valid),
            "null": len(values) - len(valid),
        }

    judge_models = sorted(
        {
            batch.get("llm_judge")
            for batch in batches
            if batch.get("llm_judge")
        }
    )

    return {
        "generated_at": datetime.now().isoformat(),
        "metrics": metrics,
        "judge_provider": "groq",
        "llm_judges": judge_models,
        "batch_files": batches,
        "total_questions_aggregated": len(items),
        "summary": summary,
        "per_question": items,
    }


def write_markdown(report: dict, path: Path) -> None:
    metrics = report["metrics"]
    lines = [
        "# RAGAS Aggregate Report",
        "",
        f"- Generated at: {report['generated_at']}",
        f"- Judge provider: {report.get('judge_provider', 'groq')}",
        "- LLM judges: " + ", ".join(report.get("llm_judges", [])),
        f"- Total questions aggregated: {report['total_questions_aggregated']}",
        "",
        "## Summary",
        "",
        "| Metric | Average | Valid | Null |",
        "|---|---:|---:|---:|",
    ]
    for metric, data in report["summary"].items():
        avg = data["avg"] if data["avg"] is not None else "null"
        lines.append(f"| {metric} | {avg} | {data['valid']} | {data['null']} |")

    lines.extend(["", "## Batch Files"])
    for batch in report["batch_files"]:
        model = batch.get("llm_judge") or "unknown-model"
        lines.append(f"- `{batch['file']}` ({batch['total_evaluated']} questions, judge: `{model}`)")

    lines.extend(
        [
            "",
            "## Per Question",
            "",
            "| ID | " + " | ".join(metrics) + " |",
            "|---" + "|---:" * len(metrics) + "|",
        ]
    )
    for item in report["per_question"]:
        values = [item["scores"].get(metric) for metric in metrics]
        lines.append("| " + str(item["id"]) + " | " + " | ".join(str(value) for value in values) + " |")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Aggregate RAGAS batch reports")
    parser.add_argument("--pattern", required=True, help="Glob pattern for batch JSON reports")
    parser.add_argument("--output-json", type=Path, required=True, help="Output aggregate JSON path")
    parser.add_argument("--output-md", type=Path, required=True, help="Output aggregate Markdown path")
    parser.add_argument("--metrics", nargs="+", default=DEFAULT_METRICS, help="Metric names to aggregate")
    args = parser.parse_args()

    report = aggregate(args.pattern, args.metrics)
    args.output_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(report, args.output_md)

    print(f"Aggregated {report['total_questions_aggregated']} questions")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    print(f"JSON: {args.output_json}")
    print(f"Markdown: {args.output_md}")


if __name__ == "__main__":
    main()
