from qdrant_client import QdrantClient
from app.config import settings
from app.core.rag.langchain_engine import langchain_engine
import json

def debug_query(question: str):
    # Ensure URL is correct
    url = settings.QDRANT_URL.replace("localhost", "127.0.0.1")
    client = QdrantClient(url=url, timeout=10)
    
    print(f"--- DEBUGGING QUERY: {question} ---")
    
    # 1. Search in Qdrant directly
    results = langchain_engine.qdrant.similarity_search(question, k=10)
    
    print("\n[RETRIEVED TOP 10]:")
    for i, doc in enumerate(results, 1):
        meta = doc.metadata
        print(f"{i}. Index: {meta.get('chunk_index')} | Doc: {meta.get('judul_dokumen')} | Hierarchy: {meta.get('hierarchy')}")
        print(f"   Snippet: {doc.page_content[:150]}...\n")

    # 2. Specifically look for Arsitektur SPBE Indikator in Qdrant
    print("\n[SEARCHING FOR SPECIFIC ARSITEKTUR CHUNKS]:")
    points, _ = client.scroll(
        collection_name=settings.QDRANT_COLLECTION,
        scroll_filter={
            "must": [
                {"key": "metadata.indikator", "match": {"text": "Kebijakan Arsitektur SPBE"}}
            ]
        },
        limit=5
    )
    
    if points:
        for p in points:
            m = p.payload['metadata']
            print(f"Found Target Indikator -> Index: {m.get('chunk_index')} | Text Hash: {hash(p.payload['text'])}")
            print(f"Text Preview: {p.payload['text'][:200]}...")
    else:
        print("Target Indikator 'Kebijakan Arsitektur SPBE' NOT FOUND in metadata search.")

if __name__ == '__main__':
    debug_query("Data dukung apa yang wajib disiapkan agar mencapai tingkat kematangan 5 pada indikator Kebijakan Arsitektur SPBE?")
