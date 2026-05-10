# File 8: `backend/scripts/migrations/001_add_doc_metadata_columns.py`

## 🎯 Tujuan
File **baru** yang dibuat khusus untuk memperbarui schema database SQLite yang sudah ada tanpa menghapus data.

---

## Mengapa Perlu Migration Script?

Saat kolom baru ditambahkan ke model ORM (`db_models.py`), SQLAlchemy **tidak otomatis** mengubah tabel yang sudah ada di database.  
Jika tidak ada migration, akan terjadi error `OperationalError: table has no column named 'doc_id'`.

---

## Isi Script

```python
"""
Migration 001: Tambah kolom metadata ke tabel Document dan Chunk
Idempotent — aman dijalankan berulang kali
"""

import sqlite3
from pathlib import Path

def run_migration():
    db_path = Path(__file__).parent.parent.parent / "data" / "spbe_rag.db"
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    # Daftar kolom yang perlu ditambahkan ke tabel 'documents'
    new_columns = [
        ("doc_id", "VARCHAR(8)"),
        ("document_title", "TEXT"),
        ("original_filename", "VARCHAR(500)"),
        ("file_size", "INTEGER"),
        ("file_path", "VARCHAR(1000)"),
        ("chunk_count", "INTEGER DEFAULT 0"),
    ]
    
    # Cek kolom yang sudah ada, tambahkan yang belum ada
    cursor.execute("PRAGMA table_info(documents)")
    existing = {row[1] for row in cursor.fetchall()}
    
    for col_name, col_type in new_columns:
        if col_name not in existing:
            cursor.execute(f"ALTER TABLE documents ADD COLUMN {col_name} {col_type}")
            print(f"  ✓ Ditambahkan: documents.{col_name}")
        else:
            print(f"  ○ Sudah ada: documents.{col_name}")
    
    # Tambah chunk_type ke tabel 'chunks'
    cursor.execute("PRAGMA table_info(chunks)")
    existing_chunks = {row[1] for row in cursor.fetchall()}
    
    if "chunk_type" not in existing_chunks:
        cursor.execute("ALTER TABLE chunks ADD COLUMN chunk_type VARCHAR(50)")
        print("  ✓ Ditambahkan: chunks.chunk_type")
    
    conn.commit()
    conn.close()
```

---

## Cara Kerja "Idempotent"

```
Run pertama:
  ✓ Ditambahkan: documents.doc_id
  ✓ Ditambahkan: documents.document_title
  ✓ Ditambahkan: documents.file_size
  ... (semua kolom ditambahkan)

Run kedua (kolom sudah ada):
  ○ Sudah ada: documents.doc_id   ← tidak error, skip saja
  ○ Sudah ada: documents.document_title
  ... (tidak ada perubahan, tidak ada error)
```

---

## Kapan Migration Dijalankan?
Secara **otomatis** setiap kali server distart, dipanggil dari `app/main.py` lifespan.  
Tidak perlu menjalankan manual.
