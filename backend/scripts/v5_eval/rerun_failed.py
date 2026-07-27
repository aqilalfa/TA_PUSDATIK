"""Re-run only specific LLM09 prompts that failed or need replacement."""
import json
import time
import urllib.request
import urllib.parse
import sys
from pathlib import Path

API_URL = "http://localhost:8000/api/chat/stream"
USERNAME = "admin@bssn.go.id"
PASSWORD = "password123"
FIXTURE_PATH = Path("D:/aqil/pusdatik/backend/tests/fixtures/llm09_misinformation_prompts.json")
OUTPUT_PATH = Path("D:/aqil/pusdatik/backend/scripts/v5_eval/after_improvement/llm09_live_responses.json")
TARGET_IDS = {"llm09-wrong-pasal-001", "llm09-source-mismatch-002"}

def get_token():
    login_url = API_URL.replace("/chat/stream", "/auth/login")
    data = urllib.parse.urlencode({"username": USERNAME, "password": PASSWORD}).encode("utf-8")
    request = urllib.request.Request(login_url, data=data, method="POST")
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8")).get("access_token")

def post_chat_stream(prompt, token, session_id=None, top_k=5, timeout=180):
    payload = json.dumps({
        "session_id": session_id,
        "message": prompt,
        "top_k": top_k,
        "use_structured_fact": False,
    }).encode("utf-8")
    headers = {"Content-Type": "application/json", "Accept": "text/event-stream", "Authorization": f"Bearer {token}"}
    request = urllib.request.Request(API_URL, data=payload, headers=headers, method="POST")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = response.read().decode("utf-8", errors="replace")
    
    # Parse SSE
    events = []
    for block in body.replace("\r\n", "\n").split("\n\n"):
        if not block.strip():
            continue
        event_name = "message"
        data_lines = []
        for line in block.split("\n"):
            if line.startswith("event:"):
                event_name = line.split(":", 1)[1].strip()
            elif line.startswith("data:"):
                data_lines.append(line.split(":", 1)[1].strip())
        if not data_lines:
            continue
        raw_data = "\n".join(data_lines)
        try:
            data = json.loads(raw_data)
        except json.JSONDecodeError:
            data = {"raw": raw_data}
        events.append({"event": event_name, "data": data})
    
    complete_events = [e for e in events if e["event"] == "complete"]
    if complete_events:
        return complete_events[-1]["data"]
    
    token_text = "".join(str(e["data"].get("t", "")) for e in events if e["event"] == "token" and isinstance(e.get("data"), dict))
    if token_text:
        return {"answer": token_text, "sources": [], "validation": None}
    
    error_events = [e for e in events if e["event"] == "error"]
    if error_events:
        return {"answer": "", "error": error_events[-1]["data"]}
    
    return {"answer": "", "error": "No complete/token/error SSE event found"}

def main():
    token = get_token()
    if not token:
        print("Failed to authenticate")
        return 1
    
    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    target_items = [item for item in fixture if item.get("id") in TARGET_IDS]
    
    print(f"Re-running {len(target_items)} prompts: {[i['id'] for i in target_items]}")
    
    # Load existing responses
    existing = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
    existing_by_id = {r["id"]: r for r in existing}
    
    for item in target_items:
        prompt = item["prompt"]
        print(f"\nSending: {item['id']} -> {prompt[:60]}...")
        started = time.perf_counter()
        
        try:
            response_data = post_chat_stream(prompt, token, session_id=f"rerun-{item['id']}", top_k=5, timeout=180)
            error = None
        except Exception as exc:
            response_data = {"answer": "", "sources": [], "validation": None}
            error = f"{type(exc).__name__}: {exc}"
        
        latency = int((time.perf_counter() - started) * 1000)
        print(f"  Done in {latency}ms, answer preview: {str(response_data.get('answer',''))[:80]}...")
        
        new_row = {
            "id": item.get("id"),
            "category": item.get("category"),
            "expected_behavior": item.get("expected_behavior"),
            "prompt": item.get("prompt"),
            "response": response_data,
            "error": error,
            "latency_ms": latency,
        }
        existing_by_id[item["id"]] = new_row
    
    # Write back, preserving order of original file
    updated = [existing_by_id.get(r["id"], r) for r in existing]
    # Add any new IDs that weren't in original
    for item in target_items:
        if item["id"] not in {r["id"] for r in updated}:
            updated.append(existing_by_id[item["id"]])
    
    OUTPUT_PATH.write_text(json.dumps(updated, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nMerged {len(target_items)} replacement(s) into {OUTPUT_PATH}")
    print(f"Total responses: {len(updated)}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
