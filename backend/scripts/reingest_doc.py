#!/usr/bin/env python3
"""Re-process a single document with the figure extraction pipeline.

Usage:
    python scripts/reingest_doc.py --doc-id 1
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

from loguru import logger


def main():
    parser = argparse.ArgumentParser(description="Re-ingest one document with figure pipeline")
    parser.add_argument("--doc-id", required=True, help="Document ID (numeric) in SQLite")
    args = parser.parse_args()

    from app.core.ingestion.document_manager import get_document_manager
    manager = get_document_manager()

    doc = manager.get_document(args.doc_id)
    if not doc:
        logger.error(f"Doc id {args.doc_id} not found")
        sys.exit(1)

    logger.info(f"Re-ingesting doc {args.doc_id}: {doc.get('original_filename')}")

    # Step 1: preview chunks with figure pipeline
    preview = manager.preview_chunks(args.doc_id, use_figure_pipeline=True)
    chunks = preview.get("chunks", [])
    figure_chunks = [c for c in chunks if c.get("chunk_type") == "figure"]
    logger.info(f"Generated {len(chunks)} chunks total, {len(figure_chunks)} figure chunks")

    # Step 2: save chunks (replaces existing)
    saved = manager.save_chunks(args.doc_id, chunks)
    logger.info(f"Saved {saved} chunks to SQLite")

    # Step 3: index in Qdrant + BM25
    result = manager.index_document(args.doc_id)
    logger.success(f"Indexing result: {result}")


if __name__ == "__main__":
    main()
