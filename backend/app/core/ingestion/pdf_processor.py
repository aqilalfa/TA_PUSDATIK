"""
Complete document processing pipeline — Restructured

Pipeline:
1. PDF → Text  (Marker preferred, OCR fallback)
2. Text → Structured JSON  (json_structure_parser)
3. JSON → 600-char chunks with metadata  (structured_chunker)
4. Chunks → Database + Qdrant vector store
"""

import json
from pathlib import Path
from typing import Dict, Tuple, Optional
from datetime import datetime
from loguru import logger
from sqlalchemy.orm import Session

from app.core.ingestion.marker_converter import marker_converter, MarkerConversionError
from app.core.ingestion.ocr import ocr_processor
from app.core.ingestion.json_structure_parser import parse_document, detect_doc_type
from app.core.ingestion.structured_chunker import chunk_document
from app.core.rag.langchain_engine import langchain_engine
from app.models.db_models import Document, Chunk

# Output directory for OCR results
OCR_OUTPUT_DIR = Path("data/ocr_output")
OCR_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


class DocumentProcessor:
    """
    Complete document processing pipeline

    Workflow:
    1. PDF to Text (Marker preferred, OCR fallback)
    2. Parse into structured JSON (bab/pasal/ayat or sections/paragraphs)
    3. Chunk into ≤600 char pieces with rich metadata
    4. Store in database and vector store
    """

    @staticmethod
    def _convert_pdf_to_text(
        pdf_path: str, filename: str, force_ocr: bool = False
    ) -> Tuple[str, Optional[str], str]:
        """
        Convert PDF to text using Marker (preferred) or OCR (fallback).

        Returns:
            Tuple of (text, markdown_path, method_used)
        """
        # If force_ocr, skip Marker entirely
        if force_ocr:
            logger.info("Force OCR mode - skipping Marker")
            text, ocr_used = ocr_processor.process_pdf(pdf_path, force_ocr=True)
            method = "ocr" if ocr_used else "direct"

            if ocr_used:
                ocr_output_path = str(OCR_OUTPUT_DIR / f"{Path(filename).stem}_ocr.txt")
                ocr_processor.save_ocr_result(text, ocr_output_path)
                logger.info(f"OCR result saved to: {ocr_output_path}")

            return text, None, method

        # Try Marker first (better for tables and structure)
        if marker_converter.is_available():
            try:
                logger.info("Attempting Marker conversion...")
                text, markdown_path, used_marker = marker_converter.convert(
                    pdf_path, save_output=True
                )

                if used_marker:
                    logger.success("Marker conversion successful")
                    return text, markdown_path, "marker"

            except MarkerConversionError as e:
                logger.warning(f"Marker conversion failed: {e}")
            except Exception as e:
                logger.warning(f"Marker error: {e}")
        else:
            logger.info("Marker not available, using OCR pipeline")

        # Fallback to OCR
        logger.info("Using OCR pipeline for text extraction...")
        text, ocr_used = ocr_processor.process_pdf(pdf_path, force_ocr=False)
        method = "ocr" if ocr_used else "direct"

        if ocr_used:
            ocr_output_path = f"data/ocr_output/{Path(filename).stem}_ocr.txt"
            ocr_processor.save_ocr_result(text, ocr_output_path)
            logger.info(f"OCR result saved to: {ocr_output_path}")

        return text, None, method

    @staticmethod
    def process_document(
        pdf_path: str, filename: str, doc_id: int, db: Session,
        force_ocr: bool = False, doc_type_hint: str = None
    ) -> Dict:
        """
        Process a single document through the complete pipeline.

        Args:
            pdf_path: Path to PDF file
            filename: Original filename
            doc_id: Database document ID
            db: Database session
            force_ocr: Force OCR even if text-selectable
            doc_type_hint: If provided, skip classification and use this type directly

        Returns:
            Processing result dictionary
        """
        logger.info(f"Starting document processing: {filename}")
        logger.info("=" * 60)

        result = {
            "document_id": doc_id,
            "filename": filename,
            "status": "processing",
            "steps_completed": [],
            "errors": [],
        }

        document = None

        try:
            # Get document from database
            document = db.query(Document).filter(Document.id == doc_id).first()
            if not document:
                raise ValueError(f"Document {doc_id} not found in database")

            document.status = "processing"
            db.commit()

            # STEP 1: PDF → Text
            logger.info("STEP 1: PDF to Text Conversion...")

            text, markdown_path, conversion_method = (
                DocumentProcessor._convert_pdf_to_text(pdf_path, filename, force_ocr)
            )

            ocr_used = conversion_method == "ocr"
            document.ocr_needed = ocr_used
            db.commit()

            result["steps_completed"].append("text_extraction")
            result["conversion_method"] = conversion_method
            result["text_length"] = len(text)

            logger.success(f"✓ Text extraction complete (method: {conversion_method}, {len(text)} chars)")

            # STEP 2: Text → Structured JSON
            logger.info("STEP 2: Parsing into structured JSON...")

            # Determine document type
            folder_hint = doc_type_hint or ""
            # Map old "audit" hint to "laporan"
            if folder_hint == "audit":
                folder_hint = "laporan"

            doc_structure = parse_document(
                text=text,
                filename=filename,
                folder_hint=folder_hint,
            )

            doc_type = doc_structure.get("type", "laporan")
            document.doc_type = doc_type
            document.doc_metadata = json.dumps(doc_structure, ensure_ascii=False)
            db.commit()

            result["steps_completed"].append("json_parsing")
            result["doc_type"] = doc_type

            logger.success(f"✓ Parsed as '{doc_type}'")

            # STEP 3: JSON → Chunks (≤600 chars)
            logger.info("STEP 3: Structured chunking (max 600 chars)...")

            chunks = chunk_document(doc_structure)

            result["steps_completed"].append("chunking")
            result["chunk_count"] = len(chunks)

            logger.success(f"✓ Created {len(chunks)} chunks")

            # STEP 4: Store chunks in database
            logger.info("STEP 4: Storing chunks in database...")

            for i, chunk_data in enumerate(chunks):
                chunk = Chunk(
                    document_id=doc_id,
                    chunk_text=chunk_data["text"],
                    chunk_index=i,
                    chunk_metadata=json.dumps(
                        chunk_data["metadata"], ensure_ascii=False
                    ),
                )
                db.add(chunk)

            db.commit()

            result["steps_completed"].append("database_storage")
            logger.success(f"✓ Stored {len(chunks)} chunks in database")

            # STEP 5: Store in vector store
            logger.info("STEP 5: Indexing in vector store...")

            texts = [chunk["text"] for chunk in chunks]
            
            # Enrich metadata with chunk_index and document_id for retrieval tracking
            metadatas = []
            for i, chunk in enumerate(chunks):
                meta = chunk["metadata"].copy()
                meta["chunk_index"] = chunk.get("chunk_index", i)
                meta["document_id"] = doc_id
                metadatas.append(meta)

            langchain_engine.add_documents(texts, metadatas)

            result["steps_completed"].append("vector_indexing")
            logger.success(f"✓ Indexed {len(chunks)} chunks in vector store")

            # Update document status
            document.status = "completed"
            document.processed_at = datetime.utcnow()
            db.commit()

            result["status"] = "completed"

            logger.info("=" * 60)
            logger.success(f"✓ Document processing complete: {filename}")
            logger.info(f"  - Type: {doc_type}")
            logger.info(f"  - Chunks: {len(chunks)}")
            logger.info(f"  - OCR used: {ocr_used}")
            logger.info("=" * 60)

            return result

        except Exception as e:
            logger.error(f"Error processing document: {e}")

            if document:
                document.status = "failed"
                document.error_message = str(e)
                db.commit()

            result["status"] = "failed"
            result["errors"].append(str(e))

            raise


async def process_document_async(pdf_path: str, filename: str, doc_id: int, db: Session):
    """
    Async wrapper for document processing (for background tasks)
    """
    import asyncio

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None,
        DocumentProcessor.process_document,
        pdf_path,
        filename,
        doc_id,
        db,
    )
