from pathlib import Path
from app.database import SessionLocal
from app.models.db_models import Document
from app.api.rag_documents import _resolve_real_path

db = SessionLocal()
working = []
missing = []

for d in db.query(Document).order_by(Document.id).all():
    candidates = [p for p in (d.file_path, d.original_path) if p]
    resolved = None
    for p in candidates:
        r = _resolve_real_path(p)
        if r:
            resolved = r
            break
    title = (d.document_title or d.filename or d.original_filename or str(d.doc_id))[:90]
    row = {
        "id": d.id,
        "doc_id": d.doc_id,
        "title": title,
        "resolved": str(resolved) if resolved else None,
        "candidates": candidates,
    }
    (working if resolved else missing).append(row)

print(f"WORKING={len(working)}")
for r in working:
    print(f"OK id={r['id']} doc_id={r['doc_id']} | {r['title']}")
    print(f"   -> {r['resolved']}")

print(f"MISSING={len(missing)}")
for r in missing:
    print(f"FAIL id={r['id']} doc_id={r['doc_id']} | {r['title']}")
    print(f"   paths={r['candidates']}")

# Focus Laporan 2024 variants
print("---LAPORAN 2024 VARIANTS---")
for d in db.query(Document).all():
    title = (d.document_title or d.filename or d.original_filename or "")
    if "2024" in title and ("Laporan" in title or "laporan" in title.lower() or "Evaluasi" in title):
        r = _resolve_real_path(d.file_path) or _resolve_real_path(d.original_path)
        print(f"id={d.id} doc_id={d.doc_id} title={title[:80]}")
        print(f"  file_path={d.file_path}")
        print(f"  original_path={d.original_path}")
        print(f"  resolved={r}")

db.close()
