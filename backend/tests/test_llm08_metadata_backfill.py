import json
import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_backfill_merges_security_metadata_without_losing_legacy_metadata(tmp_path):
    """Legacy parser metadata must be preserved while adding LLM08 security metadata."""
    from scripts.backfill_llm08_metadata import build_document_security_metadata, merge_document_metadata

    pdf_path = tmp_path / "legacy.pdf"
    pdf_path.write_bytes(b"%PDF-1.7\nlegacy")
    legacy_metadata = {"judul_dokumen": "Pedoman SPBE", "chapters": ["BAB I"]}
    document = SimpleNamespace(
        file_path=str(pdf_path),
        original_path=None,
        original_filename="legacy.pdf",
        filename="stored_legacy.pdf",
        uploaded_by=3,
    )

    security = build_document_security_metadata(document)
    merged = merge_document_metadata(json.dumps(legacy_metadata), security)

    assert merged["judul_dokumen"] == "Pedoman SPBE"
    assert merged["chapters"] == ["BAB I"]
    assert merged["security"]["allowed_roles"] == ["admin_pusdatik", "staff"]
    assert merged["security"]["classification"] == "internal"
    assert merged["security"]["uploaded_by"] == 3
    assert merged["security"]["source_hash"].startswith("sha256:")


def test_backfill_preserves_existing_security_over_defaults(tmp_path):
    """Backfill must not widen access for documents that already have explicit security metadata."""
    from scripts.backfill_llm08_metadata import build_document_security_metadata, merge_document_metadata

    pdf_path = tmp_path / "restricted.pdf"
    pdf_path.write_bytes(b"%PDF-1.7\nrestricted")
    document = SimpleNamespace(
        file_path=str(pdf_path),
        original_path=None,
        original_filename="restricted.pdf",
        filename="restricted.pdf",
        uploaded_by=None,
    )
    existing = {
        "security": {
            "allowed_roles": ["admin_pusdatik"],
            "classification": "restricted_audit",
        }
    }

    security = build_document_security_metadata(document)
    merged = merge_document_metadata(json.dumps(existing), security)

    assert merged["security"]["allowed_roles"] == ["admin_pusdatik"]
    assert merged["security"]["classification"] == "restricted_audit"
    assert merged["security"]["source_hash"].startswith("sha256:")


def test_qdrant_payload_update_uses_doc_filter_and_security_only():
    """Qdrant payload backfill should patch security fields by doc_id without touching vectors."""
    from scripts.backfill_llm08_metadata import build_qdrant_payload_update

    update = build_qdrant_payload_update(
        "doc-123",
        {
            "classification": "internal",
            "allowed_roles": ["staff"],
            "source_hash": "sha256:" + "b" * 64,
            "uploaded_by": 3,
        },
    )

    assert update["filter"] == {"must": [{"key": "doc_id", "match": {"value": "doc-123"}}]}
    assert update["payload"]["allowed_roles"] == ["staff"]
    assert update["payload"]["source_hash"].startswith("sha256:")
    assert "vector" not in update



def test_backfill_updates_only_documents_with_missing_security_fields(tmp_path):
    """DB backfill should update legacy rows and leave complete security rows untouched."""
    from scripts.backfill_llm08_metadata import backfill_session_documents

    legacy_pdf = tmp_path / "legacy.pdf"
    legacy_pdf.write_bytes(b"%PDF-1.7\nlegacy")
    complete_pdf = tmp_path / "complete.pdf"
    complete_pdf.write_bytes(b"%PDF-1.7\ncomplete")

    legacy_doc = SimpleNamespace(
        id=1,
        file_path=str(legacy_pdf),
        original_path=None,
        original_filename="legacy.pdf",
        filename="legacy.pdf",
        uploaded_by=None,
        doc_metadata=json.dumps({"judul_dokumen": "Legacy"}),
    )
    complete_doc = SimpleNamespace(
        id=2,
        file_path=str(complete_pdf),
        original_path=None,
        original_filename="complete.pdf",
        filename="complete.pdf",
        uploaded_by=None,
        doc_metadata=json.dumps({
            "security": {
                "classification": "internal",
                "allowed_roles": ["admin_pusdatik", "staff"],
                "source_hash": "sha256:" + "a" * 64,
            }
        }),
    )

    class FakeQuery:
        def all(self):
            return [legacy_doc, complete_doc]

    class FakeSession:
        def __init__(self):
            self.committed = False
        def query(self, _model):
            return FakeQuery()
        def commit(self):
            self.committed = True

    session = FakeSession()
    result = backfill_session_documents(session)

    assert result == {"scanned": 2, "updated": 1, "skipped": 1, "dry_run": False}
    assert session.committed is True
    assert json.loads(legacy_doc.doc_metadata)["security"]["source_hash"].startswith("sha256:")
    assert json.loads(complete_doc.doc_metadata)["security"]["source_hash"] == "sha256:" + "a" * 64
