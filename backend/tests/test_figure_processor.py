import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

from app.core.ingestion.figures.processor import process_figures
from app.core.ingestion.figures.image_extractor import ExtractedImage


SAMPLE_MD = """\
Pendahuluan.

![](_page_25_Picture_3.jpeg)

Gambar 7. Grafik Bobot Penilaian Domain SPBE

Lalu paragraf lain.

![](_page_30_Picture_1.jpeg)

Foto Presiden saat penyerahan

![](_page_45_Picture_2.jpeg)

Tabel 12. Daftar instansi peserta evaluasi
"""


def _make_extracted_image(page, idx, tmp_path):
    fid = f"fig_p{page:03d}_{idx:02d}"
    p = tmp_path / f"{fid}.png"
    p.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
    return ExtractedImage(
        figure_id=fid,
        page=page,
        image_path=p,
        bbox=(0, 0, 100, 100),
        width=800,
        height=600,
    )


def test_process_figures_routes_chart_to_vlm_and_skips_photo(tmp_path):
    images = [
        _make_extracted_image(26, 1, tmp_path),  # page 25 marker → page 26 fitz; chart
        _make_extracted_image(31, 1, tmp_path),  # page 30 marker → page 31 fitz; photo
        _make_extracted_image(46, 1, tmp_path),  # page 45 marker → page 46 fitz; table
    ]

    with patch("app.core.ingestion.figures.processor.extract_images_from_pdf", return_value=images), \
         patch("app.core.ingestion.figures.processor.extract_with_vlm", return_value=("VLM summary", "VLM detail", "qwen3-vl:4b")) as vlm_mock, \
         patch("app.core.ingestion.figures.processor.extract_table_with_ocr", return_value=("OCR summary", "OCR detail", "raw text")) as ocr_mock:

        results = process_figures(
            pdf_path=tmp_path / "fake.pdf",
            marker_md=SAMPLE_MD,
            output_dir=tmp_path,
            use_cache=False,
        )

    by_id = {r.figure_id: r for r in results}
    assert "fig_p026_01" in by_id
    assert "fig_p046_01" in by_id
    # Photo and diagram/timeline are completely excluded from results
    assert "fig_p031_01" not in by_id

    chart = by_id["fig_p026_01"]
    assert chart.extraction_method == "vlm"
    assert chart.figure_type == "bar_chart"
    assert chart.figure_number == "Gambar 7"
    assert "VLM summary" in chart.summary

    table = by_id["fig_p046_01"]
    assert table.extraction_method == "ocr"
    assert table.figure_type == "table_image"
    assert table.figure_number == "Tabel 12"

    assert vlm_mock.call_count == 1
    assert ocr_mock.call_count == 1


def test_process_figures_uses_cache_on_second_run(tmp_path):
    images = [_make_extracted_image(26, 1, tmp_path)]

    # First call — VLM is called
    with patch("app.core.ingestion.figures.processor.extract_images_from_pdf", return_value=images), \
         patch("app.core.ingestion.figures.processor.extract_with_vlm", return_value=("S", "D", "qwen3-vl:4b")) as vlm:
        process_figures(
            pdf_path=tmp_path / "fake.pdf",
            marker_md=SAMPLE_MD,
            output_dir=tmp_path,
            use_cache=True,
        )
        assert vlm.call_count == 1

    # Second call — cache hit, VLM not called
    with patch("app.core.ingestion.figures.processor.extract_images_from_pdf", return_value=images), \
         patch("app.core.ingestion.figures.processor.extract_with_vlm") as vlm2:
        results = process_figures(
            pdf_path=tmp_path / "fake.pdf",
            marker_md=SAMPLE_MD,
            output_dir=tmp_path,
            use_cache=True,
        )
        assert vlm2.call_count == 0
        assert results[0].summary == "S"
