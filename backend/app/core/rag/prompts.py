"""
Prompt Templates for SPBE RAG System - Indonesian Legal Documents
Enhanced with strict grounding rules for legal accuracy

Quality Focus:
- Faithfulness: Strict grounding to source documents
- Precision: No hallucinating Pasal/Ayat numbers
- Complete Lists: Always cite full a, b, c, d lists
- Citation Tracking: Every claim must be cited
"""

from typing import List, Dict, Optional
import re


# =============================================================================
# SYSTEM PROMPTS - Strict Legal Document Grounding
# =============================================================================

SYSTEM_PROMPT_LEGAL = """Anda adalah asisten ahli hukum SPBE di BSSN. Tugas Anda adalah menjawab pertanyaan berdasarkan konteks dokumen yang diberikan.

ATURAN KETAT:

1. JANGAN PERNAH mengarang nomor Pasal atau Ayat. Jika konteks tidak memiliki nomor ayat, JANGAN tulis 'ayat (1)'.

2. Selalu sebutkan Pasal dan Ayat sumber referensi di akhir kalimat dengan format [1], [2], [3].

3. Jika jawaban berupa daftar (list) seperti a, b, c, d, pastikan Anda mengambil SELURUH daftar tersebut. JANGAN berhenti di tengah.

4. Jika informasi tidak ada dalam konteks, katakan: "Informasi tersebut tidak ditemukan dalam dokumen yang tersedia."

5. Gunakan gaya bahasa formal pemerintahan Indonesia.

6. Kutip teks PERSIS seperti yang tertulis dalam dokumen untuk nomor Pasal, Ayat, dan daftar huruf.

PENGETAHUAN STRUKTUR EVALUASI SPBE:
Struktur penilaian SPBE memiliki hierarki yang WAJIB dibedakan:
- DOMAIN (4 total): area penerapan SPBE yang dinilai.
  Domain 1: Kebijakan Internal SPBE, Domain 2: Tata Kelola SPBE, Domain 3: Manajemen SPBE, Domain 4: Layanan SPBE.
- ASPEK (8 total): area SPESIFIK penerapan SPBE di dalam domain.
  Aspek 1: Kebijakan Internal Tata Kelola SPBE (Domain 1),
  Aspek 2: Perencanaan Strategis SPBE (Domain 2),
  Aspek 3: Teknologi Informasi dan Komunikasi (Domain 2),
  Aspek 4: Penyelenggara SPBE (Domain 2),
  Aspek 5: Penerapan Manajemen SPBE (Domain 3),
  Aspek 6: Pelaksanaan Audit TIK (Domain 3),
  Aspek 7: Layanan Administrasi Pemerintahan Berbasis Elektronik (Domain 4),
  Aspek 8: Layanan Publik Berbasis Elektronik (Domain 4).
- INDIKATOR (47 total): informasi SPESIFIK dari aspek yang dinilai (Indikator 1 s.d. 47).

ATURAN HIERARKI:
- JANGAN PERNAH menyebut indikator sebagai aspek atau sebaliknya.
- Jika ditanya tentang "aspek", jawab dengan 8 ASPEK, BUKAN indikator.
- Jika ditanya tentang "indikator", jawab dengan INDIKATOR, BUKAN aspek.
- Jika ditanya tentang "domain", jawab dengan 4 DOMAIN.
- Selalu jelaskan hubungan hierarki: Domain > Aspek > Indikator.

PEMBEDAAN KETENTUAN ADMINISTRATIF VS SUBSTANTIF:
- Jika ditanya tentang "ruang lingkup", "cakupan", atau "objek" suatu audit/kegiatan, jawab dengan SUBSTANSI (apa yang diaudit/dilakukan), BUKAN ketentuan administratif (surat tugas, nama auditor, jabatan).
- Ketentuan tentang isi surat penugasan (nama auditor, jabatan, nama instansi) adalah ADMINISTRATIF, bukan ruang lingkup substantif.
- Ruang lingkup substantif biasanya ada di pasal-pasal awal (objek, standar, kriteria, prosedur).

FORMAT JAWABAN:
- Mulai dengan ringkasan singkat
- Jelaskan detail dengan referensi [1], [2], [3]
- Jika ada daftar, tulis lengkap semua butir"""


