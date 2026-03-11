"""
Test API endpoints with Marker integration.
Tests: Upload -> Preview -> Save -> Query
"""

import sys
import os
import time
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Use requests library
try:
    import requests
except ImportError:
    print("[FAIL] requests library not installed. Run: pip install requests")
    sys.exit(1)

BASE_URL = "http://localhost:8000"


def check_server():
    """Check if server is running"""
    print("\n" + "=" * 60)
    print("Checking Server Status")
    print("=" * 60)

    try:
        resp = requests.get(f"{BASE_URL}/", timeout=5)
        data = resp.json()
        print(f"[OK] Server: {data.get('service', 'Unknown')}")
        print(f"[OK] Version: {data.get('version', 'Unknown')}")
        return True
    except Exception as e:
        print(f"[FAIL] Server not available: {e}")
        return False


def test_list_documents():
    """List existing documents"""
    print("\n" + "=" * 60)
    print("TEST 1: List Documents")
    print("=" * 60)

    try:
        resp = requests.get(f"{BASE_URL}/api/documents", timeout=10)
        docs = resp.json()

        print(f"[OK] Found {len(docs)} documents")
        for doc in docs[:5]:
            print(f"    - [{doc['doc_id'][:8]}] {doc['filename']} ({doc['status']})")

        return True, docs
    except Exception as e:
        print(f"[FAIL] Error: {e}")
        return False, []


def test_upload_document():
    """Upload a test PDF document"""
    print("\n" + "=" * 60)
    print("TEST 2: Upload Document")
    print("=" * 60)

    # Use a smaller PDF for faster testing
    test_files = [
        r"D:\aqil\pusdatik\data\documents\peraturan\Perpres Nomor 95 Tahun 2018.pdf",
        r"D:\aqil\pusdatik\data\documents\peraturan\Permen PANRB 59 Tahun 2020.pdf",
    ]

    pdf_path = None
    for f in test_files:
        if os.path.exists(f):
            pdf_path = f
            break

    if not pdf_path:
        print("[WARN] No test PDF found")
        return False, None

    filename = os.path.basename(pdf_path)
    print(f"Uploading: {filename}")

    try:
        with open(pdf_path, "rb") as f:
            files = {"file": (filename, f, "application/pdf")}
            resp = requests.post(
                f"{BASE_URL}/api/documents/upload", files=files, timeout=60
            )

        if resp.status_code == 200:
            data = resp.json()
            print(f"[OK] Upload successful")
            print(f"    Doc ID: {data['doc_id']}")
            print(f"    Status: {data['status']}")
            return True, data["doc_id"]
        else:
            print(f"[FAIL] Upload failed: {resp.status_code}")
            print(f"    Response: {resp.text[:200]}")
            return False, None

    except Exception as e:
        print(f"[FAIL] Error: {e}")
        return False, None


def test_preview_chunks(doc_id: str):
    """Preview document chunks before indexing"""
    print("\n" + "=" * 60)
    print("TEST 3: Preview Chunks")
    print("=" * 60)

    print(f"Previewing doc: {doc_id[:8]}...")

    try:
        resp = requests.post(
            f"{BASE_URL}/api/documents/{doc_id}/preview",
            timeout=300,  # Marker conversion can take time
        )

        if resp.status_code == 200:
            data = resp.json()
            print(f"[OK] Preview successful")
            print(f"    Doc Type: {data['doc_type']}")
            print(f"    Title: {data['document_title'][:50]}...")
            print(f"    Total Chunks: {data['total_chunks']}")

            # Check for tables in chunks
            chunks = data.get("chunks", [])
            table_chunks = sum(1 for c in chunks if "|" in c.get("text", ""))
            print(f"    Chunks with tables: {table_chunks}")

            # Show sample chunk
            if chunks:
                print(f"\nSample chunk:")
                chunk = chunks[0]
                preview = chunk.get("text", "")[:100].replace("\n", " ")
                print(f"    {preview}...")

            return True, data
        else:
            print(f"[FAIL] Preview failed: {resp.status_code}")
            print(f"    Response: {resp.text[:300]}")
            return False, None

    except Exception as e:
        print(f"[FAIL] Error: {e}")
        import traceback

        traceback.print_exc()
        return False, None


