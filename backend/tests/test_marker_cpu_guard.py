"""Tests for Marker runtime safety guard."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_should_skip_marker_without_gpu_by_default(monkeypatch, tmp_path):
    from app.core.ingestion import marker_converter as mc

    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n%%EOF")

    monkeypatch.setattr(mc.MarkerConfig, "ALLOW_CPU_MARKER", False)
    monkeypatch.setattr(
        mc,
        "get_pdf_info",
        lambda _path: {
            "exists": True,
            "size_mb": 1,
            "pages": 30,
            "encrypted": False,
            "valid": True,
            "error": None,
        },
    )
    monkeypatch.setattr(mc, "get_gpu_memory_info", lambda: {"available": False})

    skip_marker, reason, details = mc.should_skip_marker(pdf_path)

    assert skip_marker is True
    assert "GPU tidak tersedia" in reason
    assert details["pdf_info"]["pages"] == 30


def test_should_not_skip_marker_when_gpu_available(monkeypatch, tmp_path):
    from app.core.ingestion import marker_converter as mc

    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n%%EOF")

    monkeypatch.setattr(mc.MarkerConfig, "ALLOW_CPU_MARKER", False)
    monkeypatch.setattr(
        mc,
        "get_pdf_info",
        lambda _path: {
            "exists": True,
            "size_mb": 1,
            "pages": 30,
            "encrypted": False,
            "valid": True,
            "error": None,
        },
    )
    monkeypatch.setattr(mc, "get_gpu_memory_info", lambda: {"available": True})

    skip_marker, reason, _details = mc.should_skip_marker(pdf_path)

    assert skip_marker is False
    assert reason == ""
