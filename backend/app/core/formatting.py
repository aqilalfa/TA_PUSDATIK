"""
Shared formatting utilities for SPBE RAG citation/source display.

Used by all server variants (server_full, server_hybrid, server_ultra)
to ensure consistent citation formatting with full hierarchy.

Functions:
    format_context_with_parent: Format chunks with source list for LLM context
    extract_sources: Extract hierarchical source info for frontend display
    sanitize_citations: Remove invalid citation numbers from LLM answer
    filter_used_sources: Filter to only actually-cited sources
"""

import re
from typing import List, Dict


def format_context_with_parent(chunks: List[Dict], max_chars: int = 6000) -> str:
    """Format chunks dengan daftar sumber eksplisit di awal.

    Format:
    DAFTAR SUMBER YANG TERSEDIA:
    [1] Perpres Nomor 95 Tahun 2018
    [2] Laporan Evaluasi SPBE 2024

    DETAIL DOKUMEN:
    [1] Dokumen: Perpres 95/2018 | Pasal 8 Ayat (1)
    Isi: <teks dokumen>
    """
    if not chunks:
        return "Tidak ada dokumen yang ditemukan."

    # Step 1: Buat daftar sumber ringkas di awal
    source_list = ["DAFTAR SUMBER YANG TERSEDIA:"]
    for i, c in enumerate(chunks, 1):
        meta = c.get("metadata", {})
        doc_title = meta.get("document_title", "Dokumen")
        source_list.append(f"[{i}] {doc_title}")

    source_summary = "\n".join(source_list)
    source_summary += f"\n\nPENTING: Gunakan HANYA nomor sumber [1] sampai [{len(chunks)}] di atas. Jangan gunakan nomor lain.\n"
    source_summary += "\nDETAIL DOKUMEN:\n"

    # Step 2: Format detail dokumen
    parts = []
    total = len(source_summary)

    for i, c in enumerate(chunks, 1):
        meta = c.get("metadata", {})
        doc_title = meta.get("document_title", "Dokumen")
        pasal = meta.get("pasal", "")
        ayat = meta.get("ayat", "")
        parent_context = c.get("parent_context", "")
        raw_text = c.get("text", "")

        # Header sederhana
        ref_parts = [f"[{i}] Dokumen: {doc_title}"]
        if pasal:
            ref_parts.append(f"{pasal}")
            if ayat:
                ref_parts.append(f"Ayat ({ayat})")

        header = " | ".join(ref_parts)

        # Jika ada parent context, gabungkan
        if parent_context and c.get("has_parent"):
            content = f"{parent_context[:1200]}"
        else:
            content = raw_text

        text = f"{header}\nIsi: {content}\n"

        if total + len(text) > max_chars:
            break

        parts.append(text)
        total += len(text)

    return source_summary + "\n".join(parts)


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
