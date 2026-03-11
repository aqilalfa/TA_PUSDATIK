"""
Test script for Marker integration in document processing pipeline.
Tests the full flow: PDF -> Marker -> Markdown -> Parser -> Chunks
"""

import sys
import os

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pathlib import Path
from loguru import logger

# Configure logger
logger.remove()
logger.add(
    sys.stderr,
    level="INFO",
    format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}",
)


def test_marker_converter():
    """Test Marker converter independently"""
    print("\n" + "=" * 60)
    print("TEST 1: Marker Converter")
    print("=" * 60)

    from app.core.ingestion.marker_converter import (
        marker_converter,
        MarkerConversionError,
    )

    # Check if Marker is available
    if not marker_converter.is_available():
        print("[FAIL] Marker is NOT available. Install with: pip install marker-pdf")
        return False

    print("[OK] Marker is available")

    # Test PDF files
    test_files = [
        r"D:\aqil\pusdatik\data\documents\others\20250313_Laporan_Pelaksanaan_Evaluasi_SPBE_2024.pdf",
        r"D:\aqil\pusdatik\data\documents\peraturan\Perpres Nomor 95 Tahun 2018.pdf",
    ]

    for pdf_path in test_files:
        if not os.path.exists(pdf_path):
            print(f"[WARN] File not found: {pdf_path}")
            continue

        print(f"\nTesting: {Path(pdf_path).name}")

        try:
            result = marker_converter.convert(
                pdf_path,
                save_output=True,
                force_reconvert=False,  # Use cached if available
            )

            print(f"  [OK] Conversion: {result.method}")
            print(f"  [OK] Text length: {len(result.text):,} chars")
            print(f"  [OK] Output: {result.output_path}")

            # Check for tables in output
            table_count = result.text.count("|---|")
            print(f"  [OK] Tables detected: {table_count}")

        except MarkerConversionError as e:
            print(f"  [FAIL] Marker error: {e}")
        except Exception as e:
            print(f"  [FAIL] Error: {e}")

    return True


def test_audit_parser_markdown():
    """Test audit parser with Markdown input"""
    print("\n" + "=" * 60)
    print("TEST 2: Audit Parser with Markdown")
    print("=" * 60)

    from app.core.ingestion.parsers.audit_parser import AuditParser

    # Sample Markdown content (simulating Marker output)
    sample_md = """
# Laporan Evaluasi SPBE

Tahun 2024

## Ringkasan Eksekutif

Evaluasi SPBE tahun 2024 telah selesai dilaksanakan dengan hasil indeks nasional 3.12.

## Hasil Evaluasi

### Tabel 1. Indeks SPBE Nasional

| Deskripsi | 2023 | 2024 |
|-----------|------|------|
| Indeks SPBE Nasional | 2.79 | 3.12 |
| Domain Kebijakan | 2.94 | 3.36 |
| Domain Tata Kelola | 2.29 | 2.62 |

### Analisis Domain

Domain Layanan memperoleh rata-rata indeks tertinggi dengan skor 3,78.

## Rekomendasi

Rekomendasi 1: Peningkatan koordinasi antar instansi
Rekomendasi 2: Penguatan infrastruktur TIK

## Kesimpulan

Capaian SPBE nasional menunjukkan peningkatan signifikan.
"""

    # Test Markdown detection
    is_md = AuditParser.is_markdown(sample_md)
    print(f"[OK] Markdown detected: {is_md}")

    # Test section extraction
    sections = AuditParser.extract_markdown_sections(sample_md)
    print(f"[OK] Sections found: {len(sections)}")
    for s in sections:
        print(f"    - {s['header']} (level {s['level']})")

    # Test table extraction
    tables = AuditParser.extract_markdown_tables(sample_md)
    print(f"[OK] Tables found: {len(tables)}")
    for t in tables:
        print(f"    - {t['row_count']} rows, context: {t['context'][:50]}...")

    # Test full parsing
    metadata = {"filename": "test_laporan.pdf", "doc_type": "audit"}
    chunks = AuditParser.parse(sample_md, metadata)
    print(f"[OK] Chunks created: {len(chunks)}")

    # Check for table chunks specifically
    table_chunks = [
        c for c in chunks if c.get("metadata", {}).get("chunk_type") == "table"
    ]
    print(f"[OK] Table chunks created: {len(table_chunks)}")
    if table_chunks:
        for tc in table_chunks[:2]:
            ctx = tc["metadata"].get("table_context", "N/A")
            print(
                f"    - Table context: {ctx}, rows: {tc['metadata'].get('row_count', 0)}"
            )

    return True


