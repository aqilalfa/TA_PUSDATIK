# backend/tests/test_chunker_figure_integration.py
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pathlib import Path
from app.core.ingestion.structured_chunker import (
    inject_figure_summaries,
    make_figure_chunks,
)
from app.core.ingestion.figures.types import FigureExtraction


def _fig(fid, num, ftype, summary, detail, page=26, method="vlm"):
    return FigureExtraction(
        figure_id=fid,
        figure_number=num,
        caption=f"{num}. Caption",
        figure_type=ftype,
        page=page,
        image_path=Path(f"/tmp/{fid}.png"),
        summary=summary,
        detail=detail,
        raw_ocr=None,
        extraction_method=method,
        extraction_model="qwen3-vl:4b" if method == "vlm" else None,
    )


def test_inject_figure_summaries_adds_line_after_caption():
    md = """\
Lorem ipsum dolor sit amet.

Gambar 7. Caption

Paragraf berikutnya.
"""
    figs = [_fig("fig_p026_01", "Gambar 7", "pie_chart",
                 "Bobot: Layanan 45,5%, Manajemen 13%",
                 "Pie chart penuh deskripsi.")]
    out = inject_figure_summaries(md, figs)
    assert "[Gambar 7] Bobot: Layanan 45,5%, Manajemen 13%" in out
    # Original markdown structure preserved
    assert "Lorem ipsum" in out
    assert "Paragraf berikutnya." in out


def test_inject_skips_photos():
    md = "Foto Presiden\n"
    figs = [_fig("fig_p031_01", "", "photo", "", "", method="skipped")]
    out = inject_figure_summaries(md, figs)
    assert out == md  # unchanged


def test_make_figure_chunks_creates_one_chunk_per_extracted_figure():
    figs = [
        _fig("fig_p026_01", "Gambar 7", "pie_chart", "Bobot: ...", "Pie chart...", page=26),
        _fig("fig_p031_01", "", "photo", "", "", page=31, method="skipped"),
        _fig("fig_p046_01", "Tabel 12", "table_image", "Tabel: ...", "Tabel rincian...", page=46, method="ocr"),
    ]
    chunks = make_figure_chunks(
        figs,
        doc_title="Laporan Evaluasi SPBE 2024",
        filename="spbe.pdf",
        doc_type="laporan",
    )

    # Photo skipped — only 2 chunks
    assert len(chunks) == 2

    chart_chunk = next(c for c in chunks if "Gambar 7" in c["text"])
    assert chart_chunk["chunk_type"] == "figure"
    assert "Pie chart" in chart_chunk["text"]
    # document_manager-compatible format — metadata smuggled in standard fields
    assert chart_chunk["context_header"] == "Figure: Gambar 7"
    assert chart_chunk["section"] == "Gambar 7. Caption"  # full caption
    assert chart_chunk["filename"] == "spbe.pdf"
    assert chart_chunk["doc_type"] == "laporan"
    assert chart_chunk["table_context"] == "pie_chart|fig_p026_01|page:26|vlm"

    table_chunk = next(c for c in chunks if "Tabel 12" in c["text"])
    assert "table_image" in table_chunk["table_context"]
    assert "ocr" in table_chunk["table_context"]
