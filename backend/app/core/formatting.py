"""
Shared formatting utilities for SPBE RAG citation/source display.

Used by server routes to ensure consistent citation cleanup/source shaping.

Functions:
    extract_sources: Extract hierarchical source info for frontend display
    sanitize_citations: Remove invalid citation numbers from LLM answer
    filter_used_sources: Filter to only actually-cited sources
    strip_markdown_emphasis: Remove markdown emphasis markers from text
    append_citation_reference_block: Append human-readable citation-to-title map
"""

import re
from typing import List, Dict


def extract_sources(chunks: List[Dict]) -> List[Dict]:
    """Extract source info for display with full hierarchy.

    Format output seperti:
    [1] Permenpan RB Nomor 5 Tahun 2020  > Pasal 1
    [2] peraturan bssn no 8 tahun 2024  > BAB III > Bagian Kedua > Pasal 38 > Ayat (4)
    """
    sources = []
    for i, c in enumerate(chunks, 1):
        meta = c.get("metadata", {})

        # Get document title - clean filename
        doc_title = (
            meta.get("tentang")
            or meta.get("document_title")
            or meta.get("filename", "").replace(".pdf", "").replace("_", " ")
            or "Dokumen"
        )

        # Build full hierarchy path
        hierarchy_parts = [doc_title]

        # For peraturan documents
        if meta.get("doc_type") == "peraturan":
            if meta.get("bab"):
                hierarchy_parts.append(meta.get("bab"))
            if meta.get("bagian"):
                hierarchy_parts.append(meta.get("bagian"))
            if meta.get("pasal"):
                hierarchy_parts.append(f"Pasal {meta.get('pasal')}")
            if meta.get("ayat"):
                hierarchy_parts.append(f"Ayat ({meta.get('ayat')})")

        # For audit/report documents
        elif meta.get("doc_type") == "audit":
            if meta.get("section"):
                hierarchy_parts.append(meta.get("section").title())
            if meta.get("section_part"):
                hierarchy_parts.append(f"Bagian {meta.get('section_part')}")

        # Fallback to existing hierarchy field
        else:
            if meta.get("hierarchy"):
                hierarchy_parts = [doc_title, meta.get("hierarchy")]
            elif meta.get("context_header"):
                hierarchy_parts = [doc_title, meta.get("context_header")]

        # Build section string (hierarchy after doc_title)
        section = " > ".join(hierarchy_parts[1:]) if len(hierarchy_parts) > 1 else ""

        sources.append(
            {
                "id": i,
                "document": doc_title,
                "section": section,
                "score": round(c.get("rerank_score", c.get("score", 0)), 3),
            }
        )

    return sources


def sanitize_citations(answer: str, valid_source_count: int) -> str:
    """Hapus sitasi yang tidak valid dari jawaban.

    Args:
        answer: Jawaban dari LLM
        valid_source_count: Jumlah sumber yang tersedia (e.g., 3 berarti [1]-[3] valid)

    Returns:
        Jawaban dengan sitasi invalid dihapus
    """

    def replace_invalid(match):
        citation_num = int(match.group(1))
        if 1 <= citation_num <= valid_source_count:
            return match.group(0)  # Keep valid citation
        else:
            return ""  # Remove invalid citation

    # Remove invalid citations like [4], [5] jika hanya ada 3 sumber
    sanitized = re.sub(r"\[(\d+)\]", replace_invalid, answer)

    # Clean up artifacts: double spaces, space before punctuation
    sanitized = re.sub(r"  +", " ", sanitized)
    sanitized = re.sub(r" +\.", ".", sanitized)
    sanitized = re.sub(r" +,", ",", sanitized)

    return sanitized.strip()


def strip_markdown_emphasis(text: str) -> str:
    """Remove markdown emphasis markers to keep legal answers plain/formal."""
    if not text:
        return ""
    cleaned = text.replace("**", "")
    cleaned = cleaned.replace("__", "")
    cleaned = re.sub(r"  +", " ", cleaned)
    return cleaned


