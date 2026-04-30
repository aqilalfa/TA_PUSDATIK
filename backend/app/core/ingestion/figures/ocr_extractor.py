"""PaddleOCR-based extraction for table-image figures.

Lazy-load PaddleOCR engine to avoid loading at import time
(saves ~200MB RAM when not needed).
"""
from pathlib import Path
from typing import Tuple

import cv2
import numpy as np
from loguru import logger


_paddle_ocr_engine = None


def _get_paddle_ocr():
    """Lazy initialize PaddleOCR engine.

    Falls back to the shared ocr_processor engine if PaddlePaddle's C++ runtime
    (PDX) has already been initialized by another module, since PDX cannot be
    initialized twice in the same process.
    """
    global _paddle_ocr_engine
    if _paddle_ocr_engine is not None:
        return _paddle_ocr_engine

    try:
        from paddleocr import PaddleOCR
        _paddle_ocr_engine = PaddleOCR(
            lang="id",
            use_angle_cls=True,
            use_gpu=False,
            show_log=False,
        )
        logger.info("PaddleOCR engine initialized for figure extraction")
    except Exception as e:
        if "already" in str(e).lower() or "reinitialization" in str(e).lower():
            # PDX runtime already initialized (by ocr.py import). Reuse shared engine.
            logger.warning(f"PDX already initialized ({e}); reusing shared ocr_processor engine")
            from app.core.ingestion.ocr import ocr_processor
            if not ocr_processor._initialized:
                ocr_processor.initialize()
            _paddle_ocr_engine = ocr_processor.ocr_engine
        else:
            raise

    return _paddle_ocr_engine


def extract_table_with_ocr(
    image_path: Path,
    caption: str,
) -> Tuple[str, str, str]:
    """OCR a table image, return (summary, detail, raw_ocr_text)."""
    image_path = Path(image_path)
    img = cv2.imread(str(image_path))
    if img is None:
        logger.warning(f"OCR: cannot read {image_path}")
        return "", "", ""

    engine = _get_paddle_ocr()
    result = engine.ocr(img, cls=True)

    lines = []
    if result and result[0]:
        for line in result[0]:
            text = line[1][0] if line[1] else ""
            if text:
                lines.append(text)

    raw = "\n".join(lines)
    summary, detail = format_ocr_as_summary(raw, caption)
    return summary, detail, raw


def format_ocr_as_summary(raw: str, caption: str) -> Tuple[str, str]:
    """Convert raw OCR output → (summary, detail).

    Summary: caption + first 200 chars hint.
    Detail: caption + full OCR text.
    """
    raw = raw.strip()
    if not raw:
        return f"{caption}: (kosong)", caption

    snippet = raw[:200].replace("\n", " ")
    summary = f"{caption}: {snippet}"
    detail = f"{caption}\n\n{raw}"
    return summary, detail
