"""
Migration 001: Tambah kolom metadata ke tabel documents dan chunks
yang dibutuhkan oleh DocumentManager.

Dijalankan otomatis dari main.py startup.
Aman dijalankan berulang kali (idempotent via PRAGMA table_info check).
"""

import sqlite3
from pathlib import Path
from loguru import logger


def run(db_path: str) -> bool:
    """
    Jalankan migration: tambah kolom baru ke tabel documents dan chunks.
    Aman dijalankan berulang kali — cek eksistensi kolom dulu.

    Args:
        db_path: Path ke file SQLite (spbe_rag.db)

    Returns:
        True jika sukses
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # ── Documents table ──────────────────────────────────────────────
        cursor.execute("PRAGMA table_info(documents)")
        existing_doc_cols = {row[1] for row in cursor.fetchall()}

        doc_columns_to_add = [
            ("doc_id",           "TEXT"),
            ("document_title",   "TEXT"),
            ("original_filename","TEXT"),
            ("file_size",        "INTEGER DEFAULT 0"),
            ("file_path",        "TEXT"),
            ("chunk_count",      "INTEGER DEFAULT 0"),
        ]

        added_doc = []
        for col_name, col_def in doc_columns_to_add:
            if col_name not in existing_doc_cols:
                cursor.execute(f"ALTER TABLE documents ADD COLUMN {col_name} {col_def}")
                added_doc.append(col_name)

        # Buat unique index untuk doc_id (SQLite tidak support ADD CONSTRAINT setelah CREATE)
        cursor.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_documents_doc_id ON documents(doc_id)
        """)

        if added_doc:
            logger.success(f"Migration 001: Added columns to documents: {added_doc}")
        else:
            logger.debug("Migration 001: documents table sudah up-to-date")

        # ── Chunks table ─────────────────────────────────────────────────
        cursor.execute("PRAGMA table_info(chunks)")
        existing_chunk_cols = {row[1] for row in cursor.fetchall()}

        chunk_columns_to_add = [
            ("chunk_type", "TEXT DEFAULT 'text'"),
        ]

        added_chunk = []
        for col_name, col_def in chunk_columns_to_add:
            if col_name not in existing_chunk_cols:
                cursor.execute(f"ALTER TABLE chunks ADD COLUMN {col_name} {col_def}")
                added_chunk.append(col_name)

        if added_chunk:
            logger.success(f"Migration 001: Added columns to chunks: {added_chunk}")
        else:
            logger.debug("Migration 001: chunks table sudah up-to-date")

        conn.commit()
        return True

    except Exception as e:
        logger.error(f"Migration 001 failed: {e}")
        conn.rollback()
        return False

    finally:
        conn.close()


if __name__ == "__main__":
    # Bisa dijalankan langsung: python scripts/migrations/001_add_doc_metadata_columns.py
    import sys

    db_path = Path(__file__).parent.parent.parent / "data" / "spbe_rag.db"
    if not db_path.exists():
        print(f"Database tidak ditemukan: {db_path}")
        sys.exit(1)

    print(f"Running migration on: {db_path}")
    success = run(str(db_path))
    sys.exit(0 if success else 1)
