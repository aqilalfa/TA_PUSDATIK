#!/usr/bin/env python3
"""
Sync all database chunks to Qdrant vector store
Rebuilds the entire vector index from scratch
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import SessionLocal
from app.models.db_models import Document, Chunk
from app.config import settings
from loguru import logger
import json

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
import uuid


def sync_vectors(force_rebuild: bool = False):
    """Sync all chunks from database to Qdrant"""

    logger.info("=" * 60)
    logger.info("SPBE RAG - Vector Store Sync")
    logger.info("=" * 60)

    db = SessionLocal()

    try:
        # Get current state
        total_chunks = db.query(Chunk).count()
        logger.info(f"Database chunks: {total_chunks}")

        # Connect to Qdrant with longer timeout
        client = QdrantClient(
            url=settings.QDRANT_URL,
            timeout=60,  # 60 second timeout
        )

        # Check if collection exists
        collections = client.get_collections()
        collection_names = [c.name for c in collections.collections]

        qdrant_count = 0
        if settings.QDRANT_COLLECTION in collection_names:
            info = client.get_collection(settings.QDRANT_COLLECTION)
            qdrant_count = info.points_count
            logger.info(f"Qdrant vectors: {qdrant_count}")
        else:
            logger.info("Collection does not exist, will create")

        # Check if sync needed
        if qdrant_count == total_chunks and not force_rebuild:
            logger.success("✓ Already in sync!")
            return

        logger.warning(f"Sync needed: DB={total_chunks}, Qdrant={qdrant_count}")

        # Delete collection if exists
        if settings.QDRANT_COLLECTION in collection_names:
            logger.info("Deleting old collection...")
            client.delete_collection(settings.QDRANT_COLLECTION, timeout=30)

        # Initialize embedding model
        from app.core.rag.embeddings import embedding_manager

        embed_dim = embedding_manager.get_embedding_dim()
        logger.info(f"Embedding dimension: {embed_dim}")

        # Create new collection
        logger.info("Creating collection...")
        client.create_collection(
            collection_name=settings.QDRANT_COLLECTION,
            vectors_config=VectorParams(
                size=embed_dim,
                distance=Distance.COSINE,
            ),
            timeout=30,
        )
        logger.success("✓ Collection created")

        # Process each document
        documents = db.query(Document).all()
        total_indexed = 0

        for doc in documents:
            chunks = db.query(Chunk).filter(Chunk.document_id == doc.id).all()

            if not chunks:
                continue

            logger.info(f"Indexing: {doc.filename} ({len(chunks)} chunks)")

            texts = [c.chunk_text for c in chunks]
            metadatas = []

            for c in chunks:
                meta = json.loads(c.chunk_metadata) if c.chunk_metadata else {}
                meta["document_id"] = doc.id
                meta["chunk_id"] = c.id
                meta["doc_type"] = doc.doc_type
                meta["filename"] = doc.filename
                metadatas.append(meta)

            # Generate embeddings
            logger.info(f"  Generating embeddings for {len(texts)} chunks...")
            embeddings = embedding_manager.embed_texts(texts)

            # Create points
            points = []
            for i, (text, meta, emb) in enumerate(zip(texts, metadatas, embeddings)):
                point_id = str(uuid.uuid4())
                payload = {"text": text, **meta}
                points.append(PointStruct(id=point_id, vector=emb, payload=payload))

            # Upload to Qdrant
            client.upsert(
                collection_name=settings.QDRANT_COLLECTION,
                points=points,
                wait=True,
            )

            total_indexed += len(points)
            logger.success(f"  ✓ Indexed {len(points)} chunks")

        # Verify
        info = client.get_collection(settings.QDRANT_COLLECTION)
        logger.info("=" * 60)
        logger.success(f"✓ Sync complete! Qdrant now has {info.points_count} vectors")
        logger.info("=" * 60)

    finally:
        db.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--force", action="store_true", help="Force rebuild even if counts match"
    )
    args = parser.parse_args()

    sync_vectors(force_rebuild=args.force)
