#!/usr/bin/env python3
"""
OCR Pipeline Test Script
Test OCR functionality with sample PDFs and evaluate quality
"""

import sys
from pathlib import Path
import argparse
from typing import Dict, List
import time

# Add app to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.ingestion.ocr import ocr_processor
from loguru import logger
import json


class OCRTester:
    """Test OCR pipeline with various PDFs"""

    def __init__(self):
        self.results = []

    def test_single_pdf(self, pdf_path: str, force_ocr: bool = False) -> Dict:
        """
        Test OCR on a single PDF

        Args:
            pdf_path: Path to PDF file
            force_ocr: Force OCR even if text-selectable

        Returns:
            Test results dictionary
        """
        logger.info("=" * 70)
        logger.info(f"Testing OCR on: {pdf_path}")
        logger.info("=" * 70)

        result = {
            "file": pdf_path,
            "file_size_mb": Path(pdf_path).stat().st_size / (1024 * 1024),
            "force_ocr": force_ocr,
            "success": False,
            "error": None,
        }

        try:
            # Step 1: Check if OCR is needed
            logger.info("\n[STEP 1] Detecting if OCR is needed...")
            start_time = time.time()

            needs_ocr = ocr_processor.detect_ocr_needed(pdf_path)
            detection_time = time.time() - start_time

            result["needs_ocr"] = needs_ocr
            result["detection_time_sec"] = round(detection_time, 2)

            logger.info(
                f"  ✓ Detection complete: {'OCR NEEDED' if needs_ocr else 'Text-selectable'}"
            )
            logger.info(f"  ⏱ Detection time: {detection_time:.2f}s")

            # Step 2: Process PDF
            logger.info("\n[STEP 2] Processing PDF...")
            start_time = time.time()

            text, ocr_used = ocr_processor.process_pdf(pdf_path, force_ocr=force_ocr)
            processing_time = time.time() - start_time

            result["ocr_used"] = ocr_used
            result["processing_time_sec"] = round(processing_time, 2)
            result["text_length"] = len(text)
            result["word_count"] = len(text.split())
            result["char_count"] = len(text.strip())

            logger.info(f"  ✓ Processing complete")
            logger.info(f"  ⏱ Processing time: {processing_time:.2f}s")
            logger.info(
                f"  📄 Text extracted: {len(text)} chars, {len(text.split())} words"
            )

            # Step 3: Text quality assessment
            logger.info("\n[STEP 3] Assessing text quality...")
            quality = self.assess_text_quality(text)
            result["quality"] = quality

            logger.info(f"  Quality Score: {quality['overall_score']}/100")
            logger.info(f"    - Readability: {quality['readability_score']}/100")
            logger.info(f"    - Indonesian content: {quality['indonesian_score']}/100")
            logger.info(f"    - Structure: {quality['structure_score']}/100")

            # Step 4: Sample preview
            logger.info("\n[STEP 4] Text Preview...")
            preview = text[:500].replace("\n", " ")
            logger.info(f"  First 500 chars: {preview}...")
            result["preview"] = preview

            result["success"] = True

            # Summary
            logger.info("\n" + "=" * 70)
            logger.success("✓ OCR Test PASSED")
            logger.info("=" * 70)
            logger.info(f"Summary:")
            logger.info(f"  • File size: {result['file_size_mb']:.2f} MB")
            logger.info(f"  • OCR used: {'Yes' if ocr_used else 'No'}")
            logger.info(f"  • Processing time: {processing_time:.2f}s")
            logger.info(f"  • Text extracted: {result['word_count']} words")
            logger.info(f"  • Quality score: {quality['overall_score']}/100")
            logger.info("=" * 70)

        except Exception as e:
            logger.error(f"✗ OCR Test FAILED: {e}")
            result["error"] = str(e)

        self.results.append(result)
        return result

    def assess_text_quality(self, text: str) -> Dict:
        """
        Assess quality of extracted text

        Returns:
            Quality metrics dictionary
        """
        quality = {
            "readability_score": 0,
            "indonesian_score": 0,
            "structure_score": 0,
            "overall_score": 0,
        }

        # Readability: ratio of alphanumeric to total chars
        alphanum = sum(c.isalnum() for c in text)
        total = len(text)
        if total > 0:
            quality["readability_score"] = int((alphanum / total) * 100)

        # Indonesian content: check for Indonesian words
        indonesian_words = [
            "yang",
            "dan",
            "untuk",
            "dengan",
            "pada",
            "dalam",
            "dari",
            "adalah",
            "ini",
            "itu",
            "oleh",
            "ke",
            "di",
            "sebagai",
            "pasal",
            "ayat",
            "peraturan",
            "pemerintah",
            "tentang",
        ]
        text_lower = text.lower()
        indonesian_count = sum(1 for word in indonesian_words if word in text_lower)
        quality["indonesian_score"] = min(
            int((indonesian_count / len(indonesian_words)) * 100), 100
        )

        # Structure: check for common document structures
        has_pasal = "pasal" in text_lower
        has_bab = "bab" in text_lower
        has_ayat = "ayat" in text_lower or "(" in text and ")" in text
        has_numbers = any(c.isdigit() for c in text)

        structure_indicators = [has_pasal, has_bab, has_ayat, has_numbers]
        quality["structure_score"] = int(
            (sum(structure_indicators) / len(structure_indicators)) * 100
        )

        # Overall score (weighted average)
        quality["overall_score"] = int(
            (
                quality["readability_score"] * 0.4
                + quality["indonesian_score"] * 0.3
                + quality["structure_score"] * 0.3
            )
        )

        return quality

    def test_batch(self, pdf_dir: str, force_ocr: bool = False) -> List[Dict]:
        """
        Test OCR on all PDFs in a directory

        Args:
            pdf_dir: Directory containing PDFs
            force_ocr: Force OCR on all files

        Returns:
            List of test results
        """
        pdf_path = Path(pdf_dir)
        pdf_files = list(pdf_path.rglob("*.pdf"))

        if not pdf_files:
            logger.warning(f"No PDF files found in {pdf_dir}")
            return []

        logger.info(f"Found {len(pdf_files)} PDF files to test")

        for i, pdf_file in enumerate(pdf_files, 1):
            logger.info(f"\n\n{'=' * 70}")
            logger.info(f"Test {i}/{len(pdf_files)}")
            logger.info(f"{'=' * 70}\n")

            self.test_single_pdf(str(pdf_file), force_ocr=force_ocr)

        return self.results

    def generate_report(self, output_file: str = None):
        """Generate test report"""
        if not self.results:
            logger.warning("No test results to report")
            return

        logger.info("\n\n" + "=" * 70)
        logger.info("OCR TEST REPORT")
        logger.info("=" * 70)

        successful = [r for r in self.results if r["success"]]
        failed = [r for r in self.results if not r["success"]]

        logger.info(f"\nTotal tests: {len(self.results)}")
        logger.info(f"  ✓ Successful: {len(successful)}")
        logger.info(f"  ✗ Failed: {len(failed)}")

        if successful:
            avg_processing_time = sum(
                r["processing_time_sec"] for r in successful
            ) / len(successful)
            avg_quality = sum(r["quality"]["overall_score"] for r in successful) / len(
                successful
            )
            ocr_used_count = sum(1 for r in successful if r["ocr_used"])

            logger.info(f"\nPerformance Metrics:")
            logger.info(f"  • Avg processing time: {avg_processing_time:.2f}s")
            logger.info(f"  • Avg quality score: {avg_quality:.1f}/100")
            logger.info(f"  • OCR used: {ocr_used_count}/{len(successful)} files")

            logger.info(f"\nDetailed Results:")
            for r in successful:
                logger.info(f"\n  File: {Path(r['file']).name}")
                logger.info(f"    Size: {r['file_size_mb']:.2f} MB")
                logger.info(f"    OCR: {'Yes' if r['ocr_used'] else 'No'}")
                logger.info(f"    Time: {r['processing_time_sec']:.2f}s")
                logger.info(f"    Words: {r['word_count']}")
                logger.info(f"    Quality: {r['quality']['overall_score']}/100")

        if failed:
            logger.info(f"\nFailed Tests:")
            for r in failed:
                logger.info(f"  ✗ {Path(r['file']).name}: {r['error']}")

        # Save to file if specified
        if output_file:
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(self.results, f, indent=2, ensure_ascii=False)
            logger.info(f"\n✓ Report saved to: {output_file}")

        logger.info("\n" + "=" * 70)


