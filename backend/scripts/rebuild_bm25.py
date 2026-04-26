#!/usr/bin/env python3
"""
Rebuild BM25 index from existing chunks in database.
Run this after re-ingestion or when BM25 format needs updating.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import SessionLocal
from app.models.db_models import Chunk
from loguru import logger
import pickle
import json
import re


def tokenize(text: str):
    text = text.lower()
    return re.findall(r"\b\w+\b", text)


def build_bm25_search_text(text: str, metadata: dict) -> str:
    """Compose lexical search text for BM25 using chunk content + structural metadata.

    Excludes document-level fields (judul_dokumen, filename, doc_type) that are
    identical across all chunks of a document — they inflate term frequency without
    adding discriminative value and hurt BM25 IDF scores.
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


def rebuild_bm25():
    """Rebuild BM25 index with proper format for server_full.py"""
    from rank_bm25 import BM25Okapi

    logger.info("Rebuilding BM25 index...")

    db = SessionLocal()
    try:
        chunks = db.query(Chunk).all()

        if not chunks:
            logger.warning("No chunks found!")
            return

        logger.info(f"Found {len(chunks)} chunks")

        # Build documents list with metadata
        documents = []
        corpus = []

        for c in chunks:
            # Parse chunk_metadata JSON
            metadata = {}
            if c.chunk_metadata:
                try:
                    metadata = json.loads(c.chunk_metadata)
                except:
                    pass

            text = c.chunk_text or ""
            search_text = build_bm25_search_text(text, metadata)

            documents.append({"text": text, "metadata": metadata})
            corpus.append(tokenize(search_text))

        # Build BM25 index
        bm25 = BM25Okapi(corpus)

        # Save
        bm25_path = Path(__file__).parent.parent / "data" / "bm25_index.pkl"
        with open(bm25_path, "wb") as f:
            pickle.dump({"bm25": bm25, "documents": documents}, f)

        logger.success(f"BM25 index rebuilt: {len(documents)} documents")
        logger.info(f"Saved to: {bm25_path}")

        # Verify
        with open(bm25_path, "rb") as f:
            data = pickle.load(f)
        logger.info(f"Verified keys: {list(data.keys())}")
        if data.get("documents"):
            sample = data["documents"][0]
            logger.info(f"Sample document keys: {list(sample.keys())}")
            logger.info(
                f"Sample metadata keys: {list(sample.get('metadata', {}).keys())}"
            )

    finally:
        db.close()


if __name__ == "__main__":
    rebuild_bm25()
