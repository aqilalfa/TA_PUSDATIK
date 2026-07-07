import json

def check_missing():
    with open("data/eval_ragas_final_40_qwen3_32b_merged.json", "r", encoding="utf-8") as f:
        data = json.load(f)

    missing = []
    for q in data["per_question"]:
        metrics = q.get("scores", {})
        missing_metrics = [k for k, v in metrics.items() if v is None]
        if missing_metrics:
            missing.append(q["id"])
            print(f"{q['id']} is missing: {missing_metrics}")

    print(f"Total missing: {len(missing)}")

if __name__ == "__main__":
    check_missing()