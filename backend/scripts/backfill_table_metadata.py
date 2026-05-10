#!/usr/bin/env python3
"""Backfill ``is_table`` / ``table_label`` metadata on existing chunks.

Runs the same heuristic that ``structured_chunker`` uses during fresh ingestion,
but applied to already-indexed chunks in SQLite. After running this, rerun
``rebuild_bm25.py`` and ``sync_vectors.py --force`` so BM25 and Qdrant pick up
the new metadata.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger

from app.core.ingestion.structured_chunker import _detect_table_label, _is_table_like_text
from app.database import SessionLocal
from app.models.db_models import Chunk


def backfill(dry_run: bool = False) -> None:
    db = SessionLocal()
    try:
        chunks = db.query(Chunk).all()
        logger.info(f"Scanning {len(chunks)} chunks...")

        updated = 0
        flagged = 0
        labeled = 0

        for chunk in chunks:
            meta = {}
            if chunk.chunk_metadata:
                try:
                    meta = json.loads(chunk.chunk_metadata)
                except json.JSONDecodeError:
                    logger.warning(f"Chunk {chunk.id}: invalid JSON metadata, skipping")
                    continue

            text = chunk.chunk_text or ""
            looks_table = _is_table_like_text(text)
            label = _detect_table_label(text)

            changed = False
            if looks_table and not meta.get("is_table"):
                meta["is_table"] = True
                flagged += 1
                changed = True
            if label and meta.get("table_label") != label:
                meta["table_label"] = label
                labeled += 1
                changed = True

            if changed:
                updated += 1
                if not dry_run:
                    chunk.chunk_metadata = json.dumps(meta, ensure_ascii=False)
                    if looks_table and chunk.chunk_type != "table":
                        chunk.chunk_type = "table"

        if dry_run:
            logger.info(
                f"[DRY RUN] Would update {updated} chunks "
                f"(flagged={flagged}, labeled={labeled})"
            )
        else:
            db.commit()
            logger.success(
                f"Updated {updated} chunks (flagged={flagged}, labeled={labeled})"
            )
            logger.info(
                "Next steps: run `python backend/scripts/rebuild_bm25.py` "
                "and `python backend/scripts/sync_vectors.py --force`."
            )
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    args = parser.parse_args()
    backfill(dry_run=args.dry_run)
