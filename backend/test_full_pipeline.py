"""
Test full pipeline with cached Marker conversion.
This tests: Marker converter (cached) -> Classifier -> Parser -> Chunks
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pathlib import Path


def test_marker_converter_cached():
    """Test Marker converter with cached output"""
    print("\n" + "=" * 60)
    print("TEST 1: Marker Converter (Cached)")
    print("=" * 60)

    from app.core.ingestion.marker_converter import marker_converter

    # Check availability
    print(f"[OK] Marker available: {marker_converter.is_available()}")

    # Test with PDF that has cached conversion
    pdf_path = r"D:\aqil\pusdatik\data\documents\others\20250313_Laporan_Pelaksanaan_Evaluasi_SPBE_2024.pdf"

    if not os.path.exists(pdf_path):
        print(f"[WARN] PDF not found: {pdf_path}")
        return False

    print(f"\nTesting: {Path(pdf_path).name}")

    try:
        text, md_path, used_marker = marker_converter.convert(
            pdf_path,
            save_output=True,
            force_reconvert=False,  # Use cached
        )

        print(f"[OK] Used Marker: {used_marker}")
        print(f"[OK] Text length: {len(text):,} chars")
        print(f"[OK] Output path: {md_path}")

        # Check for tables
        table_count = text.count("|---|")
        print(f"[OK] Tables (|---|): {table_count}")

        return True

    except Exception as e:
        print(f"[FAIL] Error: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_document_processor_convert():
    """Test Document processor's _convert_pdf_to_text method"""
    print("\n" + "=" * 60)
    print("TEST 2: Document Processor Convert Method")
    print("=" * 60)

    from app.core.ingestion.pdf_processor import DocumentProcessor

    pdf_path = r"D:\aqil\pusdatik\data\documents\others\20250313_Laporan_Pelaksanaan_Evaluasi_SPBE_2024.pdf"
    filename = Path(pdf_path).name

    print(f"Testing: {filename}")

    try:
        text, md_path, method = DocumentProcessor._convert_pdf_to_text(
            pdf_path, filename, force_ocr=False
        )

        print(f"[OK] Method used: {method}")
        print(f"[OK] Text length: {len(text):,} chars")
        print(f"[OK] MD path: {md_path}")

        return True

    except Exception as e:
        print(f"[FAIL] Error: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_full_pipeline():
    """Test complete pipeline: Marker -> Classify -> Parse"""
    print("\n" + "=" * 60)
    print("TEST 3: Full Pipeline")
    print("=" * 60)

    from app.core.ingestion.marker_converter import marker_converter
    from app.core.ingestion.metadata_extractor import (
        classify_document,
        extract_metadata,
    )
    from app.core.ingestion.parsers.audit_parser import AuditParser
    from app.core.ingestion.parsers.peraturan_parser import PeraturanParser

    pdf_path = r"D:\aqil\pusdatik\data\documents\others\20250313_Laporan_Pelaksanaan_Evaluasi_SPBE_2024.pdf"
    filename = Path(pdf_path).name

    # Step 1: Convert
    print("\nStep 1: Marker Conversion...")
    text, md_path, used_marker = marker_converter.convert(pdf_path)
    print(f"  [OK] Method: {'Marker' if used_marker else 'OCR'}")
    print(f"  [OK] Text: {len(text):,} chars")

    # Step 2: Classify
    print("\nStep 2: Classification...")
    doc_type = classify_document(text, filename)
    meta = extract_metadata(text, doc_type)
    print(f"  [OK] Type: {doc_type}")
    print(f"  [OK] Metadata: {meta}")

    # Step 3: Parse
    print("\nStep 3: Parsing...")
    metadata = {"filename": filename, "doc_type": doc_type, **meta}

    if doc_type == "peraturan":
        chunks = PeraturanParser.parse(text, metadata)
    else:
        chunks = AuditParser.parse(text, metadata)

    print(f"  [OK] Chunks created: {len(chunks)}")

    # Analyze
    print("\nStep 4: Analysis...")
    chunk_sizes = [len(c["text"]) for c in chunks]
    print(f"  [OK] Size range: {min(chunk_sizes)}-{max(chunk_sizes)} chars")
    print(f"  [OK] Average: {sum(chunk_sizes) // len(chunk_sizes)} chars")

    table_chunks = sum(1 for c in chunks if "|" in c["text"])
    print(f"  [OK] Chunks with tables: {table_chunks}")

    # Show sample
    print("\nSample chunks:")
    for i, chunk in enumerate(chunks[:3]):
        preview = chunk["text"][:80].replace("\n", " ")
        section = chunk["metadata"].get("section", "N/A")
        print(f"  [{i + 1}] ({section}) {preview}...")

    return True


def main():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("FULL PIPELINE TEST SUITE")
    print("=" * 60)

    results = []

    # Test 1
    try:
        results.append(("Marker Cached", test_marker_converter_cached()))
    except Exception as e:
        print(f"[FAIL] Test 1: {e}")
        results.append(("Marker Cached", False))

    # Test 2
    try:
        results.append(("Document Processor", test_document_processor_convert()))
    except Exception as e:
        print(f"[FAIL] Test 2: {e}")
        results.append(("Document Processor", False))

    # Test 3
    try:
        results.append(("Full Pipeline", test_full_pipeline()))
    except Exception as e:
        print(f"[FAIL] Test 3: {e}")
        import traceback

        traceback.print_exc()
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
