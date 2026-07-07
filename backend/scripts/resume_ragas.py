#!/usr/bin/env python3
import json
import os
import sys
import math
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from evaluate_ragas import (
    load_env_files,
    build_ragas_config,
    _clean_text,
    run_ragas,
    resolve_metrics
)
from ragas import EvaluationDataset, SingleTurnSample

def main():
    MERGED_PATH = Path("data/eval_ragas_final_40_qwen3_32b_merged.json")
    RESULTS_PATH = Path("data/eval_results_final_40.json")

    with open(MERGED_PATH, "r", encoding="utf-8") as f:
        merged_data = json.load(f)

    with open(RESULTS_PATH, "r", encoding="utf-8") as f:
        all_results = json.load(f)

    results_by_id = {r["id"]: r for r in all_results}

    # Find missing
    missing_items = []
    for q in merged_data["per_question"]:
        metrics = q.get("scores", {})
        missing_metrics = [k for k, v in metrics.items() if v is None]
        if missing_metrics:
            missing_items.append((q["id"], missing_metrics))

    if not missing_items:
        print("No missing items to resume.")
        return

    print(f"Found {len(missing_items)} questions with missing metrics. Starting evaluation with llama-3.3-70b-versatile...")

    llm, embed = build_ragas_config("groq", "llama-3.3-70b-versatile", "firqaaa/indo-sentence-bert-base")

    # Evaluate each missing item
    for q_id, missing_metrics in missing_items:
        print(f"\nEvaluating {q_id} for metrics: {missing_metrics}")
        r = results_by_id[q_id]
        sample = SingleTurnSample(
            user_input=r["question"],
            response=_clean_text(r["answer"]),
            retrieved_contexts=[_clean_text(c) for c in r["contexts"]],
            reference=r["ground_truth"],
        )
        dataset = EvaluationDataset(samples=[sample])
        
        _, metrics_objs = resolve_metrics(missing_metrics)
        
        try:
            result = run_ragas(dataset, llm, embed, metrics_objs, missing_metrics, 60, 1)
            scores_df = result.to_pandas()
            
            # Update the merged_data
            for q in merged_data["per_question"]:
                if q["id"] == q_id:
                    for m in missing_metrics:
                        val = scores_df.iloc[0].get(m)
                        if val is not None and math.isfinite(val):
                            q["scores"][m] = float(val)
                            print(f"  {m}: {float(val):.4f}")
                        else:
                            print(f"  {m}: Failed to evaluate")
                    break
                    
            # Save incrementally
            with open(MERGED_PATH, "w", encoding="utf-8") as f:
                json.dump(merged_data, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            print(f"Error evaluating {q_id}: {e}")

    # Recalculate averages
    print("\nRecalculating averages...")
    from collections import defaultdict
    sums = defaultdict(float)
    counts = defaultdict(int)

    for q in merged_data['per_question']:
        for m, v in q['scores'].items():
            if v is not None:
                sums[m] += v
                counts[m] += 1

    averages = {}
    for m in sums:
        averages[m] = round(sums[m] / counts[m], 4)

    merged_data['averages'] = averages
    merged_data['valid_counts'] = dict(counts)

    with open(MERGED_PATH, "w", encoding="utf-8") as f:
        json.dump(merged_data, f, ensure_ascii=False, indent=2)

    print("\nFinal Averages:")
    for k, v in averages.items():
        print(f"{k}: {v} (valid: {counts[k]})")

if __name__ == "__main__":
    main()