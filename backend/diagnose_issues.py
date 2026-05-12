"""
Diagnose two issues:
1. Why indicator_literal_search returns 0 results (MatchText support)
2. What default model backend uses, and verify Ollama can respond
"""
import httpx
import json

BASE = "http://localhost:8000"

# --- Test 1: Check default model ---
print("=== CHECK DEFAULT MODEL ===")
try:
    r = httpx.get(f"{BASE}/api/models/default", timeout=10)
    print(f"Default model endpoint: {r.status_code}")
    print(r.text[:200])
except Exception as e:
    print(f"Error: {e}")

# --- Test 2: Direct Ollama call with minimal prompt ---
print("\n=== DIRECT OLLAMA TEST ===")
try:
    r = httpx.post(
        "http://localhost:11434/api/chat",
        json={
            "model": "qwen2.5:3b",
            "messages": [{"role": "user", "content": "Apa itu SPBE? Jawab singkat 1 kalimat."}],
            "stream": False,
            "options": {"num_predict": 100, "num_ctx": 2048}
        },
        timeout=60
    )
    print(f"Status: {r.status_code}")
    if r.status_code == 200:
        resp = r.json()
        print("Answer:", resp.get("message", {}).get("content", ""))
    else:
        print("Error body:", r.text[:300])
except Exception as e:
    print(f"Exception: {e}")

# --- Test 3: Raw Qdrant scroll to verify field key ---
print("\n=== QDRANT FIELD PROBE (hierarchy) ===")
try:
    from qdrant_client import QdrantClient
    from qdrant_client.models import Filter, FieldCondition, MatchValue

    client = QdrantClient(url="http://localhost:6333", check_compatibility=False)
    COLL = "document_chunks"

    # Scroll first 5 docs and print their payload structure
    points, _ = client.scroll(collection_name=COLL, limit=3, with_payload=True, with_vectors=False)
    if points:
        p = points[0]
        print("Sample payload keys:", list(p.payload.keys()))
        # Check if metadata is nested
        if "metadata" in p.payload:
            print("Nested metadata keys:", list(p.payload["metadata"].keys())[:15])
        else:
            print("Top-level keys (no 'metadata' wrapper):", list(p.payload.keys())[:15])

    # Now try scrolling with hierarchy filter
    from qdrant_client.models import MatchText
    test_pts, _ = client.scroll(
        collection_name=COLL,
        scroll_filter=Filter(must=[
            FieldCondition(key="metadata.hierarchy", match=MatchText(text="Indikator 21"))
        ]),
        limit=5,
        with_payload=True,
        with_vectors=False
    )
    print(f"\nMatchText 'Indikator 21' in metadata.hierarchy: {len(test_pts)} results")
    for p in test_pts:
        meta = p.payload.get("metadata", p.payload)
        print(f"  - {meta.get('hierarchy','')[-70:]}")

    # Try without nesting prefix
    test_pts2, _ = client.scroll(
        collection_name=COLL,
        scroll_filter=Filter(must=[
            FieldCondition(key="hierarchy", match=MatchText(text="Indikator 21"))
        ]),
        limit=5,
        with_payload=True,
        with_vectors=False
    )
    print(f"\nMatchText 'Indikator 21' in hierarchy (no prefix): {len(test_pts2)} results")
    for p in test_pts2:
        meta = p.payload.get("metadata", p.payload)
        print(f"  - {meta.get('hierarchy','')[-70:]}")

except Exception as e:
    import traceback
    print(f"Qdrant error: {e}")
    traceback.print_exc()
