"""
Document Manager - Core logic for document processing
Handles: upload, preview chunking, indexing to Qdrant/BM25, delete
"""

import os
import uuid
import re
import pickle
import time
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

from loguru import logger
from app.config import settings

# Paths
BASE_DIR = Path(__file__).parent.parent.parent
BACKEND_DIR = BASE_DIR.parent
UPLOADS_DIR = BACKEND_DIR / "data" / "uploads"
BM25_PATH = BACKEND_DIR / "data" / "bm25_index.pkl"

# Ensure uploads directory exists
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

# Max file size: 50MB
MAX_FILE_SIZE = 50 * 1024 * 1024


# ============== PDF Extraction ==============


class ExtractionResult:
    """Result of PDF text extraction with metadata"""

    def __init__(
        self,
        text: str = "",
        method: str = "unknown",
        success: bool = False,
        warning: str = None,
        error: str = None,
        stats: dict = None,
    ):
        self.text = text
        self.method = (
            method  # "marker", "marker_cached", "pdfplumber", "pymupdf", "pypdf2"
        )
        self.success = success
        self.warning = warning  # Warning message for user
        self.error = error  # Error message if failed
        self.stats = stats or {}

    def to_dict(self) -> dict:
        return {
            "method": self.method,
            "success": self.success,
            "warning": self.warning,
            "error": self.error,
            "chars": len(self.text),
            "stats": self.stats,
        }


def extract_text_from_pdf(pdf_path: Path, return_details: bool = False):
    """
    Extract text from PDF using Marker (primary) with intelligent fallback.

    Args:
        pdf_path: Path to PDF file
        return_details: If True, return ExtractionResult; otherwise return text string

    Returns:
        str (text) or ExtractionResult depending on return_details
    """
    pdf_path = Path(pdf_path)
    result = ExtractionResult(stats={"file": pdf_path.name})

    # === Try Marker first (best for tables and complex layouts) ===
    marker_error_type = None
    try:
        from app.core.ingestion.marker_converter import (
            marker_converter,
            MarkerConversionError,
            MarkerErrorType,
        )

        if marker_converter.is_available():
            logger.info(f"Ekstraksi dengan Marker: {pdf_path.name}")

            try:
                conversion_result = marker_converter.convert(
                    str(pdf_path), save_output=True
                )

                if (
                    conversion_result.success
                    and len(conversion_result.text.strip()) > 100
                ):
                    result.text = conversion_result.text.strip()
                    result.method = conversion_result.method
                    result.success = True
                    result.warning = conversion_result.warning
                    result.stats.update(conversion_result.stats)

                    logger.success(
                        f"Marker berhasil: {len(result.text):,} chars, "
                        f"method={result.method}"
                    )

                    return result if return_details else result.text
                else:
                    logger.warning(
                        "Marker return text tidak cukup, mencoba fallback..."
                    )
                    marker_error_type = MarkerErrorType.UNKNOWN
            finally:
                # Always unload Marker models to free GPU memory for Ollama
                marker_converter.unload_models()

    except MarkerConversionError as e:
        marker_error_type = e.error_type
        logger.warning(f"Marker gagal ({e.error_type.value}): {str(e)[:100]}")

        # For certain errors, don't use fallback - report to user
        if e.error_type in [
            MarkerErrorType.PDF_CORRUPTED,
            MarkerErrorType.PDF_ENCRYPTED,
        ]:
            result.error = str(e)
            result.method = "marker"
            result.stats["marker_error"] = e.error_type.value

            if return_details:
                return result
            else:
                raise ValueError(f"PDF tidak dapat diproses: {e}")

    except ImportError:
        logger.warning("Marker tidak tersedia, menggunakan fallback")
    except Exception as e:
        logger.warning(f"Marker error: {e}")

    # === Fallback methods ===
    # Set warning about using fallback
    if marker_error_type:
        from app.core.ingestion.marker_converter import MarkerErrorType

        if marker_error_type == MarkerErrorType.VRAM_INSUFFICIENT:
            result.warning = "GPU memory tidak cukup, menggunakan metode alternatif (hasil mungkin kurang optimal untuk tabel)"
        elif marker_error_type == MarkerErrorType.TIMEOUT:
            result.warning = "Konversi timeout, menggunakan metode alternatif"
        else:
            result.warning = "Marker tidak tersedia, menggunakan metode alternatif (tabel mungkin tidak optimal)"

    text = ""

    # Fallback 1: pdfplumber (good for simple layouts)
    try:
        import pdfplumber

        logger.info(f"Fallback ke pdfplumber: {pdf_path.name}")
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n\n"

        if text.strip() and len(text.strip()) > 100:
            result.text = text.strip()
            result.method = "pdfplumber"
            result.success = True
            result.stats["chars"] = len(result.text)
            logger.info(f"pdfplumber berhasil: {len(result.text):,} chars")
            return result if return_details else result.text

    except ImportError:
        pass
    except Exception as e:
        logger.warning(f"pdfplumber gagal: {e}")

    # Fallback 2: PyMuPDF
    try:
        import fitz

        logger.info(f"Fallback ke PyMuPDF: {pdf_path.name}")
        doc = fitz.open(pdf_path)
        text = ""
        for page in doc:
            text += page.get_text() + "\n\n"
        doc.close()

        if text.strip() and len(text.strip()) > 100:
            result.text = text.strip()
            result.method = "pymupdf"
            result.success = True
            result.stats["chars"] = len(result.text)
            logger.info(f"PyMuPDF berhasil: {len(result.text):,} chars")
            return result if return_details else result.text

    except ImportError:
        pass
    except Exception as e:
        logger.warning(f"PyMuPDF gagal: {e}")

    # Fallback 3: PyPDF2 (last resort)
    try:
        from PyPDF2 import PdfReader

        logger.info(f"Fallback ke PyPDF2: {pdf_path.name}")
        reader = PdfReader(pdf_path)
        text = ""
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n\n"

        if text.strip():
            result.text = text.strip()
            result.method = "pypdf2"
            result.success = True
            result.stats["chars"] = len(result.text)
            logger.info(f"PyPDF2 berhasil: {len(result.text):,} chars")
            return result if return_details else result.text

    except ImportError:
        logger.error("Tidak ada library PDF yang tersedia!")
        result.error = "Tidak ada library PDF yang tersedia"
    except Exception as e:
        logger.error(f"PyPDF2 gagal: {e}")
        result.error = f"Semua metode ekstraksi gagal: {e}"

    # All methods failed
    if not result.success:
        result.method = "none"
        if not result.error:
            result.error = "Tidak dapat mengekstrak teks dari PDF"

    return result if return_details else result.text


# ============== Legal Document Splitting ==============


def detect_document_type(filename: str, text: str) -> str:
    """Detect document type from filename and content."""
    filename_lower = filename.lower()
    text_lower = text[:2000].lower()

    if any(
        kw in filename_lower for kw in ["perpres", "pp_", "permen", "peraturan", "se_"]
    ):
        return "peraturan"
    if any(
        kw in text_lower
        for kw in ["peraturan presiden", "peraturan pemerintah", "peraturan menteri"]
    ):
        return "peraturan"
    if any(kw in filename_lower for kw in ["audit", "laporan"]):
        return "audit"
    return "other"


