# File 3: `backend/app/core/ingestion/document_manager.py`

## 🎯 Tujuan Perubahan
Ini adalah perubahan **terbesar dan terpenting** dalam Phase 1. Mengganti semua operasi database yang menggunakan raw SQL (`get_connection()`) dengan SQLAlchemy ORM.

---

## ❌ Sebelum (Problem)

`DocumentManager.__init__` melakukan assignment fungsi raw SQL:
```python
def __init__(self):
    # 10+ baris seperti ini:
    self.get_document = db_functions.get_document_by_id     # RAW SQL
    self.list_documents = db_functions.list_all_documents   # RAW SQL
    self.create_document = db_functions.create_document     # RAW SQL
    self.delete_document = db_functions.delete_document     # RAW SQL
    # dst...
```

Dan `sync_from_qdrant` langsung pakai koneksi raw:
```python
def sync_from_qdrant(self):
    conn = get_connection()   # raw SQL connection!
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM documents")  # SQL mentah
    ...
```

**Masalah:**
- Database diakses via **2 jalur parallel** → risiko data korup
- Kalau SQLAlchemy dan raw SQL bersamaan → transaction conflict
- Sulit debug karena tidak ada type checking

---

## ✅ Sesudah (Fix)

Semua method diganti menjadi ORM native:

```python
def get_document(self, doc_id: str):
    """Ambil dokumen via ORM."""
    db = self._get_db()
    try:
        return db.query(Document).filter(Document.doc_id == doc_id).first()
    finally:
        db.close()

def list_documents(self) -> list:
    """List semua dokumen via ORM."""
    db = self._get_db()
    try:
        return db.query(Document).order_by(Document.created_at.desc()).all()
    finally:
        db.close()

def sync_from_qdrant(self):
    """Sinkronisasi via ORM — tidak ada raw SQL."""
    db = self._get_db()
    try:
        existing = {d.doc_id for d in db.query(Document).all()}
        # ... operasi ORM
    finally:
        db.close()
```

---

## 📊 Daftar Method yang Direfactor

| Method | Sebelum | Sesudah |
|--------|---------|---------|
| `get_document` | raw SQL via assignment | ORM query |
| `list_documents` | raw SQL | ORM query |
| `create_document` | raw SQL INSERT | `db.add(Document(...))` |
| `update_document` | raw SQL UPDATE | `doc.field = value; db.commit()` |
| `delete_document` | raw SQL DELETE | `db.delete(doc); db.commit()` |
| `get_chunks` | raw SQL | ORM relationship |
| `get_chunk_count` | raw SQL COUNT | `db.query(Chunk).count()` |
| `update_chunk` | raw SQL | ORM update |
| `delete_chunk` | raw SQL | ORM delete |
| `sync_from_qdrant` | `get_connection()` + cursor | SessionLocal() ORM |

---

## 💡 Prinsip Desain
- **Interface tidak berubah**: nama method dan return type sama persis → tidak ada breaking change untuk kode lain
- **Session management eksplisit**: setiap method buka dan tutup session sendiri dengan `try/finally`
- **Error handling**: rollback otomatis jika ada exception