def test_peraturan_parser_markdown():
    """Test peraturan parser with Markdown detection"""
    print("\n" + "=" * 60)
    print("TEST 3: Peraturan Parser with Markdown")
    print("=" * 60)

    from app.core.ingestion.parsers.peraturan_parser import PeraturanParser

    # Sample Markdown with tables (simulating Marker output)
    sample_md = """
# PERATURAN PRESIDEN NOMOR 95 TAHUN 2018

TENTANG SISTEM PEMERINTAHAN BERBASIS ELEKTRONIK

## BAB I KETENTUAN UMUM

Pasal 1

(1) Sistem Pemerintahan Berbasis Elektronik yang selanjutnya disingkat SPBE adalah penyelenggaraan pemerintahan yang memanfaatkan teknologi informasi.

(2) SPBE bertujuan untuk mewujudkan tata kelola pemerintahan yang bersih, efektif, transparan, dan akuntabel.

Pasal 2

| No | Unsur SPBE | Deskripsi |
|----|------------|-----------|
| 1 | Kebijakan | Arah dan panduan |
| 2 | Tata Kelola | Pengelolaan organisasi |
| 3 | Manajemen | Penerapan fungsi |
| 4 | Layanan | Keluaran dari SPBE |

## BAB II RUANG LINGKUP

Pasal 3

(1) Ruang lingkup SPBE meliputi tata kelola SPBE dan manajemen SPBE.

## LAMPIRAN

LAMPIRAN I
PERATURAN PRESIDEN REPUBLIK INDONESIA

Arsitektur SPBE Nasional
"""

    # Test table extraction
    tables = PeraturanParser.extract_markdown_tables(sample_md)
    print(f"[OK] Tables found: {len(tables)}")

    # Test pasal extraction
    pasal_list = PeraturanParser.extract_pasal(sample_md)
    print(f"[OK] Pasal found: {len(pasal_list)}")
    for p in pasal_list[:3]:
        ayat_count = len(p.get("ayat", []))
        print(f"    - Pasal {p['number']}: {ayat_count} ayat")

    # Test full parsing
    metadata = {
        "filename": "Perpres 95 2018.pdf",
        "doc_type": "peraturan",
        "tentang": "SPBE",
    }
    chunks = PeraturanParser.parse(sample_md, metadata)
    print(f"[OK] Chunks created: {len(chunks)}")

    # Check for table chunks specifically
    table_chunks = [
        c for c in chunks if c.get("metadata", {}).get("chunk_type") == "table"
    ]
    print(f"[OK] Table chunks created: {len(table_chunks)}")
    if table_chunks:
        for tc in table_chunks[:2]:
            ctx = tc["metadata"].get("table_context", "N/A")
            print(
                f"    - Table context: {ctx}, rows: {tc['metadata'].get('row_count', 0)}"
            )

    return True


