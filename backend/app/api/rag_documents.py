"""
RAG Document File Serving API
Endpoint terpisah untuk serve PDF dan chunk lookup (digunakan oleh citation popup).
Prefix: /api/rag/documents

Mendukung dua mode lookup berdasarkan parameter {doc_id}:
- UUID string (dokumen baru via document_manager): match ke Document.doc_id
- Integer string (dokumen lama / legacy): match ke Document.id (integer PK)
"""

import json
import os
from pathlib import Path
from loguru import logger

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth_dependencies import get_current_user
from app.models.db_models import Document, Chunk
from app.core.rag.access_control import user_can_access_metadata

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


def _document_access_metadata(document: Document) -> dict:
    if not document.doc_metadata:
        return {}
    try:
        parsed = json.loads(document.doc_metadata)
        return parsed.get("security", parsed) if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def _resolve_real_path(stored_path: str | None) -> Path | None:
    """
    Resolve absolute path from DB string.
    Works transparently inside Docker (/app/data) and local Dev.
    """
    if not stored_path:
        return None
        
    # 1. Coba path yang persis ada di database (selalu berhasil di Docker)
    p = Path(stored_path)
    if p.exists():
        return p
        
    # 2. Jika gagal dan path adalah /app/data/... (artinya jalan di lokal OS), 
    # terjemahkan ke direktori proyek lokal
    if stored_path.startswith("/app/data/"):
        local_backend_dir = Path(__file__).resolve().parent.parent.parent
        # local_backend_dir == .../backend
        translated = local_backend_dir / "data" / stored_path[10:] 
        if translated.exists():
            return translated

    # 3. Handle legacy absolute Windows paths mapped to docker
    # e.g. D:\aqil\pusdatik\data\documents\... -> /app/data/documents/...
    if "\\" in stored_path and "data\\documents" in stored_path.lower():
        # Extrak bagian setelah data\documents
        try:
            parts = stored_path.lower().split("data\\documents\\")
            if len(parts) == 2:
                # Reconstruct path inside docker
                relative_part = parts[1].replace("\\", "/")
                docker_path = Path("/app/data/documents") / relative_part
                logger.warning(f"[_resolve_real_path] checking Docker path: {docker_path}")
                if docker_path.exists():
                    return docker_path
        except Exception as e:
            logger.warning(f"[_resolve_real_path] exception parsing docker path: {e}")

    # 4. Fallback: Cari nama file-nya saja di direktori uploads atau documents
    filename = Path(stored_path.replace("\\", "/")).name
    
    # Check uploads dengan suffix/akhiran file name jika ada UUID prefix
    uploads_dir = Path(__file__).resolve().parent.parent.parent / "data" / "uploads"
    fallback_exact = uploads_dir / filename
    if fallback_exact.exists():
        return fallback_exact
        
    # Search inside uploads_dir for files ending with our filename
    # e.g., 8bd71bb1_Permenpan_RB_Nomor_59_Tahun_2020.pdf matching "Permenpan RB Nomor 59 Tahun 2020.pdf"
    if uploads_dir.exists():
        # Clean filename for substring match (replace spaces with underscores if needed)
        clean_name = filename.replace(" ", "_").lower()
        for f in uploads_dir.iterdir():
            if f.is_file():
                if filename.lower() in f.name.lower() or clean_name in f.name.lower():
                    return f

    # Check documents (recursive if possible, but for safety check common subdirs)
    docs_dir = Path(__file__).resolve().parent.parent.parent.parent / "data" / "documents"
    for subdir in ["peraturan", "audit", "pedoman", "lainnya", ""]:
        sub_fallback = docs_dir / subdir / filename
        if sub_fallback.exists():
            return sub_fallback
            
    # Try one level up (if running locally out of docker)
    return None

@router.get("/by-doc-id/{doc_id}/file")
def serve_document_file(
    doc_id: str,
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    """
    Serve the original PDF file for a document.
    Mendukung doc_id UUID (baru) maupun integer ID (legacy).
    """
    document = _find_document(doc_id, db)
    if not user_can_access_metadata(_document_access_metadata(document), _user):
        raise HTTPException(status_code=403, detail="Document access denied")

    real_path = _resolve_real_path(document.file_path) or _resolve_real_path(document.original_path)
    
    if not real_path:
        raise HTTPException(
            status_code=404,
            detail=f"File not found on disk (path: {document.file_path or document.original_path!r})"
        )

    return FileResponse(
        path=str(real_path),
        media_type="application/pdf",
        filename=document.original_filename or document.filename,
    )


@router.get("/by-doc-id/{doc_id}/chunks/{chunk_index}")
def get_chunk_by_index(
    doc_id: str,
    chunk_index: int,
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    """
    Get a single chunk by document identifier and chunk_index.
    Mendukung doc_id UUID (baru) maupun integer ID (legacy).
    Digunakan oleh CitationPopup untuk menampilkan preview teks chunk.
    """
    document = _find_document(doc_id, db)
    if not user_can_access_metadata(_document_access_metadata(document), _user):
        raise HTTPException(status_code=403, detail="Document access denied")

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
