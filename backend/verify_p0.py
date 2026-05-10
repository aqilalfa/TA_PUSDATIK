import ast, sys
sys.path.insert(0, ".")
errors = []

from app.config import settings
assert settings.QDRANT_COLLECTION == "document_chunks"
print("[OK] config.py:", settings.QDRANT_COLLECTION)

c = open("app/api/routes/chat.py", encoding="utf-8").read()
ast.parse(c)
assert "from loguru import logger" in c
assert "get_default_model" in c
assert "session_id = request.session_id" in c
assert "request.session_id = new_session.id" not in c
print("[OK] chat.py - logger, get_default_model, local session_id, no mutation")

c = open("app/core/ingestion/document_manager.py", encoding="utf-8").read()
ast.parse(c)
assert "from app.config import settings" in c
assert "except ImportError:" in c
hc = [l.strip() for l in c.split("\n") if '"document_chunks"' in l and not l.strip().startswith("#")]
assert not hc, f"Hardcoded masih: {hc}"
print("[OK] document_manager.py - settings, try/except, no hardcode")

c = open("app/api/documents.py", encoding="utf-8").read()
ast.parse(c)
assert "from app.config import settings" in c
hc = [l.strip() for l in c.split("\n") if '"document_chunks"' in l and not l.strip().startswith("#")]
assert not hc, f"Hardcoded masih: {hc}"
print("[OK] api/documents.py - settings, no hardcode")

c = open("app/main.py", encoding="utf-8").read()
ast.parse(c)
assert "doc_mgmt_router" in c
assert "documents, models" not in c
assert "default_user" in c
assert "SessionLocal" in c
print("[OK] main.py - doc_mgmt_router mounted, ensure_default_user, SessionLocal")

print("")
print("=== FASE 0 VERIFIED - ALL CHECKS PASSED ===")
