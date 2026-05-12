from app.core.rag.langchain_engine import langchain_engine
from qdrant_client.models import Filter, FieldCondition, MatchText, MatchValue
import json

def search_for_indicator_21():
    print("Searching for ANY chunk containing 'Indikator 21' or 'Indikator ke-21'...")
    
    langchain_engine.initialize()
    client = langchain_engine.client
    collection = langchain_engine.collection_name
    
    # 1. Try full text search via Qdrant scroll (simple filter)
    # Note: Qdrant MatchText is for full-text indexed fields
    results, _ = client.scroll(
        collection_name=collection,
        scroll_filter=Filter(
            should=[
                FieldCondition(key="text", match=MatchText(text="Indikator 21")),
                FieldCondition(key="text", match=MatchText(text="Indikator ke-21")),
                FieldCondition(key="metadata.context_header", match=MatchText(text="Indikator 21"))
            ]
        ),
        limit=10,
        with_payload=True
    )
    
    print(f"Found {len(results)} matches.")
    for i, r in enumerate(results, 1):
        print(f"\nMatch {i}:")
        payload = r.payload
        text = payload.get("text", "")
        meta = payload.get("metadata", {})
        print(f"  Doc: {meta.get('document_title') or meta.get('filename')}")
        print(f"  Header: {meta.get('context_header')}")
        print(f"  Snippet: {text[:200]}...")

if __name__ == "__main__":
    search_for_indicator_21()
