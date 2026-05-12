import re
from typing import Dict, Any, Optional

def clean_title_text(value: str) -> str:
    """Normalize title-like text for consistent source rendering."""
    text = str(value or "").strip()
    if not text:
        return ""
    text = re.sub(r"\.pdf$", "", text, flags=re.IGNORECASE)
    text = text.replace("_", " ")
    text = re.sub(r"\s+", " ", text).strip(" -")
    return text

def detect_regulation_type(text: str) -> str:
    """Detect high-level doc type to resolve conflicting metadata titles."""
    t = str(text or "").lower()
    if "peraturan presiden" in t or re.search(r"\bperpres\b", t):
        return "perpres"
    if "peraturan menteri" in t or "permenpan" in t or re.search(r"\bpermen\b", t):
        return "permen"
    if "peraturan pemerintah" in t or re.search(r"\bpp\b", t):
        return "pp"
    if "pedoman" in t:
        return "pedoman"
    if "laporan" in t:
        return "laporan"
    return ""

def is_suspicious_title(title: str) -> bool:
    """Identify malformed extracted titles such as 'tentang 59 Tahun 2020'."""
    t = str(title or "").lower()
    if not t:
        return True
    if re.search(r"\btentang\s+\d+\s+tahun\s+\d{4}\b", t):
        return True
    if t.count("tahun") >= 2 and re.search(
        r"\bnomor\s+\d+.*\btahun\s+\d{4}.*\btahun\s+\d{4}\b", t
    ):
        return True
    return False

def normalize_document_title(metadata: Dict[str, Any]) -> str:
    """Choose the most reliable document title between metadata fields and filename."""
    meta = metadata or {}
    raw_title = (
        meta.get("document_title")
        or meta.get("judul_dokumen")
        or meta.get("tentang")
        or ""
    )
    raw_filename = meta.get("filename") or ""

    title = clean_title_text(raw_title)
    filename_title = clean_title_text(raw_filename)

    if not title:
        return filename_title or "Dokumen"
    if not filename_title:
        return title

    title_type = detect_regulation_type(title)
    file_type = detect_regulation_type(filename_title)

    if title_type and file_type and title_type != file_type:
        return filename_title
    if is_suspicious_title(title):
        return filename_title
    if len(title) < 12 and len(filename_title) > len(title):
        return filename_title

    return title

def clean_about_text(value: str) -> str:
    """Normalize about/subject phrase used in legal document cover titles."""
    text = clean_title_text(value)
    if not text:
        return ""
    text = re.sub(r"^(?i:tentang)\s+", "", text).strip()
    text = re.sub(r"\s+", " ", text)

    if text.isupper() and len(text) > 6:
        text = text.title()
        text = re.sub(r"\bSpbe\b", "SPBE", text)
        text = re.sub(r"\bTik\b", "TIK", text)
        text = re.sub(r"\bBssn\b", "BSSN", text)
        text = re.sub(r"\bPan\s*Rb\b", "PAN RB", text)

    return text.strip(" -")

def build_cover_citation_title(metadata: Dict[str, Any]) -> str:
    """Build a fuller citation title aligned with document cover style when possible."""
    meta = metadata or {}
    base_title = normalize_document_title(meta)
    about_text = clean_about_text(str(meta.get("tentang") or ""))

    if not about_text:
        return base_title
    if is_suspicious_title(about_text):
        return base_title

    base_lower = base_title.lower()
    about_lower = about_text.lower()

    if about_lower in base_lower:
        return base_title
    if "tentang" in base_lower:
        return base_title
    if base_title == "Dokumen":
        return about_text

    return f"{base_title} tentang {about_text}"
