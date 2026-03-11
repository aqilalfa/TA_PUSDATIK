"""
Document Management API Router
"""

from fastapi import APIRouter, HTTPException, UploadFile, File, Query
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from loguru import logger

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
    bab: Optional[str] = None
    bagian: Optional[str] = None
    pasal: Optional[str] = None
    ayat: Optional[str] = None
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


def get_manager():
    from app.core.ingestion.document_manager import get_document_manager

    return get_document_manager()


@router.post("/upload", response_model=UploadResponse)
async def upload_document(file: UploadFile = File(...)):
    filename = file.filename or "document.pdf"
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Hanya file PDF yang didukung")
    try:
        content = await file.read()
        manager = get_manager()
        result = manager.upload_file(content, filename)
        logger.info(f"Uploaded: {result['doc_id']} - {filename}")
        return UploadResponse(**result)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        logger.error(f"Upload error: {e}")
        raise HTTPException(500, f"Gagal mengupload: {e}")


@router.post("/{doc_id}/preview", response_model=PreviewResponse)
async def preview_chunks(doc_id: str):
    try:
        manager = get_manager()
        result = manager.preview_chunks(doc_id)
        logger.info(f"Preview: {doc_id} - {result['total_chunks']} chunks")
        return PreviewResponse(**result)
    except ValueError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        logger.error(f"Preview error: {e}")
        raise HTTPException(500, f"Gagal preview: {e}")


@router.post("/{doc_id}/save", response_model=IndexResponse)
async def save_document(doc_id: str):
    try:
        manager = get_manager()
        result = manager.index_document(doc_id)
        logger.info(f"Indexed: {doc_id} - {result['chunks_indexed']} chunks")
        return IndexResponse(**result)
    except ValueError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        logger.error(f"Index error: {e}")
        raise HTTPException(500, f"Gagal index: {e}")


@router.get("", response_model=List[DocumentResponse])
async def list_documents():
    try:
        manager = get_manager()
        docs = manager.list_documents()
        return [DocumentResponse(**d) for d in docs]
    except Exception as e:
        logger.error(f"List error: {e}")
        raise HTTPException(500, f"Gagal list: {e}")


@router.get("/{doc_id}")
async def get_document(doc_id: str):
    try:
        manager = get_manager()
        return manager.get_document_detail(doc_id)
    except ValueError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        logger.error(f"Get doc error: {e}")
        raise HTTPException(500, f"Gagal get: {e}")


@router.get("/{doc_id}/chunks", response_model=List[ChunkResponse])
async def get_chunks(doc_id: str, limit: int = 50, offset: int = 0):
    try:
        from app.core.database import get_chunks, get_document
        import httpx

        doc = get_document(doc_id)
        if not doc:
            raise HTTPException(404, f"Dokumen tidak ditemukan: {doc_id}")

        # First try to get from SQLite
        chunks = get_chunks(doc_id, limit=limit, offset=offset)

        # If no chunks in SQLite and doc is legacy (indexed), get from Qdrant
        if not chunks and doc.get("status") == "indexed":
            document_title = doc.get("document_title", "")
            if document_title:
                try:
                    # Query Qdrant by document_title
                    qdrant_url = "http://localhost:6333"
                    collection_name = "document_chunks"

                    resp = httpx.post(
                        f"{qdrant_url}/collections/{collection_name}/points/scroll",
                        json={
                            "filter": {
                                "must": [
                                    {
                                        "key": "document_title",
                                        "match": {"value": document_title},
                                    }
                                ]
                            },
                            "limit": limit,
                            "offset": offset,
                            "with_payload": True,
                            "with_vector": False,
                        },
                        timeout=30,
                    )

                    if resp.status_code == 200:
                        points = resp.json().get("result", {}).get("points", [])

                        # Sort points by chunk_index from payload (if available)
                        # This ensures correct ordering even though Qdrant doesn't guarantee order
                        sorted_points = sorted(
                            points,
                            key=lambda p: p.get("payload", {}).get(
                                "chunk_index", 999999
                            ),
                        )

                        return [
                            ChunkResponse(
                                id=i,
                                chunk_index=p.get("payload", {}).get("chunk_index", i),
                                text=p.get("payload", {}).get("text", ""),
                                raw_text=p.get("payload", {}).get("raw_text", ""),
                                context_header=p.get("payload", {}).get(
                                    "context_header", ""
                                ),
                                bab=p.get("payload", {}).get("bab", ""),
                                bagian=p.get("payload", {}).get("bagian", ""),
                                pasal=p.get("payload", {}).get("pasal", ""),
                                ayat=p.get("payload", {}).get("ayat", ""),
                                is_parent=bool(p.get("payload", {}).get("is_parent")),
                                is_indexed=True,
                            )
                            for i, p in enumerate(sorted_points)
                        ]
                except Exception as e:
                    logger.warning(f"Qdrant query failed: {e}")

        return [
            ChunkResponse(
                id=c["id"],
                chunk_index=c["chunk_index"],
                text=c["text"],
                raw_text=c.get("raw_text"),
                context_header=c.get("context_header"),
                bab=c.get("bab"),
                bagian=c.get("bagian"),
                pasal=c.get("pasal"),
                ayat=c.get("ayat"),
                is_parent=bool(c.get("is_parent")),
                is_indexed=bool(c.get("is_indexed")),
            )
            for c in chunks
        ]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get chunks error: {e}")
        raise HTTPException(500, f"Gagal get chunks: {e}")


@router.put("/chunks/{chunk_id}", response_model=MessageResponse)
async def update_chunk(chunk_id: int, request: ChunkUpdateRequest):
    try:
        from app.core.database import update_chunk

        success = update_chunk(chunk_id, request.text)
        if not success:
            raise HTTPException(404, f"Chunk tidak ditemukan: {chunk_id}")
        return MessageResponse(message=f"Chunk {chunk_id} diperbarui")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update chunk error: {e}")
        raise HTTPException(500, f"Gagal update: {e}")


@router.delete("/chunks/{chunk_id}", response_model=MessageResponse)
async def delete_single_chunk(chunk_id: int):
    try:
        from app.core.database import delete_chunk

        success = delete_chunk(chunk_id)
        if not success:
            raise HTTPException(404, f"Chunk tidak ditemukan: {chunk_id}")
        return MessageResponse(message=f"Chunk {chunk_id} dihapus")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete chunk error: {e}")
        raise HTTPException(500, f"Gagal delete: {e}")


@router.delete("/{doc_id}", response_model=DeleteResponse)
async def delete_document(doc_id: str):
    try:
        manager = get_manager()
        result = manager.delete_document(doc_id)
        logger.info(f"Deleted: {doc_id}")
        return DeleteResponse(**result)
    except ValueError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        logger.error(f"Delete error: {e}")
        raise HTTPException(500, f"Gagal delete: {e}")


class SyncResponse(BaseModel):
    total_in_qdrant: int
    imported: int
    skipped: int
    status: str
    error: Optional[str] = None


@router.post("/sync", response_model=SyncResponse)
async def sync_from_qdrant():
    """Sync documents from Qdrant to SQLite.

    Scans existing Qdrant collection and imports document metadata
    to SQLite for display in the document management UI.
    """
    try:
        manager = get_manager()
        result = manager.sync_from_qdrant()
        return SyncResponse(**result)
    except Exception as e:
        logger.error(f"Sync error: {e}")
        raise HTTPException(500, f"Gagal sync: {e}")