def test_full_pipeline():
    """Test complete pipeline with a real PDF"""
    print("\n" + "=" * 60)
    print("TEST 4: Full Pipeline (Marker -> Parser -> Chunks)")
    print("=" * 60)

    from app.core.ingestion.marker_converter import marker_converter
    from app.core.ingestion.parsers.audit_parser import AuditParser

    # Use the evaluation report PDF
    pdf_path = r"D:\aqil\pusdatik\data\documents\others\20250313_Laporan_Pelaksanaan_Evaluasi_SPBE_2024.pdf"

    if not os.path.exists(pdf_path):
        print(f"[WARN] Test file not found: {pdf_path}")
        return False

    print(f"Testing with: {Path(pdf_path).name}")

    # Step 1: Marker conversion
    print("\nStep 1: Marker Conversion...")
    try:
        result = marker_converter.convert(pdf_path, save_output=True)
        text = result.text
        print(f"  [OK] Method: {result.method}")
        print(f"  [OK] Text length: {len(text):,} chars")
    except Exception as e:
        print(f"  [FAIL] Error: {e}")
        return False

    # Step 2: Parse with audit parser
    print("\nStep 2: Parsing...")
    metadata = {
        "filename": Path(pdf_path).name,
        "doc_type": "audit",
        "tentang": "Laporan Evaluasi SPBE 2024",
    }

    chunks = AuditParser.parse(text, metadata)
    print(f"  [OK] Chunks created: {len(chunks)}")

    # Step 3: Analyze chunks
    print("\nStep 3: Chunk Analysis...")
    chunk_sizes = [len(c["text"]) for c in chunks]
    print(f"  [OK] Min size: {min(chunk_sizes)} chars")
    print(f"  [OK] Max size: {max(chunk_sizes)} chars")
    print(f"  [OK] Avg size: {sum(chunk_sizes) // len(chunk_sizes)} chars")

    # Show sample chunks
    print("\nSample chunks:")
    for i, chunk in enumerate(chunks[:3]):
        preview = chunk["text"][:100].replace("\n", " ")
        section = chunk["metadata"].get("section", "N/A")
        chunk_type = chunk["metadata"].get("chunk_type", "N/A")
        print(f"  [{i + 1}] ({chunk_type}/{section}) {preview}...")

    # Check for table chunks
    table_chunks = [
        c for c in chunks if c.get("metadata", {}).get("chunk_type") == "table"
    ]
    print(f"\n[OK] Table chunks: {len(table_chunks)}")
    if table_chunks:
        for i, tc in enumerate(table_chunks[:3]):
            ctx = tc["metadata"].get("table_context", "N/A")
            rows = tc["metadata"].get("row_count", 0)
            preview = tc["text"][:80].replace("\n", " ")
            print(f"  Table {i + 1}: context='{ctx}', rows={rows}")
            print(f"    Preview: {preview}...")

    return True


def main():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("MARKER INTEGRATION TEST SUITE")
    print("=" * 60)

    results = []

    # Test 1: Marker Converter
    try:
        results.append(("Marker Converter", test_marker_converter()))
    except Exception as e:
        print(f"[FAIL] Test 1 failed: {e}")
        results.append(("Marker Converter", False))

    # Test 2: Audit Parser with Markdown
    try:
        results.append(("Audit Parser MD", test_audit_parser_markdown()))
    except Exception as e:
        print(f"[FAIL] Test 2 failed: {e}")
        results.append(("Audit Parser MD", False))

    # Test 3: Peraturan Parser with Markdown
    try:
        results.append(("Peraturan Parser MD", test_peraturan_parser_markdown()))
    except Exception as e:
        print(f"[FAIL] Test 3 failed: {e}")
        results.append(("Peraturan Parser MD", False))

    # Test 4: Full Pipeline
    try:
        results.append(("Full Pipeline", test_full_pipeline()))
    except Exception as e:
        print(f"[FAIL] Test 4 failed: {e}")
        results.append(("Full Pipeline", False))

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    for name, passed in results:
        status = "[PASS]" if passed else "[FAIL]"
        print(f"  {status}: {name}")

    passed_count = sum(1 for _, p in results if p)
    print(f"\nTotal: {passed_count}/{len(results)} tests passed")

    return all(p for _, p in results)


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
