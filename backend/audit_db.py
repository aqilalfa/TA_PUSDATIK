import sys
from pathlib import Path

# Add backend to path
backend_path = Path("d:/aqil/pusdatik/backend")
sys.path.append(str(backend_path))

from app.database import SessionLocal
from app.models.db_models import Chunk, Document as DBDocument
from sqlalchemy import func

def audit_docs_and_chunks():
    print("=== DOCUMENT AND CHUNK AUDIT ===")
    db = SessionLocal()
    try:
        docs = db.query(DBDocument).all()
        print(f"{'ID':<5} | {'DocID':<15} | {'Status':<10} | {'Count (SQL)':<12} | {'Filename':<30}")
        print("-" * 80)
        for doc in docs:
            chunk_count = db.query(func.count(Chunk.id)).filter(Chunk.document_id == doc.id).scalar()
            print(f"{doc.id:<5} | {str(doc.doc_id):<15} | {str(doc.status):<10} | {chunk_count:<12} | {doc.filename[:30]}")
            
        # Check for orphan chunks
        orphan_count = db.query(func.count(Chunk.id)).filter(~Chunk.document_id.in_(db.query(DBDocument.id))).scalar()
        print(f"\nOrphan chunks: {orphan_count}")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    audit_docs_and_chunks()
