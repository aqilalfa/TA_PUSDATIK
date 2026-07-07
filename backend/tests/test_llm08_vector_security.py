import json
import os
import sys
from typing import cast

import pytest
from pydantic import ValidationError
from qdrant_client import QdrantClient
from langchain_qdrant import QdrantVectorStore

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class DummyUser:
    def __init__(self, user_id=7, roles=None, department="DEPUTI_EVALUASI", email="user@bssn.go.id"):
        self.id = user_id
        self.roles = json.dumps(roles or ["staff"])
        self.department = department
        self.email = email


def _condition_keys(filter_obj):
    return [getattr(condition, "key", None) for condition in (filter_obj.must or [])]


def test_qdrant_filter_combines_document_scope_and_user_role_access():
    """RAG retrieval must scope vector search by both requested document and user role."""
    from app.core.rag.access_control import build_qdrant_access_filter

    qdrant_filter = build_qdrant_access_filter(
        doc_id="doc-123",
        current_user=DummyUser(roles=["staff"]),
    )

    keys = _condition_keys(qdrant_filter)

    assert "doc_id" in keys
    assert "allowed_roles" in keys


def test_qdrant_filter_denies_authenticated_users_without_roles():
    """Malformed/empty user roles must not degrade into unfiltered vector search."""
    from app.core.rag.access_control import build_qdrant_access_filter

    qdrant_filter = build_qdrant_access_filter(current_user=DummyUser(roles=[]))

    assert "allowed_roles" in _condition_keys(qdrant_filter)


def test_metadata_access_denies_chunks_for_unlisted_roles():
    """BM25/local retrieval must not return chunks whose access metadata excludes the user."""
    from app.core.rag.access_control import user_can_access_metadata

    metadata = {
        "classification": "restricted_audit",
        "allowed_roles": ["admin_pusdatik"],
        "department": "PUSDATIK",
    }

    assert not user_can_access_metadata(metadata, DummyUser(roles=["staff"]))
    assert user_can_access_metadata(metadata, DummyUser(roles=["admin_pusdatik"]))


def test_bm25_search_filters_inaccessible_documents():
    """Hybrid BM25 path must enforce the same access metadata as vector retrieval."""
    from app.core.rag.engine.retrievers import HybridRetriever

    class FakeBM25:
        def get_scores(self, _query):
            return [10.0, 9.0]

    docs = [
        {"text": "admin only", "metadata": {"doc_id": "a", "allowed_roles": ["admin_pusdatik"]}},
        {"text": "evaluator allowed", "metadata": {"doc_id": "b", "allowed_roles": ["staff"]}},
    ]

    retriever = HybridRetriever(
        qdrant_client=cast(QdrantClient, None),
        vector_store=cast(QdrantVectorStore, None),
        bm25_instance=FakeBM25(),
    )
    results = retriever.bm25_search(
        "audit",
        top_k=5,
        bm25_docs=docs,
        current_user=DummyUser(roles=["staff"]),
    )

    assert [doc.page_content for doc in results] == ["evaluator allowed"]


def test_literal_qdrant_searches_include_user_role_filter():
    """Literal Qdrant searches must not bypass permission-aware vector retrieval."""
    from app.core.rag.engine.retrievers import HybridRetriever

    class FakeClient:
        def __init__(self):
            self.filters = []

        def scroll(self, collection_name, scroll_filter, **kwargs):
            self.filters.append(scroll_filter)
            return [], None

    client = FakeClient()
    retriever = HybridRetriever(
        qdrant_client=cast(QdrantClient, client),
        vector_store=cast(QdrantVectorStore, None),
    )

    retriever.table_literal_search("lihat tabel 10", "chunks", current_user=DummyUser(roles=["staff"]))
    retriever.indicator_literal_search("indikator 21", "chunks", current_user=DummyUser(roles=["staff"]))

    assert client.filters
    for qdrant_filter in client.filters:
        first_filter = (qdrant_filter.should or [qdrant_filter])[0]
        keys = _condition_keys(first_filter)
        assert "allowed_roles" in keys


