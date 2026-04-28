"""Test PyMuPDF-based figure image extraction."""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pathlib import Path
import pytest
from app.core.ingestion.figures.image_extractor import (
    extract_images_from_pdf,
    ExtractedImage,
)


SPBE_PDF = Path(__file__).parent.parent.parent / "data" / "documents" / "audit" / "20250313_Laporan_Pelaksanaan_Evaluasi_SPBE_2024.pdf"


@pytest.mark.skipif(not SPBE_PDF.exists(), reason="SPBE 2024 PDF not present")
def test_extract_images_from_spbe_2024(tmp_path):
    """SPBE 2024 PDF has many figures (charts, diagrams, photos).
    Expect at least 30 extracted images with valid metadata."""
    images = extract_images_from_pdf(SPBE_PDF, output_dir=tmp_path)

    assert len(images) >= 30, f"expected >= 30 images, got {len(images)}"
    for img in images:
        assert isinstance(img, ExtractedImage)
        assert img.image_path.exists()
        assert img.image_path.suffix == ".png"
        assert img.page >= 1
        assert len(img.bbox) == 4  # x0, y0, x1, y1
        assert img.width > 0 and img.height > 0


def test_extract_images_creates_unique_ids(tmp_path):
    """Each image should have unique figure_id even on same page."""
    if not SPBE_PDF.exists():
        pytest.skip("SPBE 2024 PDF not present")
    images = extract_images_from_pdf(SPBE_PDF, output_dir=tmp_path)
    ids = [img.figure_id for img in images]
    assert len(ids) == len(set(ids)), "figure_ids must be unique"
