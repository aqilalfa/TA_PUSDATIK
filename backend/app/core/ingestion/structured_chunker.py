"""
Structured Chunker for SPBE RAG System

Takes structured JSON (from json_structure_parser) and produces chunks
with a maximum size of 600 characters and configurable overlap.

Strategies:
  - Peraturan: chunk per ayat/pasal from batang_tubuh
  - Lampiran SPBE: Each indicator becomes a chunk (or split if >600 chars)
  - Laporan:   chunk per paragraph, split large paragraphs with overlap

Every chunk carries full metadata for retrieval context.
"""

import re
from pathlib import Path
from typing import List, Dict, Any, Optional
from loguru import logger
# Import langchain removed to avoid Torch OOM
from app.config import settings


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

MAX_CHUNK_SIZE = getattr(settings, "CHUNK_SIZE", 600)
CHUNK_OVERLAP = getattr(settings, "CHUNK_OVERLAP", 100)
MIN_CHUNK_SIZE = 80  # Don't create tiny chunks
MIN_JSON_CHUNKS_THRESHOLD = 20

MAX_CHUNK_SIZE_PERATURAN = getattr(settings, "CHUNK_SIZE_PERATURAN", 900)
CHUNK_OVERLAP_PERATURAN  = getattr(settings, "CHUNK_OVERLAP_PERATURAN", 150)
MAX_CHUNK_SIZE_LAPORAN   = getattr(settings, "CHUNK_SIZE_LAPORAN", 1800)
CHUNK_OVERLAP_LAPORAN    = getattr(settings, "CHUNK_OVERLAP_LAPORAN", 200)


def _normalize_overlap(max_size: int, overlap: int) -> int:
    """Keep overlap within safe bounds to avoid loops and invalid windows."""
    if max_size <= 1:
        return 0
    return max(0, min(overlap, max_size - 1))


def _snap_start_to_word_boundary(text: str, index: int, window: int = 32) -> int:
    """Shift split start to nearest word boundary to avoid mid-word chunks."""
    if index <= 0 or index >= len(text):
        return index

    if text[index].isspace() or text[index - 1].isspace():
        return index

    right_limit = min(len(text), index + window)
    for pos in range(index, right_limit):
        if text[pos].isspace():
            return min(pos + 1, len(text))

    left_limit = max(0, index - window)
    for pos in range(index, left_limit, -1):
        if text[pos - 1].isspace():
            return pos

    return index


# ---------------------------------------------------------------------------
# Text splitting utilities
# ---------------------------------------------------------------------------

def split_text_with_overlap(
    text: str,
    max_size: int = MAX_CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP,
) -> List[str]:
    """Split long text into bounded chunks with overlap and boundary-aware starts."""
    if not text:
        return []

    max_size = max(1, max_size)
    overlap = _normalize_overlap(max_size, overlap)

    if len(text) <= max_size:
        return [text.strip()]

    chunks = []
    start = 0
    text_len = len(text)
    
    while start < text_len:
        if start + max_size >= text_len:
            chunks.append(text[start:].strip())
            break
            
        end = min(start + max_size, text_len)
        # Find best separator
        best_end = end
        for sep in ["\n\n", "\n", ". ", " "]:
            search_start = min(start + overlap, end - 1)
            pos = text.rfind(sep, search_start, end)
            if pos != -1:
                best_end = pos + len(sep)
                break

        piece = text[start:best_end].strip()
        if piece:
            chunks.append(piece)
        
        prev_start = start
        # Advance with overlap
        next_start = best_end - overlap
        if next_start <= prev_start:
            start = best_end
        else:
            start = _snap_start_to_word_boundary(text, next_start)

        if start <= prev_start:
            # hard guard against any accidental non-advancing index
            start = min(text_len, best_end)

    return [c for c in chunks if c]


def _is_table_like_text(text: str) -> bool:
    """Heuristic to detect linearized table text that should split by row."""
    lowered = text.lower()
    if "|" in text and "tabel" in lowered:
        return True

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) < 3:
        return False

    row_like = sum(1 for line in lines if ":" in line and ";" in line)
    if row_like >= 2:
        return True

    return "tabel" in lowered and row_like >= 1


