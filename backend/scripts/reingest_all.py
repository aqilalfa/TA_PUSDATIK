#!/usr/bin/env python3
"""
Re-ingest all documents with the new structured JSON pipeline.

Pipeline:
  PDF → Text (Marker/OCR) → JSON Structure → 600-char chunks → DB + Qdrant + BM25
"""

import sys
import os
from pathlib import Path

# Force CPU mode to avoid CUDA hang
os.environ["CUDA_VISIBLE_DEVICES"] = ""

sys.path.insert(0, str(Path(__file__).parent.parent))

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams
from app.core.rag.langchain_engine import langchain_engine
import numpy as np

from app.database import SessionLocal, engine
from app.models.db_models import Document, Chunk
from app.core.ingestion.pdf_processor import DocumentProcessor
from app.config import settings
from loguru import logger
from datetime import datetime
import json
import re


# Default path - can be overridden via command line
DEFAULT_DOCS_DIR = r"D:\aqil\pusdatik\data\documents"


def _tokenize(text: str):
    return re.findall(r"\b\w+\b", text.lower())


def _build_bm25_search_text(text: str, metadata: dict) -> str:
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


def rebuild_bm25_index(db):
    """Rebuild BM25 index from all chunks in database."""
    logger.info("\n[Step 6] Rebuilding BM25 index...")

    try:
        import pickle
        from rank_bm25 import BM25Okapi

        chunks = db.query(Chunk).all()
        if not chunks:
            logger.warning("  No chunks found, skipping BM25 index")
            return

        corpus = []
        documents = []
        for c in chunks:
            text = (c.chunk_text or "").strip()
            if not text:
                continue

            metadata = {}
            if c.chunk_metadata:
                try:
                    metadata = json.loads(c.chunk_metadata)
                except Exception:
                    metadata = {}

            search_text = _build_bm25_search_text(text, metadata)

            documents.append({"text": text, "metadata": metadata})
            corpus.append(_tokenize(search_text))

        if not documents:
            logger.warning("  No non-empty chunk text found, skipping BM25 index")
            return

        bm25 = BM25Okapi(corpus)

        bm25_path = Path(__file__).parent.parent / "data" / "bm25_index.pkl"
        bm25_path.parent.mkdir(parents=True, exist_ok=True)

        with open(bm25_path, "wb") as f:
            pickle.dump({"bm25": bm25, "documents": documents}, f)

        logger.success(f"  ✓ BM25 index rebuilt with {len(documents)} documents")
        logger.info(f"    Saved to: {bm25_path}")

    except Exception as e:
        logger.error(f"  ✗ Failed to rebuild BM25 index: {e}")
        import traceback
        traceback.print_exc()


