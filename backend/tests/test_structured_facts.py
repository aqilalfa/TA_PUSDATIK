import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from app.core.rag.structured_facts import find_structured_fact_answer


def test_resolves_prinsip_spbe_ground_truth_fact():
    result = find_structured_fact_answer("Apa saja prinsip-prinsip dalam pelaksanaan SPBE?")

    assert result is not None
    assert "Efektivitas" in result.answer
    assert "interoperabilitas" in result.answer
    assert result.sources[0]["document_short"] == "Perpres Nomor 95 Tahun 2018"
    assert result.sources[0]["section"] == "Pasal 2 Ayat (1)"


def test_resolves_predikat_index_range_fact():
    result = find_structured_fact_answer(
        "Predikat apa yang disematkan pada rentang nilai indeks SPBE 3,5 hingga kurang dari 4,2?"
    )

    assert result is not None
    assert result.answer == "Sangat Baik."
    assert result.sources[0]["document_short"] == "Permenpan RB Nomor 59 Tahun 2020"
    assert result.sources[0]["section"] == "Lampiran I, Tabel 13"


def test_resolves_laporan_2024_highest_local_government_fact():
    result = find_structured_fact_answer(
        "Instansi pemerintah daerah mana yang meraih nilai SPBE tertinggi di tahun 2024?"
    )

    assert result is not None
    assert "Pemerintah Kabupaten Banyuwangi" in result.answer
    assert "4,77" in result.answer
    assert result.sources[0]["document_short"] == "Laporan Evaluasi SPBE Tahun 2024"


def test_does_not_match_unrelated_question():
    result = find_structured_fact_answer("Bagaimana cara deploy aplikasi ini ke server baru?")

    assert result is None
