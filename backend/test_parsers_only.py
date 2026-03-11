"""
Test script for parsers with Markdown input (no Marker conversion needed).
This tests the Markdown parsing capabilities independently.
"""

import sys
import os

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pathlib import Path


def test_audit_parser_markdown():
    """Test audit parser with Markdown input"""
    print("\n" + "=" * 60)
    print("TEST 1: Audit Parser with Markdown")
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
        ctx = t["context"][:50] if len(t["context"]) > 50 else t["context"]
        print(f"    - {t['row_count']} rows, context: {ctx}...")

    # Test full parsing
    metadata = {"filename": "test_laporan.pdf", "doc_type": "audit"}
    chunks = AuditParser.parse(sample_md, metadata)
    print(f"[OK] Chunks created: {len(chunks)}")

    # Show sample chunk
    if chunks:
        print("\nSample chunk:")
        chunk = chunks[0]
        print(f"  Text preview: {chunk['text'][:100]}...")
        print(f"  Section: {chunk['metadata'].get('section', 'N/A')}")

    return True


def test_peraturan_parser_markdown():
    """Test peraturan parser with Markdown detection"""
    print("\n" + "=" * 60)
    print("TEST 2: Peraturan Parser with Markdown")
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

    # Show sample chunk
    if chunks:
        print("\nSample chunk:")
        chunk = chunks[0]
        preview = chunk["text"][:100].replace("\n", " ")
        print(f"  Text preview: {preview}...")
        print(f"  Pasal: {chunk['metadata'].get('pasal', 'N/A')}")

    return True


def test_real_markdown_file():
    """Test parsers with actual Marker output file"""
    print("\n" + "=" * 60)
    print("TEST 3: Real Markdown File Parsing")
    print("=" * 60)

    md_file = Path(
        r"D:\aqil\pusdatik\backend\data\marker_test\20250313_Laporan_Pelaksanaan_Evaluasi_SPBE_2024.md"
    )

    if not md_file.exists():
        print(f"[WARN] Test file not found: {md_file}")
        return False

    print(f"Reading: {md_file.name}")

    with open(md_file, "r", encoding="utf-8") as f:
        content = f.read()

    print(f"[OK] File size: {len(content):,} chars")

    # Test with audit parser
    from app.core.ingestion.parsers.audit_parser import AuditParser

    is_md = AuditParser.is_markdown(content)
    print(f"[OK] Is Markdown: {is_md}")

    sections = AuditParser.extract_markdown_sections(content)
    print(f"[OK] Sections found: {len(sections)}")

    tables = AuditParser.extract_markdown_tables(content)
    print(f"[OK] Tables found: {len(tables)}")

    # Parse the content
    metadata = {
        "filename": md_file.name,
        "doc_type": "audit",
        "tentang": "Laporan Evaluasi SPBE 2024",
    }

    chunks = AuditParser.parse(content, metadata)
    print(f"[OK] Chunks created: {len(chunks)}")

    # Analyze chunks
    if chunks:
        chunk_sizes = [len(c["text"]) for c in chunks]
        print(f"\nChunk statistics:")
        print(f"  Min size: {min(chunk_sizes)} chars")
        print(f"  Max size: {max(chunk_sizes)} chars")
        print(f"  Avg size: {sum(chunk_sizes) // len(chunk_sizes)} chars")

        # Check table content in chunks
        table_chunks = [c for c in chunks if "|" in c["text"]]
        print(f"  Chunks with tables: {len(table_chunks)}")

    return True


def main():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("PARSER MARKDOWN TEST SUITE")
    print("=" * 60)

    results = []

    # Test 1: Audit Parser with sample Markdown
    try:
        results.append(("Audit Parser MD", test_audit_parser_markdown()))
    except Exception as e:
        print(f"[FAIL] Test 1 failed: {e}")
        import traceback

        traceback.print_exc()
        results.append(("Audit Parser MD", False))

    # Test 2: Peraturan Parser with sample Markdown
    try:
        results.append(("Peraturan Parser MD", test_peraturan_parser_markdown()))
    except Exception as e:
        print(f"[FAIL] Test 2 failed: {e}")
        import traceback

        traceback.print_exc()
        results.append(("Peraturan Parser MD", False))

    # Test 3: Real Markdown file
    try:
        results.append(("Real MD File", test_real_markdown_file()))
    except Exception as e:
        print(f"[FAIL] Test 3 failed: {e}")
        import traceback

        traceback.print_exc()
        results.append(("Real MD File", False))

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
