"""
SQLite Database Setup for Document Management
Stores document metadata and processing status
"""

import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any
import json
from loguru import logger

# Database path - use same database as SQLAlchemy ORM (spbe_rag.db)
DB_PATH = Path(__file__).parent.parent.parent / "data" / "spbe_rag.db"


def get_connection() -> sqlite3.Connection:
    """Get database connection with row factory."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_database():
    """Initialize database tables."""
    conn = get_connection()
    cursor = conn.cursor()

    # Documents table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            doc_id TEXT UNIQUE NOT NULL,
            filename TEXT NOT NULL,
            original_filename TEXT NOT NULL,
            document_title TEXT,
            doc_type TEXT DEFAULT 'other',
            file_size INTEGER DEFAULT 0,
            file_path TEXT,
            status TEXT DEFAULT 'uploaded',
            chunk_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            processed_at TIMESTAMP,
            error_message TEXT
        )
    """)

    # Chunks table (for preview before indexing)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chunks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            doc_id TEXT NOT NULL,
            chunk_index INTEGER NOT NULL,
            text TEXT NOT NULL,
            raw_text TEXT,
            context_header TEXT,
            bab TEXT,
            bagian TEXT,
            pasal TEXT,
            ayat TEXT,
            parent_pasal_text TEXT,
            is_parent BOOLEAN DEFAULT 0,
            is_indexed BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (doc_id) REFERENCES documents(doc_id) ON DELETE CASCADE
        )
    """)

    # Index for faster queries
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_chunks_doc_id ON chunks(doc_id)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(status)
    """)

    conn.commit()
    conn.close()


# ============== Document Operations ==============


def create_document(
    doc_id: str,
    filename: str,
    original_filename: str,
    file_size: int,
    file_path: str,
) -> Dict[str, Any]:
    """Create a new document record."""
    conn = get_connection()
    cursor = conn.cursor()

    # Extract title from filename
    document_title = Path(original_filename).stem.replace("_", " ").replace("-", " ")

    cursor.execute(
        """
        INSERT INTO documents (doc_id, filename, original_path, document_title, file_size, status)
        VALUES (?, ?, ?, ?, ?, 'uploaded')
    """,
        (doc_id, original_filename, file_path, document_title, file_size),
    )

    conn.commit()

    # Fetch the created document
    cursor.execute("SELECT * FROM documents WHERE doc_id = ?", (doc_id,))
    row = cursor.fetchone()
    conn.close()

    return dict(row) if row else {}


def get_document(doc_id: str) -> Optional[Dict[str, Any]]:
    """Get document by doc_id."""
    conn = get_connection()
    cursor = conn.cursor()

    try:
        # First try by doc_id directly
        cursor.execute(
            """
            SELECT id, doc_id, filename as original_filename, filename,
                   document_title, doc_type, file_size,
                   original_path as file_path, status,
                   chunk_count, uploaded_at as created_at, 
                   processed_at, error_message
            FROM documents
            WHERE doc_id = ?
        """,
            (doc_id,),
        )
        row = cursor.fetchone()

        # If not found, try by integer id
        if not row and doc_id.isdigit():
            cursor.execute(
                """
                SELECT id, COALESCE(doc_id, CAST(id AS TEXT)) as doc_id, 
                       filename as original_filename, filename,
                       document_title, doc_type, COALESCE(file_size, 0) as file_size,
                       original_path as file_path, status,
                       COALESCE(chunk_count, 0) as chunk_count, 
                       uploaded_at as created_at, 
                       processed_at, error_message
                FROM documents
                WHERE id = ?
            """,
                (int(doc_id),),
            )
            row = cursor.fetchone()

        if row:
            result = dict(row)
            conn.close()
            return result
    except Exception as e:
        logger.warning(f"get_document failed: {e}")

    conn.close()
    return None