SYSTEM_PROMPT_SPBE = """Anda adalah asisten hukum Indonesia yang membantu menjawab pertanyaan tentang regulasi SPBE berdasarkan dokumen yang diberikan.

ATURAN WAJIB:
1. HANYA jawab berdasarkan dokumen yang diberikan
2. JANGAN mengarang Pasal atau Ayat yang tidak ada dalam konteks
3. Sertakan referensi [1], [2], [3] di setiap kalimat yang mengandung informasi dari dokumen
4. Jika ada daftar (a, b, c, d...), tulis LENGKAP semua butir
5. Jika informasi tidak ada, katakan "tidak ditemukan dalam dokumen"

PANDUAN:
- Gunakan bahasa Indonesia formal
- Kutip pasal/ayat PERSIS seperti dalam dokumen
- Format: "Berdasarkan Pasal X [1], ..." atau "Menurut dokumen [2], ..."

PENGETAHUAN STRUKTUR EVALUASI SPBE:
Struktur penilaian tingkat kematangan SPBE memiliki hierarki:
- DOMAIN (4): Kebijakan Internal SPBE, Tata Kelola SPBE, Manajemen SPBE, Layanan SPBE.
- ASPEK (8): Kebijakan Internal Tata Kelola SPBE, Perencanaan Strategis SPBE, Teknologi Informasi dan Komunikasi, Penyelenggara SPBE, Penerapan Manajemen SPBE, Pelaksanaan Audit TIK, Layanan Administrasi Pemerintahan Berbasis Elektronik, Layanan Publik Berbasis Elektronik.
- INDIKATOR (47): ukuran spesifik di dalam setiap aspek (Indikator 1 s.d. 47).

PEMBEDAAN KETENTUAN ADMINISTRATIF VS SUBSTANTIF:
- Jika ditanya "ruang lingkup" atau "objek" audit/kegiatan, jawab dengan SUBSTANSI (apa yang diaudit), BUKAN administratif (surat tugas, nama auditor).
- Ruang lingkup substantif biasanya di pasal-pasal awal tentang objek, standar, kriteria, dan prosedur.
ATURAN: JANGAN mencampurkan level hierarki. Indikator BUKAN aspek. Aspek BUKAN domain.

CATATAN: Akurasi lebih penting dari kelengkapan. Lebih baik menjawab sebagian dengan benar daripada lengkap tapi salah."""


SYSTEM_PROMPT_STRICT = """Jawab pertanyaan HANYA berdasarkan dokumen yang diberikan.

ATURAN:
- Sertakan [1], [2], [3] di setiap kalimat
- JANGAN mengarang Pasal/Ayat
- Tulis daftar LENGKAP (a sampai z jika ada)
- Jika tidak ada di dokumen, katakan "tidak ditemukan"

Jawab dalam bahasa Indonesia formal."""


# =============================================================================
# CONTEXT FORMATTING - Enhanced with Parent Document Context
# =============================================================================


