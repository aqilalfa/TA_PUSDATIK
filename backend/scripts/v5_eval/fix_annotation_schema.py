"""Fix the annotation file structure to match the baseline evaluator's expected schema.

The baseline evaluator expects: {"datasets": {"live": {"responses": [...]}}}
Our file has: {"responses": [...]} at root level.
This script wraps it correctly and also strips the _-prefixed reference fields
that the evaluator doesn't expect (they're for human review only).
"""
import json
from pathlib import Path

ANNOT_PATH = Path("D:/aqil/pusdatik/backend/scripts/v5_eval/after_improvement/llm09_live_manual_annotations.json")

data = json.loads(ANNOT_PATH.read_text(encoding="utf-8"))

# Extract responses and clean _-prefixed fields
raw_responses = data.pop("responses", [])
clean_responses = []
for r in raw_responses:
    clean = {}
    for k, v in r.items():
        if not k.startswith("_"):
            clean[k] = v
    clean_responses.append(clean)

# Wrap in the expected structure
wrapped = {
    "schema_version": data.get("schema_version", "1.0"),
    "annotation_method": data.get("annotation_method", "manual_claim_to_exact_retrieved_context_review"),
    "metric_policy": data.get("metric_policy", {}),
    "datasets": {
        "live": {
            "source_review_file": "llm09_live_retrieved_context.json",
            "responses": clean_responses,
        }
    }
}

ANNOT_PATH.write_text(json.dumps(wrapped, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"Fixed annotation file structure: {len(clean_responses)} responses wrapped under datasets.live")
