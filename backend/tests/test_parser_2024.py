import pytest
import os
import json
from app.core.ingestion.json_structure_parser import parse_document

def test_parse_laporan_2024_extracts_capaian():
    # Simulasikan isi markdown Laporan 2024
    md_content = """# Laporan Evaluasi SPBE Tahun 2024
    
Tabel 9. Hasil Evaluasi SPBE Kementerian
| No | Nama Instansi | D1 | D2 | D3 | D4 | Indeks | Predikat |
|---|---|---|---|---|---|---|---|
| 1 | Kementerian A | 4.0 | 3.0 | 2.0 | 4.0 | 3.25 | Baik |
| 2 | Kementerian B | 5.0 | 4.0 | 3.0 | 5.0 | 4.25 | Memuaskan |

Tabel 10. Hasil Evaluasi SPBE Lembaga Pemerintah Non Kementerian (LPNK)
| No | Nama Instansi | D1 | D2 | D3 | D4 | Indeks | Predikat |
|---|---|---|---|---|---|---|---|
| 1 | Badan X | 3.0 | 2.0 | 1.0 | 3.0 | 2.25 | Cukup |
"""
    doc = parse_document(text=md_content, filename="Laporan_Evaluasi_SPBE_2024.pdf", folder_hint="laporan")
    
    assert doc.get("type") == "laporan_spbe"
    capaian = doc.get("data_capaian_instansi", [])
    assert len(capaian) == 3
    assert capaian[0]["nama_instansi"] == "Kementerian A"
    assert capaian[0]["indeks_spbe_akhir"] == 3.25
    assert doc["metadata_dokumen"]["tahun_evaluasi"] == "2024"
    assert capaian[0]["jenis_instansi"] == "Kementerian"
    
    assert capaian[2]["nama_instansi"] == "Badan X"
    assert capaian[2]["jenis_instansi"] == "Lembaga Pemerintah Non Kementerian (LPNK)"
