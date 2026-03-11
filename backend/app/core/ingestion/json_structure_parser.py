"""
JSON Structure Parser for Indonesian Legal & Audit Documents

Converts raw text (from Marker/OCR) into a structured JSON representation.
Detects: BAB, Bagian, Pasal, Ayat, headings, tables, paragraphs.

Output formats:
  - "peraturan": hierarchical `metadata_dokumen`, `batang_tubuh`, and `lampiran`
  - "laporan":   sectioned by headings with paragraphs

Tables are linearized into readable "Header: Value" text.
Images (![...]) are stripped.
"""

import re
import json
from typing import List, Dict, Any, Optional
from loguru import logger


# ---------------------------------------------------------------------------
# Table linearization
# ---------------------------------------------------------------------------

def linearize_table(table_text: str) -> str:
    """Convert markdown table into linearized readable text."""
    lines = [l.strip() for l in table_text.strip().split("\n") if l.strip()]
    if len(lines) < 2:
        return table_text

    def parse_row(row: str) -> List[str]:
        cells = [c.strip() for c in row.strip().strip("|").split("|")]
        return [c for c in cells if c]

    headers = parse_row(lines[0])

    data_lines = []
    for line in lines[1:]:
        if re.match(r"^\|[\s\-:|\+]+\|?$", line):
            continue
        data_lines.append(line)

    if not headers:
        return table_text

    results = []
    for line in data_lines:
        cells = parse_row(line)
        parts = []
        for i, cell in enumerate(cells):
            header = headers[i] if i < len(headers) else f"Kolom{i+1}"
            if cell and cell != "-":
                parts.append(f"{header}: {cell}")
        if parts:
            results.append("; ".join(parts))

    return "\n".join(results) if results else table_text


def extract_and_linearize_tables(text: str) -> str:
    table_pattern = re.compile(
        r"((?:^\|.+\|[ \t]*$\n?){2,})",
        re.MULTILINE,
    )

    def replace_table(match):
        table_text = match.group(1)
        linearized = linearize_table(table_text)
        return "\n" + linearized + "\n"

    return table_pattern.sub(replace_table, text)


# ---------------------------------------------------------------------------
# Text cleaning
# ---------------------------------------------------------------------------

def clean_text(text: str) -> str:
    text = re.sub(r"!\[.*?\]\(.*?\)", "", text)
    text = re.sub(r"---\s*Page\s+\d+\s*---", "", text)
    text = extract_and_linearize_tables(text)
    text = re.sub(r"\n{4,}", "\n\n\n", text)
    return text.strip()


# ---------------------------------------------------------------------------
# Advanced SPBE Lampiran Parsing
# ---------------------------------------------------------------------------

def parse_spbe_lampiran(lampiran_text: str) -> Dict[str, Any]:
    """Parse the lampiran specifically looking for SPBE domains/aspek/indikator."""
    kuesioner = []
    
    # We look for Domain, Aspek, Indikator markers
    tokens = re.finditer(r"(?i)(Domain\s+(\d+)\s*[:.]\s*(.+?)\n|Aspek\s+(\d+)\s*[:.]\s*(.+?)\n|Indikator\s+(\d+)\s*[:.]\s*(.+?)\n)", lampiran_text)
    
    current_domain_no = None
    current_domain_nama = None
    current_aspek_no = None
    current_aspek_nama = None
    indicators_raw = []
    
    current_indikator = None
    
    for match in tokens:
        full_match = match.group(0)
        
        if "domain" in full_match.lower() and match.group(2):
            current_domain_no = int(match.group(2))
            current_domain_nama = match.group(3).strip()
        elif "aspek" in full_match.lower() and match.group(4):
            current_aspek_no = int(match.group(4))
            current_aspek_nama = match.group(5).strip()
        elif "indikator" in full_match.lower() and match.group(6):
            if current_indikator:
                current_indikator["body_end"] = match.start()
                indicators_raw.append(current_indikator)
            
            current_indikator = {
                "domain_nomor": current_domain_no,
                "domain_nama": current_domain_nama,
                "aspek_nomor": current_aspek_no,
                "aspek_nama": current_aspek_nama,
                "indikator_nomor": int(match.group(6)),
                "indikator_nama": match.group(7).strip(),
                "body_start": match.end()
            }
            
    if current_indikator:
        current_indikator["body_end"] = len(lampiran_text)
        indicators_raw.append(current_indikator)
        
    for ind in indicators_raw:
        body = lampiran_text[ind["body_start"]:ind["body_end"]]
        
        # Pertanyaan is text before the first "1 \n" or "Tingkat 1"
        pertanyaan_match = re.search(r"(.*?)(?=\n\s*(?:1|Tingkat\s*1)\s*\n|\Z)", body, re.IGNORECASE | re.DOTALL)
        if pertanyaan_match:
            pert = pertanyaan_match.group(1).strip()
            # Clean up OCR noise in pertanyaan
            pert = re.sub(r"(Tingkat|Kriteria)\s*$", "", pert).strip()
            ind["pertanyaan"] = pert
        else:
            ind["pertanyaan"] = ""
            
        kriteria = {}
        for i in range(1, 6):
            # Look for "1 \n" or "Tingkat 1 \n"
            current_num = rf"\n\s*(?:{i}|Tingkat\s*{i})\s*\n"
            next_num = rf"\n\s*(?:{i+1}|Tingkat\s*{i+1})\s*\n" if i < 5 else r"\n\s*Jawaban\s*:"
            
            pattern = rf"{current_num}(.*?)(?={next_num}|\Z)"
            lvl_match = re.search(pattern, "\n" + body, re.IGNORECASE | re.DOTALL)
            
            if lvl_match:
                k_text = lvl_match.group(1).strip()
                # PDFs have weird repeats: "Konsep... Konsep...". We just keep the first sentence/block or just take it as is
                # Truncate at Jawaban just in case
                k_text = re.sub(r"Jawaban\s*:.*", "", k_text, flags=re.IGNORECASE | re.DOTALL).strip()
                # Remove repeated blocks (naive approach for OCR artifacts)
                lines = k_text.split('\n')
                unique_lines = []
                for line in lines:
                    line = line.strip()
                    if line and line not in unique_lines:
                        unique_lines.append(line)
                kriteria[f"tingkat_{i}"] = " ".join(unique_lines)
            else:
                kriteria[f"tingkat_{i}"] = ""
                
        ind["kriteria_penilaian"] = kriteria
        
        del ind["body_start"]
        del ind["body_end"]
        kuesioner.append(ind)
        
    return {
        "judul_lampiran": "LAMPIRAN",
        "kuesioner_indikator": kuesioner
    }


