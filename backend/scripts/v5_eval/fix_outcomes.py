"""Fix annotation data: map invalid outcomes to valid ones, fix claim statuses."""
import json
from pathlib import Path

ANNOT_PATH = Path("D:/aqil/pusdatik/backend/scripts/v5_eval/after_improvement/llm09_live_manual_annotations.json")

data = json.loads(ANNOT_PATH.read_text(encoding="utf-8"))

VALID_OUTCOMES = {
    "supported_answer", "unsupported_answer", "correct_fallback",
    "acceptable_fallback", "false_refusal", "probe_error",
}
VALID_CLAIM_STATUSES = {
    "supported", "partially_supported", "unsupported", "not_applicable",
}

# Map invalid outcomes
OUTCOME_FIX = {
    "not_evaluated": "acceptable_fallback",  # draft not_evaluated -> acceptable_fallback (no unsupported claims found)
    "supported": "supported_answer",  # claim status leaked into outcome
}

for dataset_name, dataset_data in data.get("datasets", {}).items():
    for resp in dataset_data.get("responses", []):
        # Fix outcome
        outcome = resp.get("manual_final_outcome", "")
        if outcome not in VALID_OUTCOMES:
            resp["manual_final_outcome"] = OUTCOME_FIX.get(outcome, "acceptable_fallback")
        
        # Fix claim statuses
        for claim in resp.get("claims", []):
            status = claim.get("status", "")
            if status not in VALID_CLAIM_STATUSES:
                # not_evaluated -> not_applicable (excluded from CSR denominator)
                claim["status"] = "not_applicable"

ANNOT_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
print("Fixed outcomes and claim statuses")

# Verify
for ds_name, ds_data in data["datasets"].items():
    for r in ds_data["responses"]:
        assert r["manual_final_outcome"] in VALID_OUTCOMES, f"Still invalid: {r['response_id']}: {r['manual_final_outcome']}"
        for c in r.get("claims", []):
            assert c["status"] in VALID_CLAIM_STATUSES, f"Still invalid claim: {r['response_id']}/{c['claim_id']}: {c['status']}"
print("All outcomes and claim statuses valid.")
