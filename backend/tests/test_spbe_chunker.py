import pytest
from app.core.ingestion.structured_chunker import chunk_document

def test_laporan_spbe_chunking():
    mock_json = {
        "type": "laporan_spbe",
        "metadata_dokumen": {
            "tahun_evaluasi": "2024",
            "penerbit": "Kementerian PANRB"
        },
        "data_capaian_instansi": [
            {
                "nama_instansi": "Badan Kepegawaian Negara",
                "jenis_instansi": "Kementerian",
                "kategori_wilayah": "Nasional",
                "skor_domain": {
                    "kebijakan_internal": 4.4,
                    "tata_kelola": 4.0,
                    "manajemen_spbe": 3.55,
                    "layanan_spbe": 4.19
                },
                "indeks_spbe_akhir": 4.06,
                "predikat": "Sangat Baik"
            }
        ]
    }
    
    chunks = chunk_document(mock_json)
    
    # We expect 1 chunk for the agency
    agency_chunks = [c for c in chunks if c.get("metadata", {}).get("doc_type") == "laporan_spbe"]
    assert len(agency_chunks) == 1
    
    chunk = agency_chunks[0]
    assert "Badan Kepegawaian Negara" in chunk["text"]
    assert "4.06" in chunk["text"]
    assert "Sangat Baik" in chunk["text"]
    
    # Check Metadata Injection
    assert chunk["metadata"]["tahun_evaluasi"] == "2024"
    assert chunk["metadata"]["nama_instansi"] == "Badan Kepegawaian Negara"
    assert chunk["metadata"]["indeks_spbe"] == 4.06

if __name__ == "__main__":
    test_laporan_spbe_chunking()
    print("Test finished")
