"""Tests for VLM-based figure extraction via Ollama."""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

from app.core.ingestion.figures.vlm_extractor import (
    extract_with_vlm,
    parse_vlm_output,
    VLM_MODEL,
    MAX_RETRIES,
    CHART_PROMPT,
    DIAGRAM_PROMPT,
)


def test_vlm_default_model_is_qwen3_vl_4b():
    assert VLM_MODEL == "qwen3-vl:4b"


def test_vlm_prompts_are_minimal():
    # Prompts must stay short to avoid qwen3-vl thinking-mode token exhaustion
    assert len(CHART_PROMPT) < 30
    assert len(DIAGRAM_PROMPT) < 30


def test_parse_vlm_output_with_summary_and_detail():
    raw = (
        "SUMMARY: Bobot domain SPBE: Layanan 45,5%, Tata Kelola 25%, "
        "Kebijakan 16,5%, Manajemen 13%.\n"
        "DETAIL: Pie chart yang menampilkan distribusi bobot 4 domain SPBE. "
        "Layanan SPBE memiliki bobot terbesar (45,5%), diikuti Tata Kelola (25%), "
        "Kebijakan Internal (16,5%), dan Manajemen (13%)."
    )
    summary, detail = parse_vlm_output(raw)
    assert "45,5%" in summary
    assert "Layanan" in summary
    assert "Pie chart" in detail
    assert "distribusi bobot" in detail


def test_parse_vlm_output_missing_labels_falls_back_to_split():
    raw = "Bobot domain: Layanan 45,5%, Manajemen 13%.\nDeskripsi pie chart penuh dengan 4 segmen."
    summary, detail = parse_vlm_output(raw)
    assert summary  # non-empty
    assert detail   # non-empty


def test_extract_with_vlm_calls_ollama(tmp_path):
    img = tmp_path / "test.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)  # fake PNG header

    fake_response = MagicMock()
    fake_response.status_code = 200
    fake_response.json.return_value = {
        "message": {"content": "SUMMARY: Test.\nDETAIL: Test detail."}
    }
    fake_response.raise_for_status = MagicMock()

    with patch("app.core.ingestion.figures.vlm_extractor.httpx.Client") as MockClient:
        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.post.return_value = fake_response
        MockClient.return_value = mock_client

        summary, detail, model = extract_with_vlm(
            image_path=img,
            figure_type="pie_chart",
            caption="Gambar 7. Grafik Bobot Penilaian Domain SPBE",
        )

    assert summary == "Test."
    assert detail == "Test detail."
    assert model == "qwen3-vl:4b"
    mock_client.post.assert_called_once()
    # Verify the messages include image and minimal prompt
    call_kwargs = mock_client.post.call_args.kwargs
    messages = call_kwargs["json"]["messages"]
    assert len(messages) == 1
    assert "images" in messages[0]
    assert call_kwargs["json"]["model"] == "qwen3-vl:4b"
    assert call_kwargs["json"]["think"] is False
