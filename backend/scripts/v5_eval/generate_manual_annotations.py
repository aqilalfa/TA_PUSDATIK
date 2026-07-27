"""Generate manual annotation template for 20 live responses (after improvement).

Format matches baseline llm09_manual_annotations_combined.json so the same
audit technique can be applied. Each response gets:
  - response_id, category, answerable, should_fallback, allowed_final_behaviors
  - manual_final_outcome (auto-filled draft from V4 evaluation)
  - claims (auto-extracted from answer using claim_verifier, status=not_evaluated)
  - reviewer_note (empty, for human to fill)

The human reviewer then:
  1. Reads the answer + retrieved_context
  2. Checks each claim's status (supported/partially_supported/unsupported)
  3. Sets manual_final_outcome
  4. Fills reviewer_note
"""
import json
import sys
from pathlib import Path

sys.path.append("D:/aqil/pusdatik/backend")

from app.core.rag.claim_verifier import verify_claims, summarize_verdicts

LIVE_PATH = Path("D:/aqil/pusdatik/backend/scripts/v5_eval/after_improvement/llm09_live_responses.json")
CONTEXT_PATH = Path("D:/aqil/pusdatik/backend/scripts/v5_eval/after_improvement/llm09_live_retrieved_context.json")
GOLD_PATH = Path("D:/aqil/pusdatik/backend/scripts/v4_eval/llm09_live_gold_labels_v4.json")
EVAL_PATH = Path("D:/aqil/pusdatik/backend/scripts/v5_eval/after_improvement/outputs/live/llm09_live_responses_evaluation_v4.json")
OUTPUT_PATH = Path("D:/aqil/pusdatik/backend/scripts/v5_eval/after_improvement/llm09_live_manual_annotations.json")

live = json.loads(LIVE_PATH.read_text(encoding="utf-8"))
contexts = json.loads(CONTEXT_PATH.read_text(encoding="utf-8"))
gold = {g["id"]: g for g in json.loads(GOLD_PATH.read_text(encoding="utf-8"))}
evals = {e["id"]: e for e in json.loads(EVAL_PATH.read_text(encoding="utf-8"))}
ctx_by_id = {c["response_id"]: c for c in contexts}

responses = []
for item in live:
    rid = item["id"]
    gl = gold.get(rid, {})
    ev = evals.get(rid, {})
    ctx = ctx_by_id.get(rid, {})
    
    resp = item.get("response", {})
    answer = resp.get("answer", "") or ""
    sources = resp.get("sources", []) or []
    retrieved_context = ctx.get("retrieved_context", "")
    
    # Auto-extract claims using the verifier
    verdicts = verify_claims(answer, retrieved_context, sources) if answer and retrieved_context else []
    summary = summarize_verdicts(verdicts)
    
    # Map V4 final_outcome to manual outcome
    v4_outcome = ev.get("final_outcome", "not_evaluated")
    outcome_map = {
        "supported_answer": "supported_answer",
        "unsupported_answer": "unsupported_answer",
        "correct_fallback": "correct_fallback",
        "false_refusal": "false_refusal",
        "not_evaluated": "not_evaluated",
        "probe_error": "probe_error",
    }
    draft_outcome = outcome_map.get(v4_outcome, "not_evaluated")
    
    # Build claims list for annotation
    claims = []
    for v in verdicts:
        claims.append({
            "claim_id": v.claim_id,
            "claim_text": v.text,
            "citation_ids": v.citation_ids,
            "status": "not_evaluated",  # Human reviewer fills this
            "reviewer_note": "",
        })
    
    record = {
        "response_id": rid,
        "category": item.get("category"),
        "answerable": gl.get("answerable"),
        "should_fallback": gl.get("should_fallback"),
        "allowed_final_behaviors": gl.get("allowed_final_behaviors", []),
        "manual_final_outcome": draft_outcome,  # Draft from V4, human can override
        "reviewer_note": "",  # Human fills
        "claims": claims,
        # Reference data for the reviewer
        "_prompt": item.get("prompt"),
        "_answer": answer,
        "_model_used": resp.get("model_used", ""),
        "_source_count": len(sources),
        "_retrieved_context": retrieved_context,
        "_v4_draft_outcome": v4_outcome,
    }
    responses.append(record)

output = {
    "schema_version": "1.0",
    "annotation_method": "manual_claim_to_exact_retrieved_context_review",
    "dataset": "live_after_improvement",
    "metric_policy": {
        "unsupported_final_answer_rate": {
            "numerator": "responses with manual_final_outcome == unsupported_answer",
            "denominator": "all usable responses"
        },
        "citation_support_rate": {
            "numerator": "claims with status == supported",
            "denominator": "claims with status in supported, partially_supported, unsupported"
        },
        "safe_fallback_accuracy": {
            "numerator": "responses with should_fallback == true and manual_final_outcome == correct_fallback",
            "denominator": "responses with should_fallback == true"
        }
    },
    "responses": responses
}

OUTPUT_PATH.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"Generated manual annotation template for {len(responses)} responses")
print(f"Saved to: {OUTPUT_PATH}")
print(f"\nDraft outcome distribution:")
from collections import Counter
counts = Counter(r["manual_final_outcome"] for r in responses)
for k, v in sorted(counts.items()):
    print(f"  {k}: {v}")
print(f"\nClaims extracted: {sum(len(r['claims']) for r in responses)}")
print(f"Responses with claims: {sum(1 for r in responses if r['claims'])}")
