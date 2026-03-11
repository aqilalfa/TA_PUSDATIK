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


def extract_pasals(text: str) -> List[Dict]:
    """Extract Pasal structure from legal document."""
    pasals = []

    pasal_pattern = re.compile(r"^Pasal\s+(\d+)\s*$", re.MULTILINE | re.IGNORECASE)
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
        start = match.end()

        if i + 1 < len(matches):
            end = matches[i + 1].start()
        else:
            end = len(text)

        content = text[start:end].strip()

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
    max_chunk_size: int = 1500,
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
    """Manages document upload, processing, and indexing."""

    def __init__(self):
        from app.core.database import (
            create_document,
            get_document,
            get_all_documents,
            update_document,
            delete_document as db_delete_document,
            save_chunks,
            get_chunks,
            get_chunk_count,
            mark_chunks_indexed,
            update_chunk,
            delete_chunk,
        )

        self.create_document = create_document
        self.get_document = get_document
        self.get_all_documents = get_all_documents
        self.update_document = update_document
        self.db_delete_document = db_delete_document
        self.save_chunks = save_chunks
        self.get_chunks = get_chunks
        self.get_chunk_count = get_chunk_count
        self.mark_chunks_indexed = mark_chunks_indexed
        self.update_chunk = update_chunk
        self.delete_chunk = delete_chunk

        # Lazy load embedding model
        self._embedding_model = None
        self._tokenizer = None

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

    def preview_chunks(self, doc_id: str) -> Dict[str, Any]:
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
        if detected_type == "audit":
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
                        "document_title": doc_title,
                        "filename": doc["original_filename"],
                        "doc_type": detected_type,
                        "bab": "",
                        "bagian": "",
                        "pasal": "",
                        "ayat": "",
                        "parent_pasal_text": "",
                        "is_parent": True,
                        "chunk_type": chunk["metadata"].get("chunk_type", "section"),
                        "section": chunk["metadata"].get("section", ""),
                        "table_context": chunk["metadata"].get("table_context", ""),
                        "original_table": chunk["metadata"].get("original_table", ""),
                    }
                )
        elif detected_type == "peraturan":
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
                        "document_title": doc_title,
                        "filename": doc["original_filename"],
                        "doc_type": detected_type,
                        "bab": meta.get("bab", ""),
                        "bagian": meta.get("bagian", ""),
                        "pasal": meta.get("pasal", ""),
                        "ayat": meta.get("ayat", ""),
                        "parent_pasal_text": "",
                        "is_parent": True,
                        "chunk_type": meta.get("section_type", "pasal"),
                        "section": meta.get("hierarchy", ""),
                        "table_context": meta.get("table_context", ""),
                        "original_table": meta.get("original_table", ""),
                    }
                )
        else:
            # Fallback to original splitting for other document types
            logger.info(f"Using default splitter for document: {doc_title}")
            chunks = split_legal_document(
                text=text,
                doc_title=doc_title,
                filename=doc["original_filename"],
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

    def index_document(self, doc_id: str) -> Dict[str, Any]:
        """Index document chunks to Qdrant and BM25."""
        import httpx

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

        # Upload to Qdrant
        qdrant_url = "http://localhost:6333"
        collection_name = "document_chunks"

        try:
            points = []
            for i, (chunk, emb) in enumerate(zip(chunks, embeddings)):
                if emb is None:
                    continue

                point_id = str(uuid.uuid4())
                points.append(
                    {
                        "id": point_id,
                        "vector": emb,
                        "payload": {
                            "chunk_index": i,  # Simpan index untuk ordering
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
                            "doc_id": doc_id,
                            # Fields for table support
                            "chunk_type": chunk.get("chunk_type", "text"),
                            "section": chunk.get("section", ""),
                            "table_context": chunk.get("table_context", ""),
                            "original_table": chunk.get("original_table", ""),
                        },
                    }
                )

            # Batch upload
            batch_size = 100
            for i in range(0, len(points), batch_size):
                batch = points[i : i + batch_size]
                resp = httpx.put(
                    f"{qdrant_url}/collections/{collection_name}/points",
                    json={"points": batch},
                    timeout=60,
                )
                if resp.status_code not in [200, 201]:
                    logger.error(f"Qdrant upload failed: {resp.text}")

            logger.info(f"Uploaded {len(points)} points to Qdrant")

        except Exception as e:
            logger.error(f"Qdrant indexing failed: {e}")

        # Mark chunks as indexed
        self.mark_chunks_indexed(doc_id)

        # Update document status BEFORE BM25 rebuild (so this doc is included)
        self.update_document(
            doc_id, status="indexed", processed_at=datetime.now().isoformat()
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
        def tokenize(text):
            return re.findall(r"\b\w+\b", text.lower())

        tokenized = [tokenize(c["text"]) for c in all_chunks]

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
        qdrant_url = "http://localhost:6333"
        collection_name = "document_chunks"
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
        """Get all documents with metadata."""
        docs = self.get_all_documents()
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
        """Sync documents from Qdrant to SQLite.

        Scans Qdrant collection for unique documents and creates
        records in SQLite for documents not yet tracked.
        """
        import httpx
        from app.core.database import get_connection

        qdrant_url = "http://localhost:6333"
        collection_name = "document_chunks"

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
                    payload = point.get("payload", {})
                    doc_title = payload.get("document_title", "")
                    filename = payload.get("filename", "")
                    doc_type = payload.get("doc_type", "other")

                    if doc_title and doc_title not in all_docs:
                        all_docs[doc_title] = {
                            "document_title": doc_title,
                            "filename": filename or doc_title,
                            "doc_type": doc_type,
                            "chunk_count": 0,
                        }

                    if doc_title:
                        all_docs[doc_title]["chunk_count"] += 1

                # Next page
                offset = result.get("next_page_offset")
                if not offset:
                    break

            logger.info(f"Found {len(all_docs)} unique documents in Qdrant")

            # Insert into SQLite (skip if already exists)
            conn = get_connection()
            cursor = conn.cursor()

            imported = 0
            skipped = 0

            for doc_title, info in all_docs.items():
                # Generate doc_id from title hash
                doc_id = f"legacy_{abs(hash(doc_title)) % 100000:05d}"

                # Check if already exists
                cursor.execute(
                    "SELECT doc_id FROM documents WHERE document_title = ?",
                    (doc_title,),
                )
                existing = cursor.fetchone()

                if existing:
                    skipped += 1
                    continue

                # Insert new document
                cursor.execute(
                    """
                    INSERT INTO documents (
                        doc_id, filename, original_filename, document_title,
                        doc_type, file_size, file_path, status, chunk_count,
                        created_at, processed_at
                    ) VALUES (?, ?, ?, ?, ?, 0, '', 'indexed', ?, 
                              datetime('now'), datetime('now'))
                """,
                    (
                        doc_id,
                        info["filename"],
                        info["filename"],
                        doc_title,
                        info["doc_type"],
                        info["chunk_count"],
                    ),
                )
                imported += 1

            conn.commit()
            conn.close()

            logger.info(f"Sync complete: {imported} imported, {skipped} skipped")

            return {
                "total_in_qdrant": len(all_docs),
                "imported": imported,
                "skipped": skipped,
                "status": "success",
            }

        except Exception as e:
            logger.error(f"Sync from Qdrant failed: {e}")
            return {
                "total_in_qdrant": 0,
                "imported": 0,
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