# ---------------------------------------------------------------------------
# Structure detection for Peraturan
# ---------------------------------------------------------------------------

_RE_BAB = re.compile(
    r"^(?:#+\s*)?BAB\s+([IVXLCDM]+)\b[.\s]*(.*)$",
    re.MULTILINE | re.IGNORECASE,
)
_RE_BAGIAN = re.compile(
    r"^(?:#+\s*)?Bagian\s+(Kesatu|Kedua|Ketiga|Keempat|Kelima|Keenam|Ketujuh|Kedelapan|Kesembilan|Kesepuluh|\w+)\b[.\s]*(.*)$",
    re.MULTILINE | re.IGNORECASE,
)
_RE_PASAL = re.compile(
    r"^\s*(?:#+\s*)?Pasal\s+(\d+)\s*(.*?)$",
    re.MULTILINE | re.IGNORECASE,
)
_RE_AYAT = re.compile(
    r"^\s*\((\d+)\)\s+(.+)",
    re.MULTILINE,
)

def parse_petunjuk_teknis(text: str) -> Dict[str, Any]:
    """Hierarchical parser for the 'Petunjuk Teknis' often found in SE Lampiran."""
    # This is basically a mini-version of parse_peraturan (BAB/Pasal style)
    # But often Petunjuk Teknis uses BAB I, BAB II without 'Pasal'. 
    # It might use 'A. ', '1. ', 'a) '.
    
    sections = []
    lines = text.split("\n")
    current_bab = None
    pending_text = []

    def flush_pending():
        nonlocal pending_text, current_bab
        if current_bab and pending_text:
            text_block = "\n".join(pending_text).strip()
            if text_block:
                if not current_bab["pasal"]:
                    current_bab["pasal"].append({"nomor": "isi", "isi": text_block, "ayat": []})
                else:
                    current_bab["pasal"][0]["isi"] += "\n" + text_block
            pending_text = []

    for line in lines:
        stripped = line.strip()
        # Better BAB regex for Petunjuk Teknis: "# **BAB I PENDAHULUAN**", "BAB I", etc.
        m_bab = re.match(r"^(?:#+\s*)?(?:\*\*\s*)?BAB\s+([IVXLCDM]+)(?:\s+(.*?))?(?:\s*\*\*)?$", stripped, re.IGNORECASE)
        
        if m_bab:
            flush_pending()
            current_bab = {
                "bab_nomor": m_bab.group(1).upper(),
                "bab_judul": m_bab.group(2).strip() if m_bab.group(2) else "",
                "pasal": []
            }
            sections.append(current_bab)
            continue
            
        # If current_bab is missing a title, look for it in the following heading lines
        if current_bab and not current_bab["bab_judul"] and stripped:
            # Matches header patterns like "#### **TITLE**" or just "**TITLE**"
            title_match = re.search(r"^(?:#+\s*)?(?:\*\*\s*)?(.*?)(?:\s*\*\*)?$", stripped)
            if title_match and len(title_match.group(1)) > 3:
                current_bab["bab_judul"] = title_match.group(1).strip()
                continue
        
        pending_text.append(line)
    
    flush_pending()
    return {"sections": sections}

