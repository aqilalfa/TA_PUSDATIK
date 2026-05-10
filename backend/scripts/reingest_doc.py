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

    # Step 1: preview_chunks runs full figure pipeline and saves ALL chunks to SQLite internally.
    # It returns only up to 50 for display — do NOT call save_chunks again with that truncated list.
    preview = manager.preview_chunks(args.doc_id, use_figure_pipeline=True)
    total = preview.get("total_chunks", 0)
    logger.info(f"Generated {total} total chunks (preview_chunks already saved them to SQLite)")

    # Step 2: index in Qdrant + BM25 (reads from SQLite, so sees the full chunk set)
    result = manager.index_document(args.doc_id)
    logger.success(f"Indexing result: {result}")


if __name__ == "__main__":
    main()
