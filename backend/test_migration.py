import sys
sys.path.insert(0, ".")

# Test migration module dapat diimport
from scripts.migrations import migration_001
print("[OK] migration_001 can be imported")

# Test db_models syntax
import ast
c = open("app/models/db_models.py", encoding="utf-8").read()
ast.parse(c)
assert "doc_id" in c
assert "document_title" in c
assert "file_size" in c
assert "chunk_count" in c
assert "original_filename" in c
print("[OK] db_models.py - all new columns present, syntax valid")

# Test main.py has migration call
c = open("app/main.py", encoding="utf-8").read()
ast.parse(c)
assert "migration_001" in c
assert "db_path = engine.url.database" in c
print("[OK] main.py - migration call present, syntax valid")

print("")
print("=== PHASE 1 STEP 1-3 VERIFIED ===")