def parse_surat_edaran(text: str, metadata_dokumen: Dict[str, Any], filename: str) -> Dict[str, Any]:
    """High-granularity parser for Surat Edaran (SE) aligning with Laporan standards."""
    result = {
        "type": "peraturan",
        "metadata_dokumen": metadata_dokumen,
        "penerima": [],
        "latar_belakang": "",
        "maksud_dan_tujuan": {"maksud": "", "tujuan": ""},
        "ruang_lingkup": "",
        "dasar_hukum": [],
        "isi_edaran": "",
        "penutup": "",
        "lampiran": {},
        "batang_tubuh": [] # Keeping for compatibility
    }
    
    # Metadata enhancements
    if "KEMENTERIAN" in text.upper():
        result["metadata_dokumen"]["penerbit"] = "Kementerian PANRB" # Defaulting to known publisher if meta missing
    
    # Isolate Lampiran
    # Robust pattern for: "LAMPIRAN", "# **LAMPIRAN", "  **LAMPIRAN", etc.
    lamp_pattern = re.compile(r"\n+\s*(?:#+\s*)?(?:\*\*)?LAMPIRAN(?:\s+.*)?\n", re.IGNORECASE)
    lamp_match = list(lamp_pattern.finditer(text))
    if lamp_match:
        # Usually the last "LAMPIRAN" header is the one we want if there are multiple (e.g. references)
        # But for SE 18, it's the one starting the big appendix.
        # We'll take the first one that looks like a major section if multiple exist.
        match = lamp_match[0]
        # In SE 18, the first "LAMPIRAN" match is actually the header on page 1.
        # We need to find the one that denotes the END of the SE body.
        # A better heuristic: the one that is NOT followed immediately by "NOMOR" on the same line (which is the main title)
        for m in lamp_match:
            snippet = text[m.start():m.start()+200].upper()
            if "PETUNJUK TEKNIS" in snippet or "PEDOMAN" in snippet or ("LAMPIRAN" in snippet and len(snippet.split("\n")[0]) < 100):
                match = m
                break
        
        last_lamp_start = match.start()
        tubuh_text = text[:last_lamp_start]
        lamp_text = text[last_lamp_start:]
    else:
        tubuh_text = text
        lamp_text = ""

    # Split body into lines
    lines = tubuh_text.split("\n")
    
    # 1. Extract Recipients (Yth. block)
    yth_idx = -1
    for idx, l in enumerate(lines[:100]):
        if re.search(r"Yth\.|Kepada", l, re.IGNORECASE):
            yth_idx = idx
            break
            
    if yth_idx != -1:
        penerima = []
        for l in lines[yth_idx+1:]:
            stripped = l.strip()
            # Stop if we hit the first section or SE title
            if re.match(r"^(?:#+\s*)?(?:\*\*\s*)?1\.\s+", stripped, re.IGNORECASE) or re.match(r"^(?:#+\s*)?(?:\*\*\s*)?SURAT\s*EDARAN", stripped, re.IGNORECASE):
                break
            # Skip empty lines, page numbers, and table separators
            if stripped and not re.match(r"^- \d+ -", stripped) and not stripped.startswith("|"):
                penerima.append(stripped)
        result["penerima"] = [p for p in penerima if len(p) > 3]

    # 2. Extract Numbered Sections (1-6)
    section_map = {
        "1": "latar_belakang",
        "2": "maksud_dan_tujuan",
        "3": "ruang_lingkup",
        "4": "dasar_hukum",
        "5": "isi_edaran",
        "6": "penutup"
    }
    
    current_key = None
    current_content = []
    
    # Improved regex: Matches "# **1. Latar Belakang**", "1. **Latar Belakang**", "**1. Latar Belakang**", etc.
    re_section = re.compile(r"^(?:#+\s*)?(?:\*\*\s*)?(\d+)\.\s+(?:\*\*\s*)?(.*?)(?:\s*\*\*)?$", re.IGNORECASE)
    
    for line in lines:
        stripped = line.strip()
        m = re_section.match(stripped)
        
        if m:
            num = m.group(1)
            judul = m.group(2).upper()
            
            # Validation: SE sections are usually short headings
            if num in section_map and (len(judul) < 100 or any(kw in judul for kw in ["LATAR", "MAKSUD", "TUJUAN", "RUANG", "DASAR", "ISI", "LSI", "PENUTUP"])):
                # Flush previous
                if current_key and current_content:
                    raw_block = "\n".join(current_content).strip()
                    if current_key == "maksud_dan_tujuan":
                        # Better "Maksud" and "Tujuan" extraction (handles bolding # a. Maksud)
                        m_part = re.search(r"(?:#\s+)?(?:[ab]\.\s+)?Maksud(.*?)(?=(?:#\s+)?(?:[ab]\.\s+)?Tujuan|\Z)", raw_block, re.DOTALL | re.IGNORECASE)
                        t_part = re.search(r"(?:#\s+)?(?:[ab]\.\s+)?Tujuan(.*)", raw_block, re.DOTALL | re.IGNORECASE)
                        result["maksud_dan_tujuan"]["maksud"] = m_part.group(1).strip() if m_part else ""
                        result["maksud_dan_tujuan"]["tujuan"] = t_part.group(1).strip() if t_part else ""
                    elif current_key == "dasar_hukum":
                        result["dasar_hukum"] = [l.strip().lstrip("- ").strip() for l in raw_block.split("\n") if len(l.strip()) > 10]
                    else:
                        result[current_key] = raw_block
                
                current_key = section_map[num]
                current_content = []
                continue
        
        if current_key:
            current_content.append(line)

    # Final flush
    if current_key and current_content:
        raw_block = "\n".join(current_content).strip()
        if current_key == "maksud_dan_tujuan":
            m_part = re.search(r"(?:#\s+)?(?:[ab]\.\s+)?Maksud(.*?)(?=(?:#\s+)?(?:[ab]\.\s+)?Tujuan|\Z)", raw_block, re.DOTALL | re.IGNORECASE)
            t_part = re.search(r"(?:#\s+)?(?:[ab]\.\s+)?Tujuan(.*)", raw_block, re.DOTALL | re.IGNORECASE)
            result["maksud_dan_tujuan"]["maksud"] = m_part.group(1).strip() if m_part else ""
            result["maksud_dan_tujuan"]["tujuan"] = t_part.group(1).strip() if t_part else ""
        elif current_key == "dasar_hukum":
            result["dasar_hukum"] = [l.strip().lstrip("- ").strip() for l in raw_block.split("\n") if len(l.strip()) > 10]
        else:
            result[current_key] = raw_block

    # 3. Deep Lampiran Parsing (Petunjuk Teknis)
    if lamp_text:
        if "PETUNJUK TEKNIS" in lamp_text.upper():
            result["lampiran"] = parse_petunjuk_teknis(lamp_text)
        else:
            result["lampiran"] = {"isi_teks": lamp_text}

    # Map to batang_tubuh for compatibility with chunker
    for k in ["latar_belakang", "isi_edaran", "penutup"]:
        if result[k]:
            result["batang_tubuh"].append({
                "bab_nomor": k,
                "bab_judul": k.replace("_", " ").title(),
                "pasal": [{"nomor": "isi", "isi": result[k], "ayat": []}]
            })

    return result

