"""Check specific Tabel 4 chunk (the problematic one)."""
from app.database import SessionLocal
from app.models.db_models import Chunk
import json

db = SessionLocal()
chunks = db.query(Chunk).filter(Chunk.document_id == 8).all()

for c in chunks:
    meta = json.loads(c.chunk_metadata) if c.chunk_metadata else {}
    text_lower = c.chunk_text.lower()
    if "nasional" in text_lower and "rerata" in text_lower and "|" in c.chunk_text:
        print(f"=== Chunk {c.chunk_index} (type={meta.get('chunk_type','text')}) ===")
        print(f"context_header: {meta.get('context_header', '')}")
        print(f"table_context ({len(str(meta.get('table_context','')))} chars):")
        print(str(meta.get("table_context", ""))[:400])
        print(f"\nparent_text ({len(str(meta.get('parent_pasal_text','')))} chars):")
        print(str(meta.get("parent_pasal_text", ""))[:300])
        print(f"\nchunk text:")
        print(c.chunk_text)
        print("=" * 60)

db.close()
