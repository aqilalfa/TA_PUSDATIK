# backend/tests/test_figure_classifier.py
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from app.core.ingestion.figures.classifier import classify


CASES = [
    # (caption, dims, expected_type)
    ("Gambar 7. Grafik Bobot Penilaian Domain SPBE",        (800, 600), "bar_chart"),
    ("Gambar 8. Grafik Bobot Penilaian Aspek SPBE",         (800, 600), "bar_chart"),
    ("Gambar 1. Capaian Indeks SPBE Nasional 2018-2024",    (1000, 500), "line_chart"),
    ("Gambar X. Pie chart distribusi instansi",             (600, 600), "pie_chart"),
    ("Gambar X. Diagram lingkaran komposisi",               (600, 600), "pie_chart"),
    ("Gambar X. Diagram batang capaian",                    (800, 500), "bar_chart"),
    ("Gambar 4. Kriteria Tingkat Kematangan Proses",        (900, 700), "diagram"),
    ("Gambar 6. Struktur Penilaian Tingkat Kematangan SPBE",(900, 700), "diagram"),
    ("Gambar 3. Tim Koordinasi SPBE",                       (900, 700), "diagram"),
    ("Gambar 10. Lini Masa Pelaksanaan Evaluasi SPBE 2024", (1500, 400), "timeline_image"),
    ("Tabel 5. Daftar Instansi (sebagai gambar)",           (900, 1200), "table_image"),
    ("Foto Presiden saat penyerahan award",                 (800, 600), "photo"),
    ("Gambar X. Tim pelaksanaan",                           (800, 600), "photo"),
    ("Gambar tanpa caption deskriptif",                     (3000, 800), "timeline_image"),  # aspect-ratio fallback
    ("Gambar tanpa caption deskriptif",                     (800, 600), "diagram"),  # default
]


@pytest.mark.parametrize("caption,dims,expected", CASES)
def test_classify(caption, dims, expected):
    assert classify(caption, dims) == expected
