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

SYSTEM_PROMPT_LEGAL = """Anda adalah asisten hukum yang menjawab pertanyaan tentang pasal dan ayat dari dokumen peraturan Indonesia.

ATURAN WAJIB:
1. JANGAN PERNAH mengarang nomor Pasal atau Ayat. Jika konteks tidak memiliki nomor ayat, JANGAN tulis nomor ayat apapun.
2. Kutip teks PERSIS seperti yang tertulis dalam dokumen untuk nomor Pasal, Ayat, dan daftar huruf.
3. Sertakan referensi [n] di setiap kalimat atau poin yang bersumber dari dokumen.
4. Jika ada daftar (a, b, c, d...), tulis LENGKAP semua butir yang ada di konteks.
5. JANGAN generalisasi atau menambahkan interpretasi di luar teks dokumen.
6. Jika informasi tidak ada dalam konteks, katakan: "Informasi tersebut tidak ditemukan dalam dokumen yang tersedia."
7. Gunakan bahasa Indonesia formal pemerintahan.

FORMAT JAWABAN:
- Sebutkan nomor Pasal/Ayat sumber di awal jawaban
- Kutip isi pasal/ayat dengan referensi [n]
- Jika ada daftar huruf, sajikan lengkap dengan referensi per butir"""


SYSTEM_PROMPT_SPBE = """Anda adalah asisten hukum Indonesia yang membantu menjawab pertanyaan tentang regulasi SPBE berdasarkan dokumen yang diberikan.

ATURAN WAJIB:
1. HANYA jawab berdasarkan dokumen yang diberikan
2. JANGAN mengarang Pasal atau Ayat yang tidak ada dalam konteks
3. Sertakan referensi [1], [2], [3] di setiap kalimat yang mengandung informasi dari dokumen
4. Jika ada daftar (a, b, c, d...), tulis LENGKAP semua butir
5. Jika informasi terlihat parsial, jelaskan dulu bagian yang tersedia di konteks; hanya nyatakan keterbatasan jika benar-benar tidak ada bukti relevan
6. Jika pertanyaan menyebut "Tabel X" dan konteks memuat "Tabel X", jawab berdasarkan isi/nilai tabel tersebut
7. DILARANG menyatakan "tidak ditemukan" untuk "Tabel X" jika label "Tabel X" ada di konteks
8. Jika konteks hanya memuat sebagian tabel, jelaskan bahwa jawaban berdasarkan bagian tabel yang tersedia

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

ATURAN KHUSUS DOMAIN EVALUASI SPBE:
- Jika pertanyaan menyebut "domain evaluasi SPBE", jawab HANYA 4 domain evaluasi: Kebijakan Internal SPBE, Tata Kelola SPBE, Manajemen SPBE, dan Layanan SPBE.
- Jangan mencampur dengan domain arsitektur SPBE kecuali pertanyaan secara eksplisit meminta domain arsitektur.
ATURAN: JANGAN mencampurkan level hierarki. Indikator BUKAN aspek. Aspek BUKAN domain.

CATATAN: Akurasi lebih penting dari kelengkapan. Lebih baik menjawab sebagian dengan benar daripada lengkap tapi salah."""


SYSTEM_PROMPT_STRICT = """Jawab pertanyaan HANYA berdasarkan dokumen yang diberikan.

ATURAN:
- Sertakan [1], [2], [3] di setiap kalimat
- JANGAN mengarang Pasal/Ayat
- Tulis daftar LENGKAP (a sampai z jika ada)
- Jika tidak ada di dokumen, katakan "tidak ditemukan"

Jawab dalam bahasa Indonesia formal."""


SYSTEM_PROMPT_TABLE = """Anda adalah asisten yang membaca tabel dari dokumen pemerintah Indonesia.

ATURAN WAJIB:
1. Baca nilai tabel PERSIS seperti yang tertulis. JANGAN paraphrase atau ubah angka.
2. Sertakan SEMUA baris dan kolom yang ada di konteks. JANGAN lewati baris.
3. JANGAN mengarang nilai yang tidak tertulis di tabel.
4. Sertakan referensi [n] di setiap baris atau kelompok baris tabel.
5. Jika tabel tidak ada di konteks, katakan: "Tabel tidak ditemukan dalam dokumen yang tersedia."
6. Gunakan bahasa Indonesia formal.

FORMAT JAWABAN:
- Mulai dengan menyebut nama/judul tabel yang ditemukan
- Sajikan isi tabel dalam format yang mudah dibaca (baris per baris atau markdown table)
- Sertakan sitasi [n] di tiap baris"""


