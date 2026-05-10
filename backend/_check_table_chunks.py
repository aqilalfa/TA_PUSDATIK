"""Check table chunks have proper parent context after re-preview."""
from app.database import SessionLocal
from app.models.db_models import Chunk
import json

db = SessionLocal()
chunks = db.query(Chunk).filter(Chunk.document_id == 8).all()

table_chunks = []
for c in chunks:
    meta = json.loads(c.chunk_metadata) if c.chunk_metadata else {}
    if meta.get("chunk_type") == "table" or c.chunk_type == "table":
        table_chunks.append((c.chunk_index, meta, c.chunk_text))

print(f"Total table chunks found: {len(table_chunks)}")
for idx, meta, txt in table_chunks[:8]:
    print(f"\n--- Table Chunk {idx} ---")
    print(f"  context_header: {meta.get('context_header', '')}")
    print(f"  table_context: {str(meta.get('table_context', ''))[:150]}")
    print(f"  parent_text: {str(meta.get('parent_pasal_text', ''))[:100]}")
    print(f"  text preview: {txt[:180]}")

db.close()
