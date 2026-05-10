from app.database import SessionLocal
from app.models.db_models import Chunk
import json

db = SessionLocal()
rows = db.query(Chunk.chunk_text, Chunk.chunk_metadata).all()
targets = ['Permenpan RB Nomor 5 Tahun 2020.pdf', 'SE Menteri PAN-RB Nomor 18 Tahun 2022.pdf']
for text, meta_str in rows:
    meta = json.loads(meta_str)
    fname = meta.get('filename', '')
    if fname in targets:
        print(f"=== {fname} ===")
        print(text[:500])
        print("---")
db.close()