def reingest_all(docs_dir: str = None):
    """Re-ingest all documents from scratch using new structured JSON pipeline."""
    docs_dir = docs_dir or DEFAULT_DOCS_DIR

    logger.info("=" * 60)
    logger.info("SPBE RAG - Complete Re-Ingestion (Structured JSON Pipeline)")
    logger.info("=" * 60)
    logger.info(f"Documents directory: {docs_dir}")

    db = SessionLocal()

    try:
        # Step 1: Clear existing data
        logger.info("\n[Step 1] Clearing existing data...")

        chunk_count = db.query(Chunk).count()
        doc_count = db.query(Document).count()
        logger.info(f"  Deleting {chunk_count} chunks and {doc_count} documents")

        db.query(Chunk).delete()
        db.query(Document).delete()
        db.commit()

        logger.success("  ✓ Database cleared")

        # Step 2: Clear Qdrant collection
        logger.info("\n[Step 2] Clearing Qdrant collection...")

        client = QdrantClient(url=settings.QDRANT_URL, timeout=60)

        try:
            client.delete_collection(settings.QDRANT_COLLECTION, timeout=30)
            logger.info("  Deleted old collection")
        except:
            pass

        # Initialize embedding model for dimension
        logger.info("  Loading embedding model via LangChain Engine...")
        if not langchain_engine._initialized:
            langchain_engine.initialize()
            
        # Get dimension from a sample query if not easily available
        embed_dim = 768 # Standard for firqaaa/indo-sentence-bert-base
        logger.info(f"  Embedding dimension: {embed_dim}")

        client.create_collection(
            collection_name=settings.QDRANT_COLLECTION,
            vectors_config=VectorParams(size=embed_dim, distance=Distance.COSINE),
            timeout=30,
        )
        logger.success("  ✓ Qdrant collection recreated")

        # Step 3: Find all PDFs
        logger.info("\n[Step 3] Finding PDF documents...")

        docs_path = Path(docs_dir)
        if not docs_path.exists():
            logger.error(f"  ✗ Documents directory not found: {docs_dir}")
            return

        pdf_files = list(docs_path.rglob("*.pdf"))

        if not pdf_files:
            logger.warning(f"  No PDF files found in {docs_dir}")
            return

        logger.info(f"  Found {len(pdf_files)} PDF files:")
        for f in pdf_files:
            rel_path = f.relative_to(docs_path)
            logger.info(f"    - {rel_path}")

        # Step 4: Process each document
        logger.info("\n[Step 4] Processing documents...")

        processor = DocumentProcessor()
        total_chunks = 0
        processed = 0
        failed = 0

        for i, pdf_path in enumerate(pdf_files, 1):
            logger.info(f"\n  [{i}/{len(pdf_files)}] {pdf_path.name}")
            logger.info("  " + "-" * 50)

            try:
                # Determine doc type from folder or filename
                parent_folder = pdf_path.parent.name.lower()
                filename = pdf_path.name
                
                if "peraturan" in parent_folder:
                    file_doc_type = "peraturan"
                elif "pedoman" in parent_folder:
                    file_doc_type = "pedoman_spbe"
                elif "Evaluasi_SPBE" in filename:
                    file_doc_type = "laporan_spbe"
                elif parent_folder in ("audit", "others", "laporan"):
                    file_doc_type = "laporan"
                else:
                    file_doc_type = ""

                # Create document record
                document = Document(
                    filename=pdf_path.name,
                    original_path=str(pdf_path),
                    doc_type=file_doc_type or "unknown",
                    status="pending",
                    uploaded_by=1,
                    uploaded_at=datetime.utcnow(),
                )
                db.add(document)
                db.commit()
                db.refresh(document)

                # Process
                result = processor.process_document(
                    pdf_path=str(pdf_path),
                    filename=pdf_path.name,
                    doc_id=document.id,
                    db=db,
                    doc_type_hint=file_doc_type,
                )

                chunk_count = result.get("chunk_count", 0)
                total_chunks += chunk_count
                processed += 1

                logger.success(f"  ✓ {result['doc_type']}: {chunk_count} chunks")

            except Exception as e:
                logger.error(f"  ✗ Failed: {e}")
                failed += 1
                import traceback
                traceback.print_exc()
                continue

        # Step 5: Verify results
        logger.info("\n[Step 5] Verifying results...")

        final_docs = db.query(Document).count()
        final_chunks = db.query(Chunk).count()

        qdrant_info = client.get_collection(settings.QDRANT_COLLECTION)

        logger.info(f"  Database: {final_docs} documents, {final_chunks} chunks")
        logger.info(f"  Qdrant: {qdrant_info.points_count} vectors")

        # Summary per document
        logger.info("\n  Per-document summary:")
        logger.info("  " + "-" * 56)
        for doc in db.query(Document).all():
            chunks = db.query(Chunk).filter(Chunk.document_id == doc.id).all()
            if chunks:
                sizes = [len(c.chunk_text) for c in chunks]
                avg_len = sum(sizes) / len(chunks)
                max_len = max(sizes)
                logger.info(
                    f"  [{doc.doc_type:10}] {len(chunks):3d} chunks (avg {avg_len:5.0f}, max {max_len:5d}) - {doc.filename[:35]}"
                )
            else:
                logger.warning(
                    f"  [{doc.doc_type:10}]   0 chunks - {doc.filename[:35]}"
                )

        # Step 6: Rebuild BM25 index
        rebuild_bm25_index(db)

        # Final summary
        logger.info("\n" + "=" * 60)
        logger.success("✓ Re-ingestion complete!")
        logger.info(f"  Processed: {processed} documents")
        logger.info(f"  Failed: {failed} documents")
        logger.info(f"  Total chunks: {final_chunks}")
        logger.info(f"  Max chunk size: {settings.CHUNK_SIZE} chars")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"Re-ingestion failed: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Re-ingest all documents into SPBE RAG (Structured JSON Pipeline)"
    )
    parser.add_argument(
        "--docs-dir",
        default=DEFAULT_DOCS_DIR,
        help=f"Directory containing PDF documents (default: {DEFAULT_DOCS_DIR})",
    )

    args = parser.parse_args()
    reingest_all(docs_dir=args.docs_dir)
