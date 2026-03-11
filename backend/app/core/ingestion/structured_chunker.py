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
from typing import List, Dict, Any, Optional
from loguru import logger
from langchain_text_splitters import RecursiveCharacterTextSplitter
from app.config import settings


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

MAX_CHUNK_SIZE = getattr(settings, "CHUNK_SIZE", 600)
CHUNK_OVERLAP = getattr(settings, "CHUNK_OVERLAP", 100)
MIN_CHUNK_SIZE = 80  # Don't create tiny chunks


# ---------------------------------------------------------------------------
# Text splitting utilities
# ---------------------------------------------------------------------------

def split_text_with_overlap(
    text: str,
    max_size: int = MAX_CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP,
) -> List[str]:
    """Split long text using Langchain's RecursiveCharacterTextSplitter."""
    if len(text) <= max_size:
        return [text]

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=max_size,
        chunk_overlap=overlap,
        separators=["\n\n", "\n", ".", " ", ""],
    )
    return splitter.split_text(text)


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
        for piece in split_text_with_overlap(preamble):
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

                    if len(buffer_text) + len(candidate) + 1 <= MAX_CHUNK_SIZE:
                        buffer_text += ("\n" + candidate if buffer_text else candidate)
                        buffer_ayat_range.append(ayat_nomor)
                    else:
                        if buffer_text:
                            ayat_label = f"Ayat ({buffer_ayat_range[0]})" if len(buffer_ayat_range) == 1 else f"Ayat ({buffer_ayat_range[0]})-({buffer_ayat_range[-1]})"
                            complete_text = f"{pasal_isi}\n{buffer_text}" if pasal_isi else buffer_text
                            for piece in split_text_with_overlap(complete_text):
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
                    for piece in split_text_with_overlap(complete_text):
                        chunks.append({
                            "text": piece,
                            "metadata": {
                                **pasal_meta,
                                "ayat": ayat_label,
                                "hierarchy": f"{hierarchy} > {ayat_label}",
                            },
                        })
            elif pasal_isi:
                for piece in split_text_with_overlap(pasal_isi):
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
                
                # Logical Chunking: 1 Indicator exactly = 1 Chunk
                chunks.append({
                    "text": full_ind_text,
                    "metadata": ind_meta
                })
        else:
            # Fallback for normal Lampiran text
            isi = lampiran.get("isi_teks", "")
            if isi:
                for piece in split_text_with_overlap(isi):
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

            if len(buffer_text) + len(para) + 1 <= MAX_CHUNK_SIZE:
                buffer_text += ("\n\n" + para if buffer_text else para)
            else:
                if buffer_text:
                    for piece in split_text_with_overlap(buffer_text):
                        chunks.append({
                            "text": piece,
                            "metadata": {**base_meta},
                        })
                buffer_text = para

        if buffer_text:
            for piece in split_text_with_overlap(buffer_text):
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
        for piece in split_text_with_overlap(text_w_topik):
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
            if len(buffer_text) + len(candidate) + 1 <= MAX_CHUNK_SIZE:
                buffer_text += "\n" + candidate
            else:
                for piece in split_text_with_overlap(buffer_text):
                    chunks.append({"text": piece, "metadata": meta})
                buffer_text = candidate
        
        if buffer_text:
            for piece in split_text_with_overlap(buffer_text):
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
        
        chunks.append({"text": candidate, "metadata": meta})

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
                for piece in split_text_with_overlap(isi):
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
        
        # Logical Chunking: 1 Indicator exactly = 1 Chunk
        chunks.append({"text": full_ind_text, "metadata": meta})

    return chunks


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def chunk_document(doc: Dict[str, Any]) -> List[Dict[str, Any]]:
    doc_type = doc.get("type", "laporan")

    if doc_type == "peraturan":
        chunks = chunk_peraturan(doc)
    elif doc_type == "laporan_spbe":
        chunks = chunk_laporan_spbe(doc)
    elif doc_type == "pedoman_spbe":
        chunks = chunk_pedoman_spbe(doc)
    else:
        chunks = chunk_laporan(doc)

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
