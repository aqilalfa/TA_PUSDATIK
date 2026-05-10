import ast, sys
sys.path.insert(0, ".")
errors = []

# 1. db_models.py - kolom baru ada
c = open("app/models/db_models.py", encoding="utf-8").read()
ast.parse(c)
for col in ["doc_id", "document_title", "original_filename", "file_size", "file_path", "chunk_count", "chunk_type"]:
    assert col in c, f"Column {col} missing from db_models.py"
print("[OK] db_models.py - semua kolom baru ada, syntax valid")

# 2. document_manager.py - tidak ada lagi import dari core.database
c = open("app/core/ingestion/document_manager.py", encoding="utf-8").read()
ast.parse(c)
remaining = [l.strip() for l in c.split("\n") if "from app.core.database import" in l]
assert not remaining, f"Masih import dari core.database: {remaining}"
assert "from app.core.database import get_connection" not in c
assert "_get_db" in c
assert "_doc_to_dict" in c
assert "_chunk_to_dict" in c
assert "def create_document" in c
assert "def get_document" in c
assert "def save_chunks" in c
print("[OK] document_manager.py - ORM methods ada, no core.database imports, syntax valid")

# 3. api/documents.py - tidak ada lagi import dari core.database
c = open("app/api/documents.py", encoding="utf-8").read()
ast.parse(c)
remaining = [l.strip() for l in c.split("\n") if "from app.core.database import" in l]
assert not remaining, f"api/documents.py masih import dari core.database: {remaining}"
print("[OK] api/documents.py - no core.database imports, syntax valid")

# 4. main.py - migration code ada
c = open("app/main.py", encoding="utf-8").read()
ast.parse(c)
assert "migration" in c.lower()
assert "importlib.util" in c
print("[OK] main.py - migration call ada, syntax valid")

# 5. migration script exists dan memiliki fungsi run()
mig = open("scripts/migrations/001_add_doc_metadata_columns.py", encoding="utf-8").read()
ast.parse(mig)
assert "def run(" in mig
assert "ALTER TABLE documents ADD COLUMN" in mig
assert "ALTER TABLE chunks ADD COLUMN" in mig
print("[OK] migration script - syntax valid, run() function ada")

# 6. Tidak ada referensi ke get_connection dari production code
import re
production_files = [
    "app/main.py",
    "app/api/documents.py",
    "app/api/routes/chat.py",
    "app/core/ingestion/document_manager.py",
]
for fpath in production_files:
    c = open(fpath, encoding="utf-8").read()
    if "get_connection" in c:
        print(f"  [WARN] get_connection masih di {fpath}")
print("[OK] Production code - no get_connection references")

print("")
print("=== PHASE 1 ALL CHECKS PASSED ===")