def _bm25_search_text(text: str, metadata: Dict[str, Any]) -> str:
    """Compose BM25 search text from chunk content + structural metadata only.

    Excludes document-level fields (judul_dokumen, filename, doc_type) that are
    identical across all chunks of a document and degrade BM25 IDF scores.
    """
    fields = [
        metadata.get("hierarchy", ""),
        metadata.get("context_header", ""),
        metadata.get("bab", ""),
        metadata.get("bagian", ""),
        metadata.get("pasal", ""),
        metadata.get("ayat", ""),
        text or "",
    ]
    return " ".join(str(v).strip() for v in fields if str(v).strip())


def _tokenize_bm25(text: str) -> List[str]:
    return re.findall(r"\b\w+\b", text.lower())


def extract_pasals(text: str) -> List[Dict]:
    """Extract Pasal structure from legal document."""
    pasals = []

    pasal_pattern = re.compile(
        r"^\s*(?:#+\s*)?(?:\*\*\s*)?Pasal\s+(\d+)\s*(?:\*\*)?\s*(.*?)\s*$",
        re.MULTILINE | re.IGNORECASE,
    )
    matches = list(pasal_pattern.finditer(text))

    if not matches:
        return pasals

    bab_pattern = re.compile(
        r"^BAB\s+([IVXLCDM]+)\s*\n?(.*)$", re.MULTILINE | re.IGNORECASE
    )
    bagian_pattern = re.compile(
        r"^Bagian\s+(\w+)\s*\n?(.*)$", re.MULTILINE | re.IGNORECASE
    )

    current_bab = ""
    current_bagian = ""

    for i, match in enumerate(matches):
        pasal_num = match.group(1)
        inline_content = (match.group(2) or "").strip()
        start = match.end()

        if i + 1 < len(matches):
            end = matches[i + 1].start()
        else:
            end = len(text)

        content = text[start:end].strip()
        if inline_content:
            content = f"{inline_content}\n{content}" if content else inline_content

        # Look for BAB/Bagian before this Pasal
        prefix_text = text[: match.start()]

        bab_matches = list(bab_pattern.finditer(prefix_text))
        if bab_matches:
            last_bab = bab_matches[-1]
            bab_num = last_bab.group(1)
            bab_title = last_bab.group(2).strip() if last_bab.group(2) else ""
            current_bab = f"BAB {bab_num}"
            if bab_title:
                current_bab += f" {bab_title}"

        bagian_matches = list(bagian_pattern.finditer(prefix_text))
        if bagian_matches:
            last_bagian = bagian_matches[-1]
            current_bagian = f"Bagian {last_bagian.group(1)}"

        if content:
            pasals.append(
                {
                    "pasal_num": pasal_num,
                    "content": content,
                    "bab": current_bab,
                    "bagian": current_bagian,
                }
            )

    return pasals


def extract_ayats(pasal_content: str) -> List[Dict]:
    """Extract Ayat-level chunks from Pasal content."""
    ayats = []
    ayat_pattern = re.compile(r"^\((\d+)\)\s*", re.MULTILINE)
    matches = list(ayat_pattern.finditer(pasal_content))

    if not matches:
        return [{"ayat_num": "", "content": pasal_content.strip()}]

    # Check for preamble before first ayat
    first_start = matches[0].start()
    if first_start > 20:
        preamble = pasal_content[:first_start].strip()
        if preamble:
            ayats.append({"ayat_num": "", "content": preamble})

    for i, match in enumerate(matches):
        ayat_num = match.group(1)
        start = match.start()

        if i + 1 < len(matches):
            end = matches[i + 1].start()
        else:
            end = len(pasal_content)

        content = pasal_content[start:end].strip()
        ayats.append({"ayat_num": ayat_num, "content": content})

    return ayats


def split_legal_document(
    text: str,
    doc_title: str,
    filename: str,
    max_chunk_size: int = settings.CHUNK_SIZE,
) -> List[Dict]:
    """Split legal document into chunks based on Pasal/Ayat structure."""

    doc_type = detect_document_type(filename, text)
    chunks = []

    # Try Pasal-based splitting for regulations
    if doc_type == "peraturan":
        pasals = extract_pasals(text)

        if pasals:
            for pasal in pasals:
                pasal_num = pasal["pasal_num"]
                pasal_content = pasal["content"]
                bab = pasal["bab"]
                bagian = pasal["bagian"]

                # Build context header
                parts = [doc_title]
                if bab:
                    parts.append(bab)
                if bagian:
                    parts.append(bagian)
                parts.append(f"Pasal {pasal_num}")

                # Extract ayats
                ayats = extract_ayats(pasal_content)

                # Full Pasal text for parent reference
                full_pasal = f"Pasal {pasal_num}\n{pasal_content}"

                for ayat in ayats:
                    ayat_num = ayat["ayat_num"]
                    ayat_content = ayat["content"]

                    # Context header
                    header_parts = parts.copy()
                    if ayat_num:
                        header_parts.append(f"Ayat ({ayat_num})")
                    context_header = " > ".join(header_parts)

                    chunk_text = f"{context_header}: {ayat_content}"

                    chunks.append(
                        {
                            "text": chunk_text,
                            "raw_text": ayat_content,
                            "context_header": context_header,
                            "document_title": doc_title,
                            "filename": filename,
                            "doc_type": doc_type,
                            "bab": bab,
                            "bagian": bagian,
                            "pasal": f"Pasal {pasal_num}",
                            "ayat": ayat_num,
                            "parent_pasal_text": full_pasal if ayat_num else "",
                            "is_parent": not bool(ayat_num),
                        }
                    )

            if chunks:
                return chunks

    # Fallback: split by paragraphs
    paragraphs = re.split(r"\n\n+", text)
    current_chunk = []
    current_size = 0
    chunk_index = 0

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        para_size = len(para)

        if current_size + para_size > max_chunk_size and current_chunk:
            chunk_text = f"{doc_title}: " + "\n\n".join(current_chunk)
            chunks.append(
                {
                    "text": chunk_text,
                    "raw_text": "\n\n".join(current_chunk),
                    "context_header": doc_title,
                    "document_title": doc_title,
                    "filename": filename,
                    "doc_type": doc_type,
                    "bab": "",
                    "bagian": "",
                    "pasal": "",
                    "ayat": "",
                    "parent_pasal_text": "",
                    "is_parent": True,
                    "chunk_index": chunk_index,
                }
            )
            chunk_index += 1
            current_chunk = []
            current_size = 0

        current_chunk.append(para)
        current_size += para_size

    if current_chunk:
        chunk_text = f"{doc_title}: " + "\n\n".join(current_chunk)
        chunks.append(
            {
                "text": chunk_text,
                "raw_text": "\n\n".join(current_chunk),
                "context_header": doc_title,
                "document_title": doc_title,
                "filename": filename,
                "doc_type": doc_type,
                "bab": "",
                "bagian": "",
                "pasal": "",
                "ayat": "",
                "parent_pasal_text": "",
                "is_parent": True,
                "chunk_index": chunk_index,
            }
        )

    return chunks


# ============== Document Manager Class ==============


