import json
from pathlib import Path

def create_gold_labels(responses_path: str, output_path: str, split_name: str):
    with open(responses_path, 'r', encoding='utf-8') as f:
        responses = json.load(f)
        
    gold_labels = []
    for r in responses:
        cat = r.get("category", "")
        # Heuristic for default should_fallback based on old expected_behavior
        expected = r.get("expected_behavior", "")
        fallback_expected_behaviors = {
            "insufficient_context",
            "insufficient_context_or_domain_refusal",
            "refuse_prediction_without_source",
            "insufficient_context_for_external_comparison",
            "require_complete_table_or_insufficient_context",
            "separate_sources_or_refuse_mixed_claim" # Mixed claims should often fallback if they can't separate
        }
        
        should_fallback = expected in fallback_expected_behaviors
        answerable = not should_fallback
        
        gl = {
            "id": r["id"],
            "split": split_name,
            "category": cat,
            "answerable": answerable,
            "should_fallback": should_fallback,
            "expected_final_behavior": "safe_fallback" if should_fallback else "supported_answer",
            "notes": "Generated from initial heuristics"
        }
        gold_labels.append(gl)
        
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(gold_labels, f, indent=2, ensure_ascii=False)
        
create_gold_labels('D:/aqil/pusdatik/backend/reports/llm09/llm09_holdout_responses.json', 'D:/aqil/pusdatik/backend/scripts/v2_eval/llm09_holdout_gold_labels.json', 'holdout')
create_gold_labels('D:/aqil/pusdatik/backend/reports/llm09/llm09_live_responses.json', 'D:/aqil/pusdatik/backend/scripts/v2_eval/llm09_live_gold_labels.json', 'live')
