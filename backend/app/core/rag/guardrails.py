import re
from typing import List

def extract_guardrail_focus_terms(query: str, max_terms: int = 8) -> List[str]:
    """Extract concise focus terms from query for generic grounding guardrails."""
    stopwords = {
        "yang", "dan", "atau", "dari", "pada", "untuk", "dalam", "dengan", "apa",
        "siapa", "bagaimana", "kapan", "dimana", "jelaskan", "sebutkan", "tolong",
        "berdasarkan", "peraturan", "tentang", "isi", "dokumen",
    }

    tokens = re.findall(r"[a-zA-Z0-9]{2,}", str(query or "").lower())
    focus_terms: List[str] = []

    for token in tokens:
        if token in stopwords: continue
        if token.isdigit() and len(token) < 2: continue
        if not token.isdigit() and len(token) < 3: continue
        if token not in focus_terms:
            focus_terms.append(token)
        if len(focus_terms) >= max_terms: break

    return focus_terms

def build_table_guardrail(query: str, context: str) -> str:
    """Build dynamic instruction so table queries do not collapse to false negatives."""
    q = str(query or "")
    c = str(context or "")
    table_match = re.search(r"\b(?:tabel|table)\s*(?:ke[-\s]*)?(\d{1,3})\b", q, re.IGNORECASE)
    if not table_match:
        return ""

    table_no = table_match.group(1)
    table_pattern = re.compile(
        rf"\b(?:tabel|table)\s*(?:ke[-\s]*)?{re.escape(table_no)}\b",
        re.IGNORECASE,
    )
    if not table_pattern.search(c):
        return ""

    return (
        f"Instruksi tambahan pertanyaan tabel: konteks memuat Tabel {table_no}. "
        f"Wajib jawab menggunakan isi Tabel {table_no} yang tersedia di konteks, sertakan sitasi [n], "
        "dan jangan menyatakan 'tidak ditemukan' untuk Tabel tersebut. "
        "Jika isi tabel yang tersedia benar-benar parsial, nyatakan jawaban berdasar bagian yang tersedia saja."
    )

def build_generic_grounding_guardrail(query: str, context: str) -> str:
    """Build query-agnostic grounding instruction to reduce generic false-negative claims."""
    q = str(query or "")
    c = str(context or "")
    c_lower = c.lower()

    if not q.strip() or not c.strip():
        return ""

    focus_terms = extract_guardrail_focus_terms(q)
    anchored_terms = [
        term for term in focus_terms if re.search(rf"\b{re.escape(term)}\b", c_lower)
    ]

    if not anchored_terms:
        return ""

    instructions = [
        "Instruksi tambahan kualitas jawaban:",
        "- Gunakan hanya fakta yang ada pada konteks referensi.",
        "- Fokus pada inti pertanyaan, jangan melebar ke topik lain.",
        "- Jangan menyatakan informasi 'tidak ditemukan/tidak tersedia' jika istilah kunci terlihat di konteks;"
        " jelaskan bagian yang tersedia secara faktual.",
        "- Pastikan poin informatif memiliki sitasi [n].",
        "- Istilah kunci yang wajib dicakup bila tersedia: " + ", ".join(anchored_terms[:8]) + ".",
    ]

    if re.search(
        r"\b(?:apa saja|sebutkan|daftar|rincian|langkah|tahap|komponen|indikator)\b",
        q, re.IGNORECASE
    ):
        instructions.append(
            "- Karena pertanyaan meminta rincian, tulis butir utama secara lengkap dalam format daftar."
        )

    return "\n".join(instructions)

def build_quality_guardrail(query: str, context: str) -> str:
    """Combine generic and specialized guardrails."""
    parts: List[str] = []

    generic = build_generic_grounding_guardrail(query, context)
    if generic: parts.append(generic)

    table = build_table_guardrail(query, context)
    if table: parts.append(table)

    return "\n\n".join(parts)
