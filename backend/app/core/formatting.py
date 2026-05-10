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
        cited_ids = [int(s.get("id")) for s in sources[: min(3, len(sources))] if s.get("id")]
    else:
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
    """Filter sources to only include those actually cited in the answer."""
    citations = re.findall(r"\[(\d+)\]", answer)
    used_ids = set(int(c) for c in citations)

    if not used_ids:
        return sources[:3]

    filtered = [s for s in sources if s.get("id") in used_ids]

    for i, s in enumerate(filtered, 1):
        s["id"] = i

    return filtered