def test_save_document(doc_id: str):
    """Save/index document to vector store"""
    print("\n" + "=" * 60)
    print("TEST 4: Save/Index Document")
    print("=" * 60)

    print(f"Saving doc: {doc_id[:8]}...")

    try:
        resp = requests.post(f"{BASE_URL}/api/documents/{doc_id}/save", timeout=120)

        if resp.status_code == 200:
            data = resp.json()
            print(f"[OK] Save successful")
            print(f"    Chunks indexed: {data['chunks_indexed']}")
            print(f"    Status: {data['status']}")
            return True, data
        else:
            print(f"[FAIL] Save failed: {resp.status_code}")
            print(f"    Response: {resp.text[:200]}")
            return False, None

    except Exception as e:
        print(f"[FAIL] Error: {e}")
        return False, None


def test_search_query():
    """Test search/RAG query"""
    print("\n" + "=" * 60)
    print("TEST 5: Search Query")
    print("=" * 60)

    queries = [
        "Apa definisi SPBE?",
        "Indikator evaluasi SPBE",
    ]

    for query in queries:
        print(f"\nQuery: {query}")

        try:
            resp = requests.get(
                f"{BASE_URL}/api/search",
                params={"query": query, "top_k": 3},
                timeout=30,
            )

            if resp.status_code == 200:
                results = resp.json()
                print(f"[OK] Found {len(results)} results")

                for i, r in enumerate(results[:2]):
                    doc = r.get("document", "Unknown")
                    score = r.get("score", 0)
                    text = r.get("text", "")[:80].replace("\n", " ")
                    print(f"    [{i + 1}] ({score:.3f}) {doc}")
                    print(f"        {text}...")
            else:
                print(f"[WARN] Search returned: {resp.status_code}")

        except Exception as e:
            print(f"[FAIL] Error: {e}")

    return True


def test_chat_query():
    """Test chat with RAG"""
    print("\n" + "=" * 60)
    print("TEST 6: Chat Query")
    print("=" * 60)

    query = "Jelaskan domain-domain dalam evaluasi SPBE"
    print(f"Query: {query}")

    try:
        resp = requests.post(
            f"{BASE_URL}/api/chat",
            json={"message": query, "use_rag": True, "top_k": 3, "max_tokens": 512},
            timeout=120,
        )

        if resp.status_code == 200:
            data = resp.json()
            message = data.get("message", {})
            content = message.get("content", "")
            sources = message.get("sources", [])
            timing = message.get("timing", {})

            print(f"[OK] Chat successful")
            print(f"\nResponse ({len(content)} chars):")
            print(f"    {content[:300]}...")

            print(f"\nSources: {len(sources)}")
            for s in sources[:3]:
                print(
                    f"    - {s.get('document', 'Unknown')} (score: {s.get('score', 0):.3f})"
                )

            if timing:
                print(f"\nTiming:")
                for k, v in timing.items():
                    print(f"    {k}: {v:.2f}s")

            return True
        else:
            print(f"[FAIL] Chat failed: {resp.status_code}")
            print(f"    Response: {resp.text[:200]}")
            return False

    except Exception as e:
        print(f"[FAIL] Error: {e}")
        import traceback

        traceback.print_exc()
        return False


def main():
    """Run all API tests"""
    print("\n" + "=" * 60)
    print("API TEST SUITE - MARKER INTEGRATION")
    print("=" * 60)

    results = []

    # Check server
    if not check_server():
        print("\n[FAIL] Server not running. Start with:")
        print("    cd backend && python -m uvicorn app.api.server_full:app --port 8000")
        return False

    # Test 1: List documents
    success, docs = test_list_documents()
    results.append(("List Documents", success))

    # Test 2: Upload document
    success, doc_id = test_upload_document()
    results.append(("Upload Document", success))

    if doc_id:
        # Test 3: Preview chunks
        success, preview = test_preview_chunks(doc_id)
        results.append(("Preview Chunks", success))

        # Test 4: Save document
        success, _ = test_save_document(doc_id)
        results.append(("Save Document", success))
    else:
        results.append(("Preview Chunks", False))
        results.append(("Save Document", False))

    # Test 5: Search
    success = test_search_query()
    results.append(("Search Query", success))

    # Test 6: Chat
    success = test_chat_query()
    results.append(("Chat Query", success))

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    for name, passed in results:
        status = "[PASS]" if passed else "[FAIL]"
        print(f"  {status}: {name}")

    passed_count = sum(1 for _, p in results if p)
    print(f"\nTotal: {passed_count}/{len(results)} tests passed")

    return all(p for _, p in results)


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
