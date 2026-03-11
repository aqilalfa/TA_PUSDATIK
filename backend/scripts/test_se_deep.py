
import os
import json
import sys
from pathlib import Path

# Add backend to path
sys.path.append(str(Path(__file__).parent.parent))

from app.core.ingestion.pdf_processor import DocumentProcessor
from app.core.ingestion.json_structure_parser import parse_document

def test_deep_se():
    pdf_path = r"d:\aqil\pusdatik\data\documents\peraturan\SE Menteri PAN-RB Nomor 18 Tahun 2022.pdf"
    filename = "SE Menteri PAN-RB Nomor 18 Tahun 2022.pdf"
    
    print(f"Processing {filename}...")
    processor = DocumentProcessor()
    
    # 1. Extraction
    text, _, _ = processor._convert_pdf_to_text(pdf_path, filename, force_ocr=False)
    print(f"Extracted {len(text)} characters.")
    
    # 2. Parsing
    struct = parse_document(text, filename, folder_hint="peraturan")
    
    # 3. Validation
    print("\nMETADATA:")
    print(json.dumps(struct.get("metadata_dokumen"), indent=2))
    
    print(f"\nPENERIMA: {len(struct.get('penerima', []))} items")
    print(f"LATAR BELAKANG: {len(struct.get('latar_belakang', ''))} chars")
    print(f"MAKSUD: {len(struct.get('maksud_dan_tujuan', {}).get('maksud', ''))} chars")
    print(f"TUJUAN: {len(struct.get('maksud_dan_tujuan', {}).get('tujuan', ''))} chars")
    print(f"DASAR HUKUM: {len(struct.get('dasar_hukum', []))} items")
    
    lamp_sections = struct.get("lampiran", {}).get("sections", [])
    print(f"\nLAMPIRAN (Petunjuk Teknis): {len(lamp_sections)} BABs detected")
    for bab in lamp_sections:
        print(f"  - {bab.get('bab_nomor')}: {bab.get('bab_judul')}")
    
    # Save output
    output_path = "se_deep_result.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(struct, f, indent=2, ensure_ascii=False)
    print(f"\nResult saved to {output_path}")

if __name__ == "__main__":
    test_deep_se()
