import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pathlib import Path
from app.core.ingestion.figures.cache import save_cache, load_cache, image_hash
from app.core.ingestion.figures.types import FigureExtraction


def _make_fig(tmp_path, fid="fig_p01_01"):
    img = tmp_path / f"{fid}.png"
    img.write_bytes(b"PNGDATA" * 50)
    return FigureExtraction(
        figure_id=fid,
        figure_number="Gambar 1",
        caption="Test",
        figure_type="diagram",
        page=1,
        image_path=img,
        summary="sum",
        detail="det",
        raw_ocr=None,
        extraction_method="vlm",
        extraction_model="qwen3-vl:4b",
    )


def test_image_hash_stable(tmp_path):
    img = tmp_path / "a.png"
    img.write_bytes(b"hello world")
    h1 = image_hash(img)
    h2 = image_hash(img)
    assert h1 == h2
    assert h1.startswith("sha256:")


def test_save_and_load_cache_roundtrip(tmp_path):
    figs = [_make_fig(tmp_path, "fig_p01_01"), _make_fig(tmp_path, "fig_p02_01")]
    cache_path = tmp_path / "figures.json"

    save_cache(cache_path, figs)
    loaded = load_cache(cache_path)

    assert len(loaded) == 2
    assert loaded[0].figure_id == "fig_p01_01"
    assert loaded[0].extraction_method == "vlm"
    assert loaded[0].image_path.exists()


def test_load_cache_returns_empty_when_missing(tmp_path):
    assert load_cache(tmp_path / "missing.json") == []