def _extract_citation_ids(answer: str) -> List[int]:
    """Extract citation ids while preserving first appearance order."""
    ids: List[int] = []
    seen = set()
    for match in re.findall(r"\[(\d+)\]", answer or ""):
        try:
            cid = int(match)
        except ValueError:
            continue
        if cid not in seen:
            seen.add(cid)
            ids.append(cid)
    return ids


def append_citation_reference_block(
    answer: str,
    sources: List[Dict],
    max_items: int = 8,
) -> str:
    """Append a citation map so [n] references are explicitly tied to document titles."""
    base_answer = (answer or "").strip()
    if not base_answer or not sources:
        return base_answer

    if re.search(r"(?im)^referensi\s+dokumen\s*:", base_answer):
        return base_answer

    cited_ids = _extract_citation_ids(base_answer)
    if not cited_ids:
        return base_answer
    cited_ids = sorted(cited_ids)

    source_by_id = {}
    for src in sources:
        src_id = src.get("id")
        if isinstance(src_id, int):
            source_by_id[src_id] = src

    lines = ["Referensi Dokumen:"]
    for cid in cited_ids[: max_items]:
        src = source_by_id.get(cid)
        if not src:
            continue

        title = str(src.get("citation_title") or src.get("document") or "Dokumen").strip()
        section = str(src.get("section") or "").strip()

        if section:
            lines.append(f"[{cid}] {title} | {section}")
        else:
            lines.append(f"[{cid}] {title}")

    if len(lines) == 1:
        return base_answer

    return f"{base_answer}\n\n" + "\n".join(lines)


def filter_used_sources(answer: str, sources: List[Dict]) -> List[Dict]:
    """Return only sources cited by the answer while preserving citation IDs."""
    core_answer = re.split(r"(?im)^Referensi\s+Dokumen\s*:", answer or "", maxsplit=1)[0]
    citations = re.findall(r"\[(\d+)\]", core_answer)
    used_ids = set()
    for citation in citations:
        try:
            used_ids.add(int(citation))
        except ValueError:
            continue

    if not used_ids:
        return []

    return [s for s in sources if s.get("id") in used_ids]


def renumber_citations_and_sources(answer: str, sources: List[Dict]) -> tuple[str, List[Dict]]:
    """Renumber cited sources by first citation appearance and update source IDs to match.

    The retrieval layer may provide sources as [1..N], while the model may cite only
    [4], [2], and [5]. For user-facing IEEE-style citations, the final answer should
    show [1], [2], [3] and the source cards should use those same IDs.
    """
    base_answer = answer or ""
    parts = re.split(r"(?im)^Referensi\s+Dokumen\s*:", base_answer, maxsplit=1)
    core_answer = parts[0]
    reference_suffix = ""
    if len(parts) > 1:
        reference_suffix = "Referensi Dokumen:" + parts[1]

    citation_order: List[int] = []
    seen = set()
    for raw_id in re.findall(r"\[(\d+)\]", core_answer):
        try:
            source_id = int(raw_id)
        except ValueError:
            continue
        if source_id not in seen:
            seen.add(source_id)
            citation_order.append(source_id)

    if not citation_order:
        return core_answer.strip(), []

    source_by_id = {}
    for src in sources:
        src_id = src.get("id")
        if isinstance(src_id, int):
            source_by_id[src_id] = src

    id_map = {
        old_id: new_id
        for new_id, old_id in enumerate(citation_order, 1)
        if old_id in source_by_id
    }

    def replace_citation(match):
        old_id = int(match.group(1))
        new_id = id_map.get(old_id)
        return f"[{new_id}]" if new_id is not None else match.group(0)

    renumbered_answer = re.sub(r"\[(\d+)\]", replace_citation, core_answer).strip()
    if reference_suffix:
        # Drop stale reference blocks; append_citation_reference_block will rebuild them.
        renumbered_answer = renumbered_answer.strip()

    renumbered_sources: List[Dict] = []
    for old_id in citation_order:
        src = source_by_id.get(old_id)
        new_id = id_map.get(old_id)
        if src is None or new_id is None:
            continue
        updated = dict(src)
        updated["id"] = new_id
        updated["original_id"] = old_id
        renumbered_sources.append(updated)

    return renumbered_answer, renumbered_sources

