"""Test reingest on a single file to get full traceback."""
import sys
import traceback
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger
logger.remove()
logger.add(sys.stderr, level="DEBUG")

from app.core.database import SessionLocal
from app.models.db_models import Document, Chunk
from datetime import datetime
from app.core.ingestion.pdf_processor import DocumentProcessor

db = SessionLocal()
try:
    # Clear any existing data for just this file
    test_pdf = Path("D:/aqil/pusdatik/data/documents/peraturan/peraturan-bssn-no-8-tahun-2024.pdf")

    # Create a doc record
    doc = Document(
        filename=test_pdf.name,
        original_path=str(test_pdf),
        doc_type="peraturan",
        status="pending",
        uploaded_by=1,
        uploaded_at=datetime.utcnow(),
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    processor = DocumentProcessor()
    result = processor.process_document(
        pdf_path=str(test_pdf),
        filename=test_pdf.name,
        doc_id=doc.id,
        db=db,
    )
    print(f"\nSUCCESS: {result['chunk_count']} chunks")
except Exception as e:
    print(f"\nFAILED: {e}")
    traceback.print_exc()
finally:
    db.close()