SYSTEM_PROMPT_GENERAL = """Anda adalah asisten yang menjawab pertanyaan berdasarkan dokumen pemerintah Indonesia yang diberikan.

ATURAN WAJIB:
1. HANYA jawab berdasarkan dokumen yang diberikan dalam konteks.
2. Sertakan referensi [n] di setiap kalimat yang mengandung informasi dari dokumen.
3. Jika informasi tidak ada dalam konteks, katakan: "Informasi tersebut tidak ditemukan dalam dokumen yang tersedia."
4. Gunakan bahasa Indonesia formal.
5. JANGAN menjawab dari pengetahuan umum di luar konteks yang diberikan.

FORMAT JAWABAN:
- Jawab langsung dan ringkas
- Gunakan referensi [n] konsisten"""


# =============================================================================
# CONTEXT FORMATTING
# =============================================================================

# Context formatting disatukan di:
#   LangchainRAGEngine._format_context (app/core/rag/langchain_engine.py)
# agar tidak ada multi-implementasi yang berpotensi berbeda output.


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
1. Jawab berdasarkan dokumen di atas.
2. WAJIB MENCANTUMKAN nomor referensi [1], [2], dst. di AKHIR SETIAP KALIMAT atau POIN DAFTAR. JANGAN buat paragraf atau poin tanpa sitasi misal: "...adalah SPBE [1]."
3. Jika ada daftar (a, b, c...), tulis LENGKAP.
4. JANGAN mengarang poin atau Pasal/Ayat yang tidak ada di dokumen.
5. Jika pertanyaan menyebut "Tabel X" dan konteks memuat "Tabel X", utamakan isi/nilai dari tabel tersebut dan jangan menjawab "tidak ditemukan".
6. Sebelum menyatakan keterbatasan informasi, rangkum terlebih dahulu bagian yang memang tersedia di konteks.

CONTOH FORMAT JAWABAN YANG DIHARAPKAN:
Kriteria pemenuhan tingkat kematangan 5 adalah evaluasi berkelanjutan [1]. Selain itu, bukti dukung yang harus dilampirkan meliputi:
a. Laporan Audit SPBE [2].
b. Notulensi Rapat [3].

