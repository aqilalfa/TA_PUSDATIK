import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pathlib import Path
from app.core.ingestion.figures.types import FigureExtraction, FIGURE_TYPES


def test_figure_extraction_required_fields():
    fig = FigureExtraction(
        figure_id="fig_p26_01",
        figure_number="Gambar 7",
        caption="Grafik Bobot Penilaian Domain SPBE",
        figure_type="pie_chart",
        page=26,
        image_path=Path("/tmp/x.png"),
        summary="Bobot: Layanan 45,5%, Tata Kelola 25%",
        detail="Pie chart menampilkan...",
        raw_ocr=None,
        extraction_method="vlm",
        extraction_model="qwen3-vl:4b",
    )
    assert fig.figure_id == "fig_p26_01"
    assert fig.figure_type == "pie_chart"
    assert fig.extraction_method == "vlm"


def test_figure_types_enum():
    assert "pie_chart" in FIGURE_TYPES
    assert "bar_chart" in FIGURE_TYPES
    assert "line_chart" in FIGURE_TYPES
    assert "diagram" in FIGURE_TYPES
    assert "timeline_image" in FIGURE_TYPES
    assert "table_image" in FIGURE_TYPES
    assert "photo" in FIGURE_TYPES
    assert len(FIGURE_TYPES) == 7


def test_package_exports_processor():
    from app.core.ingestion.figures import process_figures, FigureExtraction
    assert callable(process_figures)
    assert FigureExtraction.__name__ == "FigureExtraction"
