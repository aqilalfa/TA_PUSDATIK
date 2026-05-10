# File 7: `start_full.bat`

## 🎯 Tujuan Perubahan
Ada 2 bug di script startup:
1. Entry point server mengarah ke modul yang tidak ada
2. Menggunakan `python` global, bukan Python dari virtual environment

---

## ❌ Sebelum (Problem)

```bat
:: BUG 1: Modul ini tidak ada di codebase!
python -m uvicorn app.api.server_full:app --host 0.0.0.0 --port 8000
```

Error yang muncul:
```
ERROR: Could not import module "app.api.server_full"
ModuleNotFoundError: No module named 'app.api.server_full'
```

**BUG 2:** Menggunakan perintah `python` tanpa path lengkap.
Masalah: di PowerShell, `call venv\Scripts\activate.bat` tidak selalu "aktif" untuk command berikutnya.
Sehingga `python` yang dipakai adalah Python global sistem — yang **tidak punya package seperti FastAPI, SQLAlchemy, dll**.

Error tambahan:
```
ModuleNotFoundError: No module named 'sqlalchemy'
ModuleNotFoundError: No module named 'fastapi'
```

---

## ✅ Sesudah (Fix)

```bat
:: FIX 1: Entry point yang benar (app.main adalah file yang ada)
:: FIX 2: Path eksplisit ke Python di dalam venv
venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

**Kenapa `venv\Scripts\python.exe` lebih aman?**
- Tidak bergantung pada `activate.bat` yang perilakunya bisa berbeda di CMD vs PowerShell
- Selalu menggunakan Python yang benar dengan semua package terinstall
- Cocok untuk dijalankan dari script `.bat`, PowerShell, atau double-click di Explorer

---

## 📁 Struktur Entry Point yang Benar

```
app/
├── main.py          ← ✅ Entry point BENAR → app.main:app
├── api/
│   ├── server_full.py   ← ❌ TIDAK ADA (file ini tidak pernah dibuat)
│   └── routes/
│       ├── chat.py
│       ├── documents.py
│       └── health.py
```
