# File 2: `backend/app/main.py`

## 🎯 Tujuan Perubahan
Menjalankan **migration database secara otomatis** saat server startup, sehingga kolom-kolom baru yang ditambahkan di `db_models.py` langsung tersedia tanpa perlu menjalankan script manual.

---

## ❌ Sebelum (Problem)

Startup biasa tanpa migration:
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # ... langsung initialize RAG engine
    yield
```

**Dampak:** Jika kolom baru ditambahkan ke ORM tapi database lama tidak diupdate → error `column not found` saat runtime.

---

## ✅ Sesudah (Fix)

Ditambahkan blok migration di awal lifespan menggunakan `importlib` (bukan `import` biasa) untuk menghindari circular dependency:

```python
@asynccontextmanager  
async def lifespan(app: FastAPI):
    # STEP 1: Jalankan migration dulu
    try:
        import importlib.util
        migration_path = Path(__file__).parent.parent / "scripts/migrations/001_add_doc_metadata_columns.py"
        spec = importlib.util.spec_from_file_location("migration_001", migration_path)
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        migration.run_migration()
        logger.info("Migration 001 selesai")
    except Exception as e:
        logger.warning(f"Migration skip: {e}")
    
    # STEP 2: Baru initialize RAG engine seperti biasa
    await langchain_engine.preload()
    yield
```

---

## 💡 Kenapa Pakai `importlib` Bukan `import` Biasa?

Jika menggunakan `import app.scripts.migrations.001_add_doc_metadata_columns`, Python akan error karena:
1. Nama file dimulai angka (`001_`) → tidak valid sebagai modul Python
2. Berpotensi circular import jika migration import dari `app.*`

`importlib` memuat file secara langsung berdasarkan path → lebih aman.

---

## 🛡️ Sifat Migration: Idempotent
Migration dirancang **aman dijalankan berulang kali** — jika kolom sudah ada, tidak akan error (menggunakan `ALTER TABLE ... IF NOT EXISTS` atau cek manual).
