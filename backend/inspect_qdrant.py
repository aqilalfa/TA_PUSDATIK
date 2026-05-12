from qdrant_client import QdrantClient
from app.config import settings

client = QdrantClient(url=settings.QDRANT_URL, check_compatibility=False)
points, _ = client.scroll(settings.QDRANT_COLLECTION, limit=5)
for p in points:
    print(f"ID: {p.id}, document_id: {p.payload.get('document_id')}, doc_id: {p.payload.get('doc_id')}, filename: {p.payload.get('filename')}")