TABLE_LABEL_PATTERN = re.compile(r"\btabel\s*(?:ke[-\s]*)?(\d{1,3})\b", re.IGNORECASE)


def _detect_table_label(text: str) -> str:
    """Return 'Tabel N' label if the chunk text references a table number."""
    match = TABLE_LABEL_PATTERN.search(text or "")
    if not match:
        return ""
    return f"Tabel {match.group(1)}"


def _split_table_like_text(
    text: str,
    max_size: int = MAX_CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP,
) -> List[str]:
    """Split table-like text by row to preserve row/column meaning across chunks."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return []

    overlap = _normalize_overlap(max_size, overlap)
    chunks: List[str] = []
    current_lines: List[str] = []
    current_len = 0

    def flush_current() -> None:
        nonlocal current_lines, current_len
        if not current_lines:
            return
        block = "\n".join(current_lines).strip()
        if block:
            chunks.append(block)
        current_lines = []
        current_len = 0

    for line in lines:
        if len(line) > max_size:
            flush_current()
            chunks.extend(
                split_text_with_overlap(line, max_size=max_size, overlap=overlap)
            )
            continue

        line_len = len(line) + (1 if current_lines else 0)
        if current_lines and current_len + line_len > max_size:
            previous_lines = current_lines[:]
            flush_current()

            overlap_lines: List[str] = []
            overlap_budget = 0
            for prev in reversed(previous_lines):
                add_len = len(prev) + (1 if overlap_lines else 0)
                if overlap_budget + add_len > overlap:
                    break
                overlap_lines.insert(0, prev)
                overlap_budget += add_len

            current_lines = overlap_lines + [line]
            current_len = sum(len(item) for item in current_lines) + max(
                0, len(current_lines) - 1
            )
            continue

        current_lines.append(line)
        current_len += line_len

    flush_current()
    return chunks


def _with_table_metadata(piece: str, base: Dict[str, Any]) -> Dict[str, Any]:
    """Augment metadata with is_table / table_label when the piece looks table-like."""
    meta = dict(base)
    is_table = bool(base.get("is_table")) or _is_table_like_text(piece)
    if is_table:
        meta["is_table"] = True
        label = base.get("table_label") or _detect_table_label(piece)
        if label:
            meta["table_label"] = label
    return meta


def append_chunk_with_limit(
    chunks: List[Dict[str, Any]],
    text: str,
    metadata: Dict[str, Any],
    max_size: int = MAX_CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP,
) -> None:
    """Append chunk(s) while keeping each piece under configured max size."""
    normalized = (text or "").strip()
    if not normalized:
        return

    is_table_block = _is_table_like_text(normalized)
    if is_table_block:
        pieces = _split_table_like_text(
            normalized,
            max_size=max_size,
            overlap=overlap,
        )
    else:
        pieces = []

    if not pieces:
        pieces = split_text_with_overlap(
            normalized,
            max_size=max_size,
            overlap=overlap,
        )

    base_meta = dict(metadata)
    if is_table_block:
        base_meta["is_table"] = True
        label = base_meta.get("table_label") or _detect_table_label(normalized)
        if label:
            base_meta["table_label"] = label

    if len(pieces) == 1:
        chunks.append({"text": pieces[0], "metadata": _with_table_metadata(pieces[0], base_meta)})
        return

    total = len(pieces)
    for idx, piece in enumerate(pieces, 1):
        piece_meta = {**base_meta, "chunk_part": idx, "chunk_parts_total": total}
        hierarchy = piece_meta.get("hierarchy", "")
        if hierarchy:
            piece_meta["hierarchy"] = f"{hierarchy} [Bagian {idx}/{total}]"
        chunks.append({"text": piece, "metadata": _with_table_metadata(piece, piece_meta)})


def _clean_marker_noise(text: str) -> str:
    """Remove common Marker artifacts like image links and empty page markers."""
    cleaned = text or ""
    cleaned = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", cleaned)
    cleaned = re.sub(r"</?span[^>]*>", "", cleaned)
    cleaned = re.sub(r"^\s*\*\*\d+\*\*\s*$", "", cleaned, flags=re.MULTILINE)
    return cleaned.strip()


def _linearize_md_table(table_text: str) -> str:
    """Convert a markdown table into compact key-value lines."""
    raw_lines = [line.strip() for line in table_text.splitlines() if line.strip()]
    lines = [
        line
        for line in raw_lines
        if not re.match(r"^\|?[\s:\-]+\|[\s|:\-]*$", line)
    ]
    if len(lines) < 2:
        return table_text

    headers = [header.strip() for header in lines[0].split("|") if header.strip()]
    if not headers:
        return table_text

    output_rows = []
    for row_line in lines[1:]:
        cells = [cell.strip() for cell in row_line.split("|") if cell.strip()]
        pairs = []
        for idx in range(min(len(headers), len(cells))):
            pairs.append(f"{headers[idx]}: {cells[idx]}")
        if pairs:
            output_rows.append("; ".join(pairs))

    if not output_rows:
        return table_text
    return "\n".join(output_rows)


def _linearize_md_tables_in_text(text: str) -> str:
    """Find markdown table blocks and convert them to linear text."""
    lines = text.splitlines()
    result_lines: List[str] = []
    table_lines: List[str] = []

    def flush_table() -> None:
        if table_lines:
            result_lines.append(_linearize_md_table("\n".join(table_lines)))
            table_lines.clear()

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("|") and stripped.endswith("|"):
            table_lines.append(stripped)
            continue

        flush_table()
        result_lines.append(line)

    flush_table()
    return "\n".join(result_lines)


def chunk_from_markdown(
    md_text: str,
    filename: str,
    doc_title: str,
) -> List[Dict[str, Any]]:
    """Fallback chunker that uses markdown heading structure directly."""
    chunks: List[Dict[str, Any]] = []
    cleaned_text = _clean_marker_noise(md_text)
    if not cleaned_text:
        return chunks

    heading_pattern = re.compile(r"^(#{1,4})\s+(.+?)\s*$")
    bab_pattern = re.compile(r"\bBAB\s+([IVXLCDM]+)\b", re.IGNORECASE)

    current_h1 = ""
    current_h2 = ""
    current_h3 = ""
    section_lines: List[str] = []

    def flush_section() -> None:
        nonlocal section_lines

        section_text = "\n".join(section_lines).strip()
        section_lines = []
        if not section_text:
            return

        section_text = _linearize_md_tables_in_text(section_text)

        bab = ""
        for heading_text in [current_h1, current_h2]:
            match = bab_pattern.search(heading_text)
            if match:
                bab = f"BAB {match.group(1).upper()}"
                break

        hierarchy_parts = [part for part in [doc_title, current_h1, current_h2, current_h3] if part]
        hierarchy = " > ".join(hierarchy_parts) if hierarchy_parts else (doc_title or "Dokumen")
        section = current_h3 or current_h2 or current_h1 or (doc_title or "")

        metadata = {
            "doc_type": "md_fallback",
            "judul_dokumen": doc_title,
            "filename": filename,
            "section": section,
            "hierarchy": hierarchy,
            "bab": bab,
            "bagian": current_h2 or current_h1 or section,
            "pasal": "",
            "ayat": "",
        }
        append_chunk_with_limit(chunks, section_text, metadata, max_size=MAX_CHUNK_SIZE_LAPORAN, overlap=CHUNK_OVERLAP_LAPORAN)

    for raw_line in cleaned_text.splitlines():
        line = raw_line.rstrip()
        match = heading_pattern.match(line.strip())

        if match:
            level = len(match.group(1))
            heading_text = re.sub(r"\*\*(.+?)\*\*", r"\1", match.group(2).strip())

            if level <= 3:
                flush_section()

            if level == 1:
                current_h1 = heading_text
                current_h2 = ""
                current_h3 = ""
                continue
            if level == 2:
                current_h2 = heading_text
                current_h3 = ""
                continue
            if level == 3:
                current_h3 = heading_text
                continue

            # Keep H4 text in body while preserving H1-H3 hierarchy context.
            section_lines.append(heading_text)
            continue

        section_lines.append(line)

    flush_section()
    return chunks


# ---------------------------------------------------------------------------
# Peraturan chunker
# ---------------------------------------------------------------------------

def chunk_peraturan(doc: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Chunk a new advanced peraturan document."""
    chunks: List[Dict[str, Any]] = []
    
    metadata = doc.get("metadata_dokumen", {})
    judul = f"{metadata.get('jenis_peraturan', 'Peraturan')} {metadata.get('nomor', '')} Tahun {metadata.get('tahun', '')}".strip()
    tentang = metadata.get("tentang", "")
    filename = metadata.get("sumber_file", doc.get("source_filename", ""))

    # Base metadata that all pieces share
    base_meta = {
        "doc_type": "peraturan",
        "judul_dokumen": judul,
        "tentang": tentang,
        "filename": filename,
    }

    # Handle preamble
    preamble = doc.get("preamble", "")
    if preamble and preamble.strip():
        for piece in split_text_with_overlap(preamble, MAX_CHUNK_SIZE_PERATURAN, CHUNK_OVERLAP_PERATURAN):
            chunks.append({
                "text": piece,
                "metadata": {
                    **base_meta,
                    "hierarchy": "Pembukaan",
                    "bab": "",
                    "pasal": "",
                    "ayat": "",
                },
            })

    # Handle Batang Tubuh
    for bab in doc.get("batang_tubuh", []):
        bab_nomor = bab.get("bab_nomor", "")
        bab_judul = bab.get("bab_judul", "")
        
        bab_label = f"BAB {bab_nomor}" if bab_nomor else ""
        if bab_judul:
            bab_label += f" - {bab_judul}"

        for pasal in bab.get("pasal", []):
            pasal_nomor = pasal.get("nomor", "")
            pasal_isi = pasal.get("isi", "")
            ayat_list = pasal.get("ayat", [])
            bagian = pasal.get("bagian", "")

            hierarchy_parts = [judul]
            if bab_label:
                hierarchy_parts.append(bab_label)
            if bagian:
                hierarchy_parts.append(bagian)
            if pasal_nomor and pasal_nomor != "intro":
                hierarchy_parts.append(f"Pasal {pasal_nomor}")

            hierarchy = " > ".join(hierarchy_parts)

            pasal_meta = {
                **base_meta,
                "bab": bab_label,
                "pasal": f"Pasal {pasal_nomor}" if pasal_nomor != "intro" else "",
                "bagian": bagian,
            }

            if ayat_list:
                buffer_text = ""
                buffer_ayat_range = []

                for ayat in ayat_list:
                    ayat_nomor = ayat.get("nomor", "")
                    ayat_isi = ayat.get("isi", "")

                    candidate = f"({ayat_nomor}) {ayat_isi}"

                    if len(buffer_text) + len(candidate) + 1 <= MAX_CHUNK_SIZE_PERATURAN:
                        buffer_text += ("\n" + candidate if buffer_text else candidate)
                        buffer_ayat_range.append(ayat_nomor)
                    else:
                        if buffer_text:
                            ayat_label = f"Ayat ({buffer_ayat_range[0]})" if len(buffer_ayat_range) == 1 else f"Ayat ({buffer_ayat_range[0]})-({buffer_ayat_range[-1]})"
                            complete_text = f"{pasal_isi}\n{buffer_text}" if pasal_isi else buffer_text
                            for piece in split_text_with_overlap(complete_text, MAX_CHUNK_SIZE_PERATURAN, CHUNK_OVERLAP_PERATURAN):
                                chunks.append({
                                    "text": piece,
                                    "metadata": {
                                        **pasal_meta,
                                        "ayat": ayat_label,
                                        "hierarchy": f"{hierarchy} > {ayat_label}",
                                    },
                                })
                        buffer_text = candidate
                        buffer_ayat_range = [ayat_nomor]

                if buffer_text:
                    ayat_label = f"Ayat ({buffer_ayat_range[0]})" if len(buffer_ayat_range) == 1 else f"Ayat ({buffer_ayat_range[0]})-({buffer_ayat_range[-1]})"
                    complete_text = f"{pasal_isi}\n{buffer_text}" if pasal_isi else buffer_text
                    if pasal_nomor and pasal_nomor != "intro":
                        complete_text = f"Pasal {pasal_nomor}\n{complete_text}"
                    for piece in split_text_with_overlap(complete_text, MAX_CHUNK_SIZE_PERATURAN, CHUNK_OVERLAP_PERATURAN):
                        chunks.append({
                            "text": piece,
                            "metadata": {
                                **pasal_meta,
                                "ayat": ayat_label,
                                "hierarchy": f"{hierarchy} > {ayat_label}",
                            },
                        })
            elif pasal_isi:
                pasal_text = pasal_isi
                if pasal_nomor and pasal_nomor != "intro":
                    pasal_text = f"Pasal {pasal_nomor}\n{pasal_isi}"
                for piece in split_text_with_overlap(pasal_text, MAX_CHUNK_SIZE_PERATURAN, CHUNK_OVERLAP_PERATURAN):
                    chunks.append({
                        "text": piece,
                        "metadata": {
                            **pasal_meta,
                            "ayat": "",
                            "hierarchy": hierarchy,
                        },
                    })

    # Handle Lampiran
    lampiran = doc.get("lampiran", {})
    if lampiran:
        judul_lampiran = lampiran.get("judul_lampiran", "Lampiran")
        lampiran_meta = {
            **base_meta,
            "bagian": judul_lampiran
        }

        # Preserve lampiran narrative BAB sections (if available).
        for bab in lampiran.get("narasi_bab", []):
            bab_nomor = str(bab.get("bab_nomor", "")).strip()
            bab_judul = str(bab.get("bab_judul", "")).strip()
            isi = str(bab.get("isi", "")).strip()
            if not isi:
                continue

            bab_label = f"BAB {bab_nomor}" if bab_nomor else "BAB"
            if bab_judul:
                bab_label += f" - {bab_judul}"

            narasi_meta = {
                **lampiran_meta,
                "bab": bab_label,
                "pasal": "",
                "ayat": "",
                "hierarchy": f"{judul} > {judul_lampiran} > {bab_label}",
            }

            append_chunk_with_limit(
                chunks,
                f"{bab_label}\n{isi}",
                narasi_meta,
                max_size=MAX_CHUNK_SIZE_PERATURAN,
                overlap=CHUNK_OVERLAP_PERATURAN,
            )
        
        # If it's the SPBE Kuesioner format
        if "kuesioner_indikator" in lampiran:
            for ind in lampiran.get("kuesioner_indikator", []):
                d_nama = ind.get("domain_nama", "")
                a_nama = ind.get("aspek_nama", "")
                i_nomor = ind.get("indikator_nomor", "")
                i_nama = ind.get("indikator_nama", "")
                pertanyaan = ind.get("pertanyaan", "")
                
                hierarchy = f"{judul} > {judul_lampiran} > Domain {ind.get('domain_nomor', '')}: {d_nama} > Aspek {ind.get('aspek_nomor', '')}: {a_nama} > Indikator {i_nomor}: {i_nama}"
                
                ind_meta = {
                    **lampiran_meta,
                    "hierarchy": hierarchy,
                    "indikator": i_nama,
                    "domain": d_nama,
                    "aspek": a_nama
                }
                
                # Combine it all. For context, we need the question and criteria
                kriteria = ind.get("kriteria_penilaian", {})
                
                # We can try putting it all in one chunk if it fits
                text_blocks = [f"Indikator {i_nomor}: {i_nama}"]
                if pertanyaan: text_blocks.append(f"Pertanyaan: {pertanyaan}")
                
                for t in range(1, 6):
                    k = kriteria.get(f"tingkat_{t}", "")
                    if k:
                        text_blocks.append(f"Tingkat {t}: {k}")
                
                full_ind_text = "\n".join(text_blocks)
                
                append_chunk_with_limit(chunks, full_ind_text, ind_meta, max_size=MAX_CHUNK_SIZE_PERATURAN, overlap=CHUNK_OVERLAP_PERATURAN)
        else:
            # Fallback for normal Lampiran text
            isi = lampiran.get("isi_teks", "")
            if isi:
                for piece in split_text_with_overlap(isi, MAX_CHUNK_SIZE_PERATURAN, CHUNK_OVERLAP_PERATURAN):
                    chunks.append({
                        "text": piece,
                        "metadata": {
                            **lampiran_meta,
                            "hierarchy": f"{judul} > {judul_lampiran}"
                        }
                    })

    return chunks


