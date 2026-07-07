"""Stable context identity helpers for retrieval, citations, and evaluation."""

from __future__ import annotations

import re
from typing import Any


def slug_text(value: Any, max_len: int = 80) -> str:
    """Return a compact lowercase slug for stable, human-readable IDs."""
    text = str(value or "").lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_")[:max_len]


def build_canonical_context_id(metadata: dict[str, Any]) -> str:
    """Build the shortest stable machine ID available for a retrieved chunk."""
    if metadata.get("canonical_context_id"):
        return str(metadata["canonical_context_id"])

    chunk_index = metadata.get("chunk_index")
    if metadata.get("doc_id") and chunk_index is not None:
        return f"doc{metadata['doc_id']}:idx{chunk_index}"
    if metadata.get("document_id") is not None and chunk_index is not None:
        return f"doc{metadata['document_id']}:idx{chunk_index}"
    if metadata.get("chunk_id"):
        return f"dbchunk:{metadata['chunk_id']}"

    title = (
        metadata.get("document_title")
        or metadata.get("judul_dokumen")
        or metadata.get("filename")
        or "unknown"
    )
    section = metadata.get("context_header") or metadata.get("hierarchy") or metadata.get("pasal") or "unknown"
    return f"{slug_text(title, 50)}:{slug_text(section, 80)}"


def build_citation_id(metadata: dict[str, Any]) -> str:
    """Build a readable source-section citation ID for reports and UI traces."""
    if metadata.get("citation_id"):
        return str(metadata["citation_id"])

    title = (
        metadata.get("document_title")
        or metadata.get("judul_dokumen")
        or metadata.get("filename")
        or metadata.get("doc_id")
        or metadata.get("document_id")
        or "unknown"
    )
    section = metadata.get("context_header") or metadata.get("hierarchy") or metadata.get("pasal") or "unknown"
    return f"{slug_text(title, 60)}:{slug_text(section, 90)}"


def enrich_context_identity(metadata: dict[str, Any]) -> dict[str, Any]:
    """Return metadata with canonical_context_id and citation_id populated."""
    enriched = dict(metadata or {})
    enriched["canonical_context_id"] = build_canonical_context_id(enriched)
    enriched["citation_id"] = build_citation_id(enriched)
    return enriched
