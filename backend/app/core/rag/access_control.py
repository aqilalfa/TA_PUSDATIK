"""Permission-aware retrieval helpers for RAG stores.

These helpers keep authorization outside the LLM. They are intentionally small
and deterministic so vector/BM25/document-serving paths can share the same
access decision.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable

from qdrant_client.models import FieldCondition, Filter, MatchAny, MatchValue


DEFAULT_ALLOWED_ROLES = ["admin_pusdatik", "staff"]
DEFAULT_CLASSIFICATION = "internal"
ADMIN_ROLE = "admin_pusdatik"
NO_MATCH_ROLE = "__spbe_no_matching_role__"


def parse_user_roles(current_user: Any | None) -> list[str]:
    """Return normalized role names from a User-like object."""
    if current_user is None:
        return []

    roles_value = getattr(current_user, "roles", None)
    if not roles_value:
        return []

    if isinstance(roles_value, str):
        try:
            parsed = json.loads(roles_value)
        except json.JSONDecodeError:
            parsed = [roles_value]
    elif isinstance(roles_value, Iterable):
        parsed = list(roles_value)
    else:
        parsed = []

    return sorted({str(role).strip() for role in parsed if str(role).strip()})


def normalize_allowed_roles(value: Any) -> list[str]:
    """Normalize metadata allowed_roles to a deterministic non-empty list."""
    if value is None or value == "":
        return list(DEFAULT_ALLOWED_ROLES)

    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            parsed = [part.strip() for part in value.split(",")]
    elif isinstance(value, Iterable):
        parsed = list(value)
    else:
        parsed = []

    roles = sorted({str(role).strip() for role in parsed if str(role).strip()})
    return roles or list(DEFAULT_ALLOWED_ROLES)


def build_document_access_metadata(
    *,
    file_content: bytes,
    filename: str,
    uploaded_by: Any | None = None,
    classification: str = DEFAULT_CLASSIFICATION,
    allowed_roles: list[str] | None = None,
) -> dict[str, Any]:
    """Build provenance and access metadata stored with every document/chunk."""
    uploader_id = getattr(uploaded_by, "id", None)
    uploader_department = getattr(uploaded_by, "department", None)

    return {
        "classification": classification or DEFAULT_CLASSIFICATION,
        "allowed_roles": normalize_allowed_roles(allowed_roles),
        "uploaded_by": uploader_id,
        "uploader_department": uploader_department,
        "source_filename": filename,
        "source_hash": "sha256:" + hashlib.sha256(file_content).hexdigest(),
    }


def enrich_metadata_with_access(metadata: dict[str, Any], access_metadata: dict[str, Any] | None) -> dict[str, Any]:
    """Return metadata enriched with normalized access fields."""
    enriched = dict(metadata or {})
    access = dict(access_metadata or {})
    enriched["classification"] = access.get("classification") or enriched.get("classification") or DEFAULT_CLASSIFICATION
    enriched["allowed_roles"] = normalize_allowed_roles(access.get("allowed_roles") or enriched.get("allowed_roles"))
    for key in ("uploaded_by", "uploader_department", "source_filename", "source_hash"):
        if access.get(key) is not None:
            enriched[key] = access[key]
        elif key not in enriched:
            enriched[key] = None
    return enriched


def user_can_access_metadata(metadata: dict[str, Any] | None, current_user: Any | None) -> bool:
    """Deterministic authorization check for chunk/document metadata."""
    roles = parse_user_roles(current_user)
    if not roles:
        return False
    if ADMIN_ROLE in roles:
        return True

    allowed_roles = normalize_allowed_roles((metadata or {}).get("allowed_roles"))
    return bool(set(roles).intersection(allowed_roles))


def build_qdrant_access_filter(doc_id: str | None = None, current_user: Any | None = None) -> Filter | None:
    """Build a Qdrant filter combining document scope and role-based access."""
    must = []
    if doc_id:
        must.append(FieldCondition(key="doc_id", match=MatchValue(value=str(doc_id))))

    roles = parse_user_roles(current_user)
    if current_user is not None and not roles:
        must.append(FieldCondition(key="allowed_roles", match=MatchAny(any=[NO_MATCH_ROLE])))
    if roles and ADMIN_ROLE not in roles:
        must.append(FieldCondition(key="allowed_roles", match=MatchAny(any=roles)))

    return Filter(must=must) if must else None
