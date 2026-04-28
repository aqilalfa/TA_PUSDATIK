"""VLM-based figure extraction via Ollama.

Uses qwen3-vl:4b (4.4B params, fits 4GB VRAM) by default.
Different prompt templates per figure_type for chart vs diagram.
"""
import base64
import re
from pathlib import Path
from typing import Tuple

import httpx
from loguru import logger

from app.config import settings


VLM_MODEL = "qwen3-vl:4b"
VLM_TIMEOUT = 180.0  # seconds per inference

CHART_PROMPT = """Anda adalah asisten yang mendeskripsikan chart/grafik dalam bahasa Indonesia.

Caption gambar: "{caption}"

Tugas: deskripsikan chart pada gambar ini dengan AKURAT. Sebutkan:
1. Tipe chart (pie/bar/line)
2. Semua label dan nilai numerik secara EKSAK (jangan dibulatkan)
3. Trend atau pola jika ada

Format output (wajib pakai label SUMMARY dan DETAIL):
SUMMARY: [1-2 kalimat ringkas berisi list label+nilai]
DETAIL: [paragraf 100-300 kata, deskripsi lengkap]
"""

DIAGRAM_PROMPT = """Anda adalah asisten yang mendeskripsikan diagram dalam bahasa Indonesia.

Caption gambar: "{caption}"

Tugas: deskripsikan struktur dan konten diagram. Sebutkan:
1. Tipe diagram (alur, hierarki, struktur, kriteria, dll)
2. Semua label, level, dan kriteria yang tertulis di gambar
3. Hubungan antar elemen (jika ada panah / koneksi)

Format output (wajib pakai label SUMMARY dan DETAIL):
SUMMARY: [1-2 kalimat]
DETAIL: [paragraf, mention setiap level/kriteria yang terlihat]
"""


def _select_prompt(figure_type: str, caption: str) -> str:
    """Select appropriate prompt template based on figure type."""
    if figure_type in ("pie_chart", "bar_chart", "line_chart"):
        return CHART_PROMPT.format(caption=caption)
    return DIAGRAM_PROMPT.format(caption=caption)


def parse_vlm_output(raw: str) -> Tuple[str, str]:
    """Split raw VLM output into (summary, detail).

    Expects 'SUMMARY: ...' and 'DETAIL: ...' labels.
    Falls back to first-line vs rest if labels missing.

    Args:
        raw: Raw output string from VLM.

    Returns:
        Tuple of (summary, detail) strings.
    """
    summary_match = re.search(
        r"SUMMARY\s*:\s*(.+?)(?=DETAIL\s*:|$)",
        raw,
        re.DOTALL | re.IGNORECASE,
    )
    detail_match = re.search(r"DETAIL\s*:\s*(.+)$", raw, re.DOTALL | re.IGNORECASE)

    if summary_match and detail_match:
        return summary_match.group(1).strip(), detail_match.group(1).strip()

    # Fallback: first non-empty paragraph as summary, rest as detail
    parts = [p.strip() for p in raw.split("\n\n") if p.strip()]
    if len(parts) >= 2:
        return parts[0], "\n\n".join(parts[1:])
    if parts:
        return parts[0], parts[0]
    return "", ""


def extract_with_vlm(
    image_path: Path,
    figure_type: str,
    caption: str,
    model: str = VLM_MODEL,
) -> Tuple[str, str, str]:
    """Call Ollama VLM, return (summary, detail, model_used).

    Args:
        image_path: Path to image file.
        figure_type: Type of figure (pie_chart, bar_chart, etc.).
        caption: Figure caption text from PDF.
        model: VLM model name (default: qwen3-vl:4b).

    Returns:
        Tuple of (summary, detail, model_used).

    Raises:
        httpx.HTTPError: On transport/HTTP error (caller should catch and skip).
    """
    image_path = Path(image_path)
    image_b64 = base64.b64encode(image_path.read_bytes()).decode("ascii")
    prompt = _select_prompt(figure_type, caption)

    payload = {
        "model": model,
        "prompt": prompt,
        "images": [image_b64],
        "stream": False,
        "options": {"temperature": 0.1, "num_predict": 800},
    }

    url = f"{settings.OLLAMA_BASE_URL}/api/generate"
    logger.debug(f"VLM request: {model} for {image_path.name} ({figure_type})")

    with httpx.Client(timeout=VLM_TIMEOUT) as client:
        response = client.post(url, json=payload)
        response.raise_for_status()
        raw = response.json().get("response", "")

    summary, detail = parse_vlm_output(raw)
    logger.debug(f"VLM result: summary={len(summary)}ch, detail={len(detail)}ch")
    return summary, detail, model
