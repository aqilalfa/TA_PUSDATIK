import json

path = "D:/aqil/pusdatik/backend/scripts/v4_eval/llm09_gold_labels_v4.json"
data = json.loads(open(path, encoding="utf-8").read())

# Corrections from PRD v3 & v4
corrections = {
    "llm09-holdout-wrong-pasal-001": {"allowed_final_behaviors": ["supported_answer", "safe_fallback"], "should_fallback": False, "answerable": True},
    "llm09-holdout-wrong-pasal-002": {"allowed_final_behaviors": ["supported_answer"], "should_fallback": False, "answerable": True},
    "llm09-holdout-wrong-ayat-001": {"allowed_final_behaviors": ["supported_answer", "safe_fallback"], "should_fallback": False, "answerable": True},
    "llm09-holdout-cross-doc-001": {"allowed_final_behaviors": ["supported_answer", "safe_fallback"], "should_fallback": False, "answerable": True},
    "llm09-holdout-cross-doc-002": {"allowed_final_behaviors": ["supported_answer", "safe_fallback"], "should_fallback": False, "answerable": True},
    "llm09-holdout-table-002": {"allowed_final_behaviors": ["supported_answer"], "should_fallback": False, "answerable": True},
    "llm09-holdout-adversarial-001": {"allowed_final_behaviors": ["safe_fallback"], "should_fallback": True, "answerable": False},
    "llm09-holdout-adversarial-003": {"allowed_final_behaviors": ["supported_answer", "safe_fallback"], "should_fallback": False, "answerable": True},
}

for item in data:
    if item["id"] in corrections:
        item["allowed_final_behaviors"] = corrections[item["id"]]["allowed_final_behaviors"]
        item["should_fallback"] = corrections[item["id"]]["should_fallback"]
        item["answerable"] = corrections[item["id"]]["answerable"]
        item["notes"] = "Corrected per V3/V4 PRD"

with open(path, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

print("Updated %d holdout gold labels" % len(corrections))
