import sys, json, os
sys.path.insert(0, r'd:\aqil\pusdatik\backend')
from app.database import SessionLocal
from app.models.db_models import Document, Chunk

out_dir_json = r'd:\aqil\pusdatik\data\json_output'
out_dir_chunks = r'd:\aqil\pusdatik\data\chunks_output'
os.makedirs(out_dir_json, exist_ok=True)
os.makedirs(out_dir_chunks, exist_ok=True)

db = SessionLocal()
try:
    # Get the specific documents requested by user
    docs = db.query(Document).filter(
        (Document.filename.like('%PEDOMAN%')) | 
        (Document.filename.like('%Laporan_Pelaksanaan_Evaluasi_SPBE%'))
    ).all()
    for d in docs:
        base = os.path.basename(d.filename).replace('.pdf', '')
        
        parsed = {}
        if d.doc_metadata:
            parsed = json.loads(d.doc_metadata)
            
        with open(os.path.join(out_dir_json, f'{base}.json'), 'w', encoding='utf-8') as f:
            json.dump(parsed, f, ensure_ascii=False, indent=2)
            
        chunks = db.query(Chunk).filter(Chunk.document_id == d.id).order_by(Chunk.chunk_index).all()
        with open(os.path.join(out_dir_chunks, f'{base}_chunks.txt'), 'w', encoding='utf-8') as f:
            for c in chunks:
                f.write(f'--- CHUNK {c.chunk_index} ---\n')
                f.write(c.chunk_metadata + '\n\n')
                f.write(c.chunk_text + '\n\n')
    print("Export successful!")
except Exception as e:
    print(f"Error: {e}")
finally:
    db.close()