def main():
    parser = argparse.ArgumentParser(
        description="Test OCR pipeline on PDF documents",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Test single PDF
  python test_ocr.py --file /app/data/documents/sample.pdf
  
  # Test with forced OCR
  python test_ocr.py --file /app/data/documents/sample.pdf --force-ocr
  
  # Test all PDFs in directory
  python test_ocr.py --dir /app/data/documents
  
  # Generate JSON report
  python test_ocr.py --dir /app/data/documents --output-report ocr_report.json
        """,
    )

    parser.add_argument("--file", help="Single PDF file to test")

    parser.add_argument("--dir", help="Directory containing PDFs to test")

    parser.add_argument(
        "--force-ocr",
        action="store_true",
        help="Force OCR even on text-selectable PDFs",
    )

    parser.add_argument("--output-report", help="Save test report to JSON file")

    args = parser.parse_args()

    if not args.file and not args.dir:
        parser.error("Must specify either --file or --dir")

    # Initialize tester
    tester = OCRTester()

    # Run tests
    if args.file:
        tester.test_single_pdf(args.file, force_ocr=args.force_ocr)
    elif args.dir:
        tester.test_batch(args.dir, force_ocr=args.force_ocr)

    # Generate report
    tester.generate_report(output_file=args.output_report)


if __name__ == "__main__":
    main()
