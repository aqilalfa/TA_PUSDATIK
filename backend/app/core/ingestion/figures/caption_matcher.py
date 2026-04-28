"""Match figure captions to extracted images via Marker markdown."""
import re
from typing import List, Tuple


IMG_REF_RE = re.compile(r"!\[\]\(_page_(\d+)_Picture_(\d+)\.jpeg\)")
CAPTION_RE = re.compile(r"^(Gambar|Tabel|Foto)\s+[\w\d]", re.MULTILINE)
FIG_NUMBER_RE = re.compile(r"^(Gambar|Tabel)\s+\d+", re.MULTILINE)


def extract_figure_number(line: str) -> str:
    """Extract 'Gambar N' or 'Tabel N' from start of a line."""
    m = FIG_NUMBER_RE.match((line or "").strip())
    return m.group(0) if m else ""


def _find_image_refs(markdown: str) -> List[Tuple[int, int, int]]:
    """Return list of (page, image_index, char_offset)."""
    refs = []
    for m in IMG_REF_RE.finditer(markdown):
        page = int(m.group(1))
        idx = int(m.group(2))
        refs.append((page, idx, m.start()))
    return refs


def _find_captions(markdown: str) -> List[Tuple[int, str]]:
    """Return list of (char_offset, full_caption_line)."""
    captions = []
    for m in CAPTION_RE.finditer(markdown):
        line_start = m.start()
        line_end = markdown.find("\n", line_start)
        line_end = line_end if line_end != -1 else len(markdown)
        captions.append((line_start, markdown[line_start:line_end].strip()))
    return captions


def find_caption_for_image(markdown: str, page: int, image_index: int) -> str:
    """Find caption that follows the image ref for (page, image_index).

    Marker uses 0-based page numbers in image refs; PyMuPDF uses 1-based.
    We try both: page-1 (Marker convention) first, then page.

    Returns caption string, or "" if no match.
    """
    refs = _find_image_refs(markdown)
    captions = _find_captions(markdown)

    # Build sorted list of all image ref offsets for "stop at next image" logic
    all_ref_offsets = sorted(o for _, _, o in refs)

    # Try Marker convention (0-based) first
    for marker_page in (page - 1, page):
        match = next(
            (offset for p, idx, offset in refs if p == marker_page and idx == image_index),
            None,
        )
        if match is not None:
            # Find the offset of the NEXT image ref after this one (upper bound)
            next_ref = next((o for o in all_ref_offsets if o > match), match + 500)
            search_end = min(match + 500, next_ref)
            # Find first caption AFTER this image offset, before next image ref
            for cap_offset, cap_text in captions:
                if match < cap_offset <= search_end:
                    return cap_text
            return ""
    return ""