# ---------------------------------------------------------------------------
# Laporan chunker
# ---------------------------------------------------------------------------

def chunk_laporan(doc: Dict[str, Any]) -> List[Dict[str, Any]]:
    chunks: List[Dict[str, Any]] = []
    judul = doc.get("judul", "")
    filename = doc.get("source_filename", "")

    for section in doc.get("sections", []):
        heading = section.get("heading", "")
        level = section.get("level", 1)
        paragraphs = section.get("paragraphs", [])

        base_meta = {
            "doc_type": "laporan",
            "judul_dokumen": judul,
            "filename": filename,
            "section": heading,
            "section_level": level,
            "hierarchy": heading,
        }

        buffer_text = ""
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            if len(buffer_text) + len(para) + 1 <= MAX_CHUNK_SIZE_LAPORAN:
                buffer_text += ("\n\n" + para if buffer_text else para)
            else:
                if buffer_text:
                    for piece in split_text_with_overlap(buffer_text, MAX_CHUNK_SIZE_LAPORAN, CHUNK_OVERLAP_LAPORAN):
                        chunks.append({
                            "text": piece,
                            "metadata": {**base_meta},
                        })
                buffer_text = para

        if buffer_text:
            for piece in split_text_with_overlap(buffer_text, MAX_CHUNK_SIZE_LAPORAN, CHUNK_OVERLAP_LAPORAN):
                chunks.append({
                    "text": piece,
                    "metadata": {**base_meta},
                })

    return chunks


