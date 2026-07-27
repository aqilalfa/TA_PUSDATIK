"""Extract exact retrieved context (sources + snippets) for all 20 live responses.

Produces a file matching the baseline annotation format so manual audit
can be performed with the same technique.
"""
import json
from pathlib import Path

LIVE_PATH = Path("D:/aqil/pusdatik/backend/scripts/v5_eval/after_improvement/llm09_live_responses.json")
OUTPUT_PATH = Path("D:/aqil/pusdatik/backend/scripts/v5_eval/after_improvement/llm09_live_retrieved_context.json")

data = json.loads(LIVE_PATH.read_text(encoding="utf-8"))

context_records = []
for item in data:
    resp = item.get("response", {})
    sources = resp.get("sources", []) or []
    
    # Build a "context" string similar to what the LLM received
    context_lines = []
    for src in sources:
        sid = src.get("id", "?")
        doc = src.get("document", "")
        section = src.get("section", "")
        snippet = src.get("snippet", "")
        hierarchy = src.get("hierarchy", "")
        context_lines.append(f"[{sid}] {doc} | {section}\n{snippet}")
    
    context_text = "\n---\n".join(context_lines) if context_lines else "(no sources retrieved)"
    
    record = {
        "response_id": item["id"],
        "category": item.get("category"),
        "expected_behavior": item.get("expected_behavior"),
        "prompt": item.get("prompt"),
        "model_used": resp.get("model_used", ""),
        "answer": resp.get("answer", ""),
        "sources": sources,
        "retrieved_context": context_text,
        "source_count": len(sources),
        "error": item.get("error"),
        "validation": resp.get("validation"),
        "answerability": resp.get("answerability"),
        "quality_check": resp.get("quality_check"),
    }
    context_records.append(record)

OUTPUT_PATH.write_text(json.dumps(context_records, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"Saved exact retrieved context for {len(context_records)} responses to {OUTPUT_PATH}")

# Summary stats
has_sources = sum(1 for r in context_records if r["source_count"] > 0)
no_sources = sum(1 for r in context_records if r["source_count"] == 0)
print(f"  With sources: {has_sources}")
print(f"  No sources (guard blocked): {no_sources}")
