#!/usr/bin/env python3
"""Backfill OWASP LLM08 security metadata for legacy documents.

Adds a `security` object to Document.doc_metadata without discarding existing
parser metadata. Re-run-safe: explicit existing security fields win over defaults.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, cast

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.rag.access_control import (  # noqa: E402
    DEFAULT_CLASSIFICATION,
    build_document_access_metadata,
    normalize_allowed_roles,
)
from app.config import settings  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.models.db_models import Document  # noqa: E402

REQUIRED_SECURITY_FIELDS = {"classification", "allowed_roles", "source_hash"}


def _read_json_object(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _document_path(document: Any) -> Path | None:
    for attr in ("file_path", "original_path"):
        value = getattr(document, attr, None)
        if value:
            path = Path(str(value))
            if path.exists() and path.is_file():
                return path
    return None


def _fallback_source_hash(document: Any) -> str:
    stable_parts = [
        str(getattr(document, "id", "")),
        str(getattr(document, "doc_id", "")),
        str(getattr(document, "original_filename", "") or getattr(document, "filename", "")),
    ]
    return "sha256:" + hashlib.sha256("|".join(stable_parts).encode("utf-8")).hexdigest()


def build_document_security_metadata(document: Any) -> dict[str, Any]:
    """Build deterministic LLM08 security metadata for one legacy document."""
    path = _document_path(document)
    filename = str(getattr(document, "original_filename", None) or getattr(document, "filename", "document"))

    if path is not None:
        file_content = path.read_bytes()
        return build_document_access_metadata(
            file_content=file_content,
            filename=filename,
            uploaded_by=None,
            classification=DEFAULT_CLASSIFICATION,
            allowed_roles=None,
        ) | {"uploaded_by": getattr(document, "uploaded_by", None)}

    return {
        "classification": DEFAULT_CLASSIFICATION,
        "allowed_roles": normalize_allowed_roles(None),
        "uploaded_by": getattr(document, "uploaded_by", None),
        "uploader_department": None,
        "source_filename": filename,
        "source_hash": _fallback_source_hash(document),
    }


def merge_document_metadata(existing_raw: str | None, security_defaults: dict[str, Any]) -> dict[str, Any]:
    """Merge security metadata into existing doc_metadata without widening access."""
    merged = _read_json_object(existing_raw)
    existing_raw_security = merged.get("security")
    existing_security = cast(dict[str, Any], existing_raw_security) if isinstance(existing_raw_security, dict) else {}

    security = dict(security_defaults)
    security.update(existing_security)
    security["allowed_roles"] = normalize_allowed_roles(security.get("allowed_roles"))
    security["classification"] = security.get("classification") or DEFAULT_CLASSIFICATION

    merged["security"] = security
    return merged


def _security_complete(metadata: dict[str, Any]) -> bool:
    raw_security = metadata.get("security")
    security = cast(dict[str, Any], raw_security) if isinstance(raw_security, dict) else {}
    return REQUIRED_SECURITY_FIELDS.issubset({key for key, value in security.items() if value})


def build_qdrant_payload_update(doc_id: str, security_metadata: dict[str, Any]) -> dict[str, Any]:
    """Build a Qdrant set-payload request that patches security metadata only."""
    payload = {
        key: security_metadata.get(key)
        for key in (
            "classification",
            "allowed_roles",
            "uploaded_by",
            "uploader_department",
            "source_filename",
            "source_hash",
        )
        if security_metadata.get(key) is not None
    }
    return {
        "payload": payload,
        "filter": {"must": [{"key": "doc_id", "match": {"value": str(doc_id)}}]},
    }


def backfill_qdrant_payloads(documents: list[Any], *, dry_run: bool = False) -> dict[str, int | bool]:
    """Patch Qdrant payloads with document security metadata without re-embedding."""
    import httpx

    scanned = updated = skipped = 0
    endpoint = f"{settings.QDRANT_URL}/collections/{settings.QDRANT_COLLECTION}/points/payload"

    for document in documents:
        scanned += 1
        doc_id = getattr(document, "doc_id", None) or getattr(document, "id", None)
        if not doc_id:
            skipped += 1
            continue
        metadata = _read_json_object(getattr(document, "doc_metadata", None))
        security = metadata.get("security") if isinstance(metadata.get("security"), dict) else None
        if not security:
            skipped += 1
            continue
        update = build_qdrant_payload_update(str(doc_id), cast(dict[str, Any], security))
        if not dry_run:
            response = httpx.post(endpoint, json=update, timeout=30)
            response.raise_for_status()
        updated += 1

    return {"scanned": scanned, "updated": updated, "skipped": skipped, "dry_run": dry_run}


def backfill_session_documents(session, *, dry_run: bool = False) -> dict[str, int | bool]:
    """Backfill all Document rows in a SQLAlchemy-like session."""
    scanned = updated = skipped = 0

    for document in session.query(Document).all():
        scanned += 1
        existing = _read_json_object(getattr(document, "doc_metadata", None))
        if _security_complete(existing):
            skipped += 1
            continue

        security = build_document_security_metadata(document)
        merged = merge_document_metadata(getattr(document, "doc_metadata", None), security)
        if not dry_run:
            document.doc_metadata = json.dumps(merged, ensure_ascii=False)
        updated += 1

    if updated and not dry_run:
        session.commit()

    return {"scanned": scanned, "updated": updated, "skipped": skipped, "dry_run": dry_run}


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill OWASP LLM08 document security metadata")
    parser.add_argument("--dry-run", action="store_true", help="Report changes without writing")
    parser.add_argument("--qdrant", action="store_true", help="Also patch Qdrant payload metadata without re-embedding")
    args = parser.parse_args()

    session = SessionLocal()
    try:
        document_result = backfill_session_documents(session, dry_run=args.dry_run)
        result: dict[str, Any] = {"documents": document_result}
        if args.qdrant:
            documents = session.query(Document).all()
            result["qdrant"] = backfill_qdrant_payloads(documents, dry_run=args.dry_run)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    finally:
        session.close()


if __name__ == "__main__":
    main()
