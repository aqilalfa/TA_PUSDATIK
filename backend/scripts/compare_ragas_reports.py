#!/usr/bin/env python3
"""Compare two RAGAS evaluation reports and print delta.

Usage:
    python scripts/compare_ragas_reports.py data/eval_baseline.json data/eval_after.json
"""
import argparse
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")


METRICS = ["faithfulness", "answer_relevancy", "context_precision", "context_recall"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("baseline", help="Path to baseline RAGAS report JSON")
    parser.add_argument("after", help="Path to post-change RAGAS report JSON")
    parser.add_argument("--threshold", type=float, default=0.0,
                        help="Min delta to flag (default: 0.0 = any change)")
    args = parser.parse_args()

    baseline = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
    after = json.loads(Path(args.after).read_text(encoding="utf-8"))

    print("=" * 70)
    print(f"RAGAS Report Comparison")
    print(f"  Baseline: {args.baseline}  ({baseline.get('total_evaluated')} questions)")
    print(f"  After:    {args.after}  ({after.get('total_evaluated')} questions)")
    print("=" * 70)
    print()
    print(f"{'Metric':<22} {'Baseline':>10} {'After':>10} {'Delta':>10} {'Status':>10}")
    print("-" * 70)

    regressions = 0
    for m in METRICS:
        b = baseline.get("averages", {}).get(m)
        a = after.get("averages", {}).get(m)
        if b is None or a is None:
            print(f"{m:<22} {'-':>10} {'-':>10} {'-':>10}")
            continue
        delta = a - b
        if delta > 0.001:
            status = "improve"
        elif delta < -0.05:
            status = "REGRESS"
            regressions += 1
        elif delta < -0.001:
            status = "minor"
        else:
            status = "same"
        print(f"{m:<22} {b:>10.4f} {a:>10.4f} {delta:>+10.4f} {status:>10}")

    print()
    # Per-question breakdown for figure GT (gt_041 onwards)
    after_pq = {pq["id"]: pq for pq in after.get("per_question", [])}
    figure_ids = [pid for pid in after_pq if pid >= "gt_041"]
    if figure_ids:
        print(f"Figure-specific GT ({len(figure_ids)} questions):")
        passed = 0
        for fid in sorted(figure_ids):
            pq = after_pq[fid]
            faith = pq["scores"].get("faithfulness", 0)
            mark = "OK" if faith >= 0.7 else "FAIL"
            if faith >= 0.7:
                passed += 1
            print(f"  {mark} {fid}: faithfulness={faith:.3f}  Q: {pq['question'][:60]}")
        print(f"\nFigure GT pass rate: {passed}/{len(figure_ids)} (target: >=10/15)")

    print()
    if regressions > 0:
        print(f"FAIL: {regressions} metric(s) regressed > 0.05")
        sys.exit(1)
    print("OK: No regressions exceeding threshold")


if __name__ == "__main__":
    main()