# ---------------------------------------------------------------------------
# Laporan Evaluasi SPBE chunker
# ---------------------------------------------------------------------------

def chunk_laporan_spbe(doc: Dict[str, Any]) -> List[Dict[str, Any]]:
    chunks: List[Dict[str, Any]] = []
    
    metadata = doc.get("metadata_dokumen", {})
    judul = f"{metadata.get('jenis_dokumen', 'Laporan')} Tahun {metadata.get('tahun_evaluasi', '')}".strip()
    filename = metadata.get("sumber_file", doc.get("source_filename", ""))

    base_meta = {
        "doc_type": "laporan_spbe",
        "judul_dokumen": judul,
        "filename": filename,
    }

    # 1. Chunk Ringkasan Eksekutif
    for ringkasan in doc.get("ringkasan_eksekutif", []):
        topik = ringkasan.get("topik", "Kesimpulan")
        isi = ringkasan.get("isi", "")
        
        meta = {
            **base_meta,
            "bagian": "Ringkasan Eksekutif",
            "topik": topik,
            "hierarchy": f"{judul} > Ringkasan Eksekutif > {topik}"
        }
        
        text_w_topik = f"{topik}: {isi}"
        for piece in split_text_with_overlap(text_w_topik, MAX_CHUNK_SIZE_LAPORAN, CHUNK_OVERLAP_LAPORAN):
            chunks.append({"text": piece, "metadata": meta})

    # 2. Chunk Rekomendasi Strategis
    for rekom in doc.get("rekomendasi_strategis", []):
        poin = rekom.get("poin_ke", 0)
        judul_rekom = rekom.get("judul", "")
        tindakan_list = rekom.get("tindakan", [])

        meta = {
            **base_meta,
            "bagian": "Rekomendasi Strategis",
            "topik": judul_rekom,
            "hierarchy": f"{judul} > Rekomendasi Strategis > {poin}. {judul_rekom}"
        }

        buffer_text = f"Rekomendasi {poin} - {judul_rekom}:"
        for tindakan in tindakan_list:
            candidate = f"• {tindakan}"
            if len(buffer_text) + len(candidate) + 1 <= MAX_CHUNK_SIZE_LAPORAN:
                buffer_text += "\n" + candidate
            else:
                for piece in split_text_with_overlap(buffer_text, MAX_CHUNK_SIZE_LAPORAN, CHUNK_OVERLAP_LAPORAN):
                    chunks.append({"text": piece, "metadata": meta})
                buffer_text = candidate

        if buffer_text:
            for piece in split_text_with_overlap(buffer_text, MAX_CHUNK_SIZE_LAPORAN, CHUNK_OVERLAP_LAPORAN):
                chunks.append({"text": piece, "metadata": meta})

    # 3. Chunk Data Capaian Instansi
    # Logical Chunking: 1 Instansi exactly = 1 Chunk (Do not use Text Splitter)
    instansi_list = doc.get("data_capaian_instansi", [])

    for inst in instansi_list:
        nama = inst.get("nama_instansi", "")
        skor = inst.get("skor_domain", {})
        indeks = inst.get("indeks_spbe_akhir", 0)
        predikat = inst.get("predikat", "")

        candidate = (
            f"Instansi: {nama}\n"
            f"- Indeks Akhir: {indeks} ({predikat})\n"
            f"- Domain Kebijakan Internal: {skor.get('kebijakan_internal', 0)}\n"
            f"- Domain Tata Kelola: {skor.get('tata_kelola', 0)}\n"
            f"- Domain Manajemen: {skor.get('manajemen_spbe', 0)}\n"
            f"- Domain Layanan: {skor.get('layanan_spbe', 0)}\n"
        )

        meta = {
            **base_meta,
            "bagian": "Data Capaian Instansi",
            "hierarchy": f"{judul} > Data Capaian Instansi"
        }

        append_chunk_with_limit(chunks, candidate, meta, max_size=MAX_CHUNK_SIZE_LAPORAN, overlap=CHUNK_OVERLAP_LAPORAN)

    return chunks