def parse_peraturan(text: str, metadata: Optional[Dict] = None, filename: str = "") -> Dict[str, Any]:
    """Parse regulation text into user's requested advanced JSON format."""
    
    metadata_dokumen = {
        "jenis_peraturan": "Peraturan",
        "nomor": "",
        "tahun": "",
        "tentang": "",
        "sumber_file": filename
    }

    # Extract info from first lines
    first_lines = text[:1500].split("\n")
    for idx, line in enumerate(first_lines):
        line = line.strip()
        
        # Enhanced extraction for Nomor/Tahun (Handling NOMOR: or NOMOR )
        if re.search(r"(?:PERATURAN|UNDANG|PERPRES|PERMEN|SURAT\s+EDARAN|NOMOR)", line, re.IGNORECASE) and not metadata_dokumen["nomor"]:
            m = re.search(r"NOMOR[:\s]+(\d+[\/\w\.-]*)\s+TAHUN\s+(\d{4})", line, re.IGNORECASE)
            if m:
                metadata_dokumen["nomor"] = m.group(1)
                metadata_dokumen["tahun"] = m.group(2)
        
        if re.search(r"TENTANG", line, re.IGNORECASE) and not metadata_dokumen["tentang"]:
            collected_tentang = []
            for j in range(idx + 1, min(idx + 5, len(first_lines))):
                l_next = first_lines[j].strip()
                if not l_next or re.search(r"DENGAN RAHMAT|PRESIDEN|MENTERI", l_next, re.IGNORECASE):
                    break
                collected_tentang.append(l_next)
            metadata_dokumen["tentang"] = " ".join(collected_tentang).strip()

        # Update jenis_peraturan if explicitly stated
        if re.search(r"^(?:PERATURAN|SURAT\s+EDARAN|KEPUTUSAN)", line, re.IGNORECASE) and len(line) < 100:
             metadata_dokumen["jenis_peraturan"] = line

    # ROUTING: Check if this is a Surat Edaran to use specialized logic
    is_se = False
    if re.search(r"SURAT\s*EDARAN", str(metadata_dokumen["jenis_peraturan"]), re.IGNORECASE):
        is_se = True
    elif re.search(r"SURAT\s*EDARAN", text[:3000], re.IGNORECASE):
        is_se = True
    
    if is_se:
        return parse_surat_edaran(text, metadata_dokumen, filename)

    result: Dict[str, Any] = {
        "type": "peraturan",
        "metadata_dokumen": metadata_dokumen,
        "batang_tubuh": [],
        "lampiran": {}
    }

    # Separate Lampiran
    lampiran_idx = text.lower().find('\n\nlampiran')
    if lampiran_idx == -1:
        lampiran_idx = text.lower().find('\nlampiran')
    
    if lampiran_idx != -1:
        tubuh_text = text[:lampiran_idx]
        lamp_text = text[lampiran_idx:]
    else:
        tubuh_text = text
        lamp_text = ""

    # Parse Batang Tubuh
    lines = tubuh_text.split("\n")
    current_bab: Optional[Dict] = None
    current_bagian: Optional[Dict] = None
    current_pasal: Optional[Dict] = None
    pending_text: List[str] = []

    def flush_pending():
        nonlocal pending_text
        if not pending_text:
            return
        full_text = "\n".join(pending_text).strip()
        if not full_text:
            pending_text = []
            return

        if current_pasal is not None:
            ayat_matches = list(_RE_AYAT.finditer(full_text))
            if ayat_matches:
                pre_text = full_text[: ayat_matches[0].start()].strip()
                if pre_text:
                    current_pasal["isi"] = (current_pasal["isi"] or "") + ("\n" + pre_text if current_pasal["isi"] else pre_text)

                for i, m in enumerate(ayat_matches):
                    ayat_end = ayat_matches[i + 1].start() if i + 1 < len(ayat_matches) else len(full_text)
                    ayat_text = full_text[m.start():ayat_end].strip()
                    ayat_content = re.sub(r"^\(\d+\)\s*", "", ayat_text).strip()
                    current_pasal["ayat"].append({
                        "nomor": m.group(1),
                        "isi": ayat_content,
                    })
            else:
                current_pasal["isi"] = (current_pasal["isi"] or "") + ("\n" + full_text if current_pasal["isi"] else full_text)
        elif current_bab is not None:
            if not current_bab.get("_intro"):
                current_bab["_intro"] = ""
            current_bab["_intro"] += ("\n" + full_text) if current_bab["_intro"] else full_text
        else:
            if "preamble" not in result:
                result["preamble"] = ""
            result["preamble"] += ("\n" + full_text) if result["preamble"] else full_text

        pending_text = []

    for line in lines:
        stripped = line.strip()

        m_bab = _RE_BAB.match(stripped)
        if m_bab:
            flush_pending()
            current_bab = {
                "bab_nomor": m_bab.group(1).upper(),
                "bab_judul": m_bab.group(2).strip(),
                "pasal": [],
            }
            result["batang_tubuh"].append(current_bab)
            current_bagian = None
            current_pasal = None
            continue

        m_bagian = _RE_BAGIAN.match(stripped)
        if m_bagian:
            flush_pending()
            current_bagian = {
                "nama": m_bagian.group(1),
                "judul": m_bagian.group(2).strip(),
            }
            current_pasal = None
            continue

        m_pasal = _RE_PASAL.match(stripped)
        if m_pasal:
            flush_pending()
            current_pasal = {
                "nomor": m_pasal.group(1),
                "isi": m_pasal.group(2).strip(),
                "ayat": [],
            }
            if current_bagian:
                current_pasal["bagian"] = f"{current_bagian['nama']} - {current_bagian['judul']}"
            if current_bab is not None:
                current_bab["pasal"].append(current_pasal)
            else:
                if not result["batang_tubuh"]:
                    current_bab = {"bab_nomor": None, "bab_judul": None, "pasal": []}
                    result["batang_tubuh"].append(current_bab)
                current_bab["pasal"].append(current_pasal)
            continue

        pending_text.append(line)

    flush_pending()

    for bab in result["batang_tubuh"]:
        intro = bab.pop("_intro", None)
        if intro and intro.strip():
            bab["pasal"].insert(0, {
                "nomor": "intro",
                "isi": intro.strip(),
                "ayat": [],
            })

    # Parse Lampiran
    if lamp_text:
        if "indikator" in lamp_text.lower() and "kematangan" in lamp_text.lower():
            result["lampiran"] = parse_spbe_lampiran(lamp_text)
        else:
            result["lampiran"] = {"isi_teks": lamp_text[:5000]} # Just storing text if not SPBE

    return result


