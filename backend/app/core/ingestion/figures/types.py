"""Type definitions for figure extraction pipeline."""
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


FIGURE_TYPES = frozenset({
    "pie_chart",
    "bar_chart",
    "line_chart",
    "diagram",
    "timeline_image",
    "table_image",
    "photo",
})


@dataclass
class FigureExtraction:
    """Result of processing one figure (image) from a PDF.

    For 'photo' type, summary/detail may be empty (figure skipped from chunks).
    """
    figure_id: str               # "fig_p26_01"
    figure_number: str           # "Gambar 7"
    caption: str                 # "Grafik Bobot Penilaian Domain SPBE"
    figure_type: str             # one of FIGURE_TYPES
    page: int                    # 1-based page number
    image_path: Path
    summary: str                 # 1-2 kalimat untuk inline injection
    detail: str                  # full description for figure chunk
    raw_ocr: Optional[str]       # raw PaddleOCR text (table_image only)
    extraction_method: str       # "vlm" | "ocr" | "skipped"
    extraction_model: Optional[str]  # e.g. "qwen3-vl:4b"
