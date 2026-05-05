"""Classify figure type from caption text + image dimensions.

Output is one of FIGURE_TYPES. Returned subtype determines downstream routing:
- pie/bar/line_chart, diagram, timeline_image → VLM
- table_image                                  → PaddleOCR
- photo                                        → skipped (no chunk)
"""
import re
from typing import Tuple


def classify(caption: str, image_dims: Tuple[int, int]) -> str:
    """Return one of FIGURE_TYPES based on caption + dims heuristics.

    Args:
        caption: Figure caption text (may be empty or None)
        image_dims: (width, height) tuple in pixels

    Returns:
        One of: pie_chart, bar_chart, line_chart, diagram, timeline_image, table_image, photo
    """
    text = (caption or "").lower()

    # Pass 1: chart subtypes (most specific first)
    if re.search(r"\b(pie|lingkaran)\b", text):
        return "pie_chart"
    if re.search(r"\b(bar|batang)\b", text):
        return "bar_chart"
    if re.search(r"\b(line|garis|tren|capaian.*tahun|indeks.*\d{4})\b", text):
        return "line_chart"
    if re.search(r"\b(grafik|chart)\b", text):
        return "bar_chart"  # default chart subtype

    # Pass 2: structural diagrams
    if re.search(r"\b(lini masa|timeline|kronologi)\b", text):
        return "timeline_image"
    if re.search(r"\b(diagram|struktur|alur|hierarki|kriteria|peta|tingkat)\b", text):
        return "diagram"

    # Pass 3: photos (check before generic "tabel" since photo caption can mention things)
    # Only "foto" explicitly, or "presiden", or "tim pelaksanaan" (people-related photos)
    # "Tim Koordinasi" alone is treated as a diagram, not a photo
    if re.search(r"\b(foto|presiden)\b", text) or re.search(r"tim pelaksanaan", text):
        return "photo"

    # Pass 4: tables
    if re.search(r"\btabel\b", text):
        return "table_image"

    # Fallback: aspect-ratio heuristic
    w, h = image_dims
    if h > 0 and w / h > 2.5:
        return "timeline_image"  # very wide → likely banner / timeline

    return "diagram"