# ---------------------------------------------------------------------------
# Structure detection for Laporan / Audit
# ---------------------------------------------------------------------------

_RE_HEADING = re.compile(
    r"^(#{1,4})\s+(.+)$",
    re.MULTILINE,
)
_RE_SECTION_HEADING = re.compile(
    r"^(?:BAB|Bab|BAGIAN|Bagian|LAMPIRAN|Lampiran)\s+.+$",
    re.MULTILINE,
)

def parse_laporan_spbe(text: str, metadata: Optional[Dict] = None, filename: str = "") -> Dict[str, Any]:
    """Parse Laporan Evaluasi SPBE specifically, rebuilding flattened tables and structure."""
    result = {
        "type": "laporan_spbe",
        "metadata_dokumen": {
            "jenis_dokumen": "Laporan Evaluasi SPBE",
            "tahun_evaluasi": "",
            "penerbit": "",
            "deputi": "",
            "sumber_file": filename
        },
        "ringkasan_eksekutif": [],
        "rekomendasi_strategis": [],
        "data_capaian_instansi": []
    }
    
    first_lines = text[:500].split('\n')
    for line in first_lines:
        line = line.strip()
        m_tahun = re.search(r"TAHUN\s+(\d{4})", line, re.IGNORECASE)
        if m_tahun and not result["metadata_dokumen"]["tahun_evaluasi"]:
            result["metadata_dokumen"]["tahun_evaluasi"] = m_tahun.group(1)
        if "KEMENTERIAN PENDAYAGUNAAN APARATUR" in line.upper():
            result["metadata_dokumen"]["penerbit"] = "Kementerian PANRB"
        if "DEPUTI BIDANG KELEMBAGAAN" in line.upper():
            result["metadata_dokumen"]["deputi"] = "Deputi Bidang Kelembagaan dan Tata Laksana"
            
    # Fallback metadata if missing (since OCR might miss the cover page)
    if not result["metadata_dokumen"]["penerbit"]:
        result["metadata_dokumen"]["penerbit"] = "Kementerian PANRB"
    if not result["metadata_dokumen"]["deputi"]:
        result["metadata_dokumen"]["deputi"] = "Deputi Bidang Kelembagaan dan Tata Laksana"
    if not result["metadata_dokumen"]["tahun_evaluasi"]:
        m_filename_year = re.search(r"SPBE_(\d{4})", filename, re.IGNORECASE)
        if m_filename_year:
            result["metadata_dokumen"]["tahun_evaluasi"] = m_filename_year.group(1)
            
    # Clean up text lines, ignore page numbers
    lines = [l.strip() for l in text.split('\n') if l.strip() and not re.match(r"^\d+\s*\|$", l.strip())] 
    
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # --- Detecting Ringkasan / Kesimpulan ---
        if re.search(r"^Kesimpulan\s*$", line, re.IGNORECASE):
            j = i + 1
            kesimpulan_lines = []
            while j < len(lines) and not re.search(r"^Tindak Lanjut", lines[j], re.IGNORECASE) and not re.search(r"^Tabel", lines[j], re.IGNORECASE):
                if lines[j]:
                    kesimpulan_lines.append(lines[j])
                j += 1
                
            if kesimpulan_lines:
                result["ringkasan_eksekutif"].append({
                    "topik": "Kesimpulan Evaluasi",
                    "isi": " ".join(kesimpulan_lines)
                })
            i = j
            continue
            
        # --- Detecting Rekomendasi ---
        if re.search(r"^Tindak Lanjut dan Rekomendasi\s*$", line, re.IGNORECASE):
            j = i + 1
            current_poin = None
            current_tindakan = []
            
            while j < len(lines) and not re.search(r"^Tabel \d+", lines[j], re.IGNORECASE) and not re.search(r"^Mendukung Arah Transformasi", lines[j], re.IGNORECASE):
                l = lines[j]
                m_judul = re.match(r"^(\d+)\.\s+(.*)", l)
                if m_judul:
                    if current_poin:
                        current_poin["tindakan"] = current_tindakan
                        result["rekomendasi_strategis"].append(current_poin)
                    current_poin = {
                        "poin_ke": int(m_judul.group(1)),
                        "judul": re.sub(r":$", "", m_judul.group(2)).strip(),
                        "tindakan": []
                    }
                    current_tindakan = []
                elif l.startswith("●") or l.startswith("-"):
                    tindakan_text = l.lstrip("●- ").strip()
                    while j + 1 < len(lines) and not re.match(r"^(?:\d+\.|●|-)", lines[j+1]) and lines[j+1]:
                        tindakan_text += " " + lines[j+1].strip()
                        j += 1
                    current_tindakan.append(tindakan_text)
                j += 1
                
            if current_poin:
                current_poin["tindakan"] = current_tindakan
                result["rekomendasi_strategis"].append(current_poin)
            i = j
            continue
            
        # --- Detecting Table Data ---
        if i + 7 < len(lines):
            try:
                val1 = lines[i].replace(',', '.')
                val2 = lines[i+1].replace(',', '.')
                val3 = lines[i+2].replace(',', '.')
                val4 = lines[i+3].replace(',', '.')
                val5 = lines[i+4].replace(',', '.')
                
                if (val1.replace('.', '', 1).isdigit() and 
                    val2.replace('.', '', 1).isdigit() and
                    val3.replace('.', '', 1).isdigit() and
                    val4.replace('.', '', 1).isdigit() and
                    val5.replace('.', '', 1).isdigit()):
                    
                    predikat = lines[i+5]
                    nomor_urut = lines[i+6]
                    nama_instansi = lines[i+7]
                    
                    if predikat in ["Sangat Baik", "Baik", "Cukup", "Kurang", "Sangat Kurang"] and nomor_urut.isdigit():
                        jenis = "Kementerian"
                        if "Kab." in nama_instansi or "Kabupaten" in nama_instansi: jenis = "Pemerintah Kabupaten"
                        elif "Kota" in nama_instansi: jenis = "Pemerintah Kota"
                        elif "Provinsi" in nama_instansi: jenis = "Pemerintah Provinsi"
                        
                        wilayah = "Nasional"
                        
                        # Grab next line if it completes the name
                        if i + 8 < len(lines) and not lines[i+8].replace(',', '.').replace('.', '', 1).isdigit():
                            if not re.search(r"^(Kesimpulan|Tabel|Tindak Lanjut|No)", lines[i+8], re.IGNORECASE):
                                nama_instansi += " " + lines[i+8]
                        
                        result["data_capaian_instansi"].append({
                            "nama_instansi": nama_instansi.strip(),
                            "jenis_instansi": jenis,
                            "kategori_wilayah": wilayah,
                            "skor_domain": {
                                "kebijakan_internal": float(val1),
                                "tata_kelola": float(val2),
                                "manajemen_spbe": float(val3),
                                "layanan_spbe": float(val4)
                            },
                            "indeks_spbe_akhir": float(val5),
                            "predikat": predikat
                        })
                        i += 7
            except ValueError:
                pass

        i += 1
        
    return result

