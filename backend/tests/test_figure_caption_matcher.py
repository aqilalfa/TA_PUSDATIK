import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.core.ingestion.figures.caption_matcher import (
    find_caption_for_image,
    extract_figure_number,
)


SAMPLE_MD = """\
Beberapa paragraf intro.

![](_page_25_Picture_3.jpeg)

Bobot Penilaian Domain SPBE
16,50% 13% 25% 45,50%

Gambar 7. Grafik Bobot Penilaian Domain SPBE

Selanjutnya pada Gambar 8 ditampilkan...

![](_page_25_Picture_5.jpeg)

Gambar 8. Grafik Bobot Penilaian Aspek SPBE
"""


def test_extract_figure_number():
    assert extract_figure_number("Gambar 7. Grafik Bobot Penilaian Domain SPBE") == "Gambar 7"
    assert extract_figure_number("Tabel 5. Daftar Indeks") == "Tabel 5"
    assert extract_figure_number("No caption here") == ""


def test_find_caption_for_image_picks_nearest_after():
    """Caption right after image ref should match."""
    caption = find_caption_for_image(SAMPLE_MD, page=25, image_index=3)
    assert "Gambar 7" in caption
    assert "Grafik Bobot Penilaian Domain SPBE" in caption


def test_find_caption_for_image_second_image():
    caption = find_caption_for_image(SAMPLE_MD, page=25, image_index=5)
    assert "Gambar 8" in caption


def test_find_caption_returns_empty_when_no_match():
    caption = find_caption_for_image("only text\nno images", page=1, image_index=1)
    assert caption == ""
