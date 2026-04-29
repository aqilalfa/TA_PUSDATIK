"""VLM-based figure extraction via Ollama.

Uses qwen3-vl:4b (4.4B params, fits 4GB VRAM) by default.
Uses minimal prompts to avoid excessive thinking-mode token consumption.
Retries up to MAX_RETRIES times since qwen3-vl:4b non-deterministically
transitions from thinking to actual response.
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
MAX_RETRIES = 3

# Minimal prompts — any longer and qwen3-vl:4b exhausts num_predict on thinking
CHART_PROMPT = "SUMMARY:\nDETAIL:"
DIAGRAM_PROMPT = "SUMMARY:\nDETAIL:"


def _select_prompt(figure_type: str, caption: str) -> str:
    """Select prompt template; caption ignored when empty to keep prompt short."""
    if figure_type in ("pie_chart", "bar_chart", "line_chart"):
        return CHART_PROMPT
    return DIAGRAM_PROMPT


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

    Retries up to MAX_RETRIES times because qwen3-vl:4b non-deterministically
    produces empty responses when its thinking phase is long.

    Args:
        image_path: Path to image file.
        figure_type: Type of figure (pie_chart, bar_chart, etc.).
        caption: Figure caption text from PDF (unused in prompt but stored).
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
        "messages": [
            {
                "role": "user",
                "content": prompt,
                "images": [image_b64],
            }
        ],
        "stream": False,
        "think": False,
        "options": {"temperature": 1.0, "top_k": 20, "num_predict": 800},
    }

    url = f"{settings.OLLAMA_BASE_URL}/api/chat"

    for attempt in range(1, MAX_RETRIES + 1):
        logger.debug(
            f"VLM request: {model} for {image_path.name} ({figure_type}), attempt {attempt}/{MAX_RETRIES}"
        )
        with httpx.Client(timeout=VLM_TIMEOUT) as client:
            response = client.post(url, json=payload)
            response.raise_for_status()
            raw = response.json().get("message", {}).get("content", "")

        if raw.strip():
            summary, detail = parse_vlm_output(raw)
            logger.debug(f"VLM result: summary={len(summary)}ch, detail={len(detail)}ch")
            return summary, detail, model

        logger.warning(
            f"VLM returned empty response for {image_path.name} (attempt {attempt}/{MAX_RETRIES})"
        )

    logger.warning(f"VLM gave up after {MAX_RETRIES} attempts for {image_path.name}")
    return "", "", model