def format_context(
    chunks: List[Dict],
    max_chars: int = 8000,
    include_parent: bool = True,
) -> str:
    """
    Format retrieved chunks into context string with citations.

    Enhanced to include parent Pasal context when available.

    Args:
        chunks: List of retrieved chunks with text and metadata
        max_chars: Maximum characters for context
        include_parent: Whether to include parent Pasal text

    Returns:
        Formatted context string with citation numbers
    """
    context_parts = []
    total_chars = 0
    seen_pasals = set()  # Track Pasals to avoid duplicate parent context

    for i, chunk in enumerate(chunks, 1):
        text = chunk.get("text", "")
        metadata = chunk.get("metadata", {})

        # Get context header if available (from new legal splitter)
        context_header = metadata.get("context_header", "")

        # Build source label
        if context_header:
            source_label = context_header
        else:
            doc_type = metadata.get("doc_type", "")
            source_label = _build_source_label(metadata, doc_type)

        # Format chunk with citation number
        chunk_text = f"[{i}] SUMBER: {source_label}\n{text}\n---"

        # Add parent Pasal context if available and not already included
        parent_text = metadata.get("parent_pasal_text", "")
        pasal = metadata.get("pasal", "")

        if include_parent and parent_text and pasal and pasal not in seen_pasals:
            # Add parent context for better completeness
            parent_context = f"\n[Konteks Lengkap {pasal}]:\n{parent_text}\n"
            if (
                total_chars + len(parent_context) < max_chars * 0.7
            ):  # Use 70% for parent
                chunk_text = parent_context + chunk_text
                seen_pasals.add(pasal)

        # Check if we exceed max chars
        if total_chars + len(chunk_text) > max_chars:
            remaining = max_chars - total_chars - 50
            if remaining > 200:
                chunk_text = chunk_text[:remaining] + "...\n---"
                context_parts.append(chunk_text)
            break

        context_parts.append(chunk_text)
        total_chars += len(chunk_text) + 2

    return "\n\n".join(context_parts)


def _build_source_label(metadata: Dict, doc_type: str) -> str:
    """Build human-readable source label from metadata."""
    # Use document_title if available (from legal splitter)
    doc_title = metadata.get("document_title", "")

    if doc_title:
        parts = [doc_title]
        if metadata.get("bab"):
            parts.append(metadata["bab"])
        if metadata.get("pasal"):
            parts.append(metadata["pasal"])
        if metadata.get("ayat"):
            parts.append(f"Ayat ({metadata['ayat']})")
        return " > ".join(parts)

    # Fallback: Use filename
    filename = metadata.get("filename", "")
    if filename:
        source_label = (
            filename.replace(".pdf", "").replace("_", " ").replace("-", " ").strip()
        )

        if metadata.get("pasal"):
            pasal_info = f"Pasal {metadata['pasal']}"
            if metadata.get("ayat"):
                pasal_info += f" Ayat ({metadata['ayat']})"
            source_label = f"{source_label}, {pasal_info}"

        return source_label

    # Last resort
    return metadata.get("tentang", "Dokumen")


# =============================================================================
# RAG PROMPT BUILDER - Optimized for Legal Q&A
# =============================================================================


def build_rag_prompt(
    query: str,
    context: str,
    system_prompt: Optional[str] = None,
    chat_history: Optional[List[Dict]] = None,
    model_type: str = "qwen",
) -> str:
    """
    Build complete RAG prompt for legal document Q&A.

    Uses stricter prompting for accuracy.

    Args:
        query: User question
        context: Formatted context from documents
        system_prompt: Override system prompt
        chat_history: Previous conversation messages
        model_type: Model family (qwen, llama, etc.)

    Returns:
        Complete prompt string
    """
    system = system_prompt or SYSTEM_PROMPT_LEGAL

    # Build user message with explicit instructions
    user_message = f"""DOKUMEN REFERENSI:

{context}

PERTANYAAN: {query}

INSTRUKSI:
1. Jawab berdasarkan dokumen di atas
2. Sertakan referensi [1], [2], [3] di setiap kalimat
3. Jika ada daftar (a, b, c...), tulis LENGKAP
4. JANGAN mengarang Pasal/Ayat yang tidak ada di dokumen

JAWABAN:"""

    # Format based on model type
    if model_type == "qwen":
        prompt = f"<|im_start|>system\n{system}<|im_end|>\n"

        if chat_history:
            for msg in chat_history[-4:]:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                prompt += f"<|im_start|>{role}\n{content}<|im_end|>\n"

        prompt += f"<|im_start|>user\n{user_message}<|im_end|>\n"
        prompt += "<|im_start|>assistant\n"
    else:
        # Generic format
        prompt = f"{system}\n\n{user_message}\n"
        if chat_history:
            for msg in chat_history[-4:]:
                prompt = (
                    f"{msg.get('role', 'user')}: {msg.get('content', '')}\n" + prompt
                )

    return prompt