JAWABAN DENGAN SITASI TERINTEGRASI:"""

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
- Jika pertanyaan menyebut "Tabel X" dan konteks memuat "Tabel X", jawab isi/nilai tabel tersebut
- Jika informasi parsial, jelaskan dulu bagian yang tersedia; nyatakan "tidak ditemukan" hanya bila benar-benar tidak ada bukti relevan

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


def _append_unique_query(queries: List[str], variant: str):
    """Append query variant while preserving insertion order and case-insensitive uniqueness."""
    normalized = " ".join((variant or "").split())
    if not normalized:
        return

    existing = {q.lower() for q in queries}
    if normalized.lower() not in existing:
        queries.append(normalized)


def expand_query(query: str) -> List[str]:
    """
    Expand query with conservative, non-destructive variants.

    Design goal:
    - Keep original user intent intact.
    - Avoid term substitution that can shift legal meaning.
    - Only add anchored variants that preserve the original query semantics.
    """
    normalized_query = " ".join((query or "").split())
    if not normalized_query:
        return []

    queries: List[str] = [normalized_query]
    query_lower = normalized_query.lower()

    nomor_match = re.search(r"nomor\s+(\d+)", query_lower)
    tahun_match = re.search(r"tahun\s+(\d{4})", query_lower)
    pasal_match = re.search(r"pasal\s+(\d+)", query_lower)
    table_match = re.search(r"\b(?:tabel|table)\s*(?:ke[-\s]*)?(\d{1,3})\b", query_lower)

    # Expansion by abbreviation clarification (equivalent meaning, no substitution).
    equivalent_terms = {
        "spbe": "sistem pemerintahan berbasis elektronik",
        "tik": "teknologi informasi dan komunikasi",
        "bssn": "badan siber dan sandi negara",
        "ippd": "instansi pusat dan pemerintah daerah",
    }
    for term, full_form in equivalent_terms.items():
        if re.search(rf"\b{re.escape(term)}\b", query_lower):
            _append_unique_query(queries, f"{normalized_query} {full_form}")

    # Keep explicit Pasal intent without rewriting the original question.
    if pasal_match:
        _append_unique_query(queries, f"{normalized_query} pasal {pasal_match.group(1)}")

    # Table-focused: add highly targeted literal anchors to reduce drift into Pasal chunks.
    if table_match:
        table_no = table_match.group(1)
        _append_unique_query(queries, f"{normalized_query} tabel {table_no}")
        _append_unique_query(queries, f"{normalized_query} lampiran tabel {table_no}")

        if nomor_match and tahun_match:
            _append_unique_query(
                queries,
                (
                    f"{normalized_query} tabel {table_no} "
                    f"nomor {nomor_match.group(1)} tahun {tahun_match.group(1)}"
                ),
            )

    # Definition-style queries: add literal legal phrase while preserving original intent.
    if ("definisi" in query_lower or "pengertian" in query_lower) and (
        "spbe" in query_lower or "sistem pemerintahan berbasis elektronik" in query_lower
    ):
        if nomor_match and tahun_match:
            _append_unique_query(
                queries,
                (
                    f"{normalized_query} pasal 1 perpres nomor {nomor_match.group(1)} "
                    f"tahun {tahun_match.group(1)} yang dimaksud dengan "
                    "sistem pemerintahan berbasis elektronik"
                ),
            )
        elif "perpres" in query_lower:
            _append_unique_query(
                queries,
                (
                    f"{normalized_query} pasal 1 perpres yang dimaksud dengan "
                    "sistem pemerintahan berbasis elektronik"
                ),
            )
        else:
            _append_unique_query(
                queries,
                (
                    f"{normalized_query} pasal 1 yang dimaksud dengan "
                    "sistem pemerintahan berbasis elektronik"
                ),
            )

    return queries[:6]


# =============================================================================
# ANSWER VALIDATION - Enhanced for Legal Accuracy
# =============================================================================


def _strip_reference_block(answer: str) -> str:
    """Remove appended reference section so core-answer validation stays focused."""
    if not answer:
        return ""
    parts = re.split(r"(?im)^Referensi\s+Dokumen\s*:\s*$", answer, maxsplit=1)
    return parts[0].strip()


def _extract_pasal_numbers(text: str) -> set:
    return set(re.findall(r"(?i)pasal\s+(\d+)", text or ""))


def _extract_ayat_numbers(text: str) -> set:
    return set(re.findall(r"(?i)ayat\s*\(?\s*(\d+)\s*\)?", text or ""))


def _build_source_metadata_number_map(sources: Optional[List[Dict]]) -> Dict[int, Dict[str, set]]:
    """Build lookup map of Pasal/Ayat numbers per source id for strict citation re-check."""
    source_map: Dict[int, Dict[str, set]] = {}
    for src in sources or []:
        raw_id = src.get("id")
        try:
            source_id = int(raw_id)
        except (TypeError, ValueError):
            continue

        section = str(src.get("section") or "")
        context_header = str(src.get("context_header") or "")
        pasal_raw = str(src.get("pasal") or "")
        ayat_raw = str(src.get("ayat") or "")

        pasals = set()
        ayats = set()

        pasals |= _extract_pasal_numbers(pasal_raw)
        pasals |= _extract_pasal_numbers(section)
        pasals |= _extract_pasal_numbers(context_header)

        ayats |= _extract_ayat_numbers(section)
        ayats |= _extract_ayat_numbers(context_header)
        ayats |= _extract_ayat_numbers(ayat_raw)

        # Fallback when source.ayat only stores numeric token (e.g., "1").
        if ayat_raw and not ayats:
            ayats |= set(re.findall(r"\d+", ayat_raw))

        source_map[source_id] = {
            "pasals": pasals,
            "ayats": ayats,
        }

    return source_map


def _audit_cited_metadata_consistency(answer: str, sources: Optional[List[Dict]]) -> Dict:
    """Re-check Pasal/Ayat claims against metadata of cited sources."""
    audit = {
        "enabled": bool(sources),
        "is_consistent": True,
        "checked_segments": 0,
        "checked_claims": 0,
        "mismatch_count": 0,
        "unverifiable_count": 0,
        "mismatches": [],
        "unverifiable": [],
    }

    source_map = _build_source_metadata_number_map(sources)
    if not source_map:
        return audit

    lines = [ln.strip() for ln in (answer or "").splitlines() if ln.strip()]
    for idx, line in enumerate(lines):
        line_pasals = _extract_pasal_numbers(line)
        line_ayats = _extract_ayat_numbers(line)
        if not line_pasals and not line_ayats:
            continue

        # Capture citations from nearby lines because model often writes:
        # line A: "Berdasarkan Pasal X Ayat (Y)"
        # line B: "...kutipan... [n]"
        nearby = " ".join(lines[max(0, idx - 1): min(len(lines), idx + 2)])

        cited_ids = []
        for c in re.findall(r"\[(\d+)\]", nearby):
            try:
                cid = int(c)
            except ValueError:
                continue
            if cid in source_map:
                cited_ids.append(cid)

        if not cited_ids:
            continue

        audit["checked_segments"] += 1

        cited_pasals = set()
        cited_ayats = set()
        for cid in cited_ids:
            cited_pasals |= source_map[cid]["pasals"]
            cited_ayats |= source_map[cid]["ayats"]

        if line_pasals:
            audit["checked_claims"] += len(line_pasals)
            if cited_pasals:
                missing_pasals = sorted(line_pasals - cited_pasals, key=lambda x: int(x))
                if missing_pasals:
                    audit["mismatch_count"] += len(missing_pasals)
                    audit["mismatches"].append(
                        {
                            "type": "pasal",
                            "citations": sorted(set(cited_ids)),
                            "claimed": missing_pasals,
                            "allowed": sorted(cited_pasals, key=lambda x: int(x)),
                            "snippet": line[:220],
                        }
                    )
            else:
                audit["unverifiable_count"] += len(line_pasals)
                audit["unverifiable"].append(
                    {
                        "type": "pasal",
                        "citations": sorted(set(cited_ids)),
                        "claimed": sorted(line_pasals, key=lambda x: int(x)),
                        "snippet": line[:220],
                    }
                )

        if line_ayats:
            audit["checked_claims"] += len(line_ayats)
            if cited_ayats:
                missing_ayats = sorted(line_ayats - cited_ayats, key=lambda x: int(x))
                if missing_ayats:
                    audit["mismatch_count"] += len(missing_ayats)
                    audit["mismatches"].append(
                        {
                            "type": "ayat",
                            "citations": sorted(set(cited_ids)),
                            "claimed": missing_ayats,
                            "allowed": sorted(cited_ayats, key=lambda x: int(x)),
                            "snippet": line[:220],
                        }
                    )
            else:
                audit["unverifiable_count"] += len(line_ayats)
                audit["unverifiable"].append(
                    {
                        "type": "ayat",
                        "citations": sorted(set(cited_ids)),
                        "claimed": sorted(line_ayats, key=lambda x: int(x)),
                        "snippet": line[:220],
                    }
                )

    audit["is_consistent"] = audit["mismatch_count"] == 0
    return audit


def validate_answer(answer: str, context: str, sources: Optional[List[Dict]] = None) -> Dict:
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

    answer_core = _strip_reference_block(answer)

    # Check for citations
    citations = re.findall(r"\[(\d+)\]", answer_core)
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
    answer_pasals = set(re.findall(r"Pasal\s+(\d+)", answer_core, re.IGNORECASE))
    context_pasals = set(re.findall(r"Pasal\s+(\d+)", context, re.IGNORECASE))

    hallucinated_pasals = answer_pasals - context_pasals
    if hallucinated_pasals:
        result["warnings"].append(
            f"Kemungkinan Pasal yang tidak ada di konteks: {', '.join(sorted(hallucinated_pasals))}"
        )
        result["confidence"] = "medium"

    # Check for hallucinated Ayat numbers
    answer_ayats = set(re.findall(r"[Aa]yat\s*\((\d+)\)", answer_core))
    context_ayats = set(re.findall(r"\((\d+)\)", context))

    hallucinated_ayats = answer_ayats - context_ayats
    if hallucinated_ayats:
        result["warnings"].append(
            f"Kemungkinan Ayat yang tidak ada di konteks: {', '.join(sorted(hallucinated_ayats))}"
        )
        result["confidence"] = "medium"

    # Check for incomplete lists
    answer_letters = set(re.findall(r"^([a-z])\.", answer_core, re.MULTILINE))
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

    answer_lower = answer_core.lower()
    for phrase in hallucination_phrases:
        if phrase in answer_lower:
            result["warnings"].append(f"Kemungkinan halusinasi: '{phrase}'")
            result["is_valid"] = False
            result["confidence"] = "low"

    # Check for Domain/Aspek/Indikator hierarchy confusion
    query_lower = context.lower()  # Use context to infer question scope
    _check_spbe_hierarchy_confusion(answer_lower, result)

    # Strict per-citation metadata re-check (Pasal/Ayat vs cited source metadata)
    metadata_audit = _audit_cited_metadata_consistency(answer_core, sources)
    result["metadata_audit"] = metadata_audit

    if metadata_audit.get("mismatch_count", 0) > 0:
        result["warnings"].append(
            "Re-check sitasi menemukan mismatch Pasal/Ayat terhadap metadata sumber yang dirujuk."
        )
        result["is_valid"] = False
        result["confidence"] = "low"
    elif metadata_audit.get("unverifiable_count", 0) > 0:
        result["warnings"].append(
            "Sebagian klaim Pasal/Ayat tidak dapat diverifikasi dari metadata sumber yang tersedia."
        )
        if result["confidence"] == "high":
            result["confidence"] = "medium"

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