def parse_laporan(text: str, metadata: Optional[Dict] = None, filename: str = "") -> Dict[str, Any]:
    """Parse report/audit text into structured JSON."""
    result: Dict[str, Any] = {
        "type": "laporan",
        "judul": (metadata or {}).get("judul", ""),
        "source_filename": filename,
        "sections": [],
    }

    first_lines = text[:300].split("\n")
    for line in first_lines:
        line = line.strip()
        if not result["judul"] and len(line) > 10 and not line.startswith("#"):
            result["judul"] = line
            break

    lines = text.split("\n")
    current_section: Optional[Dict] = None
    current_paragraphs: List[str] = []
    current_para: List[str] = []

    def flush_para():
        nonlocal current_para
        text_block = "\n".join(current_para).strip()
        if text_block:
            current_paragraphs.append(text_block)
        current_para = []

    def flush_section():
        nonlocal current_paragraphs
        flush_para()
        if current_section is not None and current_paragraphs:
            current_section["paragraphs"] = current_paragraphs
        current_paragraphs = []

    for line in lines:
        stripped = line.strip()

        m_heading = _RE_HEADING.match(stripped)
        m_section = _RE_SECTION_HEADING.match(stripped)

        if m_heading or m_section:
            flush_section()
            heading_text = m_heading.group(2) if m_heading else stripped
            level = len(m_heading.group(1)) if m_heading else 1
            current_section = {
                "heading": heading_text.strip(),
                "level": level,
                "paragraphs": [],
            }
            result["sections"].append(current_section)
            continue

        if not stripped:
            flush_para()
            continue

        current_para.append(line)

    flush_section()

    if not result["sections"] and current_paragraphs:
        result["sections"].append({
            "heading": result.get("judul", "Dokumen"),
            "level": 1,
            "paragraphs": current_paragraphs,
        })

    flush_para()
    if current_paragraphs:
        if result["sections"]:
            result["sections"][-1]["paragraphs"].extend(current_paragraphs)
        else:
            result["sections"].append({
                "heading": result.get("judul", "Dokumen"),
                "level": 1,
                "paragraphs": current_paragraphs,
            })

    return result


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_pedoman(text: str, filename: str = "") -> dict:
    result = {
        "metadata_dokumen": {
            "jenis_peraturan": "Pedoman",
            "nomor": "",
            "tahun": "",
            "tentang": "",
            "status": ""
        },
        "narasi_pedoman": [],
        "instrumen_indikator": [],
        "type": "pedoman_spbe"
    }
    
    # Clean footer
    text = re.sub(r"-\d+-\s+jdih\.menpan\.go\.id", "", text, flags=re.IGNORECASE)
    
    first_lines = text[:1000].split('\n')
    for idx, line in enumerate(first_lines):
        line = line.strip()
        m_no = re.search(r"NOMOR\s+(\d+)\s+TAHUN\s+(\d+)", line, re.IGNORECASE)
        if m_no and not result["metadata_dokumen"]["nomor"]:
            result["metadata_dokumen"]["nomor"] = m_no.group(1)
            result["metadata_dokumen"]["tahun"] = m_no.group(2)
        if line.upper() == "TENTANG" and idx + 1 < len(first_lines):
            result["metadata_dokumen"]["tentang"] = first_lines[idx+1].strip()
        if re.search(r"Mencabut.*", line, re.IGNORECASE):
            result["metadata_dokumen"]["status"] = line
            
    if not result["metadata_dokumen"]["status"]:
        result["metadata_dokumen"]["status"] = "Berlaku"

    babs = re.finditer(r"^BAB\s+([IVXLCDM]+)\s*\n+(.*?)(?=\n^BAB\s+[IVXLCDM]+|\n^I\.\s*\nDOMAIN|\Z)", text, re.MULTILINE | re.IGNORECASE | re.DOTALL)
    for b in babs:
        bab_no = b.group(1).upper()
        bab_content = b.group(2).strip()
        content_lines = bab_content.split('\n')
        bab_judul = content_lines[0].strip()
        bab_body = "\n".join(content_lines[1:])
        
        current_bab = {"bab_nomor": bab_no, "bab_judul": bab_judul, "sub_bab": []}
        
        sub_matches = list(re.finditer(r"^([A-Z])\.\s+(.*?)\n(.*?)(?=\n^[A-Z]\.\s+|\Z)", bab_body, re.MULTILINE | re.DOTALL))
        if sub_matches:
            for s in sub_matches:
                current_bab["sub_bab"].append({
                    "huruf": s.group(1),
                    "judul": s.group(2).strip(),
                    "isi_teks": re.sub(r"\n+", " ", s.group(3)).strip()
                })
        else:
             current_bab["sub_bab"].append({
                "huruf": "",
                "judul": "Umum",
                "isi_teks": re.sub(r"\n+", " ", bab_body).strip()
             })
        result["narasi_pedoman"].append(current_bab)
        
    bab3_match = re.search(r"^BAB III\s+", text, re.MULTILINE | re.IGNORECASE)
    text_for_indicators = text[:bab3_match.start()] if bab3_match else text

    ind_blocks = re.split(r"^INDIKATOR\s+\d+", text_for_indicators, flags=re.MULTILINE)
    for i, block in enumerate(ind_blocks[1:], 1):
        ind = {"domain": "", "indikator_nomor": i, "indikator_nama": "", "deskripsi": "", "kriteria_level": {}, "kriteria_bukti_dukung": {}}
        
        m_nama = re.search(r"ID-\d+\s*\n(.*?)(?=\nDeskripsi Indikator|$)", block, re.DOTALL | re.IGNORECASE)
        if m_nama: ind["indikator_nama"] = m_nama.group(1).replace('\n', ' ').strip()
            
        m_desk = re.search(r"Deskripsi Indikator.*?:(.*?)(?=\nKetentuan Penilaian|\nLevel 1|$)", block, re.DOTALL | re.IGNORECASE)
        if m_desk: ind["deskripsi"] = m_desk.group(1).replace('\n', ' ').strip()
            
        for level in range(1, 6):
            m_krit = re.search(rf"Level {level}.*?Kriteria Level(.*?)(?=Kriteria pemenuhan|Kriteria Bukti Dukung|Level {level+1}|$)", block, re.DOTALL | re.IGNORECASE)
            if m_krit: ind["kriteria_level"][str(level)] = m_krit.group(1).replace('\n', ' ').strip()
                
            m_bukti = re.search(rf"Level {level}.*?Kriteria Bukti Dukung(.*?)(?=Level {level+1}|$)", block, re.DOTALL | re.IGNORECASE)
            if m_bukti: ind["kriteria_bukti_dukung"][str(level)] = m_bukti.group(1).replace('\n', ' ').strip()

        if "Arsitektur" in ind["indikator_nama"] or "Peta Rencana" in ind["indikator_nama"]: ind["domain"] = "Kebijakan SPBE"
        elif "Tata Kelola" in block[:500]: ind["domain"] = "Tata Kelola SPBE"
        elif "Manajemen" in block[:500]: ind["domain"] = "Manajemen SPBE"
        elif "Layanan" in block[:500]: ind["domain"] = "Layanan SPBE"
        else: ind["domain"] = "Kebijakan SPBE"
        result["instrumen_indikator"].append(ind)

    return result

