# File 4: `backend/app/api/documents.py`

## 🎯 Tujuan Perubahan
Menghapus ketergantungan langsung API route ke `app.core.database` (raw SQL layer), dan menggantinya dengan pemanggilan melalui `DocumentManager`.

---

## ❌ Sebelum (Problem)

```python
# Import langsung dari database layer lama
from app.core.database import get_connection, execute_query

@router.get("/")
def list_documents():
    conn = get_connection()        # raw SQL!
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM documents")
    rows = cursor.fetchall()
    conn.close()
    return rows
```

**Masalah:**
- API route "tahu terlalu banyak" tentang database → violasi Separation of Concerns
- Jika struktur database berubah → harus update di 2 tempat (database.py DAN documents.py)
- Tidak bisa unit test tanpa koneksi database nyata

---

## ✅ Sesudah (Fix)

```python
# Semua database operation lewat DocumentManager
from app.core.ingestion.document_manager import document_manager

@router.get("/")
def list_documents():
    docs = document_manager.list_documents()   # ORM via DocumentManager
    return docs

@router.delete("/{doc_id}")
def delete_document(doc_id: str):
    success = document_manager.delete_document(doc_id)
    if not success:
        raise HTTPException(status_code=404)
    return {"status": "deleted"}
```

---

## 🏗️ Arsitektur Sesudah (yang benar)

```
Request
  ↓
API Route (documents.py)
  ↓
DocumentManager (business logic)
  ↓
SQLAlchemy ORM (db_models.py)
  ↓
SQLite Database
```

Sebelumnya ada shortcut berbahaya:
```
Request
  ↓
API Route ──────────────→ raw SQL (langsung ke database!)
  ↓
DocumentManager → ORM
  ↓
Database

← 2 jalur berbeda ke 1 database = risiko konflik!
```
