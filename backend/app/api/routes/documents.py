"""
Document management endpoints with processing integration
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.db_models import Document
from app.models.schemas import DocumentResponse, DocumentStatus
from app.core.ingestion.pdf_processor import DocumentProcessor
from datetime import datetime
from typing import List
from loguru import logger
from pathlib import Path
import os
import shutil

# Define backend directory
BACKEND_DIR = Path(__file__).parent.parent.parent.parent
DOCUMENTS_DIR = BACKEND_DIR / "data" / "documents"

router = APIRouter()


@router.post("/upload", response_model=DocumentResponse)
async def upload_document(
    file: UploadFile = File(...),
    doc_type: str = "auto",
    user_id: int = 1,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db),
):
    """
    Upload a document for processing
    Triggers complete OCR + parsing + indexing pipeline in background
    """
    logger.info(f"Uploading document: {file.filename}")

    # Validate file type
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    # Determine document type based on upload
    if doc_type == "auto":
        # Simple heuristic based on filename
        filename_lower = file.filename.lower()
        if "audit" in filename_lower:
            doc_type = "audit"
        elif any(
            keyword in filename_lower
            for keyword in ["pp", "perpres", "permen", "peraturan"]
        ):
            doc_type = "peraturan"
        else:
            doc_type = "other"

    # Save file
    # file_path = f"data/documents/{doc_type}/{file.filename}"
    file_path = str(DOCUMENTS_DIR / doc_type / file.filename)
    os.makedirs(os.path.dirname(file_path), exist_ok=True)

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    logger.info(f"File saved to: {file_path}")

    # Create document record
    document = Document(
        filename=file.filename,
        original_path=file_path,
        doc_type=doc_type,
        status="pending",
        uploaded_by=user_id,
        uploaded_at=datetime.utcnow(),
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    logger.info(f"Document record created with ID: {document.id}")

    # Add background task for processing
    background_tasks.add_task(
        process_document_background, document.id, file_path, file.filename
    )

    logger.info(f"Background processing task scheduled for document {document.id}")

    return document


def process_document_background(doc_id: int, file_path: str, filename: str):
    """Background task for document processing"""
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        processor = DocumentProcessor()
        result = processor.process_document(file_path, filename, doc_id, db)
        logger.success(f"Document {doc_id} processed successfully")
    except Exception as e:
        logger.error(f"Error processing document {doc_id}: {e}")
    finally:
        db.close()


@router.get("/{document_id}", response_model=DocumentResponse)
def get_document(document_id: int, db: Session = Depends(get_db)):
    """Get document by ID"""
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    return document


@router.get("/{document_id}/status", response_model=DocumentStatus)
def get_document_status(document_id: int, db: Session = Depends(get_db)):
    """Get document processing status"""
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    return DocumentStatus(
        id=document.id, status=document.status, error_message=document.error_message
    )


@router.get("/", response_model=List[DocumentResponse])
def list_documents(
    skip: int = 0, limit: int = 100, doc_type: str = None, db: Session = Depends(get_db)
):
    """List all documents"""
    query = db.query(Document)

    if doc_type:
        query = query.filter(Document.doc_type == doc_type)

    documents = query.offset(skip).limit(limit).all()
    return documents
