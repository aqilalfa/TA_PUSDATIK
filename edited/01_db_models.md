# File 1: `backend/app/models/db_models.py`

## 🎯 Tujuan Perubahan
Model database SQLAlchemy perlu diperluas agar bisa menyimpan metadata yang dibutuhkan oleh `DocumentManager` — sebelumnya metadata ini disimpan secara terpisah lewat raw SQL.

---

## ❌ Sebelum (Problem)

Model `Document` hanya punya kolom dasar:
```python
class Document(Base):
    id = Column(Integer, primary_key=True)
    filename = Column(String)
    doc_type = Column(String)
    status = Column(String)
    # ... kolom standar saja
```

Model `Chunk` tidak punya `chunk_type`:
```python
class Chunk(Base):
    id = Column(Integer, primary_key=True)
    document_id = Column(Integer)
    chunk_text = Column(Text)
    chunk_metadata = Column(Text)
    # tidak ada chunk_type
```

**Dampak:** `DocumentManager` tidak bisa menyimpan data penting seperti `doc_id`, `document_title`, `file_size`, dst. → data tidak konsisten.

---

## ✅ Sesudah (Fix)

Ditambahkan kolom-kolom berikut ke model `Document`:

| Kolom Baru | Tipe | Fungsi |
|------------|------|--------|
| `doc_id` | String(8) | ID pendek unik (misal: "a1b2c3d4") |
| `document_title` | Text | Judul lengkap dokumen |
| `original_filename` | String | Nama file asli sebelum di-rename |
| `file_size` | Integer | Ukuran file dalam bytes |
| `file_path` | String | Path file di server |
| `chunk_count` | Integer | Jumlah chunk yang dihasilkan |

Ditambahkan ke model `Chunk`:

| Kolom Baru | Tipe | Fungsi |
|------------|------|--------|
| `chunk_type` | String | Tipe chunk (misal: "peraturan", "laporan") |

---

## 💡 Kenapa Ini Penting?
- Kolom-kolom ini dibutuhkan agar halaman "Kelola Dokumen" di frontend bisa menampilkan info lengkap
- Tanpa ini, `DocumentManager` harus query ke raw SQL yang rawan konflik
