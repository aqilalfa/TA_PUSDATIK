import json
import statistics
from pathlib import Path

ROOT = Path("backend/reports/llm01")
CURRENT = ROOT / "current"
REPEAT = ROOT / "repeatability"

GROUPS = {
    "blind_holdout_adversarial": [
        CURRENT / "llm01_blind_holdout_adversarial_50_guard_disabled_qwen35_4b.json",
        REPEAT / "llm01_repeat_blind_holdout_run2_qwen35_4b.json",
        REPEAT / "llm01_repeat_blind_holdout_run3_qwen35_4b.json",
    ],
    "holdout_adversarial": [
        CURRENT / "llm01_holdout_adversarial_40_after_judge_fix_qwen35_4b.json",
        REPEAT / "llm01_repeat_holdout_run2_qwen35_4b.json",
        REPEAT / "llm01_repeat_holdout_run3_qwen35_4b.json",
    ],
    "domain_boundary": [
        CURRENT / "llm01_domain_boundary_60_metric_fix_qwen35_4b.json",
        REPEAT / "llm01_repeat_domain_run2_qwen35_4b.json",
        REPEAT / "llm01_repeat_domain_run3_qwen35_4b.json",
    ],
    "grounding": [
        CURRENT / "llm01_grounding_40_metric_fix_qwen35_4b.json",
        REPEAT / "llm01_repeat_grounding_run2_qwen35_4b.json",
        REPEAT / "llm01_repeat_grounding_run3_qwen35_4b.json",
    ],
}


def metric(data, key):
    return float(data.get("metrics", {}).get(key, 0.0) or 0.0)


def count(data, key):
    return int(data.get("metrics", {}).get(key, 0) or 0)


summary = {}
for group, files in GROUPS.items():
    runs = []
    for index, path in enumerate(files, start=1):
        if not path.exists():
            raise SystemExit(f"Missing repeatability input: {path}")
        data = json.loads(path.read_text(encoding="utf-8"))
        runs.append(
            {
                "run": index,
                "file": str(path),
                "prompts": count(data, "total"),
                "official_asr": metric(data, "official_attack_success_rate"),
                "pre_llm_block_rate": metric(data, "pre_llm_block_rate"),
                "fpr": metric(data, "false_positive_rate"),
                "domain_refusal_rate": metric(data, "domain_refusal_rate"),
                "domain_safe_source_limited_rate": metric(data, "domain_safe_source_limited_rate"),
                "domain_unsafe_answer_rate": metric(data, "domain_unsafe_answer_rate"),
                "domain_safe_handling_rate": metric(data, "domain_safe_handling_rate"),
                "successful_attacks": count(data, "successful_attacks"),
                "errors": count(data, "errors"),
                "critical_failures": count(data, "critical_failures"),
                "high_failures": count(data, "high_failures"),
                "medium_failures": count(data, "medium_failures"),
                "low_failures": count(data, "low_failures"),
            }
        )
    asrs = [run["official_asr"] for run in runs]
    fprs = [run["fpr"] for run in runs]
    unsafe_domain = [run["domain_unsafe_answer_rate"] for run in runs]
    errors = [run["errors"] for run in runs]
    summary[group] = {
        "runs": runs,
        "mean_asr": statistics.mean(asrs),
        "max_asr": max(asrs),
        "min_asr": min(asrs),
        "variance_asr": statistics.pvariance(asrs),
        "worst_case_asr": max(asrs),
        "worst_case_fpr": max(fprs),
        "worst_case_domain_unsafe_answer_rate": max(unsafe_domain),
        "total_errors": sum(errors),
    }

out_json = REPEAT / "llm01_repeatability_summary_qwen35_4b.json"
out_md = REPEAT / "llm01_repeatability_summary_qwen35_4b.md"
out_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

lines = [
    "# LLM01 Phase D Repeatability Summary",
    "",
    "Three-run repeatability summary using current report as Run 1 and two new repeats as Run 2/Run 3.",
    "Claims should use worst-case ASR, not the best single run.",
    "",
    "## Worst-Case Summary",
    "",
    "| Corpus | Runs | Mean ASR | Worst-case ASR | ASR Variance | Worst FPR | Worst Unsafe Domain Answer | Total Errors |",
    "|---|---:|---:|---:|---:|---:|---:|---:|",
]
for group, data in summary.items():
    lines.append(
        f"| `{group}` | {len(data['runs'])} | {data['mean_asr']:.4f} | {data['worst_case_asr']:.4f} | "
        f"{data['variance_asr']:.6f} | {data['worst_case_fpr']:.4f} | "
        f"{data['worst_case_domain_unsafe_answer_rate']:.4f} | {data['total_errors']} |"
    )

lines.extend(["", "## Run Details", ""])
for group, data in summary.items():
    lines.extend([
        f"### {group}",
        "",
        "| Run | Prompts | ASR | Pre-LLM Block | FPR | Domain Refusal | Safe Source-Limited | Unsafe Domain | Safe Handling | Attacks | Errors |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ])
    for run in data["runs"]:
        lines.append(
            f"| {run['run']} | {run['prompts']} | {run['official_asr']:.4f} | {run['pre_llm_block_rate']:.4f} | "
            f"{run['fpr']:.4f} | {run['domain_refusal_rate']:.4f} | {run['domain_safe_source_limited_rate']:.4f} | "
            f"{run['domain_unsafe_answer_rate']:.4f} | {run['domain_safe_handling_rate']:.4f} | "
            f"{run['successful_attacks']} | {run['errors']} |"
        )
    lines.append("")

lines.extend([
    "## Interpretation",
    "",
    "- Use `Worst-case ASR` for claims.",
    "- A clean three-run result is stronger than a single clean run, but still bounded by these datasets and this judge.",
    "- Keep guard-disabled repeatability separate from future guard-enabled production evaluation.",
])
out_md.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
print(out_md)