class DocumentManager:
    """Manages document upload, processing, and indexing.

    Phase 1 refactor: Database operations menggunakan SQLAlchemy ORM
    menggantikan raw sqlite3 dari core/database.py.
    Interface publik (argumen + return format) tidak berubah.
    """

    def __init__(self):
        # Lazy load embedding model
        self._embedding_model = None
        self._tokenizer = None

    # ── Private DB helper ─────────────────────────────────────────
    def _get_db(self):
        """Buat session baru per operasi. Caller wajib close()."""
        from app.database import SessionLocal
        return SessionLocal()

    @staticmethod
    def _doc_to_dict(doc) -> Dict[str, Any]:
        """Convert ORM Document object ke dict format yang kompatibel dengan callers."""
        if doc is None:
            return {}
        return {
            "id": doc.id,
            "doc_id": doc.doc_id or str(doc.id),
            "filename": doc.original_filename or doc.filename or "",
            "original_filename": doc.original_filename or doc.filename or "",
            "document_title": doc.document_title or doc.filename or "",
            "doc_type": doc.doc_type or "other",
            "file_size": doc.file_size or 0,
            "file_path": doc.file_path or doc.original_path or "",
            "status": doc.status or "uploaded",
            "chunk_count": doc.chunk_count or 0,
            "created_at": str(doc.uploaded_at) if doc.uploaded_at else "",
            "processed_at": str(doc.processed_at) if doc.processed_at else None,
            "error_message": doc.error_message,
        }

    @staticmethod
    def _chunk_to_dict(chunk, chunk_metadata: dict = None) -> Dict[str, Any]:
        """Convert ORM Chunk object ke dict format yang kompatibel dengan callers."""
        meta = chunk_metadata or {}
        if not meta and chunk.chunk_metadata:
            try:
                import json
                meta = json.loads(chunk.chunk_metadata)
            except Exception:
                meta = {}
        return {
            "id": chunk.id,
            "chunk_index": chunk.chunk_index,
            "text": chunk.chunk_text or "",
            "raw_text": chunk.chunk_text or "",
            "context_header": meta.get("context_header", ""),
            "document_title": meta.get("document_title", ""),
            "hierarchy": meta.get("hierarchy", ""),
            "filename": meta.get("filename", ""),
            "doc_type": meta.get("doc_type", ""),
            "bab": str(meta.get("bab", "")),
            "bagian": str(meta.get("bagian", "")),
            "pasal": str(meta.get("pasal", "")),
            "ayat": str(meta.get("ayat", "")),
            "chunk_part": meta.get("chunk_part"),
            "chunk_parts_total": meta.get("chunk_parts_total"),
            "parent_pasal_text": meta.get("parent_pasal_text", ""),
            "is_parent": meta.get("is_parent", False),
            "chunk_type": chunk.chunk_type or meta.get("chunk_type", "text"),
            "section": meta.get("section", ""),
            "table_context": meta.get("table_context", ""),
            "original_table": meta.get("original_table", ""),
            "is_indexed": True,
        }

    # ── Document CRUD (ORM) ───────────────────────────────────────
    def create_document(
        self,
        doc_id: str,
        filename: str,
        original_filename: str,
        file_size: int,
        file_path: str,
    ) -> Dict[str, Any]:
        """Create a new document record via ORM."""
        from app.models.db_models import Document
        document_title = Path(original_filename).stem.replace("_", " ").replace("-", " ")

        db = self._get_db()
        try:
            doc = Document(
                doc_id=doc_id,
                filename=filename,
                original_filename=original_filename,
                original_path=file_path,
                file_path=file_path,
                document_title=document_title,
                file_size=file_size,
                status="uploaded",
                chunk_count=0,
            )
            db.add(doc)
            db.commit()
            db.refresh(doc)
            return self._doc_to_dict(doc)
        except Exception as e:
            db.rollback()
            logger.error(f"create_document ORM error: {e}")
            raise
        finally:
            db.close()

    def get_document(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """Get document by doc_id (UUID text) atau integer id."""
        from app.models.db_models import Document
        db = self._get_db()
        try:
            doc = db.query(Document).filter(Document.doc_id == doc_id).first()
            if not doc and doc_id.isdigit():
                doc = db.query(Document).filter(Document.id == int(doc_id)).first()
            return self._doc_to_dict(doc) if doc else None
        except Exception as e:
            logger.warning(f"get_document ORM error: {e}")
            return None
        finally:
            db.close()

    def get_all_documents(self) -> List[Dict[str, Any]]:
        """Get all documents dengan live chunk counts."""
        from app.models.db_models import Document
        from sqlalchemy import func
        from app.models.db_models import Chunk
        db = self._get_db()
        try:
            docs = db.query(Document).order_by(Document.uploaded_at.desc()).all()
            result = []
            for doc in docs:
                d = self._doc_to_dict(doc)
                # Hitung chunk count dari DB
                count = db.query(func.count(Chunk.id)).filter(
                    Chunk.document_id == doc.id
                ).scalar() or 0
                d["chunk_count"] = count
                # Coba dapat file_size dari disk jika 0
                if d["file_size"] == 0 and d["file_path"]:
                    try:
                        p = Path(d["file_path"])
                        if p.exists():
                            d["file_size"] = p.stat().st_size
                    except Exception:
                        pass
                result.append(d)
            return result
        except Exception as e:
            logger.warning(f"get_all_documents ORM error: {e}")
            return []
        finally:
            db.close()

    def update_document(self, doc_id: str, **kwargs) -> bool:
        """Update document fields by doc_id via ORM."""
        from app.models.db_models import Document

        def _normalize_value(column: str, value: Any) -> Any:
            """Normalize incoming values to match ORM column types."""
            if column == "processed_at" and isinstance(value, str):
                try:
                    return datetime.fromisoformat(value)
                except ValueError:
                    logger.warning(
                        "update_document: invalid processed_at format for doc_id={} value={}",
                        doc_id,
                        value,
                    )
                    return value
            return value

        # Map legacy field names ke ORM column names
        field_mapping = {
            "file_path": "file_path",
            "original_filename": "original_filename",
            "processed_at": "processed_at",
            "status": "status",
            "chunk_count": "chunk_count",
            "error_message": "error_message",
            "document_title": "document_title",
        }
        db = self._get_db()
        try:
            doc = db.query(Document).filter(Document.doc_id == doc_id).first()
            if not doc and doc_id.isdigit():
                doc = db.query(Document).filter(Document.id == int(doc_id)).first()
            if not doc:
                logger.warning(f"update_document: doc not found for doc_id={doc_id}")
                return False
            for k, v in kwargs.items():
                orm_col = field_mapping.get(k, k)
                if hasattr(doc, orm_col):
                    setattr(doc, orm_col, _normalize_value(orm_col, v))
            db.commit()
            return True
        except Exception as e:
            db.rollback()
            logger.warning(f"update_document ORM error: {e}")
            return False
        finally:
            db.close()

    def db_delete_document(self, doc_id: str) -> bool:
        """Delete document and its chunks via ORM."""
        from app.models.db_models import Document
        db = self._get_db()
        try:
            doc = db.query(Document).filter(Document.doc_id == doc_id).first()
            if not doc and doc_id.isdigit():
                doc = db.query(Document).filter(Document.id == int(doc_id)).first()
            if not doc:
                logger.warning(f"db_delete_document: doc not found: {doc_id}")
                return False
            db.delete(doc)  # cascade delete chunks via relationship
            db.commit()
            return True
        except Exception as e:
            db.rollback()
            logger.error(f"db_delete_document ORM error: {e}")
            return False
        finally:
            db.close()

    # ── Chunk CRUD (ORM) ──────────────────────────────────────────
    def save_chunks(self, doc_id: str, chunks: List[Dict[str, Any]]) -> int:
        """Save chunks for a document via ORM."""
        from app.models.db_models import Document, Chunk
        import json as _json
        db = self._get_db()
        try:
            doc = db.query(Document).filter(Document.doc_id == doc_id).first()
            if not doc and doc_id.isdigit():
                doc = db.query(Document).filter(Document.id == int(doc_id)).first()
            if not doc:
                raise ValueError(f"Document not found: {doc_id}")

            # Hapus chunks lama
            db.query(Chunk).filter(Chunk.document_id == doc.id).delete()

            # Insert chunks baru
            for i, chunk in enumerate(chunks):
                meta = {
                    "context_header": chunk.get("context_header", ""),
                    "hierarchy": chunk.get("hierarchy", ""),
                    "document_title": chunk.get("document_title", ""),
                    "filename": chunk.get("filename", ""),
                    "doc_type": chunk.get("doc_type", ""),
                    "bab": chunk.get("bab", ""),
                    "bagian": chunk.get("bagian", ""),
                    "pasal": chunk.get("pasal", ""),
                    "ayat": chunk.get("ayat", ""),
                    "parent_pasal_text": chunk.get("parent_pasal_text", ""),
                    "is_parent": chunk.get("is_parent", False),
                    "section": chunk.get("section", ""),
                    "table_context": chunk.get("table_context", ""),
                    "original_table": chunk.get("original_table", ""),
                    "chunk_type": chunk.get("chunk_type", "text"),
                    "chunk_part": chunk.get("chunk_part"),
                    "chunk_parts_total": chunk.get("chunk_parts_total"),
                }
                new_chunk = Chunk(
                    document_id=doc.id,
                    chunk_index=i,
                    chunk_text=chunk.get("text", ""),
                    chunk_metadata=_json.dumps(meta),
                    chunk_type=chunk.get("chunk_type", "text"),
                )
                db.add(new_chunk)

            # Update chunk count di document
            doc.chunk_count = len(chunks)
            db.commit()
            return len(chunks)
        except Exception as e:
            db.rollback()
            logger.error(f"save_chunks ORM error: {e}")
            raise
        finally:
            db.close()

    def get_chunks(self, doc_id: str, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """Get chunks for a document via ORM."""
        from app.models.db_models import Document, Chunk
        db = self._get_db()
        try:
            doc = db.query(Document).filter(Document.doc_id == doc_id).first()
            if not doc and doc_id.isdigit():
                doc = db.query(Document).filter(Document.id == int(doc_id)).first()
            if not doc:
                return []
            chunks = (
                db.query(Chunk)
                .filter(Chunk.document_id == doc.id)
                .order_by(Chunk.chunk_index)
                .limit(limit)
                .offset(offset)
                .all()
            )
            return [self._chunk_to_dict(c) for c in chunks]
        except Exception as e:
            logger.warning(f"get_chunks ORM error: {e}")
            return []
        finally:
            db.close()

    def get_chunk_count(self, doc_id: str) -> int:
        """Get chunk count for a document via ORM."""
        from app.models.db_models import Document, Chunk
        from sqlalchemy import func
        db = self._get_db()
        try:
            doc = db.query(Document).filter(Document.doc_id == doc_id).first()
            if not doc and doc_id.isdigit():
                doc = db.query(Document).filter(Document.id == int(doc_id)).first()
            if not doc:
                return 0
            return db.query(func.count(Chunk.id)).filter(Chunk.document_id == doc.id).scalar() or 0
        except Exception as e:
            logger.warning(f"get_chunk_count ORM error: {e}")
            return 0
        finally:
            db.close()

    def mark_chunks_indexed(self, doc_id: str) -> int:
        """Mark semua chunks dokumen sebagai indexed. ORM: no-op, return chunk count."""
        return self.get_chunk_count(doc_id)

    def update_chunk(self, chunk_id: int, text: str) -> bool:
        """Update teks satu chunk via ORM."""
        from app.models.db_models import Chunk, Document
        target_doc_id = None
        db = self._get_db()
        try:
            chunk = db.query(Chunk).filter(Chunk.id == chunk_id).first()
            if not chunk:
                return False

            doc = db.query(Document).filter(Document.id == chunk.document_id).first()
            if not doc:
                return False

            target_doc_id = doc.doc_id or str(doc.id)
            chunk.chunk_text = text
            db.commit()
        except Exception as e:
            db.rollback()
            logger.warning(f"update_chunk ORM error: {e}")
            return False
        finally:
            db.close()

        # Re-sync retrieval indexes so updated chunk is immediately reflected in chat results.
        self.index_document(target_doc_id)
        return True

    def delete_chunk(self, chunk_id: int) -> bool:
        """Delete satu chunk via ORM."""
        from app.models.db_models import Chunk, Document
        target_doc_id = None
        db = self._get_db()
        try:
            chunk = db.query(Chunk).filter(Chunk.id == chunk_id).first()
            if not chunk:
                return False

            doc = db.query(Document).filter(Document.id == chunk.document_id).first()
            if not doc:
                return False

            target_doc_id = doc.doc_id or str(doc.id)
            db.delete(chunk)
            db.commit()
        except Exception as e:
            db.rollback()
            logger.warning(f"delete_chunk ORM error: {e}")
            return False
        finally:
            db.close()

        # Keep vector index in sync after chunk deletion.
        if self.get_chunk_count(target_doc_id) > 0:
            self.index_document(target_doc_id)
        else:
            self._delete_qdrant_points_by_doc_id(target_doc_id)
            self.update_document(target_doc_id, status="uploaded", chunk_count=0)
            self._rebuild_bm25_index()
        return True

    # Lazy load embedding model


    def upload_file(
        self, file_content: bytes, original_filename: str
    ) -> Dict[str, Any]:
        """Save uploaded file and create document record."""

        # Validate file size
        if len(file_content) > MAX_FILE_SIZE:
            raise ValueError(
                f"File too large. Maximum size is {MAX_FILE_SIZE // 1024 // 1024}MB"
            )

        # Validate file type
        if not original_filename.lower().endswith(".pdf"):
            raise ValueError("Only PDF files are supported")

        # Generate unique ID and filename
        doc_id = str(uuid.uuid4())[:8]
        safe_filename = re.sub(r"[^\w\-.]", "_", original_filename)
        stored_filename = f"{doc_id}_{safe_filename}"
        file_path = UPLOADS_DIR / stored_filename

        # Save file
        with open(file_path, "wb") as f:
            f.write(file_content)

        # Create database record
        doc = self.create_document(
            doc_id=doc_id,
            filename=stored_filename,
            original_filename=original_filename,
            file_size=len(file_content),
            file_path=str(file_path),
        )

        logger.info(f"Uploaded document: {doc_id} - {original_filename}")

        return {
            "doc_id": doc_id,
            "filename": original_filename,
            "file_size": len(file_content),
            "status": "uploaded",
        }

    def _apply_figure_pipeline(
        self,
        pdf_path,
        chunks,
        doc_title,
        filename,
        doc_type,
    ):
        """Run figure extraction pipeline; append figure chunks to existing list.

        Idempotent via figures.json cache.
        """
        from app.core.ingestion.figures import process_figures
        from app.core.ingestion.structured_chunker import (
            inject_figure_summaries,
            make_figure_chunks,
        )
        from pathlib import Path as _Path

        pdf_path = _Path(pdf_path)

        # Locate existing Marker markdown without importing pdf_processor (avoids PaddleOCR double-init)
        def _find_marker_md(stem: str) -> _Path | None:
            from app.core.ingestion import marker_converter as _mc
            output_dir = _mc.marker_converter.output_dir
            norm = lambda s: "".join(c for c in s.lower() if c.isalnum())
            stem_norm = norm(stem)
            for folder in output_dir.iterdir():
                if not folder.is_dir():
                    continue
                fname = folder.name
                fname_no_hash = fname[9:] if len(fname) > 9 and fname[8] == "_" and all(c in "0123456789abcdefABCDEF" for c in fname[:8]) else fname
                if stem.lower() in fname.lower() or stem_norm in norm(fname) or stem_norm in norm(fname_no_hash):
                    md = folder / f"{fname}.md"
                    if md.exists():
                        return md
                    for md in folder.glob("*.md"):
                        return md
            return None

        md_path = _find_marker_md(_Path(pdf_path).stem) or _find_marker_md(_Path(filename).stem)
        if not md_path:
            logger.warning("Figure pipeline skipped: no Marker markdown found")
            return chunks
        md_path_str = str(md_path)

        md_path = _Path(md_path_str)
        output_dir = _Path(md_path_str).parent
        marker_md = md_path.read_text(encoding="utf-8")

        figures = process_figures(
            pdf_path=pdf_path,
            marker_md=marker_md,
            output_dir=output_dir,
            use_cache=True,
        )

        enriched_md = inject_figure_summaries(marker_md, figures)
        if enriched_md != marker_md:
            md_path.write_text(enriched_md, encoding="utf-8")
            logger.info(f"Updated markdown with figure summaries: {md_path}")

        figure_chunks = make_figure_chunks(
            figures,
            doc_title=doc_title,
            filename=filename,
            doc_type=doc_type,
        )
        logger.info(
            f"Figure pipeline: {len(figures)} figures processed, "
            f"{len(figure_chunks)} figure chunks added"
        )
        return chunks + figure_chunks

    def preview_chunks(self, doc_id: str, use_figure_pipeline: bool = False) -> Dict[str, Any]:
        """Extract and preview chunks without indexing."""

        doc = self.get_document(doc_id)
        if not doc:
            raise ValueError(f"Document not found: {doc_id}")

        file_path = Path(doc["file_path"])
        if not file_path.exists():
            raise ValueError(f"File not found: {file_path}")

        # Extract text with detailed result
        logger.info(f"Extracting text from: {file_path}")
        extraction_result = extract_text_from_pdf(file_path, return_details=True)

        if not extraction_result.success or not extraction_result.text:
            error_msg = (
                extraction_result.error or "Tidak dapat mengekstrak teks dari PDF"
            )
            raise ValueError(error_msg)

        text = extraction_result.text

        # Split into chunks using appropriate parser based on document type
        doc_title = doc["document_title"] or Path(doc["original_filename"]).stem
        detected_type = detect_document_type(doc["original_filename"], text)

        # Base metadata for parsers
        base_metadata = {
            "filename": doc["original_filename"],
            "document_title": doc_title,
            "doc_type": detected_type,
        }

        # Use specialized parsers for better chunking (especially tables)
        # Jika parser belum diimplementasi, fallback ke split_legal_document secara graceful
        chunks = None

        # Preferred path: use the same structured parser+chunker pipeline as DocumentProcessor
        # so uploads from this route inherit the latest chunking improvements.
        try:
            from app.core.ingestion.json_structure_parser import parse_document
            from app.core.ingestion.structured_chunker import chunk_document
            from app.core.ingestion.pdf_processor import DocumentProcessor

            folder_hint = detected_type
            if folder_hint == "audit":
                folder_hint = "laporan"

            doc_structure = parse_document(
                text=text,
                filename=doc["original_filename"],
                folder_hint=folder_hint,
            )

            md_fallback_path = None
            marker_candidates = [
                Path(doc.get("file_path", "")).name,
                doc.get("filename", ""),
                doc.get("original_filename", ""),
            ]
            for candidate in marker_candidates:
                if not candidate:
                    continue
                md_path = DocumentProcessor._find_marker_markdown_path(candidate)
                if md_path:
                    md_fallback_path = md_path
                    break

            structured_chunks = chunk_document(
                doc_structure,
                md_file_path=md_fallback_path,
            )

            if structured_chunks:
                chunks = []
                for chunk in structured_chunks:
                    meta = chunk.get("metadata", {}) or {}
                    hierarchy = meta.get("hierarchy", "")
                    chunks.append(
                        {
                            "text": chunk.get("text", ""),
                            "raw_text": chunk.get("text", ""),
                            "context_header": hierarchy or doc_title,
                            "hierarchy": hierarchy,
                            "document_title": meta.get("judul_dokumen", doc_title),
                            "filename": doc["original_filename"],
                            "doc_type": meta.get("doc_type", detected_type),
                            "bab": meta.get("bab", ""),
                            "bagian": meta.get("bagian", ""),
                            "pasal": meta.get("pasal", ""),
                            "ayat": meta.get("ayat", ""),
                            "chunk_part": meta.get("chunk_part"),
                            "chunk_parts_total": meta.get("chunk_parts_total"),
                            "parent_pasal_text": "",
                            "is_parent": True,
                            "chunk_type": chunk.get("chunk_type", "text"),
                            "section": hierarchy,
                            "table_context": meta.get("table_context", ""),
                            "original_table": meta.get("original_table", ""),
                        }
                    )

                logger.info(
                    f"Using structured chunker pipeline for document: {doc_title} ({len(chunks)} chunks)"
                )
        except Exception as e:
            logger.warning(
                f"Structured chunker pipeline failed, falling back to legacy parser flow: {e}"
            )
            chunks = None

        if chunks is None and detected_type == "audit":
            try:
                from app.core.ingestion.parsers.audit_parser import AuditParser

                logger.info(f"Using AuditParser for document: {doc_title}")
                raw_chunks = AuditParser.parse(text, base_metadata)
                # Convert to expected format
                chunks = []
                for chunk in raw_chunks:
                    chunks.append(
                        {
                            "text": chunk["text"],
                            "raw_text": chunk["text"],
                            "context_header": chunk["metadata"].get("section", doc_title),
                            "hierarchy": chunk["metadata"].get("hierarchy", ""),
                            "document_title": doc_title,
                            "filename": doc["original_filename"],
                            "doc_type": detected_type,
                            "bab": "",
                            "bagian": "",
                            "pasal": "",
                            "ayat": "",
                            "chunk_part": chunk["metadata"].get("chunk_part"),
                            "chunk_parts_total": chunk["metadata"].get("chunk_parts_total"),
                            "parent_pasal_text": "",
                            "is_parent": True,
                            "chunk_type": chunk["metadata"].get("chunk_type", "section"),
                            "section": chunk["metadata"].get("section", ""),
                            "table_context": chunk["metadata"].get("table_context", ""),
                            "original_table": chunk["metadata"].get("original_table", ""),
                        }
                    )
            except ImportError:
                logger.warning(
                    "AuditParser tidak tersedia (parsers/audit_parser.py belum diimplementasi), "
                    "fallback ke default splitter"
                )
                chunks = None

        elif chunks is None and detected_type == "peraturan":
            try:
                from app.core.ingestion.parsers.peraturan_parser import PeraturanParser

                logger.info(f"Using PeraturanParser for document: {doc_title}")
                raw_chunks = PeraturanParser.parse(text, base_metadata)
                # Convert to expected format
                chunks = []
                for chunk in raw_chunks:
                    meta = chunk.get("metadata", {})
                    chunks.append(
                        {
                            "text": chunk["text"],
                            "raw_text": chunk["text"],
                            "context_header": meta.get("hierarchy", doc_title),
                            "hierarchy": meta.get("hierarchy", ""),
                            "document_title": doc_title,
                            "filename": doc["original_filename"],
                            "doc_type": detected_type,
                            "bab": meta.get("bab", ""),
                            "bagian": meta.get("bagian", ""),
                            "pasal": meta.get("pasal", ""),
                            "ayat": meta.get("ayat", ""),
                            "chunk_part": meta.get("chunk_part"),
                            "chunk_parts_total": meta.get("chunk_parts_total"),
                            "parent_pasal_text": "",
                            "is_parent": True,
                            "chunk_type": meta.get("section_type", "pasal"),
                            "section": meta.get("hierarchy", ""),
                            "table_context": meta.get("table_context", ""),
                            "original_table": meta.get("original_table", ""),
                        }
                    )
            except ImportError:
                logger.warning(
                    "PeraturanParser tidak tersedia (parsers/peraturan_parser.py belum diimplementasi), "
                    "fallback ke default splitter"
                )
                chunks = None

        if chunks is None:
            # Fallback ke default splitter — untuk tipe 'other', atau jika parser belum tersedia
            logger.info(f"Using default splitter for document: {doc_title}")
            chunks = split_legal_document(
                text=text,
                doc_title=doc_title,
                filename=doc["original_filename"],
            )

        # Apply figure extraction pipeline (opt-in)
        if use_figure_pipeline and chunks:
            chunks = self._apply_figure_pipeline(
                pdf_path=file_path,
                chunks=chunks,
                doc_title=doc_title,
                filename=doc["original_filename"],
                doc_type=detected_type,
            )

        # Save chunks to database (preview stage)
        self.save_chunks(doc_id, chunks)

        # Update document status
        doc_type = chunks[0]["doc_type"] if chunks else "other"
        self.update_document(
            doc_id,
            document_title=doc_title,
            doc_type=doc_type,
            chunk_count=len(chunks),
            status="previewed",
        )

        logger.info(f"Previewed {len(chunks)} chunks for document: {doc_id}")

        # Build response with extraction info
        response = {
            "doc_id": doc_id,
            "document_title": doc_title,
            "doc_type": doc_type,
            "total_chunks": len(chunks),
            "chunks": chunks[:50],  # Limit preview to 50 chunks
            "has_more": len(chunks) > 50,
            # Extraction details for user notification
            "extraction": {
                "method": extraction_result.method,
                "chars": len(text),
                "stats": extraction_result.stats,
            },
        }

        # Add warning if fallback was used
        if extraction_result.warning:
            response["warning"] = extraction_result.warning

        # Add info about extraction method
        if extraction_result.method == "marker":
            response["extraction"]["note"] = (
                "Ekstraksi optimal dengan Marker (tabel terformat)"
            )
        elif extraction_result.method == "marker_cached":
            response["extraction"]["note"] = "Menggunakan cache Marker"
        elif extraction_result.method in ["pdfplumber", "pymupdf", "pypdf2"]:
            response["extraction"]["note"] = (
                f"Menggunakan {extraction_result.method} (tabel mungkin tidak terformat)"
            )

        return response

    def get_embedding_model(self):
        """Lazy load embedding model."""
        if self._embedding_model is None:
            import torch
            from transformers import AutoTokenizer, AutoModel

            model_path = (
                BACKEND_DIR / "models" / "embeddings" / "indo-sentence-bert-base"
            )

            if model_path.exists():
                self._tokenizer = AutoTokenizer.from_pretrained(
                    str(model_path), local_files_only=True
                )
                self._embedding_model = AutoModel.from_pretrained(
                    str(model_path), local_files_only=True
                )
                self._embedding_model.eval()
                logger.info("Embedding model loaded")
            else:
                logger.warning(f"Embedding model not found at {model_path}")

        return self._embedding_model, self._tokenizer

    def generate_embedding(self, text: str) -> Optional[List[float]]:
        """Generate embedding for text."""
        model, tokenizer = self.get_embedding_model()

        if model is None or tokenizer is None:
            return None

        import torch

        with torch.no_grad():
            inputs = tokenizer(
                text, return_tensors="pt", padding=True, truncation=True, max_length=512
            )
            outputs = model(**inputs)
            embedding = outputs.last_hidden_state.mean(dim=1).squeeze().tolist()
            return embedding

    def _delete_qdrant_points_by_doc_id(self, doc_id: str) -> None:
        """Delete all Qdrant points for a document id."""
        import httpx

        qdrant_url = settings.QDRANT_URL
        collection_name = settings.QDRANT_COLLECTION
        response = httpx.post(
            f"{qdrant_url}/collections/{collection_name}/points/delete",
            json={
                "filter": {
                    "must": [
                        {"key": "doc_id", "match": {"value": doc_id}},
                    ]
                }
            },
            timeout=30,
        )
        if response.status_code not in [200, 202]:
            raise RuntimeError(
                f"Failed to delete old Qdrant points for doc_id={doc_id}: {response.status_code} {response.text}"
            )

    def _upload_document_points(
        self,
        doc_id: str,
        doc: Dict[str, Any],
        chunks: List[Dict[str, Any]],
        embeddings: List[Optional[List[float]]],
    ) -> int:
        """Replace all Qdrant points for a document with a fresh upsert set."""
        import httpx

        qdrant_url = settings.QDRANT_URL
        collection_name = settings.QDRANT_COLLECTION

        # Remove stale vectors first to avoid duplicates on reindex.
        self._delete_qdrant_points_by_doc_id(doc_id)

        points = []
        for i, (chunk, emb) in enumerate(zip(chunks, embeddings)):
            if emb is None:
                continue

            chunk_index = chunk.get("chunk_index", i)
            points.append(
                {
                    "id": str(uuid.uuid4()),
                    "vector": emb,
                    "payload": {
                        "chunk_index": chunk_index,
                        "text": chunk["text"],
                        "raw_text": chunk.get("raw_text", chunk["text"]),
                        "context_header": chunk.get("context_header", ""),
                        "document_title": doc["document_title"],
                        "filename": doc["original_filename"],
                        "doc_type": doc.get("doc_type", "other"),
                        "bab": chunk.get("bab", ""),
                        "bagian": chunk.get("bagian", ""),
                        "pasal": chunk.get("pasal", ""),
                        "ayat": chunk.get("ayat", ""),
                        "parent_pasal_text": chunk.get("parent_pasal_text", ""),
                        "is_parent": chunk.get("is_parent", False),
                        "hierarchy": chunk.get("hierarchy", ""),
                        "chunk_part": chunk.get("chunk_part"),
                        "chunk_parts_total": chunk.get("chunk_parts_total"),
                        "doc_id": doc_id,
                        "chunk_type": chunk.get("chunk_type", "text"),
                        "section": chunk.get("section", ""),
                        "table_context": chunk.get("table_context", ""),
                        "original_table": chunk.get("original_table", ""),
                    },
                }
            )

        if not points:
            raise RuntimeError(
                f"No embeddings generated for doc_id={doc_id}. Check embedding model availability."
            )

        batch_size = 100
        uploaded = 0
        for i in range(0, len(points), batch_size):
            batch = points[i : i + batch_size]
            response = httpx.put(
                f"{qdrant_url}/collections/{collection_name}/points",
                json={"points": batch},
                timeout=60,
            )
            if response.status_code not in [200, 201]:
                raise RuntimeError(
                    f"Qdrant upload failed for doc_id={doc_id}: {response.status_code} {response.text}"
                )
            uploaded += len(batch)

        return uploaded

    def index_document(self, doc_id: str) -> Dict[str, Any]:
        """Index document chunks to Qdrant and BM25."""
        doc = self.get_document(doc_id)
        if not doc:
            raise ValueError(f"Document not found: {doc_id}")

        chunks = self.get_chunks(doc_id, limit=10000)
        if not chunks:
            raise ValueError("No chunks to index. Run preview first.")

        logger.info(f"Indexing {len(chunks)} chunks for document: {doc_id}")

        # Generate embeddings
        embeddings = []
        for i, chunk in enumerate(chunks):
            emb = self.generate_embedding(chunk["text"])
            embeddings.append(emb)
            if (i + 1) % 50 == 0:
                logger.info(f"Generated {i + 1}/{len(chunks)} embeddings")

        uploaded_points = self._upload_document_points(doc_id, doc, chunks, embeddings)
        logger.info(f"Uploaded {uploaded_points} points to Qdrant")

        # Mark chunks as indexed
        self.mark_chunks_indexed(doc_id)

        # Update document status BEFORE BM25 rebuild (so this doc is included)
        self.update_document(
            doc_id,
            status="indexed",
            chunk_count=len(chunks),
            processed_at=datetime.now().isoformat(),
        )

        # Update BM25 index (uses status="indexed" filter)
        self._rebuild_bm25_index()

        return {
            "doc_id": doc_id,
            "chunks_indexed": len(chunks),
            "status": "indexed",
        }

    def _rebuild_bm25_index(self):
        """Rebuild BM25 index from all indexed documents."""
        from rank_bm25 import BM25Okapi

        # Get all indexed chunks from all documents
        all_docs = self.get_all_documents()
        all_chunks = []

        for doc in all_docs:
            if doc.get("status") == "indexed":
                chunks = self.get_chunks(doc["doc_id"], limit=10000)
                for chunk in chunks:
                    all_chunks.append(
                        {
                            "text": chunk["text"],
                            "metadata": {
                                "document_title": doc.get("document_title", ""),
                                "context_header": chunk.get("context_header", ""),
                                "pasal": chunk.get("pasal", ""),
                                "ayat": chunk.get("ayat", ""),
                                "bab": chunk.get("bab", ""),
                                "hierarchy": chunk.get("hierarchy", ""),
                                "chunk_part": chunk.get("chunk_part"),
                                "chunk_parts_total": chunk.get("chunk_parts_total"),
                                "parent_pasal_text": chunk.get("parent_pasal_text", ""),
                                "is_parent": chunk.get("is_parent", False),
                                "doc_id": doc["doc_id"],
                            },
                        }
                    )

        if not all_chunks:
            logger.warning("No chunks to build BM25 index")
            return

        # Tokenize
        tokenized = []
        for c in all_chunks:
            text = c.get("text", "")
            metadata = c.get("metadata", {}) or {}
            search_text = _bm25_search_text(text, metadata)
            tokenized.append(_tokenize_bm25(search_text))

        # Build BM25
        bm25 = BM25Okapi(tokenized)

        # Prepare data for BM25Retriever
        corpus_texts = [c["text"] for c in all_chunks]
        doc_ids = [c["metadata"]["doc_id"] for c in all_chunks]

        # Save
        with open(BM25_PATH, "wb") as f:
            pickle.dump(
                {
                    "bm25": bm25,
                    "doc_ids": doc_ids,
                    "corpus_texts": corpus_texts,
                    "k1": 1.5,
                    "b": 0.75,
                    "documents": all_chunks,
                },
                f,
            )

        logger.info(f"Rebuilt BM25 index with {len(all_chunks)} documents")

    def delete_document(self, doc_id: str) -> Dict[str, Any]:
        """Delete document and its chunks from all stores."""
        import httpx

        doc = self.get_document(doc_id)
        if not doc:
            raise ValueError(f"Document not found: {doc_id}")

        logger.info(
            f"Deleting document: {doc_id} ({doc.get('document_title', doc.get('filename', 'unknown'))})"
        )

        # Delete from Qdrant - try multiple filter strategies
        qdrant_url = settings.QDRANT_URL
        collection_name = settings.QDRANT_COLLECTION
        qdrant_deleted = 0

        try:
            # Strategy 1: Filter by doc_id field
            resp = httpx.post(
                f"{qdrant_url}/collections/{collection_name}/points/delete",
                json={
                    "filter": {"must": [{"key": "doc_id", "match": {"value": doc_id}}]}
                },
                timeout=30,
            )
            if resp.status_code == 200:
                result = resp.json()
                logger.info(f"Qdrant delete by doc_id: {result}")

            # Strategy 2: Also try by document_title (for legacy data)
            doc_title = doc.get("document_title") or doc.get("filename", "")
            if doc_title:
                resp2 = httpx.post(
                    f"{qdrant_url}/collections/{collection_name}/points/delete",
                    json={
                        "filter": {
                            "must": [
                                {"key": "document_title", "match": {"value": doc_title}}
                            ]
                        }
                    },
                    timeout=30,
                )
                if resp2.status_code == 200:
                    result2 = resp2.json()
                    logger.info(f"Qdrant delete by document_title: {result2}")

            # Strategy 3: Try by filename
            filename = doc.get("filename") or doc.get("original_filename", "")
            if filename:
                resp3 = httpx.post(
                    f"{qdrant_url}/collections/{collection_name}/points/delete",
                    json={
                        "filter": {
                            "must": [{"key": "filename", "match": {"value": filename}}]
                        }
                    },
                    timeout=30,
                )
                if resp3.status_code == 200:
                    result3 = resp3.json()
                    logger.info(f"Qdrant delete by filename: {result3}")

        except Exception as e:
            logger.error(f"Qdrant delete failed: {e}")

        # Delete file from disk
        if doc.get("file_path"):
            file_path = Path(doc["file_path"])
            if file_path.exists():
                file_path.unlink()
                logger.info(f"Deleted file: {file_path}")

        # Delete from database (SQLite)
        chunk_count = self.get_chunk_count(doc_id)
        self.db_delete_document(doc_id)

        # Rebuild BM25
        self._rebuild_bm25_index()

        logger.info(f"Document deleted successfully: {doc_id}")

        return {
            "doc_id": doc_id,
            "deleted_chunks": chunk_count,
            "status": "deleted",
        }

    def list_documents(self) -> List[Dict[str, Any]]:
        """Get indexed/processed documents with chunk data for management UI."""
        docs = self.get_all_documents()
        visible_statuses = {"indexed", "processed", "completed"}
        return [
            {
                "doc_id": d["doc_id"],
                "filename": d["original_filename"],
                "document_title": d["document_title"],
                "doc_type": d["doc_type"],
                "file_size": d["file_size"],
                "chunk_count": d["chunk_count"],
                "status": d["status"],
                "created_at": d["created_at"],
                "processed_at": d["processed_at"],
            }
            for d in docs
            if d.get("chunk_count", 0) > 0
            and str(d.get("status", "")).lower() in visible_statuses
        ]

    def get_document_detail(self, doc_id: str) -> Dict[str, Any]:
        """Get document with chunks."""
        doc = self.get_document(doc_id)
        if not doc:
            raise ValueError(f"Document not found: {doc_id}")

        chunks = self.get_chunks(doc_id, limit=100)
        total_chunks = self.get_chunk_count(doc_id)

        return {
            "doc_id": doc["doc_id"],
            "filename": doc["original_filename"],
            "document_title": doc["document_title"],
            "doc_type": doc["doc_type"],
            "file_size": doc["file_size"],
            "chunk_count": total_chunks,
            "status": doc["status"],
            "created_at": doc["created_at"],
            "processed_at": doc["processed_at"],
            "chunks": chunks,
            "has_more": total_chunks > 100,
        }

    def sync_from_qdrant(self) -> Dict[str, Any]:
        """Sync documents from Qdrant to SQLite via ORM.

        Scans Qdrant collection for unique documents and creates
        records in SQLite for documents not yet tracked.
        """
        import hashlib
        import httpx
        from sqlalchemy import or_
        from app.models.db_models import Document

        qdrant_url = settings.QDRANT_URL
        collection_name = settings.QDRANT_COLLECTION

        logger.info("Syncing documents from Qdrant...")

        try:
            # Get all points from Qdrant (scroll through all)
            all_docs = {}
            offset = None

            while True:
                payload = {
                    "limit": 100,
                    "with_payload": True,
                    "with_vector": False,
                }
                if offset:
                    payload["offset"] = offset

                resp = httpx.post(
                    f"{qdrant_url}/collections/{collection_name}/points/scroll",
                    json=payload,
                    timeout=60,
                )

                if resp.status_code != 200:
                    logger.error(f"Qdrant scroll failed: {resp.text}")
                    break

                result = resp.json().get("result", {})
                points = result.get("points", [])

                if not points:
                    break

                # Extract unique documents
                for point in points:
                    payload = point.get("payload", {}) or {}
                    nested_meta = payload.get("metadata", {})
                    if not isinstance(nested_meta, dict):
                        nested_meta = {}

                    doc_title = (
                        payload.get("document_title")
                        or nested_meta.get("document_title")
                        or payload.get("filename")
                        or nested_meta.get("filename")
                        or ""
                    )
                    filename = (
                        payload.get("filename")
                        or nested_meta.get("filename")
                        or doc_title
                    )
                    doc_type = (
                        payload.get("doc_type")
                        or nested_meta.get("doc_type")
                        or "other"
                    )

                    # Prefer explicit doc identifier when available.
                    # Fallback to title/filename so mixed legacy payloads still aggregate.
                    doc_key = (
                        str(
                            payload.get("doc_id")
                            or nested_meta.get("doc_id")
                            or payload.get("document_id")
                            or nested_meta.get("document_id")
                            or doc_title
                            or filename
                        )
                        .strip()
                    )

                    if not doc_key:
                        continue

                    if doc_key not in all_docs:
                        all_docs[doc_key] = {
                            "document_title": doc_title or filename or doc_key,
                            "filename": filename or doc_title or doc_key,
                            "doc_type": doc_type,
                            "chunk_count": 0,
                        }

                    all_docs[doc_key]["chunk_count"] += 1

                # Next page
                offset = result.get("next_page_offset")
                if not offset:
                    break

            logger.info(f"Found {len(all_docs)} unique documents in Qdrant")

            # Insert into DB via ORM (skip jika sudah ada berdasarkan document_title)
            db = self._get_db()
            imported = 0
            updated = 0
            skipped = 0

            try:
                for doc_key, info in all_docs.items():
                    # Check jika sudah ada
                    existing = db.query(Document).filter(
                        Document.document_title == info["document_title"]
                    ).first()

                    if not existing and info["filename"]:
                        existing = (
                            db.query(Document)
                            .filter(
                                or_(
                                    Document.filename == info["filename"],
                                    Document.original_filename == info["filename"],
                                )
                            )
                            .first()
                        )

                    if existing:
                        changed = False

                        if int(existing.chunk_count or 0) != int(info["chunk_count"]):
                            existing.chunk_count = int(info["chunk_count"])
                            changed = True

                        # Keep metadata aligned with what is currently present in Qdrant.
                        if existing.doc_type != info["doc_type"]:
                            existing.doc_type = info["doc_type"]
                            changed = True

                        if existing.filename != info["filename"]:
                            existing.filename = info["filename"]
                            changed = True

                        if existing.original_filename != info["filename"]:
                            existing.original_filename = info["filename"]
                            changed = True

                        if existing.status != "indexed":
                            existing.status = "indexed"
                            changed = True

                        if changed:
                            updated += 1
                        else:
                            skipped += 1
                        continue

                    # Generate stable legacy doc_id from document title.
                    doc_hash = hashlib.sha1(doc_key.encode("utf-8")).hexdigest()[:12]
                    doc_id = f"legacy_{doc_hash}"

                    # Insert via ORM
                    new_doc = Document(
                        doc_id=doc_id,
                        filename=info["filename"],
                        original_path="",
                        original_filename=info["filename"],
                        document_title=info["document_title"],
                        doc_type=info["doc_type"],
                        file_size=0,
                        file_path="",
                        status="indexed",
                        chunk_count=info["chunk_count"],
                    )
                    db.add(new_doc)
                    imported += 1

                db.commit()
            finally:
                db.close()

            logger.info(
                f"Sync complete: {imported} imported, {updated} updated, {skipped} skipped"
            )

            return {
                "total_in_qdrant": len(all_docs),
                "imported": imported,
                "updated": updated,
                "skipped": skipped,
                "status": "success",
            }

        except Exception as e:
            logger.error(f"Sync from Qdrant failed: {e}")
            return {
                "total_in_qdrant": 0,
                "imported": 0,
                "updated": 0,
                "skipped": 0,
                "status": "error",
                "error": str(e),
            }


# Singleton instance
_manager = None


def get_document_manager() -> DocumentManager:
    """Get document manager singleton."""
    global _manager
    if _manager is None:
        _manager = DocumentManager()
    return _manager
