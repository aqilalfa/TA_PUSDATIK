import sys
import os
from pathlib import Path

# Force CPU mode to avoid CUDA hang
os.environ["CUDA_VISIBLE_DEVICES"] = ""

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import SessionLocal, engine
from app.models.db_models import Document, Chunk
from app.core.ingestion.pdf_processor import DocumentProcessor
from app.config import settings
from loguru import logger
from datetime import datetime
from qdrant_client import QdrantClient

def reingest_single(pdf_path: str):
    db = SessionLocal()
    client = QdrantClient(url=settings.QDRANT_URL, timeout=60)
    processor = DocumentProcessor()
    
    path_obj = Path(pdf_path)
    filename = path_obj.name
    
    # 1. Delete old document and its chunks
    old_docs = db.query(Document).filter(Document.filename == filename).all()
    for old_doc in old_docs:
        chunks = db.query(Chunk).filter(Chunk.document_id == old_doc.id).all()
        chunk_ids = [str(c.id) for c in chunks]
        
        # Delete from Qdrant
        if chunk_ids:
            try:
                client.delete(
                    collection_name=settings.QDRANT_COLLECTION,
                    points_selector=chunk_ids
                )
            except Exception as e:
                logger.warning(f"Could not delete from Qdrant: {e}")
                
        # Delete from DB
        db.query(Chunk).filter(Chunk.document_id == old_doc.id).delete()
        db.delete(old_doc)
    db.commit()
    
    # 2. Add new document
    parent_folder = path_obj.parent.name.lower()
    file_doc_type = "laporan" if parent_folder in ("audit", "others") else "peraturan"
    
    document = Document(
        filename=filename,
        original_path=str(path_obj),
        doc_type=file_doc_type,
        status="pending",
        uploaded_by=1,
        uploaded_at=datetime.utcnow(),
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    
    # 3. Process
    result = processor.process_document(
        pdf_path=str(path_obj),
        filename=filename,
        doc_id=document.id,
        db=db,
        doc_type_hint=file_doc_type,
    )
    
    # Update type if changed during processing
    parsed_type = result.get("doc_type", file_doc_type)
    document.doc_type = parsed_type
    db.commit()
    
    logger.success(f"Processed as {parsed_type}: {result.get('chunk_count', 0)} chunks")
    db.close()

if __name__ == "__main__":
    target_pdf = r"D:\aqil\pusdatik\data\documents\audit\20250313_Laporan_Pelaksanaan_Evaluasi_SPBE_2024.pdf"
    logger.info(f"Re-ingesting single file: {target_pdf}")
    reingest_single(target_pdf)
