"""Sidecar JSON cache for FigureExtraction results."""
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from loguru import logger

from app.core.ingestion.figures.types import FigureExtraction


def image_hash(image_path: Path) -> str:
    """SHA-256 hash of image bytes, prefixed with 'sha256:'."""
    h = hashlib.sha256()
    h.update(Path(image_path).read_bytes())
    return f"sha256:{h.hexdigest()}"


def save_cache(cache_path: Path, figures: List[FigureExtraction]) -> None:
    """Serialize figures to JSON sidecar."""
    cache_path = Path(cache_path)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    payload = []
    for f in figures:
        payload.append({
            "figure_id": f.figure_id,
            "figure_number": f.figure_number,
            "caption": f.caption,
            "figure_type": f.figure_type,
            "page": f.page,
            "image_path": str(f.image_path),
            "image_hash": image_hash(f.image_path) if f.image_path.exists() else None,
            "summary": f.summary,
            "detail": f.detail,
            "raw_ocr": f.raw_ocr,
            "extraction_method": f.extraction_method,
            "extraction_model": f.extraction_model,
            "cached_at": datetime.now().isoformat(),
        })
    cache_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(f"Saved {len(figures)} figure entries to {cache_path}")


def load_cache(cache_path: Path) -> List[FigureExtraction]:
    """Load cached figures. Returns [] if file missing or invalid."""
    cache_path = Path(cache_path)
    if not cache_path.exists():
        return []
    try:
        data = json.loads(cache_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        logger.warning(f"Invalid cache JSON: {cache_path} — treating as empty")
        return []

    return [
        FigureExtraction(
            figure_id=e["figure_id"],
            figure_number=e["figure_number"],
            caption=e["caption"],
            figure_type=e["figure_type"],
            page=e["page"],
            image_path=Path(e["image_path"]),
            summary=e["summary"],
            detail=e["detail"],
            raw_ocr=e.get("raw_ocr"),
            extraction_method=e["extraction_method"],
            extraction_model=e.get("extraction_model"),
        )
        for e in data
    ]


def get_cached_for_image(cache: List[FigureExtraction], image_path: Path) -> Optional[FigureExtraction]:
    """Find cached entry matching image by hash. Returns None if not cached."""
    if not image_path.exists():
        return None
    target_hash = image_hash(image_path)
    cache_path = Path(image_path)
    for entry in cache:
        if entry.image_path == cache_path and entry.image_path.exists():
            if image_hash(entry.image_path) == target_hash:
                return entry
    return None
