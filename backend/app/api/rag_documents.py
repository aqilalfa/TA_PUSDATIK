"""
RAG Document File Serving API
Endpoint terpisah untuk serve PDF dan chunk lookup (digunakan oleh citation popup).
Prefix: /api/rag/documents

Mendukung dua mode lookup berdasarkan parameter {doc_id}:
- UUID string (dokumen baru via document_manager): match ke Document.doc_id
- Integer string (dokumen lama / legacy): match ke Document.id (integer PK)
"""

import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.db_models import Document, Chunk

router = APIRouter(prefix="/api/rag/documents", tags=["RAG Documents"])


def _find_document(doc_id_param: str, db: Session) -> Document:
    """
    Temukan dokumen dari parameter yang bisa berupa:
    1. UUID string  → cari di Document.doc_id
    2. Integer string → cari di Document.id (primary key, untuk dokumen legacy)
    Raise 404 jika tidak ditemukan.
    """
    # Coba sebagai UUID / string doc_id terlebih dulu
    document = db.query(Document).filter(Document.doc_id == doc_id_param).first()
    if document:
        return document

    # Fallback: coba parse sebagai integer (dokumen lama yang belum punya UUID)
    try:
        int_id = int(doc_id_param)
        document = db.query(Document).filter(Document.id == int_id).first()
        if document:
            return document
    except ValueError:
        pass  # Bukan integer, tidak perlu fallback

    raise HTTPException(status_code=404, detail="Document not found")


@router.get("/by-doc-id/{doc_id}/file")
def serve_document_file(doc_id: str, db: Session = Depends(get_db)):
    """
    Serve the original PDF file for a document.
    Mendukung doc_id UUID (baru) maupun integer ID (legacy).
    """
    document = _find_document(doc_id, db)

    file_path = document.file_path or document.original_path
    if not file_path or not Path(file_path).exists():
        raise HTTPException(
            status_code=404,
            detail=f"File not found on disk (path: {file_path!r})"
        )

    return FileResponse(
        path=file_path,
        media_type="application/pdf",
        filename=document.original_filename or document.filename,
    )


@router.get("/by-doc-id/{doc_id}/chunks/{chunk_index}")
def get_chunk_by_index(doc_id: str, chunk_index: int, db: Session = Depends(get_db)):
    """
    Get a single chunk by document identifier and chunk_index.
    Mendukung doc_id UUID (baru) maupun integer ID (legacy).
    Digunakan oleh CitationPopup untuk menampilkan preview teks chunk.
    """
    document = _find_document(doc_id, db)

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
        "doc_id": document.doc_id or str(document.id),  # integer fallback
        "doc_type": document.doc_type,
    }
