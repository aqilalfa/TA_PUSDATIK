import sys
import os
import json
from pathlib import Path

# Force CPU mode to avoid CUDA hang
os.environ["CUDA_VISIBLE_DEVICES"] = ""

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import SessionLocal, engine
from app.models.db_models import Document, Chunk
from app.core.ingestion.json_structure_parser import parse_document
from app.core.ingestion.structured_chunker import chunk_document
from loguru import logger
from datetime import datetime
from qdrant_client import QdrantClient
from app.config import settings
import fitz

def reingest_pedoman_standalone(pdf_path: str):
    db = SessionLocal()
    client = QdrantClient(url=settings.QDRANT_URL, timeout=60)
    
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
    
    logger.info("Deleted old chunks and document.")
    
    # 2. Add new document
    document = Document(
        filename=filename,
        original_path=str(path_obj),
        doc_type="pedoman_spbe",
        status="processing",
        uploaded_by=1,
        uploaded_at=datetime.utcnow(),
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    
    # 3. Extract text manually bypassing OCR module
    logger.info(f"Extracting text from PDF via fitz: {pdf_path}")
    doc = fitz.open(pdf_path)
    full_text = ""
    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text()
        full_text += f"\n\n--- Page {page_num + 1} ---\n\n"
        full_text += text
    doc.close()
    
    # 4. Parse text into structured JSON
    logger.info("Parsing JSON...")
    doc_structure = parse_document(
        text=full_text,
        filename=filename,
        folder_hint="pedoman_spbe",
    )
    
    doc_type = doc_structure.get("type", "pedoman_spbe")
    document.doc_type = doc_type
    document.doc_metadata = json.dumps(doc_structure, ensure_ascii=False)
    db.commit()
    
    logger.info(f"Parsed type: {doc_type}")
    
    # 5. Chunking
    logger.info("Chunking...")
    chunks_data = chunk_document(doc_structure)
    
    # 6. Save chunks to DB and Qdrant
    if not chunks_data:
        logger.warning("No chunks generated!")
        document.status = "failed"
        db.commit()
        return
        
    db_chunks = []
    points = []
    
    from app.core.rag.vector_store import vector_store_manager
    
    logger.info(f"Saving {len(chunks_data)} chunks to DB and Qdrant...")
    for i, c in enumerate(chunks_data):
        # Save to DB
        db_chunk = Chunk(
            document_id=document.id,
            chunk_text=c["text"],
            chunk_index=i,
            chunk_metadata=json.dumps(c["metadata"], ensure_ascii=False)
        )
        db.add(db_chunk)
        points.append(db_chunk)
        
    db.commit()
    
    try:
        texts_to_embed = [c["text"] for c in chunks_data]
        metadatas = [c["metadata"] for c in chunks_data]
        
        # Add tracking metadata
        for m in metadatas:
            m["document_id"] = document.id
            m["doc_type"] = doc_type
            
        vector_store_manager.add_documents(texts_to_embed, metadatas)
        logger.info(f"Uploaded to Qdrant via vector_store_manager")
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        logger.error(f"Failed to upload to Qdrant: {e}")
        db.query(Chunk).filter(Chunk.document_id == document.id).delete()
        document.status = "failed"
        db.commit()
        return
        
    document.status = "completed"
    document.processed_at = datetime.utcnow()
    db.commit()
    
    logger.success(f"Successfully processed {len(chunks_data)} chunks!")
    db.close()

if __name__ == "__main__":
    target_pdf = r"D:\aqil\pusdatik\data\documents\pedoman\PEDOMAN MENTERI PENDAYAGUNAAN APARATUR NEGARA DAN REFORMASI BIROKRASI REPUBLIK INDONESIA NOMOR 3 TAHUN 2024.pdf"
    reingest_pedoman_standalone(target_pdf)
