"""Extract embedded images from PDF using PyMuPDF.

Returns one ExtractedImage per real image (excludes inline tiny icons < 50x50).
Saves PNGs to output_dir/figures/ with deterministic naming.
"""
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple

import fitz  # PyMuPDF
from loguru import logger


MIN_DIMENSION = 50  # skip icons / decorative dots smaller than this
SUBDIR_NAME = "figures"


@dataclass
class ExtractedImage:
    """Metadata for an extracted image from PDF."""
    figure_id: str           # "fig_p{page}_{idx}"
    page: int                # 1-based
    image_path: Path
    bbox: Tuple[float, float, float, float]  # PDF coords on page
    width: int               # pixels
    height: int


def extract_images_from_pdf(pdf_path: Path, output_dir: Path) -> List[ExtractedImage]:
    """Extract all embedded images, save as PNG, return metadata list.

    Args:
        pdf_path: Path to input PDF file.
        output_dir: Directory where figures/ subdirectory will be created.

    Returns:
        List of ExtractedImage with path, page, bbox, and dimensions.
    """
    pdf_path = Path(pdf_path)
    figures_dir = Path(output_dir) / SUBDIR_NAME
    figures_dir.mkdir(parents=True, exist_ok=True)

    results: List[ExtractedImage] = []
    doc = fitz.open(pdf_path)
    try:
        for page_idx in range(len(doc)):
            page = doc[page_idx]
            page_no = page_idx + 1
            for img_idx, img_info in enumerate(page.get_images(full=True), start=1):
                xref = img_info[0]
                pix = None
                try:
                    pix = fitz.Pixmap(doc, xref)
                    if pix.width < MIN_DIMENSION or pix.height < MIN_DIMENSION:
                        continue
                    if pix.colorspace and pix.colorspace.n >= 4:
                        # CMYK or other → convert to RGB
                        pix = fitz.Pixmap(fitz.csRGB, pix)

                    figure_id = f"fig_p{page_no:03d}_{img_idx:02d}"
                    image_path = figures_dir / f"{figure_id}.png"
                    pix.save(str(image_path))

                    # bbox: best-effort via image rects on page
                    rects = page.get_image_rects(xref)
                    bbox = tuple(rects[0]) if rects else (0.0, 0.0, 0.0, 0.0)

                    results.append(ExtractedImage(
                        figure_id=figure_id,
                        page=page_no,
                        image_path=image_path,
                        bbox=bbox,
                        width=pix.width,
                        height=pix.height,
                    ))
                except Exception as e:
                    logger.warning(f"Failed extracting image {xref} on page {page_no}: {e}")
                finally:
                    if pix is not None:
                        pix = None
    finally:
        doc.close()

    logger.info(f"Extracted {len(results)} images from {pdf_path.name}")
    return results