def build_simple_prompt(query: str, context: str) -> str:
    """
    Build simpler prompt without chat format.
    Maintains strict grounding rules.
    """
    return f"""DOKUMEN REFERENSI:
{context}

PERTANYAAN: {query}

INSTRUKSI KETAT:
- Jawab HANYA berdasarkan dokumen di atas
- Sertakan referensi [1], [2] di setiap kalimat
- Jika ada daftar (a, b, c...), tulis LENGKAP semua butir
- JANGAN mengarang Pasal atau Ayat
- Jika informasi tidak ada, katakan "Tidak ditemukan dalam dokumen"

JAWABAN:"""


# =============================================================================
# SOURCE EXTRACTION - Enhanced for Legal Documents
# =============================================================================


def extract_sources(chunks: List[Dict]) -> List[Dict]:
    """
    Extract source information from chunks for citation display.
    Enhanced for legal document structure.
    """
    sources = []

    for i, chunk in enumerate(chunks, 1):
        metadata = chunk.get("metadata", {})

        # Get document name
        doc_name = (
            metadata.get("document_title")
            or metadata.get("filename", "").replace(".pdf", "").replace("_", " ")
            or metadata.get("tentang", "Dokumen")
        )

        # Build section info
        section_parts = []
        if metadata.get("bab"):
            section_parts.append(metadata["bab"])
        if metadata.get("pasal"):
            section_parts.append(metadata["pasal"])
        if metadata.get("ayat"):
            section_parts.append(f"Ayat ({metadata['ayat']})")

        section = " > ".join(section_parts) if section_parts else ""

        source = {
            "id": i,
            "document": doc_name,
            "doc_type": metadata.get("doc_type", ""),
            "section": section,
            "score": chunk.get("score", 0),
            # Additional legal metadata
            "pasal": metadata.get("pasal", ""),
            "ayat": metadata.get("ayat", ""),
            "bab": metadata.get("bab", ""),
        }

        sources.append(source)

    return sources


# =============================================================================
# QUERY EXPANSION - Enhanced for Legal Terms
# =============================================================================


def expand_query(query: str) -> List[str]:
    """
    Expand query with variations for better recall.
    Enhanced with legal terminology.
    """
    queries = [query]
    query_lower = query.lower()

    # Legal term expansions
    expansions = {
        "spbe": ["sistem pemerintahan berbasis elektronik", "e-government"],
        "tik": ["teknologi informasi dan komunikasi"],
        "audit": ["pemeriksaan", "evaluasi", "penilaian"],
        "keamanan": ["keamanan informasi", "keamanan siber", "security"],
        "bssn": ["badan siber dan sandi negara"],
        "ippd": ["instansi pusat dan pemerintah daerah"],
        "pasal": ["ketentuan", "aturan"],
        "peraturan": ["regulasi", "kebijakan"],
        "domain": ["domain penilaian SPBE", "area penerapan SPBE"],
        "aspek": ["aspek penilaian SPBE", "aspek evaluasi SPBE"],
        "indikator": ["indikator penilaian SPBE", "indikator evaluasi SPBE"],
        "struktur": ["struktur penilaian", "hierarki penilaian"],
        "pemantauan": ["pemantauan dan evaluasi", "monitoring evaluasi SPBE"],
        "arsitektur": ["rancangan", "desain", "struktur"],
        "ruang lingkup": ["objek", "cakupan", "standar", "prosedur"],
        "cakupan": ["ruang lingkup", "objek", "lingkup"],
        "mandat": ["tugas", "wewenang", "kewenangan", "tanggung jawab"],
    }

    for term, alternatives in expansions.items():
        if term in query_lower:
            for alt in alternatives[:2]:  # Limit to 2 alternatives per term
                expanded = query_lower.replace(term, alt)
                if expanded not in queries:
                    queries.append(expanded)

    # Add keyword-only version for BM25
    keywords = re.findall(r"\b\w{4,}\b", query_lower)  # Words 4+ chars
    if keywords:
        keyword_query = " ".join(keywords)
        if keyword_query not in queries:
            queries.append(keyword_query)

    return queries[:4]  # Limit to 4 variations


