from langchain_core.documents import Document


def test_context_id_helper_builds_stable_canonical_and_citation_ids():
    from app.core.rag.context_ids import enrich_context_identity

    metadata = enrich_context_identity(
        {
            "doc_id": "abc12345",
            "chunk_index": 7,
            "document_title": "Peraturan Presiden Nomor 95 Tahun 2018",
            "context_header": "BAB I > Pasal 1",
        }
    )

    assert metadata["canonical_context_id"] == "docabc12345:idx7"
    assert metadata["citation_id"] == "peraturan_presiden_nomor_95_tahun_2018:bab_i_pasal_1"


def test_rerank_removes_duplicate_canonical_contexts_before_top_k():
    from app.core.rag.engine.rankers import RAGRanker

    docs = [
        Document(page_content="same chunk variant a", metadata={"canonical_context_id": "docx:idx1", "rrf_score": 0.9}),
        Document(page_content="same chunk variant b", metadata={"canonical_context_id": "docx:idx1", "rrf_score": 0.8}),
        Document(page_content="different chunk", metadata={"canonical_context_id": "docx:idx2", "rrf_score": 0.7}),
    ]

    ranked = RAGRanker(deduplicate_contexts=True).rerank("apa itu spbe", docs, top_k=2)

    assert [doc.metadata["canonical_context_id"] for doc in ranked] == ["docx:idx1", "docx:idx2"]


def test_backfill_enriches_existing_chunk_metadata_without_losing_fields():
    from types import SimpleNamespace

    from scripts.backfill_context_ids import enrich_chunk_metadata

    chunk = SimpleNamespace(
        id=42,
        chunk_index=3,
        chunk_metadata='{"pasal": "Pasal 1", "custom": "keep-me"}',
    )
    document = SimpleNamespace(
        id=6,
        doc_id="doc-uuid",
        document_title="Perpres 95 Tahun 2018",
        original_filename="Perpres Nomor 95 Tahun 2018.pdf",
        filename="stored.pdf",
        doc_type="peraturan",
    )

    metadata = enrich_chunk_metadata(chunk, document)

    assert metadata["custom"] == "keep-me"
    assert metadata["chunk_id"] == 42
    assert metadata["chunk_index"] == 3
    assert metadata["canonical_context_id"] == "docdoc-uuid:idx3"
    assert metadata["citation_id"] == "perpres_95_tahun_2018:pasal_1"


def test_document_chunk_response_exposes_context_identity_fields():
    from app.api.documents import ChunkResponse

    response = ChunkResponse(
        id=42,
        chunk_index=3,
        text="Pasal 1",
        canonical_context_id="doc6:idx3",
        citation_id="perpres95_2018:pasal_1",
        chunk_id=42,
        doc_id="6",
    )

    dumped = response.model_dump()

    assert dumped["canonical_context_id"] == "doc6:idx3"
    assert dumped["citation_id"] == "perpres95_2018:pasal_1"
    assert dumped["chunk_id"] == 42
    assert dumped["doc_id"] == "6"


def test_document_manager_chunk_mapper_preserves_context_identity_fields():
    from types import SimpleNamespace

    from app.core.ingestion.document_manager import DocumentManager

    chunk = SimpleNamespace(
        id=42,
        chunk_index=3,
        chunk_text="Pasal 1",
        chunk_metadata=(
            '{"doc_id": "6", "document_id": 6, "chunk_id": 42, '
            '"canonical_context_id": "doc6:idx3", '
            '"citation_id": "perpres95_2018:pasal_1"}'
        ),
    )

    mapped = DocumentManager._chunk_to_dict(chunk=chunk)

    assert mapped["chunk_id"] == 42
    assert mapped["doc_id"] == "6"
    assert mapped["document_id"] == 6
    assert mapped["canonical_context_id"] == "doc6:idx3"
    assert mapped["citation_id"] == "perpres95_2018:pasal_1"


def test_retrieval_eval_aliases_include_legacy_pasal_ayat_ids():
    from scripts.evaluate_retrieval_ids import context_aliases

    aliases = context_aliases(
        {
            "filename": "peraturan-bssn-no-8-tahun-2024.pdf",
            "document_title": "peraturan bssn no 8 tahun 2024",
            "pasal": "Pasal 17",
            "ayat": "Ayat (1)",
            "context_header": "peraturan bssn no 8 tahun 2024 > BAB II > Pasal 17 > Ayat (1)",
        }
    )

    assert "bssn8_2024:p17" in aliases
    assert "bssn8_2024:p17:ay1" in aliases


def test_retrieval_eval_aliases_expand_ayat_ranges_and_hal_references():
    from scripts.evaluate_retrieval_ids import context_aliases, expand_reference_id_aliases

    aliases = context_aliases(
        {
            "filename": "peraturan-bssn-no-8-tahun-2024.pdf",
            "pasal": "Pasal 19",
            "ayat": "Ayat (1)-(5)",
            "context_header": "Pasal 19 > Ayat (1)-(5)",
        }
    )

    assert "bssn8_2024:p19:ay4" in aliases
    assert "bssn8_2024:p19:a4" in aliases
    assert "bssn8_2024:p63" in expand_reference_id_aliases("bssn8_2024:p63:ha:hal24")


def test_retrieval_eval_text_fallback_matches_legacy_chunks_conservatively():
    from scripts.evaluate_retrieval_ids import reference_text_match

    reference = (
        "Manajemen SPBE adalah serangkaian proses untuk mencapai penerapan SPBE "
        "yang efektif, efisien, dan berkesinambungan, serta layanan SPBE yang berkualitas."
    )
    legacy_chunk = (
        "PERKA BSSN NOMOR 2 TAHUN 2023: BAB I KETENTUAN UMUM Pasal 1 "
        "4. Manajemen SPBE adalah serangkaian proses untuk mencapai penerapan SPBE "
        "yang efektif, efisien, dan berkesinambungan, serta layanan SPBE yang berkualitas."
    )
    related_but_not_same_chunk = (
        "Tata Kelola SPBE BSSN disusun dan dikoordinasikan oleh unit kerja. "
        "Ruang lingkup dan manajemen SPBE dibahas dalam ketentuan lain."
    )

    assert reference_text_match(reference, legacy_chunk)
    assert not reference_text_match(reference, related_but_not_same_chunk)
