from app.core.ingestion.document_manager import detect_document_type


def test_detect_document_type_treats_perka_bssn_filename_as_peraturan():
    text = "PERKA BSSN NOMOR 2 TAHUN 2023 TENTANG PENYELENGGARAAN SPBE"

    assert detect_document_type("PERKA_BSSN_NOMOR_2_TAHUN_2023.pdf", text) == "peraturan"


def test_detect_document_type_treats_bssn_pasal_content_as_peraturan():
    text = """
    PERATURAN BADAN SIBER DAN SANDI NEGARA
    NOMOR 2 TAHUN 2023
    BAB I KETENTUAN UMUM
    Pasal 1
    Dalam Peraturan Kepala Badan ini yang dimaksud dengan...
    """

    assert detect_document_type("dokumen_internal.pdf", text) == "peraturan"


def test_chunk_document_keeps_structured_peraturan_chunks_when_markdown_lacks_legal_metadata(tmp_path):
    from app.core.ingestion.structured_chunker import chunk_document

    marker_markdown = tmp_path / "perka_bssn.md"
    marker_markdown.write_text(
        "\n".join(
            [
                "# PERKA BSSN NOMOR 2 TAHUN 2023",
                "Teks pembuka.",
                "## BAB I KETENTUAN UMUM",
                "Bagian umum tanpa metadata pasal.",
                "### Subbagian A",
                "Isi markdown fallback pertama.",
                "### Subbagian B",
                "Isi markdown fallback kedua.",
            ]
        ),
        encoding="utf-8",
    )
    structured_doc = {
        "type": "peraturan",
        "metadata_dokumen": {
            "jenis_peraturan": "PERKA BSSN",
            "nomor": "2",
            "tahun": "2023",
            "tentang": "Penyelenggaraan SPBE di Lingkungan BSSN",
            "sumber_file": "perka_bssn_2_2023.pdf",
        },
        "batang_tubuh": [
            {
                "bab_nomor": "I",
                "bab_judul": "KETENTUAN UMUM",
                "pasal": [
                    {
                        "nomor": "4",
                        "isi": "Ruang lingkup penyelenggaraan SPBE di lingkungan BSSN meliputi Tata Kelola SPBE BSSN.",
                        "ayat": [],
                    }
                ],
            }
        ],
        "lampiran": {},
    }

    chunks = chunk_document(structured_doc, md_file_path=str(marker_markdown))

    assert any(chunk["metadata"].get("pasal") == "Pasal 4" for chunk in chunks)
    assert all(chunk["metadata"].get("doc_type") == "peraturan" for chunk in chunks)