# =============================================================================
# ANSWER VALIDATION - Enhanced for Legal Accuracy
# =============================================================================


def validate_answer(answer: str, context: str) -> Dict:
    """
    Validate that answer is grounded in context.
    Enhanced checks for legal document accuracy.
    """
    result = {
        "is_valid": True,
        "has_citations": False,
        "warnings": [],
        "confidence": "high",
    }

    # Check for citations
    citations = re.findall(r"\[(\d+)\]", answer)
    result["has_citations"] = len(citations) > 0
    result["citation_count"] = len(citations)

    if not result["has_citations"]:
        result["warnings"].append("Jawaban tidak memiliki referensi/sitasi")
        result["confidence"] = "low"

    # Check citation numbers are valid
    context_sources = len(re.findall(r"^\[\d+\]", context, re.MULTILINE))
    for cite in citations:
        if int(cite) > context_sources:
            result["warnings"].append(
                f"Referensi [{cite}] tidak valid (hanya ada {context_sources} sumber)"
            )
            result["is_valid"] = False

    # Check for potentially hallucinated Pasal/Ayat numbers
    # Find Pasal numbers in answer
    answer_pasals = set(re.findall(r"Pasal\s+(\d+)", answer, re.IGNORECASE))
    context_pasals = set(re.findall(r"Pasal\s+(\d+)", context, re.IGNORECASE))

    hallucinated_pasals = answer_pasals - context_pasals
    if hallucinated_pasals:
        result["warnings"].append(
            f"Kemungkinan Pasal yang tidak ada di konteks: {', '.join(sorted(hallucinated_pasals))}"
        )
        result["confidence"] = "medium"

    # Check for hallucinated Ayat numbers
    answer_ayats = set(re.findall(r"[Aa]yat\s*\((\d+)\)", answer))
    context_ayats = set(re.findall(r"\((\d+)\)", context))

    hallucinated_ayats = answer_ayats - context_ayats
    if hallucinated_ayats:
        result["warnings"].append(
            f"Kemungkinan Ayat yang tidak ada di konteks: {', '.join(sorted(hallucinated_ayats))}"
        )
        result["confidence"] = "medium"

    # Check for incomplete lists
    answer_letters = set(re.findall(r"^([a-z])\.", answer, re.MULTILINE))
    if answer_letters:
        context_letters = set(re.findall(r"^([a-z])\.", context, re.MULTILINE))
        missing_letters = context_letters - answer_letters
        if missing_letters and len(missing_letters) > 0:
            result["warnings"].append(
                f"Daftar mungkin tidak lengkap. Huruf di konteks tapi tidak di jawaban: {', '.join(sorted(missing_letters))}"
            )

    # Check for hallucination phrases
    hallucination_phrases = [
        "berdasarkan pengetahuan saya",
        "menurut pengalaman",
        "pada umumnya",
        "biasanya dalam praktik",
        "secara umum diketahui",
        "menurut sumber lain",
        "di luar konteks",
        "tidak disebutkan tetapi",
    ]

    answer_lower = answer.lower()
    for phrase in hallucination_phrases:
        if phrase in answer_lower:
            result["warnings"].append(f"Kemungkinan halusinasi: '{phrase}'")
            result["is_valid"] = False
            result["confidence"] = "low"

    # Check for Domain/Aspek/Indikator hierarchy confusion
    query_lower = context.lower()  # Use context to infer question scope
    _check_spbe_hierarchy_confusion(answer_lower, result)

    return result


# =============================================================================
# SPBE HIERARCHY VALIDATION HELPER
# =============================================================================


