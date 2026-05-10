import sys
import asyncio
from pathlib import Path

sys.path.insert(0, r'd:\aqil\pusdatik\backend')

from app.core.ingestion.structured_chunker import chunk_from_markdown
from app.core.ingestion.document_manager import DocumentManager
from app.database import SessionLocal, init_database
from app.models.db_models import Document

async def insert_doc(filename, doc_title):
    print(f"Bypassing Marker for {filename}...")
    md_path = None
    
    # Try different formats of Marker folder
    base_marker = Path(r'd:\aqil\pusdatik\backend\data\marker_output')
    stem = Path(filename).stem
    
    # Check directly first
    exact = base_marker / stem / f"{stem}.md"
    if exact.exists():
        md_path = exact
    else:
        for folder in base_marker.iterdir():
            if folder.is_dir() and stem.lower().replace(" ", "_") in folder.name.lower():
                candidate = folder / f"{folder.name}.md"
                if candidate.exists():
                    md_path = candidate
                    break
            elif folder.is_dir() and 'se menteri' in folder.name.lower() and '18' in folder.name.lower():
                candidate = folder / f"{folder.name}.md"
                if candidate.exists():
                    md_path = candidate
                    break
            elif folder.is_dir() and 'permenpan' in folder.name.lower() and '5' in folder.name.lower():
                candidate = folder / f"{folder.name}.md"
                if candidate.exists():
                    md_path = candidate
                    break

    if not md_path:
        print(f"MD file not found for {filename}")
        return

    print(f"Using MD cache: {md_path}")
    with open(md_path, 'r', encoding='utf-8') as f:
        md_text = f.read()

    chunks = chunk_from_markdown(md_text, filename, doc_title)
    
    for i, c in enumerate(chunks):
        c['chunk_index'] = i

    print(f"Generated {len(chunks)} chunks for {filename}")

    mgr = DocumentManager()

    db = SessionLocal()
    
    db_doc = db.query(Document).filter(Document.filename.contains(Path(filename).stem)).first()
    if not db_doc:
        db_doc = Document(filename=filename, original_path=str(md_path), doc_type="peraturan", status="completed")
        db.add(db_doc)
        db.commit()
        db.refresh(db_doc)
    else:
        db_doc.status = "completed"
        db.commit()
    
    db_doc_id = str(db_doc.id)

    print(f"DB ID: {db_doc_id}")

    # Generate embeddings
    print("Generating embeddings...")
    embeddings = []
    
    # We must format dicts
    for i, c in enumerate(chunks):
        c['metadata']['document_id'] = db_doc_id
        emb = mgr.generate_embedding(c['text'])
        embeddings.append(emb)
        if (i+1) % 50 == 0:
            print(f"Embedded {i+1}/{len(chunks)}")
            
    print("Saving to Qdrant...")
    # Add _upload_document_points parameters: doc_id, document dictionary, chunks, embeddings
    stats = mgr._upload_document_points(db_doc_id, {"filename":filename, "document_title": doc_title, "doc_type": "peraturan", "original_filename": filename}, chunks, embeddings)
    print(f"Vector stats: {stats}")

async def main():
    await insert_doc('SE Menteri PAN-RB Nomor 18 Tahun 2022.pdf', 'SE 18 Tahun 2022')
    await insert_doc('Permenpan RB Nomor 5 Tahun 2020.pdf', 'Permenpan 5 Tahun 2020')

if __name__ == '__main__':
    asyncio.run(main())
