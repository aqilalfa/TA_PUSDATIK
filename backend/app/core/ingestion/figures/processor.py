"""Orchestrator: extract images → classify → route to VLM/OCR → cache."""
from pathlib import Path
from typing import List

from loguru import logger

from app.core.ingestion.figures.types import FigureExtraction
from app.core.ingestion.figures.image_extractor import (
    extract_images_from_pdf,
    ExtractedImage,
)
from app.core.ingestion.figures.classifier import classify
from app.core.ingestion.figures.caption_matcher import (
    find_caption_for_image,
    extract_figure_number,
    _find_image_refs,
)
from app.core.ingestion.figures.vlm_extractor import extract_with_vlm
from app.core.ingestion.figures.ocr_extractor import extract_table_with_ocr
from app.core.ingestion.figures.cache import (
    save_cache,
    load_cache,
    image_hash,
)


CACHE_FILENAME = "figures.json"
VLM_TYPES = {"pie_chart", "bar_chart", "line_chart", "diagram", "timeline_image"}
OCR_TYPES = {"table_image"}


def _image_idx_from_id(figure_id: str) -> int:
    """fig_p026_01 → 1"""
    return int(figure_id.rsplit("_", 1)[-1])


def _find_caption_for_extracted_image(
    markdown: str,
    img: ExtractedImage,
    page_image_order: int,
) -> str:
    """Find caption for an extracted image.

    Tries:
    1. Exact match via figure_id's trailing index (Marker Picture index).
    2. Falls back to nth image ref on the same Marker page (0-based ordinal).

    page_image_order: 0-based index of this image among all images on same fitz page.
    """
    idx = _image_idx_from_id(img.figure_id)

    # Try exact match first
    caption = find_caption_for_image(markdown, page=img.page, image_index=idx)
    if caption:
        return caption

    # Fallback: find all image refs on this Marker page (try page-1 and page)
    refs = _find_image_refs(markdown)
    for marker_page in (img.page - 1, img.page):
        page_refs = [(p, i, o) for p, i, o in refs if p == marker_page]
        page_refs.sort(key=lambda x: x[2])  # sort by char offset
        if page_image_order < len(page_refs):
            _, actual_idx, _ = page_refs[page_image_order]
            caption = find_caption_for_image(markdown, page=marker_page + 1, image_index=actual_idx)
            if caption:
                return caption
            # Try direct with marker_page (not +1)
            caption = find_caption_for_image(markdown, page=marker_page, image_index=actual_idx)
            if caption:
                return caption
    return ""


def _build_extraction(
    img: ExtractedImage,
    caption: str,
    figure_type: str,
) -> FigureExtraction:
    """Run the right extractor based on figure_type, build FigureExtraction."""
    figure_number = extract_figure_number(caption)

    if figure_type == "photo":
        return FigureExtraction(
            figure_id=img.figure_id,
            figure_number=figure_number,
            caption=caption,
            figure_type=figure_type,
            page=img.page,
            image_path=img.image_path,
            summary="",
            detail="",
            raw_ocr=None,
            extraction_method="skipped",
            extraction_model=None,
        )

    summary = ""
    detail = ""
    raw_ocr = None
    method = "skipped"
    model = None

    try:
        if figure_type in VLM_TYPES:
            summary, detail, model = extract_with_vlm(
                image_path=img.image_path,
                figure_type=figure_type,
                caption=caption or f"Gambar pada halaman {img.page}",
            )
            method = "vlm"
        elif figure_type in OCR_TYPES:
            summary, detail, raw_ocr = extract_table_with_ocr(
                image_path=img.image_path,
                caption=caption or f"Tabel pada halaman {img.page}",
            )
            method = "ocr"
    except Exception as e:
        logger.warning(f"Extraction failed for {img.figure_id} ({figure_type}): {e}")
        method = "failed"

    return FigureExtraction(
        figure_id=img.figure_id,
        figure_number=figure_number,
        caption=caption,
        figure_type=figure_type,
        page=img.page,
        image_path=img.image_path,
        summary=summary,
        detail=detail,
        raw_ocr=raw_ocr,
        extraction_method=method,
        extraction_model=model,
    )


def process_figures(
    pdf_path: Path,
    marker_md: str,
    output_dir: Path,
    use_cache: bool = True,
) -> List[FigureExtraction]:
    """Extract & process all figures from a PDF.

    output_dir: where extracted PNGs + figures.json sidecar are saved.
    Returns one FigureExtraction per image, including skipped photos.
    """
    pdf_path = Path(pdf_path)
    output_dir = Path(output_dir)
    cache_path = output_dir / CACHE_FILENAME

    cached = load_cache(cache_path) if use_cache else []
    cache_by_hash = {}
    for c in cached:
        if c.image_path.exists():
            cache_by_hash[image_hash(c.image_path)] = c

    images = extract_images_from_pdf(pdf_path, output_dir=output_dir)
    logger.info(f"Processing {len(images)} extracted images")

    # Group images by page to compute per-page order
    page_order: dict = {}
    for img in images:
        page_order.setdefault(img.page, []).append(img.figure_id)

    results: List[FigureExtraction] = []
    for img in images:
        h = image_hash(img.image_path)
        if h in cache_by_hash:
            logger.debug(f"Cache hit: {img.figure_id}")
            results.append(cache_by_hash[h])
            continue

        order_in_page = page_order[img.page].index(img.figure_id)
        caption = _find_caption_for_extracted_image(marker_md, img, order_in_page)
        figure_type = classify(caption, (img.width, img.height))
        logger.info(f"  {img.figure_id} → {figure_type} (caption: {caption[:60]!r})")

        extraction = _build_extraction(img, caption, figure_type)
        results.append(extraction)

    save_cache(cache_path, results)
    return results
