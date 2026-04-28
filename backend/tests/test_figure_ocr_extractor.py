import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pathlib import Path
from unittest.mock import patch, MagicMock
import numpy as np

from app.core.ingestion.figures.ocr_extractor import (
    extract_table_with_ocr,
    format_ocr_as_summary,
)


def test_format_ocr_as_summary_short_text():
    raw = "No\tNama\tNilai\n1\tA\t100\n2\tB\t200"
    summary, detail = format_ocr_as_summary(raw, caption="Tabel 1. Daftar Skor")
    assert "Tabel 1" in summary
    assert "100" in detail or "200" in detail


def test_extract_table_with_ocr_returns_text(tmp_path):
    img = tmp_path / "table.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

    fake_ocr_result = [[
        [[[0, 0], [100, 0], [100, 30], [0, 30]], ("Header A", 0.99)],
        [[[0, 30], [100, 30], [100, 60], [0, 60]], ("Cell 1", 0.95)],
    ]]

    with patch("app.core.ingestion.figures.ocr_extractor._get_paddle_ocr") as mock_get, \
         patch("app.core.ingestion.figures.ocr_extractor.cv2.imread", return_value=np.zeros((100, 100, 3), dtype=np.uint8)):
        mock_engine = MagicMock()
        mock_engine.ocr.return_value = fake_ocr_result
        mock_get.return_value = mock_engine

        summary, detail, raw = extract_table_with_ocr(
            image_path=img,
            caption="Tabel X. Test"
        )

    assert "Header A" in raw
    assert "Cell 1" in raw
    assert "Tabel X" in summary
