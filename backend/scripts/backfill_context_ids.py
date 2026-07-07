#!/usr/bin/env python3
"""Backfill stable canonical/citation IDs into existing SQLite chunk metadata."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger

from app.core.rag.context_ids import enrich_context_identity
from app.database import SessionLocal
from app.models.db_models import Chunk, Document


def enrich_chunk_metadata(chunk: Chunk, document: Document) -> dict[str, Any]:
    """Return chunk metadata enriched with stable IDs and document identifiers."""
    metadata: dict[str, Any] = {}
    if chunk.chunk_metadata:
        try:
            loaded = json.loads(chunk.chunk_metadata)
            if isinstance(loaded, dict):
                metadata = loaded
        except json.JSONDecodeError:
            metadata = {}

    metadata.update(
        {
            "document_id": document.id,
            "doc_id": document.doc_id or str(document.id),
            "chunk_id": chunk.id,
            "chunk_index": chunk.chunk_index,
            "document_title": metadata.get("document_title") or document.document_title or document.filename or "",
            "filename": metadata.get("filename") or document.original_filename or document.filename or "",
            "doc_type": metadata.get("doc_type") or document.doc_type or "",
        }
    )
    return enrich_context_identity(metadata)


def backfill_context_ids(dry_run: bool = False) -> dict[str, int]:
    """Backfill all chunks and return a compact summary."""
    db = SessionLocal()
    changed = 0
    scanned = 0
    try:
        rows = (
            db.query(Chunk, Document)
            .join(Document, Chunk.document_id == Document.id)
            .order_by(Document.id, Chunk.chunk_index)
            .all()
        )
        for chunk, document in rows:
            scanned += 1
            enriched = enrich_chunk_metadata(chunk, document)
            serialized = json.dumps(enriched, ensure_ascii=False)
            if chunk.chunk_metadata != serialized:
                changed += 1
                if not dry_run:
                    chunk.chunk_metadata = serialized

        if not dry_run:
            db.commit()
        else:
            db.rollback()

        return {"scanned": scanned, "changed": changed}
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill canonical_context_id/citation_id in chunk metadata")
    parser.add_argument("--dry-run", action="store_true", help="Report changes without writing")
    args = parser.parse_args()

    summary = backfill_context_ids(dry_run=args.dry_run)
    mode = "DRY RUN" if args.dry_run else "UPDATED"
    logger.success(f"{mode}: scanned={summary['scanned']} changed={summary['changed']}")


if __name__ == "__main__":
    main()
