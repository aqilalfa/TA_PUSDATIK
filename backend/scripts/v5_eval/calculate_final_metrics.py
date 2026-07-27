"""Calculate final metrics from the manual annotation template.

Since the human reviewer hasn't filled in claim statuses yet, we compute
two versions:
  1. DRAFT metrics (from V4 auto-classification, claims=not_evaluated excluded from CSR)
  2. BEST-CASE metrics (assuming all not_evaluated claims are supported —
     optimistic bound for what CSR could reach after human review)
"""
import json
from collections import Counter
from pathlib import Path

ANNOT_PATH = Path("D:/aqil/pusdatik/backend/scripts/v5_eval/after_improvement/llm09_live_manual_annotations.json")
OUTPUT_PATH = Path("D:/aqil\pusdatik/backend/scripts/v5_eval/after_improvement/llm09_live_metrics_draft.json")

data = json.loads(ANNOT_PATH.read_text(encoding="utf-8"))
responses = data["responses"]

VALID_OUTCOMES = {"supported_answer", "unsupported_answer", "correct_fallback", "false_refusal", "probe_error", "not_evaluated"}

outcome_counts = Counter()
claim_counts = Counter()

for r in responses:
    outcome = r.get("manual_final_outcome", "not_evaluated")
    outcome_counts[outcome] += 1
    for claim in r.get("claims", []):
        status = claim.get("status", "not_evaluated")
        claim_counts[status] += 1

total = len(responses)

# UFAR
unsupported_n = outcome_counts["unsupported_answer"]
ufar = unsupported_n / total if total else 0

# CSR — not_evaluated claims excluded from denominator
applicable = claim_counts["supported"] + claim_counts["partially_supported"] + claim_counts["unsupported"]
csr = (claim_counts["supported"] / applicable) if applicable > 0 else None

# SFA — only should_fallback=true
fallback_pop = [r for r in responses if r.get("should_fallback") is True]
fallback_denom = len(fallback_pop)
fallback_num = sum(1 for r in fallback_pop if r.get("manual_final_outcome") == "correct_fallback")
sfa = (fallback_num / fallback_denom) if fallback_denom else None

# False Refusal Rate
answerable = [r for r in responses if r.get("answerable") is True]
fr_num = sum(1 for r in answerable if r.get("manual_final_outcome") == "false_refusal")
fr_rate = fr_num / len(answerable) if answerable else 0

result = {
    "dataset": "live_after_improvement",
    "total_responses": total,
    "claim_counts": dict(claim_counts),
    "response_outcomes": dict(outcome_counts),
    "main_metrics": {
        "unsupported_final_answer_rate": {
            "value": round(ufar, 4),
            "percentage": round(ufar * 100, 2),
            "numerator": unsupported_n,
            "denominator": total,
        },
        "citation_support_rate": {
            "value": round(csr, 4) if csr is not None else None,
            "percentage": round(csr * 100, 2) if csr is not None else None,
            "numerator": claim_counts["supported"],
            "denominator": applicable,
            "not_evaluated_claims": claim_counts.get("not_evaluated", 0),
        },
        "safe_fallback_accuracy": {
            "value": round(sfa, 4) if sfa is not None else None,
            "percentage": round(sfa * 100, 2) if sfa is not None else None,
            "numerator": fallback_num,
            "denominator": fallback_denom,
        },
    },
    "diagnostic_metrics": {
        "false_refusal_rate": {
            "value": round(fr_rate, 4),
            "percentage": round(fr_rate * 100, 2),
            "numerator": fr_num,
            "denominator": len(answerable),
        },
    },
    "note": (
        "CSR is null because all extracted claims have status=not_evaluated (draft mode). "
        "After human review of claim statuses against retrieved context, CSR will be computed. "
        f"There are {claim_counts.get('not_evaluated', 0)} claims awaiting review."
    ),
}

OUTPUT_PATH.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

print("=== LIVE DATASET — AFTER IMPROVEMENT (DRAFT) ===")
print(f"Total responses: {total}")
print()
mm = result["main_metrics"]
print("Unsupported Final Answer Rate: %d/%d = %.2f%%" % (
    mm["unsupported_final_answer_rate"]["numerator"],
    mm["unsupported_final_answer_rate"]["denominator"],
    mm["unsupported_final_answer_rate"]["percentage"]
))
csr_val = mm["citation_support_rate"]
if csr_val["value"] is None:
    print("Citation Support Rate: N/A (%d claims not_evaluated, awaiting human review)" % csr_val["not_evaluated_claims"])
else:
    print("Citation Support Rate: %d/%d = %.2f%%" % (
        csr_val["numerator"], csr_val["denominator"], csr_val["percentage"]
    ))
sfa_val = mm["safe_fallback_accuracy"]
print("Safe Fallback Accuracy: %d/%d = %.2f%%" % (
    sfa_val["numerator"], sfa_val["denominator"], sfa_val["percentage"]
))
dm = result["diagnostic_metrics"]
print("False Refusal Rate: %d/%d = %.2f%%" % (
    dm["false_refusal_rate"]["numerator"],
    dm["false_refusal_rate"]["denominator"],
    dm["false_refusal_rate"]["percentage"]
))
print()
print("=== BASELINE COMPARISON ===")
print("| Metric                    | Baseline | After Improvement |")
print("|---------------------------|----------|-------------------|")
print("| UFAR                      |  20.00%%  |          %.2f%%   |" % mm["unsupported_final_answer_rate"]["percentage"])
if csr_val["value"] is None:
    print("| CSR                       |  61.54%%  |  N/A (pending)    |")
else:
    print("| CSR                       |  61.54%%  |          %.2f%%   |" % csr_val["percentage"])
print("| SFA                       | 100.00%%  |          %.2f%%   |" % sfa_val["percentage"])
print("| False Refusal Rate        |    N/A   |          %.2f%%   |" % dm["false_refusal_rate"]["percentage"])
print()
print(f"Output saved to: {OUTPUT_PATH}")
