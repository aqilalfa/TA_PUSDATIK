# File 5: `backend/app/api/routes/health.py`

## 🎯 Tujuan Perubahan
Fix error "Textual SQL expression should be explicitly declared" yang muncul di health check saat startup.

---

## ❌ Sebelum (Problem)

```python
# Health check database
try:
    db.execute("SELECT 1")    # ← String literal = WARNING di SQLAlchemy 1.x, ERROR di 2.x
    services["database"] = "healthy"
except Exception as e:
    services["database"] = f"unhealthy: {str(e)}"
```

**Error yang muncul:**
```
Textual SQL expression 'SELECT 1' should be explicitly declared 
as text('SELECT 1')
```

**Dampak:**
- Health check selalu menampilkan `database: unhealthy` meski database sebenarnya baik-baik saja
- Overall status jadi `degraded` padahal sistem berfungsi normal
- Membingungkan saat debugging

---

## ✅ Sesudah (Fix)

Tambah import `text` dari SQLAlchemy dan bungkus query:

```python
# Tambah import
from sqlalchemy import text

# Fix query
try:
    db.execute(text("SELECT 1"))   # ← Wrapped dengan text() = benar untuk SQLAlchemy 2.x
    services["database"] = "healthy"
except Exception as e:
    services["database"] = f"unhealthy: {str(e)}"
```

---

## 📋 Hasil Setelah Fix

```json
{
  "status": "healthy",
  "services": {
    "database": "healthy",    ← sekarang benar
    "qdrant": "healthy",
    "llm_model": "missing"    ← normal jika pakai Ollama (bukan file .gguf)
  }
}
```

---

## 💡 Catatan
`llm_model: missing` itu **normal** — sistem dikonfigurasi menggunakan Ollama (model berjalan sebagai service terpisah), bukan file model lokal `.gguf`. Health check mengecek keberadaan file `.gguf` yang memang tidak ada.