def get_all_documents() -> List[Dict[str, Any]]:
    """Get all documents with live chunk counts from chunks table."""
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT d.id, COALESCE(d.doc_id, CAST(d.id AS TEXT)) as doc_id, 
                   d.filename as original_filename, d.filename,
                   COALESCE(d.document_title, d.filename) as document_title,
                   d.doc_type, 
                   COALESCE(d.file_size, 0) as file_size,
                   d.original_path as file_path, d.status,
                   COALESCE(c_count.cnt, 0) as chunk_count,
                   d.uploaded_at as created_at, d.processed_at, d.error_message
            FROM documents d
            LEFT JOIN (
                SELECT document_id, COUNT(*) as cnt 
                FROM chunks 
                GROUP BY document_id
            ) c_count ON c_count.document_id = d.id
            ORDER BY d.uploaded_at DESC
        """)
        rows = cursor.fetchall()
    except Exception as e:
        logger.warning(f"get_all_documents failed: {e}")
        rows = []

    conn.close()

    # Post-process: compute file_size from disk if stored value is 0
    results = []
    for row in rows:
        d = dict(row)
        if d.get("file_size", 0) == 0 and d.get("file_path"):
            try:
                p = Path(d["file_path"])
                if p.exists():
                    d["file_size"] = p.stat().st_size
            except Exception:
                pass
        results.append(d)

    return results


def update_document(doc_id: str, **kwargs) -> bool:
    """Update document fields by doc_id."""
    if not kwargs:
        return False

    conn = get_connection()
    cursor = conn.cursor()

    try:
        # Map legacy field names to actual DB columns
        field_mapping = {
            "original_filename": "filename",
            "file_path": "original_path",
        }

        mapped_kwargs = {}
        for k, v in kwargs.items():
            mapped_key = field_mapping.get(k, k)
            mapped_kwargs[mapped_key] = v

        set_clause = ", ".join([f"{k} = ?" for k in mapped_kwargs.keys()])
        values = list(mapped_kwargs.values())

        # Always use doc_id column for lookup (primary identifier)
        values.append(doc_id)
        cursor.execute(
            f"UPDATE documents SET {set_clause} WHERE doc_id = ?",
            values,
        )

        # Fallback: try by integer id if doc_id is numeric and no rows matched
        if cursor.rowcount == 0 and doc_id.isdigit():
            values[-1] = int(doc_id)
            cursor.execute(
                f"UPDATE documents SET {set_clause} WHERE id = ?",
                values,
            )

        conn.commit()
        affected = cursor.rowcount
        if affected == 0:
            logger.warning(f"update_document: no rows matched for doc_id={doc_id}")
    except Exception as e:
        logger.warning(f"update_document failed: {e}")
        affected = 0

    conn.close()
    return affected > 0


def delete_document(doc_id: str) -> bool:
    """Delete document and its chunks.

    Args:
        doc_id: Can be integer id as string ("1", "2") or doc_id string ("a1b2c3d4")

    Returns:
        True if document was deleted, False otherwise
    """
    conn = get_connection()
    cursor = conn.cursor()

    try:
        # Cari dokumen dengan berbagai cara:
        # 1. doc_id column match
        # 2. id column match (jika doc_id adalah angka)
        cursor.execute(
            """
            SELECT id FROM documents 
            WHERE doc_id = ? OR CAST(id AS TEXT) = ?
            LIMIT 1
            """,
            (doc_id, doc_id),
        )
        doc_row = cursor.fetchone()

        if not doc_row:
            logger.warning(f"Document not found for deletion: {doc_id}")
            conn.close()
            return False

        document_id = doc_row[0]
        logger.info(f"Deleting document id={document_id} (doc_id={doc_id})")

        # Delete chunks first (menggunakan document_id integer)
        cursor.execute("DELETE FROM chunks WHERE document_id = ?", (document_id,))
        chunks_deleted = cursor.rowcount
        logger.info(f"Deleted {chunks_deleted} chunks from database")

        # Delete document
        cursor.execute("DELETE FROM documents WHERE id = ?", (document_id,))
        doc_deleted = cursor.rowcount

        conn.commit()
        logger.info(f"Document {doc_id} deleted successfully")

        return doc_deleted > 0

    except Exception as e:
        logger.error(f"delete_document failed: {e}")
        conn.close()
        return False

    conn.close()
    return True


# ============== Chunk Operations ==============


def save_chunks(doc_id: str, chunks: List[Dict[str, Any]]) -> int:
    """Save chunks for a document (preview stage)."""
    conn = get_connection()
    cursor = conn.cursor()

    # Get document_id (integer) from doc_id
    cursor.execute(
        "SELECT id FROM documents WHERE doc_id = ? OR CAST(id AS TEXT) = ?",
        (doc_id, doc_id),
    )
    doc_row = cursor.fetchone()
    if not doc_row:
        conn.close()
        raise ValueError(f"Document not found: {doc_id}")

    document_id = doc_row[0]

    # Clear existing chunks for this document
    cursor.execute("DELETE FROM chunks WHERE document_id = ?", (document_id,))

    # Insert new chunks (using SQLAlchemy schema)
    for i, chunk in enumerate(chunks):
        # Build metadata JSON
        meta = {
            "context_header": chunk.get("context_header", ""),
            "bab": chunk.get("bab", ""),
            "bagian": chunk.get("bagian", ""),
            "pasal": chunk.get("pasal", ""),
            "ayat": chunk.get("ayat", ""),
            "parent_pasal_text": chunk.get("parent_pasal_text", ""),
            "is_parent": chunk.get("is_parent", False),
        }

        cursor.execute(
            """
            INSERT INTO chunks (document_id, chunk_index, chunk_text, chunk_metadata)
            VALUES (?, ?, ?, ?)
        """,
            (
                document_id,
                i,
                chunk.get("text", ""),
                json.dumps(meta),
            ),
        )

    # Update document chunk count
    cursor.execute(
        "UPDATE documents SET chunk_count = ? WHERE id = ?",
        (len(chunks), document_id),
    )

    conn.commit()
    conn.close()

    return len(chunks)


def get_chunks(doc_id: str, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
    """Get chunks for a document."""
    conn = get_connection()
    cursor = conn.cursor()

    try:
        # First try to find document by doc_id column
        cursor.execute(
            """
            SELECT id FROM documents 
            WHERE doc_id = ? OR CAST(id AS TEXT) = ?
            LIMIT 1
        """,
            (doc_id, doc_id),
        )
        doc_row = cursor.fetchone()

        if doc_row:
            document_id = doc_row[0]
            cursor.execute(
                """
                SELECT c.id, c.chunk_index, c.chunk_text as text, c.chunk_metadata,
                       c.chunk_text as raw_text, '' as context_header,
                       '' as bab, '' as bagian, '' as pasal, '' as ayat,
                       '' as parent_pasal_text, 0 as is_parent, 1 as is_indexed
                FROM chunks c
                WHERE c.document_id = ?
                ORDER BY c.chunk_index
                LIMIT ? OFFSET ?
            """,
                (document_id, limit, offset),
            )
            rows = cursor.fetchall()
        else:
            rows = []
    except Exception as e:
        logger.warning(f"get_chunks failed: {e}")
        rows = []

    conn.close()

    # Parse metadata from JSON if available
    result = []
    for row in rows:
        chunk_dict = dict(row)
        # Try to extract fields from chunk_metadata JSON
        if chunk_dict.get("chunk_metadata"):
            try:
                meta = json.loads(chunk_dict["chunk_metadata"])
                chunk_dict["pasal"] = str(meta.get("pasal", ""))
                chunk_dict["ayat"] = str(meta.get("ayat", ""))
                chunk_dict["bab"] = str(meta.get("bab", ""))
                chunk_dict["bagian"] = str(meta.get("bagian", ""))
                chunk_dict["context_header"] = meta.get(
                    "context_header", ""
                ) or meta.get("hierarchy", "")
                chunk_dict["is_parent"] = meta.get("is_parent", False)
            except:
                pass
        result.append(chunk_dict)

    return result


def get_chunk_count(doc_id: str) -> int:
    """Get chunk count for a document."""
    conn = get_connection()
    cursor = conn.cursor()

    try:
        # Find document by doc_id or integer id
        cursor.execute(
            "SELECT id FROM documents WHERE doc_id = ? OR CAST(id AS TEXT) = ? LIMIT 1",
            (doc_id, doc_id),
        )
        doc_row = cursor.fetchone()
        if doc_row:
            cursor.execute(
                "SELECT COUNT(*) FROM chunks WHERE document_id = ?", (doc_row[0],)
            )
            count = cursor.fetchone()[0]
        else:
            count = 0
    except Exception as e:
        logger.warning(f"get_chunk_count failed: {e}")
        count = 0

    conn.close()
    return count


def mark_chunks_indexed(doc_id: str) -> int:
    """Mark all chunks as indexed (no-op in SQLAlchemy schema, chunks are always indexed)."""
    # In SQLAlchemy schema, there's no is_indexed column
    # Chunks are indexed immediately during ingestion
    logger.debug(
        f"mark_chunks_indexed called for doc_id={doc_id} (no-op in SQLAlchemy schema)"
    )
    return get_chunk_count(doc_id)


def update_chunk(chunk_id: int, text: str) -> bool:
    """Update a single chunk's text using SQLAlchemy schema."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE chunks SET chunk_text = ? WHERE id = ?
    """,
        (text, chunk_id),
    )
    conn.commit()
    affected = cursor.rowcount
    conn.close()
    return affected > 0


def delete_chunk(chunk_id: int) -> bool:
    """Delete a single chunk."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM chunks WHERE id = ?", (chunk_id,))
    conn.commit()
    affected = cursor.rowcount
    conn.close()
    return affected > 0


# Initialize database on module import
# Disabled: Tables already exist with SQLAlchemy ORM schema
# init_database()
