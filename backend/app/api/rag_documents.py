"""
RAG Document File Serving API
Endpoint terpisah untuk serve PDF dan chunk lookup (digunakan oleh citation popup).
Prefix: /api/rag/documents
"""

import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.db_models import Document, Chunk

router = APIRouter(prefix="/api/rag/documents", tags=["RAG Documents"])


@router.get("/by-doc-id/{doc_id}/file")
def serve_document_file(doc_id: str, db: Session = Depends(get_db)):
    """Serve the original PDF file for a document by its doc_id (UUID)."""
    document = db.query(Document).filter(Document.doc_id == doc_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    file_path = document.file_path or document.original_path
    if not file_path or not Path(file_path).exists():
        raise HTTPException(status_code=404, detail="File not found on disk")

    return FileResponse(
        path=file_path,
        media_type="application/pdf",
        filename=document.original_filename or document.filename,
    )


@router.get("/by-doc-id/{doc_id}/chunks/{chunk_index}")
def get_chunk_by_index(doc_id: str, chunk_index: int, db: Session = Depends(get_db)):
    """
    Get a single chunk by document doc_id and chunk_index.
    Digunakan oleh citation popup untuk menampilkan preview teks chunk.
    """
    document = db.query(Document).filter(Document.doc_id == doc_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    chunk = (
        db.query(Chunk)
        .filter(
            Chunk.document_id == document.id,
            Chunk.chunk_index == chunk_index,
        )
        .first()
    )

    if not chunk:
        raise HTTPException(status_code=404, detail="Chunk not found")

    meta: dict = {}
    if chunk.chunk_metadata:
        try:
            meta = json.loads(chunk.chunk_metadata)
        except Exception:
            pass

    return {
        "chunk_index": chunk.chunk_index,
        "text": chunk.chunk_text,
        "pasal": meta.get("pasal"),
        "bab": meta.get("bab"),
        "context_header": meta.get("context_header"),
        "document_title": document.document_title or document.filename,
        "doc_id": document.doc_id,
        "doc_type": document.doc_type,
    }
