#!/usr/bin/env python3
"""
Batch document ingestion script
Process multiple PDF documents at once
"""

import sys
import os
from pathlib import Path
import argparse

# Add app to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import SessionLocal
from app.models.db_models import Document, User
from app.core.ingestion.pdf_processor import DocumentProcessor
from loguru import logger
from datetime import datetime


def ingest_documents(input_dir: str, doc_type: str = "auto", user_id: int = 1):
    """
    Ingest all PDF documents from a directory

    Args:
        input_dir: Directory containing PDF files
        doc_type: Document type ('peraturan', 'audit', 'auto')
        user_id: User ID for upload tracking
    """
    logger.info("=" * 60)
    logger.info("SPBE RAG System - Document Ingestion")
    logger.info("=" * 60)

    db = SessionLocal()

    try:
        # Find all PDF files
        pdf_files = []
        input_path = Path(input_dir)

        if input_path.is_file() and input_path.suffix == ".pdf":
            # Single file
            pdf_files.append(input_path)
        elif input_path.is_dir():
            # Directory - search recursively
            pdf_files = list(input_path.rglob("*.pdf"))
        else:
            logger.error(f"Invalid input: {input_dir}")
            return

        if not pdf_files:
            logger.warning(f"No PDF files found in: {input_dir}")
            return

        logger.info(f"Found {len(pdf_files)} PDF file(s) to process")
        logger.info("")

        # Process each file
        for i, pdf_path in enumerate(pdf_files, 1):
            logger.info(f"\n[{i}/{len(pdf_files)}] Processing: {pdf_path.name}")
            logger.info("-" * 60)

            try:
                # Determine doc type if auto
                file_doc_type = doc_type
                if doc_type == "auto":
                    filename_lower = pdf_path.name.lower()
                    if "audit" in filename_lower:
                        file_doc_type = "audit"
                    elif any(
                        k in filename_lower
                        for k in ["pp", "perpres", "permen", "peraturan"]
                    ):
                        file_doc_type = "peraturan"
                    else:
                        file_doc_type = "other"

                # Create document record
                document = Document(
                    filename=pdf_path.name,
                    original_path=str(pdf_path),
                    doc_type=file_doc_type,
                    status="pending",
                    uploaded_by=user_id,
                    uploaded_at=datetime.utcnow(),
                )
                db.add(document)
                db.commit()
                db.refresh(document)

                logger.info(f"Created document record (ID: {document.id})")

                # Process document
                processor = DocumentProcessor()
                result = processor.process_document(
                    pdf_path=str(pdf_path),
                    filename=pdf_path.name,
                    doc_id=document.id,
                    db=db,
                )

                logger.success(f"✓ Successfully processed: {pdf_path.name}")
                logger.info(f"  - Type: {result['doc_type']}")
                logger.info(f"  - Chunks: {result['chunk_count']}")
                logger.info(f"  - OCR used: {result['ocr_used']}")

            except Exception as e:
                logger.error(f"✗ Failed to process {pdf_path.name}: {e}")
                continue

        logger.info("")
        logger.info("=" * 60)
        logger.success("Document ingestion complete!")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"Ingestion failed: {e}")
        raise
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(
        description="Ingest PDF documents into SPBE RAG system",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process all PDFs in a directory (auto-detect type)
  python ingest_documents.py --input-dir /app/data/documents
  
  # Process specific document types
  python ingest_documents.py --input-dir /app/data/documents/peraturan --doc-type peraturan
  python ingest_documents.py --input-dir /app/data/documents/audit --doc-type audit
  
  # Process single file
  python ingest_documents.py --input-dir /app/data/documents/PP_71_2019.pdf
        """,
    )

    parser.add_argument(
        "--input-dir",
        required=True,
        help="Directory containing PDF files or path to single PDF",
    )

    parser.add_argument(
        "--doc-type",
        default="auto",
        choices=["auto", "peraturan", "audit", "other"],
        help="Document type (default: auto-detect)",
    )

    parser.add_argument(
        "--user-id", type=int, default=1, help="User ID for tracking (default: 1)"
    )

    args = parser.parse_args()

    # Run ingestion
    ingest_documents(
        input_dir=args.input_dir, doc_type=args.doc_type, user_id=args.user_id
    )


if __name__ == "__main__":
    main()
