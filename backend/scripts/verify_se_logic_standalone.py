
import sys
import os
import json
import re
from typing import Dict, Any

# Add project root to sys.path
project_root = r"d:\aqil\pusdatik\backend"
if project_root not in sys.path:
    sys.path.append(project_root)

# Import the parser
try:
    from app.core.ingestion.json_structure_parser import parse_surat_edaran
except ImportError as e:
    print(f"Import error: {e}")
    # Manual fallback if imports are messy
    sys.path.append(os.path.join(project_root, "app", "core", "ingestion"))
    from json_structure_parser import parse_surat_edaran

def verify():
    md_path = r"d:\aqil\pusdatik\backend\data\marker_output\SE Menteri PAN-RB Nomor 18 Tahun 2022\SE Menteri PAN-RB Nomor 18 Tahun 2022.md"
    
    if not os.path.exists(md_path):
        print(f"Error: Markdown file not found at {md_path}")
        return

    with open(md_path, "r", encoding="utf-8") as f:
        text = f.read()

    metadata = {
        "jenis_peraturan": "Surat Edaran",
        "nomor": "18",
        "tahun": "2022",
        "tentang": "KETERPADUAN LAYANAN DIGITAL NASIONAL",
        "sumber_file": "se_18_2022.pdf"
    }

    print("Running parse_surat_edaran...")
    result = parse_surat_edaran(text, metadata, "se_18_2022.pdf")

    output_path = "se_verification_final.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    print(f"Result saved to {output_path}")
    
    # Summary of findings
    print("\n--- Summary ---")
    print(f"Penerima count: {len(result.get('penerima', []))}")
    print(f"Latar Belakang length: {len(result.get('latar_belakang', ''))}")
    print(f"Maksud: {len(result['maksud_dan_tujuan'].get('maksud', ''))} chars")
    print(f"Tujuan: {len(result['maksud_dan_tujuan'].get('tujuan', ''))} chars")
    print(f"Dasar Hukum count: {len(result.get('dasar_hukum', []))}")
    
    lampiran = result.get('lampiran', {})
    if isinstance(lampiran, dict) and "sections" in lampiran:
        print(f"Lampiran BAB count: {len(lampiran['sections'])}")
        for bab in lampiran['sections']:
            print(f"  - {bab.get('bab_nomor')}: {bab.get('bab_judul')}")

if __name__ == "__main__":
    verify()
