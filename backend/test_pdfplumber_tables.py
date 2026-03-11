"""
Alternative table extraction test using pdfplumber.
This is faster than Marker and doesn't require downloading large models.
"""

import pdfplumber
from pathlib import Path

TEST_PDFS = [
    r"D:\aqil\pusdatik\data\documents\others\20250313_Laporan_Pelaksanaan_Evaluasi_SPBE_2024.pdf",
]

OUTPUT_DIR = Path(r"D:\aqil\pusdatik\backend\data\marker_test")


def extract_tables_from_pdf(pdf_path: str, output_dir: Path, max_pages: int = 10):
    """Extract tables from PDF using pdfplumber."""
    pdf_path = Path(pdf_path)
    output_file = output_dir / f"{pdf_path.stem}_tables.md"

    print(f"Processing: {pdf_path.name}")

    tables_found = []

    with pdfplumber.open(pdf_path) as pdf:
        total_pages = min(len(pdf.pages), max_pages)
        print(f"  Scanning {total_pages} pages...")

        for i, page in enumerate(pdf.pages[:max_pages]):
            tables = page.extract_tables()

            if tables:
                for j, table in enumerate(tables):
                    if table and len(table) > 1:  # Has header + data
                        tables_found.append(
                            {"page": i + 1, "table_num": j + 1, "data": table}
                        )
                        print(f"    Page {i + 1}: Found table with {len(table)} rows")

    print(f"\n  Total tables found: {len(tables_found)}")

    # Save as markdown
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(f"# Tables Extracted from {pdf_path.name}\n\n")
        f.write(f"Total tables: {len(tables_found)}\n\n")

        for t in tables_found:
            f.write(f"## Page {t['page']} - Table {t['table_num']}\n\n")

            # Convert to markdown table
            data = t["data"]
            if data:
                # Header
                header = data[0]
                f.write(
                    "| "
                    + " | ".join(str(c or "").replace("\n", " ")[:50] for c in header)
                    + " |\n"
                )
                f.write("| " + " | ".join("---" for _ in header) + " |\n")

                # Rows
                for row in data[1:]:
                    f.write(
                        "| "
                        + " | ".join(str(c or "").replace("\n", " ")[:50] for c in row)
                        + " |\n"
                    )

                f.write("\n")

    print(f"  Saved to: {output_file}")

    # Show preview
    if tables_found:
        print("\n--- Preview of first table ---")
        first = tables_found[0]["data"]
        for row in first[:5]:
            print("  ", row[:3])  # First 3 columns
        if len(first) > 5:
            print(f"  ... ({len(first) - 5} more rows)")

    return str(output_file)


def main():
    print("=" * 70)
    print("PDFPlumber Table Extraction Test")
    print("=" * 70)
    print()

    for pdf in TEST_PDFS:
        if Path(pdf).exists():
            try:
                extract_tables_from_pdf(pdf, OUTPUT_DIR, max_pages=20)
            except Exception as e:
                print(f"ERROR: {e}")
        else:
            print(f"File not found: {pdf}")
        print()


if __name__ == "__main__":
    main()
