"""Final verification: checks retrieval ranking AND AI answer quality."""
import httpx
import json

BASE = "http://localhost:8000"

def check_retrieval():
    print("=" * 60)
    print("TEST 1: RETRIEVAL ACCURACY (indikator 21)")
    print("=" * 60)
    r = httpx.get(f"{BASE}/api/chat/debug/retrieval?query=indikator+21+penilaian+spbe", timeout=30)
    data = r.json()
    print(f"Query type : {data['query_type']}")
    print(f"Total docs : {data['source_count']}")
    for i, d in enumerate(data["docs"], 1):
        meta = d["metadata"]
        title = (meta.get("document_title") or meta.get("filename") or "?")[:55]
        hier  = (meta.get("hierarchy") or "")[-65:]
        boost = meta.get("query_boost", 0)
        score = round(meta.get("rerank_score", 0), 3)
        text  = d["content"][:110]
        print(f"\n  [{i}] {title}")
        print(f"       loc  : ...{hier}")
        print(f"       boost: {boost}  score: {score}")
        print(f"       text : {text}")

    # Check if top result is the real Indikator 21 chunk
    top = data["docs"][0] if data["docs"] else {}
    hier = top.get("metadata", {}).get("hierarchy", "")
    passed = "Indikator 21" in hier or "indikator 21" in hier.lower()
    print(f"\n  >> Top result is Indikator-21 chunk: {'PASS ✓' if passed else 'FAIL - needs tuning'}")
    return passed

def check_ai_answer():
    print("\n" + "=" * 60)
    print("TEST 2: AI FULL ANSWER (stream chat)")
    print("=" * 60)
    payload = {
        "message": "jelaskan mengenai indikator ke 21 penilaian spbe",
        "session_id": None,
        "use_rag": True,
        "top_k": 5,
    }
    full_answer = ""
    sources = []
    with httpx.stream("POST", f"{BASE}/api/chat/stream", json=payload, timeout=120) as resp:
        print(f"Status: {resp.status_code}")
        cur_event = None
        for line in resp.iter_lines():
            if not line:
                continue
            if line.startswith("event: "):
                cur_event = line[7:]
            elif line.startswith("data: "):
                try:
                    d = json.loads(line[6:])
                    if cur_event == "retrieval":
                        print(f"  [retrieval] {d['count']} sources found")
                    elif cur_event == "token":
                        t = d.get("t", "")
                        print(t, end="", flush=True)
                        full_answer += t
                    elif cur_event == "complete":
                        sources = d.get("sources", [])
                except Exception:
                    pass
    print(f"\n\n  Sources used: {len(sources)}")
    for s in sources:
        sect = s.get("section") or s.get("hierarchy", "")[-50:] or "(no section)"
        print(f"    [{s['id']}] {s.get('document_short','?')} | {sect}")

    passed = "manajemen risiko" in full_answer.lower() or "indikator 21" in full_answer.lower()
    print(f"\n  >> Answer mentions Indikator-21 topic: {'PASS ✓' if passed else 'FAIL'}")
    return passed

if __name__ == "__main__":
    r1 = check_retrieval()
    r2 = check_ai_answer()
    print("\n" + "=" * 60)
    print(f"OVERALL: {'ALL TESTS PASSED' if r1 and r2 else 'SOME TESTS FAILED - review output above'}")
    print("=" * 60)