def detect_doc_type(text: str, filename: str = "", folder_hint: str = "") -> str:
    """Auto-detect document type from text content or filename."""
    lower_text = text[:2000].lower()
    lower_name = filename.lower()

    if "pedoman" in lower_name and "aparatur" in lower_name and "reformasi" in lower_name:
        return "pedoman_spbe"

    if "evaluasi spbe" in lower_name or "evaluasi_spbe" in lower_name:
        return "laporan_spbe"

    if folder_hint:
        return folder_hint

    if any(kw in lower_name for kw in ["perpres", "permen", "peraturan", "bssn", "uu_", "pp_"]):
        return "peraturan"
    if re.search(r"pasal\s+\d+", lower_text) and re.search(r"bab\s+[ivxlcdm]+", lower_text):
        return "peraturan"

    if any(kw in lower_name for kw in ["laporan", "evaluasi", "audit", "hasil"]):
        return "laporan"

    pasal_count = len(re.findall(r"pasal\s+\d+", lower_text, re.IGNORECASE))
    if pasal_count >= 3:
        return "peraturan"

    return "laporan"



def parse_document(
    text: str,
    filename: str = "",
    doc_type: Optional[str] = None,
    folder_hint: str = "",
    metadata: Optional[Dict] = None,
) -> Dict[str, Any]:
    cleaned = clean_text(text)
    dtype = doc_type or detect_doc_type(cleaned, filename, folder_hint)

    logger.info(f"Parsing document as '{dtype}': {filename}")

    if dtype == "peraturan":
        result = parse_peraturan(cleaned, metadata, filename)
    elif dtype == "laporan_spbe":
        result = parse_laporan_spbe(cleaned, metadata, filename)
    elif dtype == "pedoman_spbe":
        result = parse_pedoman(cleaned, filename)
    else:
        result = parse_laporan(cleaned, metadata, filename)

    result["source_filename"] = filename

    return result


def document_to_json(
    text: str,
    filename: str = "",
    doc_type: Optional[str] = None,
    folder_hint: str = "",
    metadata: Optional[Dict] = None,
) -> str:
    structure = parse_document(text, filename, doc_type, folder_hint, metadata)
    return json.dumps(structure, ensure_ascii=False, indent=2)
