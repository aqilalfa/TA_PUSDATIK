import sys
from pathlib import Path

# Add backend to path
backend_path = Path("d:/aqil/pusdatik/backend")
sys.path.append(str(backend_path))

from app.database import SessionLocal
from app.models.db_models import Chunk, Document as DBDocument

def check_db_health():
    print("=== SQL DATABASE CHECK ===")
    try:
        db = SessionLocal()
        doc_count = db.query(DBDocument).count()
        chunk_count = db.query(Chunk).count()
        print(f"Documents in SQL: {doc_count}")
        print(f"Chunks in SQL: {chunk_count}")
        
        if chunk_count > 0:
            sample = db.query(Chunk).first()
            print(f"Sample chunk: ID={sample.id}, DocID={sample.document_id}, Snippet={sample.chunk_text[:50]}...")
        else:
            print("WARNING: No chunks found in SQL database!")
            
        db.close()
    except Exception as e:
        print(f"SQL Error: {e}")

def check_qdrant_health():
    print("\n=== QDRANT CHECK ===")
    try:
        from qdrant_client import QdrantClient
        from app.config import settings
        
        client = QdrantClient(url=settings.QDRANT_URL, check_compatibility=False)
        collection_info = client.get_collection(settings.QDRANT_COLLECTION)
        print(f"Collection: {settings.QDRANT_COLLECTION}")
        print(f"Points count: {collection_info.points_count}")
        print(f"Vectors config: {collection_info.config.params.vectors}")
        
        # Scroll to see sample payload
        points, _ = client.scroll(settings.QDRANT_COLLECTION, limit=1)
        if points:
            print("Sample payload keys:", list(points[0].payload.keys()))
            if "doc_id" in points[0].payload:
                print(f"Sample doc_id: {points[0].payload['doc_id']}")
    except Exception as e:
        print(f"Qdrant Error: {e}")

if __name__ == "__main__":
    check_db_health()
    check_qdrant_health()