def test_neighbor_context_fetch_includes_user_role_filter():
    """Neighbor chunk stitching must fetch only chunks allowed for the requesting user."""
    from app.core.rag.engine.context_stitching import ContextStitcher

    class FakeClient:
        def __init__(self):
            self.scroll_filter = None

        def scroll(self, collection_name, scroll_filter, **kwargs):
            self.scroll_filter = scroll_filter
            return [], None

    client = FakeClient()
    stitcher = ContextStitcher(cast(QdrantClient, client))

    stitcher.fetch_neighbor_documents(
        {"doc-1": {3}},
        "chunks",
        current_user=DummyUser(roles=["staff"]),
    )

    assert client.scroll_filter is not None
    assert client.scroll_filter.should is not None
    nested = client.scroll_filter.should[0]
    assert "allowed_roles" in _condition_keys(nested)


def test_documents_api_filters_and_denies_by_access_metadata():
    """Document management APIs must not expose inaccessible documents/chunks."""
    import pytest
    from fastapi import HTTPException
    from app.api.documents import _require_document_access, list_documents

    class FakeManager:
        def get_document(self, doc_id):
            return {
                "doc_id": doc_id,
                "access_metadata": {"allowed_roles": ["admin_pusdatik"]},
            }

        def list_documents(self):
            return [
                {
                    "doc_id": "admin-doc",
                    "filename": "admin.pdf",
                    "file_size": 1,
                    "chunk_count": 1,
                    "status": "indexed",
                    "access_metadata": {"allowed_roles": ["admin_pusdatik"]},
                },
                {
                    "doc_id": "eval-doc",
                    "filename": "eval.pdf",
                    "file_size": 1,
                    "chunk_count": 1,
                    "status": "indexed",
                    "access_metadata": {"allowed_roles": ["staff"]},
                },
            ]

    user = DummyUser(roles=["staff"])

    with pytest.raises(HTTPException) as excinfo:
        _require_document_access(FakeManager(), "admin-doc", user)
    assert excinfo.value.status_code == 403

    import asyncio
    visible = asyncio.run(list_documents(FakeManager(), user))
    assert [doc.doc_id for doc in visible] == ["eval-doc"]


def test_chat_request_rejects_unbounded_message_and_top_k():
    """Chat input must have deterministic request bounds before retrieval/LLM work starts."""
    from app.models.schemas import ChatRequest

    with pytest.raises(ValidationError):
        ChatRequest(message="x" * 5001, top_k=5)

    with pytest.raises(ValidationError):
        ChatRequest(message="jelaskan SPBE", top_k=51)


def test_document_upload_requires_pdf_magic_and_returns_provenance(monkeypatch, tmp_path):
    """Upload should reject spoofed PDFs and persist provenance/access metadata for later indexing."""
    import app.core.ingestion.document_manager as dm
    from app.core.ingestion.document_manager import DocumentManager

    monkeypatch.setattr(dm, "UPLOADS_DIR", tmp_path)

    manager = DocumentManager()
    captured = {}

    def fake_create_document(**kwargs):
        captured.update(kwargs)
        return {"doc_id": kwargs["doc_id"]}

    monkeypatch.setattr(manager, "create_document", fake_create_document)

    with pytest.raises(ValueError, match="valid PDF"):
        manager.upload_file(b"not a real pdf", "spoofed.pdf", uploaded_by=DummyUser())

    result = manager.upload_file(b"%PDF-1.7\nbody", "policy.pdf", uploaded_by=DummyUser())

    assert result["source_hash"].startswith("sha256:")
    assert captured["access_metadata"]["allowed_roles"] == ["admin_pusdatik", "staff"]
    assert captured["access_metadata"]["classification"] == "internal"
    assert captured["access_metadata"]["uploaded_by"] == 7
