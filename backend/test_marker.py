"""
Test Marker PDF to Markdown conversion for table extraction.
Output saved to data/marker_test/ - does NOT affect existing data.
"""

import os
import sys
from pathlib import Path

# Test PDFs - documents with tables
TEST_PDFS = [
    r"D:\aqil\pusdatik\data\documents\others\20250313_Laporan_Pelaksanaan_Evaluasi_SPBE_2024.pdf",
    r"D:\aqil\pusdatik\data\documents\peraturan\Permenpan RB Nomor 59 Tahun 2020.pdf",
]

OUTPUT_DIR = Path(r"D:\aqil\pusdatik\backend\data\marker_test")


def convert_pdf_to_markdown(pdf_path: str, output_dir: Path) -> str:
    """Convert a single PDF to Markdown using Marker."""
    from marker.converters.pdf import PdfConverter
    from marker.models import create_model_dict
    from marker.config.parser import ConfigParser

    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        print(f"  ERROR: File not found: {pdf_path}")
        return None

    print(f"  Loading Marker models (first run will download ~2GB)...")

    # Create config
    config_parser = ConfigParser(
        {
            "output_format": "markdown",
        }
    )

    # Create model dict (downloads models on first run)
    model_dict = create_model_dict()

    # Create converter
    converter = PdfConverter(
        config=config_parser.generate_config_dict(),
        artifact_dict=model_dict,
    )

    print(f"  Converting {pdf_path.name}...")

    # Convert
    rendered = converter(str(pdf_path))

    # Save output
    output_file = output_dir / f"{pdf_path.stem}.md"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(rendered.markdown)

    print(f"  Saved to: {output_file}")
    return str(output_file)


def main():
    print("=" * 70)
    print("Marker PDF to Markdown Test")
    print("=" * 70)
    print(f"Output directory: {OUTPUT_DIR}")
    print()

    # Check PDFs exist
    for pdf in TEST_PDFS:
        if Path(pdf).exists():
            print(f"  [OK] {Path(pdf).name}")
        else:
            print(f"  [MISSING] {pdf}")

    print()

    # Convert first PDF only (to test)
    pdf_path = TEST_PDFS[0]
    if Path(pdf_path).exists():
        print(f"Converting: {Path(pdf_path).name}")
        try:
            output = convert_pdf_to_markdown(pdf_path, OUTPUT_DIR)
            if output:
                print(f"\nConversion successful!")
                print(f"Output: {output}")

                # Show preview
                with open(output, "r", encoding="utf-8") as f:
                    content = f.read()
                print(f"\nFile size: {len(content):,} characters")
                print(f"\nPreview (first 2000 chars):")
                print("-" * 50)
                print(content[:2000])
                print("-" * 50)
        except Exception as e:
            print(f"ERROR: {e}")
            import traceback

            traceback.print_exc()
    else:
        print(f"Test PDF not found: {pdf_path}")


if __name__ == "__main__":
    main()
