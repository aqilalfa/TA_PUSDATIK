from qdrant_client import QdrantClient
from app.config import settings
import json

def inspect_metadata():
    url = settings.QDRANT_URL.replace("localhost", "127.0.0.1")
    client = QdrantClient(url=url, timeout=10)
    collection_name = settings.QDRANT_COLLECTION
    
    print(f"--- INSPECTING COLLECTION: {collection_name} ---")
    
    # 1. Get unique values of 'indikator' field
    # We'll scroll and collect
    indicators = set()
    points, _ = client.scroll(
        collection_name=collection_name,
        limit=1000,
        with_payload=True
    )
    
    for p in points:
        meta = p.payload.get('metadata', {})
        ind = meta.get('indikator')
        if ind:
            indicators.add(ind)
    
    print("\n[UNIQUE INDICATORS FOUND]:")
    for ind in sorted(list(indicators)):
        print(f"- {ind}")

    # 2. Specifically check for anything containing "Arsitektur"
    print("\n[ARSITEKTUR RELATED CHUNKS]:")
    for p in points:
        meta = p.payload.get('metadata', {})
        ind = meta.get('indikator', '')
        if "Arsitektur" in ind:
            print(f"- Index: {meta.get('chunk_index')} | Indikator: {ind}")
            print(f"  Doc: {meta.get('judul_dokumen')}")

if __name__ == '__main__':
    inspect_metadata()
