import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

def test_source_dict_includes_doc_id():
    """Source dict built by retrieve_context must include numeric doc_id field."""
    from langchain_core.documents import Document
    from app.core.rag.langchain_engine import LangchainRAGEngine

    engine = LangchainRAGEngine.__new__(LangchainRAGEngine)
    # Minimum attrs used by _format_context + source builder
    fake_doc = Document(
        page_content="dummy",
        metadata={
            "document_id": 7,
            "doc_id": "7",
            "filename": "PP Nomor 71 Tahun 2019.pdf",
            "document_title": "PP Nomor 71 Tahun 2019.pdf",
            "judul_dokumen": "PP Nomor 71 Tahun 2019",
        },
    )
    sources = engine._build_sources_list([fake_doc])

    assert sources[0]["doc_id"] == "7"
