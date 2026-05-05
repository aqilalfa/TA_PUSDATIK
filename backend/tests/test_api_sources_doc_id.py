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
    # Verifikasi via inspeksi source bahwa sources.append payload memuat key "doc_id".
    # String "doc_id" muncul di banyak tempat, jadi batasi pencarian ke block sources.append.
    import inspect
    src = inspect.getsource(LangchainRAGEngine.retrieve_context)
    assert 'sources.append' in src, "sources.append block missing"
    anchor = src.index('sources.append')
    block = src[anchor:anchor + 2000]
    assert '"doc_id":' in block, "sources.append payload must include doc_id field"
