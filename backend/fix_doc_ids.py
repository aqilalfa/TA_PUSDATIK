import sys
from pathlib import Path

# Add backend to path
backend_path = Path("d:/aqil/pusdatik/backend")
sys.path.append(str(backend_path))

from app.database import SessionLocal
from app.models.db_models import Document as DBDocument

def fix_missing_doc_ids():
    print("=== FIXING MISSING DOC_IDS ===")
    db = SessionLocal()
    try:
        docs = db.query(DBDocument).filter(DBDocument.doc_id == None).all()
        print(f"Found {len(docs)} documents with missing doc_id")
        for doc in docs:
            # Use integer ID as doc_id for legacy documents
            doc.doc_id = str(doc.id)
            print(f"  - Set doc_id={doc.doc_id} for ID={doc.id} ({doc.filename})")
        
        db.commit()
        print("Update successful!")
    except Exception as e:
        db.rollback()
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    fix_missing_doc_ids()
