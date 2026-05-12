"""
Document Management API Router
"""

from fastapi import APIRouter, HTTPException, UploadFile, File, Query
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from loguru import logger
from app.config import settings

router = APIRouter(prefix="/api/documents", tags=["Documents"])


class DocumentResponse(BaseModel):
    doc_id: str
    filename: str
    document_title: Optional[str] = None
    doc_type: Optional[str] = None
    file_size: int = 0
    chunk_count: int = 0
    status: str
    created_at: Optional[str] = None
    processed_at: Optional[str] = None


class ChunkResponse(BaseModel):
    id: int
    chunk_index: int
    text: str
    raw_text: Optional[str] = None
    context_header: Optional[str] = None
    hierarchy: Optional[str] = None
    bab: Optional[str] = None
    bagian: Optional[str] = None
    pasal: Optional[str] = None
    ayat: Optional[str] = None
    chunk_part: Optional[int] = None
    chunk_parts_total: Optional[int] = None
    is_parent: bool = False
    is_indexed: bool = False


class PreviewResponse(BaseModel):
    doc_id: str
    document_title: str
    doc_type: str
    total_chunks: int
    chunks: List[Dict[str, Any]]
    has_more: bool = False


class UploadResponse(BaseModel):
    doc_id: str
    filename: str
    file_size: int
    status: str


class IndexResponse(BaseModel):
    doc_id: str
    chunks_indexed: int
    status: str


class DeleteResponse(BaseModel):
    doc_id: str
    deleted_chunks: int
    status: str


class ChunkUpdateRequest(BaseModel):
    text: str


class MessageResponse(BaseModel):
    message: str
    success: bool = True


from fastapi import APIRouter, HTTPException, UploadFile, File, Query, Depends

def get_manager():
    from app.core.ingestion.document_manager import get_document_manager
    return get_document_manager()

@router.post("/upload", response_model=UploadResponse)
async def upload_document(
    file: UploadFile = File(...), 
    manager=Depends(get_manager)
):
    filename = file.filename or "document.pdf"
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Hanya file PDF yang didukung")
    try:
        content = await file.read()
        result = manager.upload_file(content, filename)
        return UploadResponse(**result)
    except ValueError as e:
        raise HTTPException(400, str(e))

@router.post("/{doc_id}/preview", response_model=PreviewResponse)
async def preview_chunks(doc_id: str, manager=Depends(get_manager)):
    try:
        result = manager.preview_chunks(doc_id)
        return PreviewResponse(**result)
    except ValueError as e:
        raise HTTPException(404, str(e))

@router.post("/{doc_id}/save", response_model=IndexResponse)
async def save_document(doc_id: str, manager=Depends(get_manager)):
    try:
        result = manager.index_document(doc_id)
        return IndexResponse(**result)
    except ValueError as e:
        raise HTTPException(404, str(e))

@router.get("", response_model=List[DocumentResponse])
async def list_documents(manager=Depends(get_manager)):
    return [DocumentResponse(**d) for d in manager.list_documents()]

@router.get("/{doc_id}")
async def get_document(doc_id: str, manager=Depends(get_manager)):
    try:
        return manager.get_document_detail(doc_id)
    except ValueError as e:
        raise HTTPException(404, str(e))

@router.get("/{doc_id}/chunks", response_model=List[ChunkResponse])
async def get_chunks(
    doc_id: str, 
    limit: int = 50, 
    offset: int = 0, 
    manager=Depends(get_manager)
):
    """Get chunks for a document. Handles both SQLite and Qdrant fallback automatically."""
    try:
        chunks = manager.get_chunks(doc_id, limit=limit, offset=offset)
        if not chunks:
            # Check if document exists at all
            if not manager.get_document(doc_id):
                raise HTTPException(404, f"Dokumen tidak ditemukan: {doc_id}")
            return []
            
        return [ChunkResponse(**c) for c in chunks]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get chunks error: {e}")
        raise HTTPException(500, f"Gagal mengambil data chunk: {e}")

@router.put("/chunks/{chunk_id}", response_model=MessageResponse)
async def update_chunk(
    chunk_id: int, 
    request: ChunkUpdateRequest, 
    manager=Depends(get_manager)
):
    if not manager.update_chunk(chunk_id, request.text):
        raise HTTPException(404, f"Chunk {chunk_id} tidak ditemukan")
    return MessageResponse(message=f"Chunk {chunk_id} diperbarui")

@router.delete("/chunks/{chunk_id}", response_model=MessageResponse)
async def delete_single_chunk(chunk_id: int, manager=Depends(get_manager)):
    if not manager.delete_chunk(chunk_id):
        raise HTTPException(404, f"Chunk {chunk_id} tidak ditemukan")
    return MessageResponse(message=f"Chunk {chunk_id} dihapus")

class SyncResponse(BaseModel):
    total_in_qdrant: int
    imported: int
    updated: int = 0
    skipped: int
    status: str
    error: Optional[str] = None
@router.delete("/{doc_id}", response_model=DeleteResponse)
async def delete_document(doc_id: str, manager=Depends(get_manager)):
    try:
        result = manager.delete_document(doc_id)
        return DeleteResponse(**result)
    except ValueError as e:
        raise HTTPException(404, str(e))

@router.post("/sync", response_model=SyncResponse)
async def sync_from_qdrant(manager=Depends(get_manager)):
    """Sync documents from Qdrant to SQLite."""
    try:
        result = manager.sync_from_qdrant()
        return SyncResponse(**result)
    except Exception as e:
        logger.error(f"Sync error: {e}")
        raise HTTPException(500, f"Gagal sync: {e}")