# Known SPBE indicator names (lowercase) - these should NOT be called "aspek"
_SPBE_INDICATOR_NAMES = [
    "manajemen data",
    "pembangunan aplikasi",
    "layanan pusat data",
    "sistem penghubung layanan",
    "layanan jaringan intra",
    "manajemen keamanan informasi",
    "audit teknologi",
    "arsitektur spbe",
    "peta rencana spbe",
    "manajemen risiko",
    "manajemen aset tik",
    "kompetensi sumber daya manusia",
    "manajemen pengetahuan",
    "manajemen perubahan",
    "manajemen layanan spbe",
    "audit infrastruktur",
    "audit aplikasi",
    "audit keamanan",
    "layanan perencanaan",
    "layanan penganggaran",
    "layanan keuangan",
    "layanan pengadaan",
    "layanan kepegawaian",
    "layanan kearsipan",
    "data terbuka",
    "tim koordinasi spbe",
    "kolaborasi penerapan spbe",
    "inovasi proses bisnis",
    "keterpaduan rencana",
]

# Known SPBE aspect names (lowercase) - these should NOT be called "indikator"
_SPBE_ASPEK_NAMES = [
    "kebijakan internal tata kelola spbe",
    "perencanaan strategis spbe",
    "teknologi informasi dan komunikasi",
    "penyelenggara spbe",
    "penerapan manajemen spbe",
    "pelaksanaan audit tik",
    "layanan administrasi pemerintahan berbasis elektronik",
    "layanan publik berbasis elektronik",
]


def _check_spbe_hierarchy_confusion(answer_lower: str, result: dict) -> None:
    """
    Check if the answer confuses SPBE hierarchy levels.
    For example, presenting indicators as aspects or vice versa.
    """
    # Check if indicators are being presented as "aspek"
    indicators_as_aspek = []
    for indicator_name in _SPBE_INDICATOR_NAMES:
        if indicator_name in answer_lower:
            # Check if this indicator is being called an "aspek" nearby
            # Look for patterns like "aspek ... <indicator_name>"
            idx = answer_lower.find(indicator_name)
            # Check 200 chars before the indicator mention for "aspek"
            context_before = answer_lower[max(0, idx - 200):idx]
            if "aspek" in context_before and "indikator" not in context_before:
                indicators_as_aspek.append(indicator_name)

    if indicators_as_aspek:
        result["warnings"].append(
            f"Kemungkinan pencampuran hierarki SPBE: indikator berikut mungkin "
            f"disebut sebagai aspek: {', '.join(indicators_as_aspek[:3])}"
        )
        result["confidence"] = "medium"

    # Check if aspects are being presented as "indikator"
    aspek_as_indikator = []
    for aspek_name in _SPBE_ASPEK_NAMES:
        if aspek_name in answer_lower:
            idx = answer_lower.find(aspek_name)
            context_before = answer_lower[max(0, idx - 200):idx]
            if "indikator" in context_before and "aspek" not in context_before:
                aspek_as_indikator.append(aspek_name)

    if aspek_as_indikator:
        result["warnings"].append(
            f"Kemungkinan pencampuran hierarki SPBE: aspek berikut mungkin "
            f"disebut sebagai indikator: {', '.join(aspek_as_indikator[:3])}"
        )
        result["confidence"] = "medium"


# =============================================================================
# PARENT DOCUMENT RETRIEVAL HELPER
# =============================================================================


def get_parent_pasal_chunks(
    child_chunks: List[Dict],
    all_chunks: List[Dict],
) -> List[Dict]:
    """
    Get parent Pasal chunks for child ayat chunks.
    Implements Parent Document Retrieval strategy.

    Args:
        child_chunks: Retrieved ayat-level chunks
        all_chunks: All available chunks (or access to vector DB)

    Returns:
        Enriched chunks with parent Pasal context
    """
    enriched = []
    seen_pasals = set()

    for chunk in child_chunks:
        metadata = chunk.get("metadata", {})
        pasal = metadata.get("pasal", "")

        # Check if this is an ayat chunk that needs parent context
        if metadata.get("ayat") and pasal and pasal not in seen_pasals:
            # Find parent Pasal chunk
            parent = None
            for c in all_chunks:
                c_meta = c.get("metadata", {})
                if c_meta.get("pasal") == pasal and c_meta.get("is_parent"):
                    parent = c
                    break

            if parent:
                # Add parent context to chunk metadata
                chunk["metadata"]["parent_pasal_text"] = parent.get("text", "")
                seen_pasals.add(pasal)

        enriched.append(chunk)

    return enriched
