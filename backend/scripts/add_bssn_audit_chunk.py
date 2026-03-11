#!/usr/bin/env python3
"""Add synthetic summary chunk for BSSN Audit Keamanan SPBE scope."""
import sys
import re
import uuid
import pickle
import shutil
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

from loguru import logger

COLLECTION = "document_chunks"
DOC_ID = "bssn8_2024"

BSSN_AUDIT_SCOPE_SUMMARY = """Ruang Lingkup dan Objek Audit Keamanan SPBE berdasarkan Peraturan BSSN Nomor 8 Tahun 2024
 
 STANDAR AUDIT KEAMANAN SPBE (Pasal 2):
 Standar terdiri atas objek, pelaksana, kriteria, bukti, dan kesimpulan audit.
 
 RUANG LINGKUP DAN OBJEK AUDIT (Pasal 3):
 Ruang lingkup pelaksanaan Audit Keamanan SPBE mencakup pemeriksaan terhadap 4 (empat) objek utama:
 1. Infrastruktur SPBE Nasional (Pusat Data, Jaringan Intra, Sistem Penghubung Layanan);
 2. Infrastruktur SPBE Instansi Pusat dan Pemerintah Daerah;
 3. Aplikasi Umum; dan
 4. Aplikasi Khusus.
 
 Audit ini juga mencakup pemeriksaan terhadap keamanan data dan informasi yang dikelola di dalam sistem tersebut.
 
 ASPEK PEMERIKSAAN / LINGKUP PROSEDUR (Pasal 10):
 Audit memeriksa 3 aspek substantif:
 a. Perencanaan (kebijakan & prosedur);
 b. Pengembangan (desain kendali); dan
 c. Pengoperasian (implementasi kendali).
 
 PELAKSANA / MANDAT (Pasal 36-37):
 BSSN melaksanakan Audit Keamanan SPBE melalui LATIK pemerintah (BSSN) atau LATIK Terakreditasi. Surat penugasan adalah syarat administratif."""


def main():
    from qdrant_client import QdrantClient
    from qdrant_client.models import PointStruct

    logger.info("Adding BSSN Audit Scope synthetic chunk...")

    client = QdrantClient(host="localhost", port=6333, check_compatibility=False)

    # Load embedding model
    from app.core.rag.embeddings import embedding_manager
    embedding_manager.initialize()

    # Generate embedding
    embedding = embedding_manager.embed_text(BSSN_AUDIT_SCOPE_SUMMARY)

    # Get the doc_id from existing BSSN chunks
    all_chunks = []
    offset = None
    while True:
        points, nxt = client.scroll(COLLECTION, limit=100, offset=offset, with_payload=True)
        all_chunks.extend(points)
        if nxt is None or len(points) == 0:
            break
        offset = nxt

    bssn = [p for p in all_chunks if "bssn" in (p.payload.get("filename", "")).lower()]
    actual_doc_id = bssn[0].payload.get("doc_id", DOC_ID) if bssn else DOC_ID

    # Create point
    chunk_id = str(uuid.uuid4())
    payload = {
        "text": BSSN_AUDIT_SCOPE_SUMMARY,
        "raw_text": BSSN_AUDIT_SCOPE_SUMMARY,
        "chunk_index": 998,
        "context_header": "Ruang Lingkup dan Objek Audit Keamanan SPBE",
        "document_title": "peraturan-bssn-no-8-tahun-2024",
        "filename": "peraturan-bssn-no-8-tahun-2024.pdf",
        "doc_type": "peraturan",
        "bab": "BAB I KETENTUAN UMUM",
        "bagian": "Bagian Kedua Objek Audit Keamanan SPBE",
        "pasal": "2-10",
        "ayat": "",
        "parent_pasal_text": "",
        "is_parent": False,
        "doc_id": actual_doc_id,
        "chunk_type": "synthetic_scope_summary",
        "section": "Standar dan Objek Audit Keamanan SPBE",
        "table_context": "",
        "original_table": "",
    }

    client.upsert(
        collection_name=COLLECTION,
        points=[PointStruct(id=chunk_id, vector=embedding, payload=payload)]
    )
    logger.success(f"Upserted synthetic chunk: {chunk_id[:12]}...")

    # Rebuild BM25
    logger.info("Rebuilding BM25 index...")
    bm25_path = Path(__file__).parent.parent / "data" / "bm25_index.pkl"

    if bm25_path.exists():
        shutil.copy2(bm25_path, bm25_path.with_suffix(".pkl.bak"))

    from rank_bm25 import BM25Okapi

    # Reload all chunks from Qdrant (includes new one)
    all_fresh = []
    offset = None
    while True:
        points, nxt = client.scroll(COLLECTION, limit=100, offset=offset, with_payload=True)
        all_fresh.extend(points)
        if nxt is None or len(points) == 0:
            break
        offset = nxt

    documents = []
    corpus = []
    for p in all_fresh:
        pl = p.payload or {}
        text = pl.get("text", "")
        metadata = {k: v for k, v in pl.items() if k != "text"}
        documents.append({"text": text, "metadata": metadata})
        corpus.append(re.findall(r"\b\w+\b", text.lower()))

    bm25 = BM25Okapi(corpus)
    with open(bm25_path, "wb") as f:
        pickle.dump({"bm25": bm25, "documents": documents}, f)

    logger.success(f"BM25 rebuilt: {len(documents)} documents")
    logger.info("DONE!")


if __name__ == "__main__":
    main()
