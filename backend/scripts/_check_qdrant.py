from qdrant_client import QdrantClient
from app.config import settings

def check_qdrant():
    url = settings.QDRANT_URL.replace("localhost", "127.0.0.1")
    client = QdrantClient(url=url, timeout=10)
    collection_name = settings.QDRANT_COLLECTION
    
    try:
        info = client.get_collection(collection_name)
        print(f"\n--- Qdrant Status for '{collection_name}' ---")
        print(f"Total Vectors/Chunks: {info.points_count}")
        
        points, next_page = client.scroll(
            collection_name=collection_name,
            limit=1,
            with_payload=True,
            with_vectors=False
        )
        if points:
            payload = points[0].payload
            print(f"\nTop-level keys: {list(payload.keys())}")
            if 'metadata' in payload:
                print(f"Metadata keys: {list(payload['metadata'].keys())}")
                print(f"Metadata sample: {payload['metadata']}")
            else:
                print("No 'metadata' key found in payload.")
        
    except Exception as e:
        print(f"Error connecting to Qdrant: {e}")

if __name__ == '__main__':
    check_qdrant()