# ---------------------------------------------------------------------------
# Pedoman SPBE chunker
# ---------------------------------------------------------------------------

def chunk_pedoman_spbe(doc: Dict[str, Any]) -> List[Dict[str, Any]]:
    chunks: List[Dict[str, Any]] = []
    
    metadata = doc.get("metadata_dokumen", {})
    judul = f"{metadata.get('jenis_dokumen', 'Pedoman')} Nomor {metadata.get('nomor', '')} Tahun {metadata.get('tahun', '')}".strip()
    filename = metadata.get("sumber_file", doc.get("source_filename", ""))

    base_meta = {
        "doc_type": "pedoman_spbe",
        "judul_dokumen": judul,
        "filename": filename,
    }

    # 1. Chunk Narasi Pedoman
    for bab in doc.get("narasi_pedoman", []):
        bab_no = bab.get("bab_nomor", "")
        bab_judul = bab.get("bab_judul", "")
        
        bab_label = f"BAB {bab_no}" if bab_no else ""
        if bab_judul: bab_label += f" - {bab_judul}"
            
        for sub in bab.get("sub_bab", []):
            huruf = sub.get("huruf", "")
            sub_judul = sub.get("judul", "")
            isi = sub.get("isi_teks", "")
            
            sub_label = f"{huruf}. {sub_judul}" if huruf else sub_judul
            hierarchy = f"{judul} > {bab_label} > {sub_label}"
            
            meta = {
                **base_meta,
                "bab": bab_label,
                "bagian": sub_label,
                "hierarchy": hierarchy
            }
            
            if isi:
                for piece in split_text_with_overlap(isi, MAX_CHUNK_SIZE_LAPORAN, CHUNK_OVERLAP_LAPORAN):
                    chunks.append({"text": piece, "metadata": meta})

    # 2. Chunk Instrumen Indikator
    for ind in doc.get("instrumen_indikator", []):
        domain = ind.get("domain", "")
        i_nomor = ind.get("indikator_nomor", "")
        i_nama = ind.get("indikator_nama", "")
        deskripsi = ind.get("deskripsi", "")
        
        hierarchy = f"{judul} > Lampiran Instrumen > Domain: {domain} > Indikator {i_nomor}: {i_nama}"
        
        meta = {
            **base_meta,
            "domain": domain,
            "indikator": i_nama,
            "hierarchy": hierarchy
        }
        
        text_blocks = [f"Indikator {i_nomor}: {i_nama}"]
        if deskripsi:
            text_blocks.append(f"Deskripsi: {deskripsi}")
            
        k_level = ind.get("kriteria_level", {})
        k_bukti = ind.get("kriteria_bukti_dukung", {})
        
        for t in range(1, 6):
            lvl_text = k_level.get(str(t), "")
            bukti_text = k_bukti.get(str(t), "")
            
            if lvl_text or bukti_text:
                text_blocks.append(f"Tingkat {t}:")
                if lvl_text: text_blocks.append(f"- Kriteria: {lvl_text}")
                if bukti_text: text_blocks.append(f"- Bukti Dukung: {bukti_text}")
                
        full_ind_text = "\n".join(text_blocks)

        append_chunk_with_limit(chunks, full_ind_text, meta, max_size=MAX_CHUNK_SIZE_LAPORAN, overlap=CHUNK_OVERLAP_LAPORAN)

    return chunks


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def chunk_document(doc: Dict[str, Any], md_file_path: Optional[str] = None) -> List[Dict[str, Any]]:
    doc_type = doc.get("type", "laporan")

    if doc_type == "peraturan":
        chunks = chunk_peraturan(doc)
    elif doc_type == "laporan_spbe":
        chunks = chunk_laporan_spbe(doc)
    elif doc_type == "pedoman_spbe":
        chunks = chunk_pedoman_spbe(doc)
    else:
        chunks = chunk_laporan(doc)

    if len(chunks) < MIN_JSON_CHUNKS_THRESHOLD and md_file_path:
        md_path = Path(md_file_path)
        if md_path.exists():
            logger.warning(
                "JSON parser menghasilkan {} chunks (< {}). Mencoba fallback markdown: {}",
                len(chunks),
                MIN_JSON_CHUNKS_THRESHOLD,
                md_path.name,
            )
            try:
                with open(md_path, "r", encoding="utf-8") as f:
                    md_text = f.read()

                metadata = doc.get("metadata_dokumen") or {}
                doc_title = (
                    metadata.get("tentang")
                    or doc.get("judul")
                    or Path(doc.get("source_filename") or md_path.stem).stem
                )
                filename = doc.get("source_filename") or md_path.name

                md_chunks = chunk_from_markdown(md_text, filename, doc_title)
                if len(md_chunks) > len(chunks):
                    logger.success(
                        "Fallback markdown aktif: {} chunks (sebelumnya {} chunks)",
                        len(md_chunks),
                        len(chunks),
                    )
                    chunks = md_chunks
                else:
                    logger.info(
                        "Fallback markdown tidak menggantikan hasil JSON ({} <= {})",
                        len(md_chunks),
                        len(chunks),
                    )
            except Exception as e:
                logger.error(f"Fallback markdown gagal: {e}. Tetap gunakan JSON chunks.")

    final_chunks = []
    for i, chunk in enumerate(chunks):
        text = chunk["text"].strip()
        if len(text) < 10:
            continue
        chunk["chunk_index"] = i
        final_chunks.append(chunk)

    sizes = [len(c["text"]) for c in final_chunks]
    if sizes:
        logger.info(
            f"Chunked {doc_type} into {len(final_chunks)} chunks: "
            f"avg={sum(sizes)//len(sizes)} chars, "
            f"min={min(sizes)}, max={max(sizes)}"
        )
    else:
        logger.warning(f"No chunks produced for {doc_type} document")

    return final_chunks
