from pathlib import Path
from app.database import SessionLocal
from app.models.db_models import Document, Chunk

db = SessionLocal()
lines = []
for d in db.query(Document).all():
    fp = d.file_path or ""
    op = d.original_path or ""
    exists = (Path(fp).exists() if fp else False) or (Path(op).exists() if op else False)
    title = (d.document_title or d.filename or "")[:80]
    lines.append(f"{d.id}|{d.doc_id}|exists={exists}|fp={fp}|title={title}")

out = Path("/tmp/all_docs.txt")
out.write_text("\n".join(lines), encoding="utf-8")
print("WROTE", len(lines))
print(out.read_text(encoding="utf-8"))

d = db.query(Document).filter(Document.doc_id == "46744099").first()
if d:
    c = db.query(Chunk).filter(Chunk.document_id == d.id).first()
    print("CHUNK_META", (c.chunk_metadata or "none")[:500] if c else "no-chunk")
else:
    print("doc 46744099 not found")
db.close()
