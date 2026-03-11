import os
import json
from pathlib import Path
from loguru import logger
from app.core.ingestion.pdf_processor import DocumentProcessor

# Force CPU to avoid CUDA issues
os.environ["CUDA_VISIBLE_DEVICES"] = ""

OUTPUT_DIR = Path("d:/aqil/pusdatik/data/chunks_output")
INPUT_DIR = Path("d:/aqil/pusdatik/data/documents/peraturan")

def export_peraturan():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    processor = DocumentProcessor()
    
    # Process all PDFs in the directory
    pdf_files = list(INPUT_DIR.glob("*.pdf"))
    if not pdf_files:
        logger.error(f"No PDF files found in {INPUT_DIR}")
        return
        
    for pdf_path in pdf_files:
        filename = pdf_path.name
        logger.info(f"Processing: {filename}")
        
        # 1. Convert to text
        text, _, method = processor._convert_pdf_to_text(str(pdf_path), filename, force_ocr=False)
        
        # 2. Parse JSON Structure
        from app.core.ingestion.json_structure_parser import parse_document
        struct = parse_document(text, filename, folder_hint="peraturan")
        
        # Save structural JSON
        json_path = OUTPUT_DIR / f"{pdf_path.stem}.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(struct, f, indent=2, ensure_ascii=False)
            
        # 3. Create Chunks
        from app.core.ingestion.structured_chunker import chunk_document
        chunks = chunk_document(struct)
        
        # Save chunk visualizations
        txt_path = OUTPUT_DIR / f"{pdf_path.stem}_chunks.txt"
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(f"DOCUMENT: {filename}\n")
            f.write(f"TYPE: {struct.get('type')}\n")
            f.write(f"TOTAL CHUNKS: {len(chunks)}\n")
            f.write("="*60 + "\n\n")
            
            for i, c in enumerate(chunks, 1):
                f.write(f"--- CHUNK {i} ---\n")
                f.write(f"METADATA: {json.dumps(c.get('metadata', {}), ensure_ascii=False)}\n")
                f.write(f"CONTENT:\n{c.get('text', '')}\n")
                f.write("-" * 40 + "\n\n")
                
        logger.success(f"Exported {len(chunks)} chunks for {filename}")

if __name__ == "__main__":
    export_peraturan()
