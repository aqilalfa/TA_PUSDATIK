"""Lightweight LLM09 pre-generation guardrails.

These checks are intentionally deterministic and cheap: regex + metadata/snippet
matching only, no extra LLM call. The goal is to fail closed before generation
when retrieved chunks are only semantically adjacent but do not provide enough
evidence for the user's core request.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any

from app.core.rag.claim_verifier import _build_context_source_blocks
from app.core.rag.quality_check import extract_focus_terms


FALLBACK_MESSAGE = (
    "Maaf, konteks dokumen yang tersedia belum cukup untuk menjawab pertanyaan ini "
    "secara terverifikasi. Silakan ajukan pertanyaan yang lebih spesifik atau pastikan "
    "dokumen sumber yang relevan sudah tersedia dan dapat diakses."
)

AGGREGATION_PATTERN = re.compile(
    r"\b(?:tertinggi|terendah|ranking|urutkan|semua|seluruh|rata[-\s]?rata|"
    r"tren|kesimpulan\s+(?:tabel|menyeluruh)|secara\s+nasional|skor\s+terendah|skor\s+tertinggi)\b",
    re.IGNORECASE,
)

COMPARISON_PATTERN = re.compile(r"\b(?:bandingkan|perbandingan|dibandingkan|versus|vs\.?|dengan\s+estonia)\b", re.IGNORECASE)
OUT_OF_DOMAIN_PATTERN = re.compile(r"\b(?:pegawai\s+bssn|tahun\s+ini|prediksi|blockchain|surat\s+edaran\s+internal\s+terbaru|estonia)\b", re.IGNORECASE)
PASAL_PATTERN = re.compile(r"\bpasal\s+(\d+)\b", re.IGNORECASE)
AYAT_PATTERN = re.compile(r"\bayat\s*\(?(\d+)\)?", re.IGNORECASE)

# Comparison trigger words are query INTENT markers, not entities the evidence
# must contain — requiring them in evidence blocked nearly every comparison.
_COMPARISON_TRIGGER_TERMS = {"bandingkan", "membandingkan", "dibandingkan", "perbandingan", "versus", "vs"}

_ACRONYM_EXPANSIONS = {
    "iiv": ["infrastruktur informasi vital", "iiv"],
    "spbe": ["sistem pemerintahan berbasis elektronik", "spbe"],
    "bssn": ["badan siber dan sandi negara", "bssn"],
    "tik": ["teknologi informasi dan komunikasi", "tik"],
    "ippd": ["instansi pusat dan pemerintah daerah", "ippd", "instansi pusat", "pemerintah daerah"],
}

_BAGIAN_SUFFIX_PATTERN = re.compile(r"\s*\[Bagian\s+\d+/\d+\]\s*$", re.IGNORECASE)

# Aliases for regulation TYPE tokens: a query naming 'Perpres 71/2019' must not
# be satisfied by 'PP Nomor 71 Tahun 2019' just because number+year coincide.
_REGULATION_TYPE_ALIASES = {
    "perpres": ("peraturan presiden", "perpres"),
    "peraturan presiden": ("peraturan presiden", "perpres"),
    "pp": ("peraturan pemerintah", "pp"),
    "peraturan pemerintah": ("peraturan pemerintah", "pp"),
    "peraturan bssn": ("peraturan bssn", "peraturan kepala", "badan siber dan sandi negara"),
    "peraturan kepala": ("peraturan bssn", "peraturan kepala", "badan siber dan sandi negara"),
}
DOC_HINT_PATTERN = re.compile(r"\b(?:Perpres|PP|Peraturan\s+BSSN|BSSN|Peraturan\s+Presiden|PERATURAN\s+KEPALA)[^,\.\n]{0,80}", re.IGNORECASE)

GENERIC_FOCUS_TERMS = {
    "spbe", "bssn", "audit", "keamanan", "sistem", "pemerintahan", "elektronik",
    "dokumen", "sumber", "peraturan", "nasional", "pasal", "ayat", "tahun", "dimaksud", "arti", "makna"
}


@dataclass
class LLM09GuardDecision:
    allowed: bool
    reason: str = ""
    risk_category: str = "normal"
    details: dict[str, Any] = field(default_factory=dict)


def _source_text(source: dict[str, Any]) -> str:
    parts = [
        source.get("document"),
        source.get("document_short"),
        source.get("section"),
        source.get("hierarchy"),
        source.get("snippet"),
    ]
    return "\n".join(str(part) for part in parts if part)


def _combined_evidence(sources: list[dict[str, Any]], context: str) -> str:
    source_text = "\n".join(_source_text(src) for src in sources)
    return f"{context}\n{source_text}".lower()


def _important_terms(query: str) -> list[str]:
    return [term for term in extract_focus_terms(query, max_terms=12) if term not in GENERIC_FOCUS_TERMS]


def _term_present(term: str, evidence_lower: str) -> bool:
    """Word-boundary term match with acronym-expansion variants."""
    variants = _ACRONYM_EXPANSIONS.get(term.lower(), [term.lower()])
    return any(re.search(rf"\b{re.escape(variant)}\b", evidence_lower) for variant in variants)


def _focus_coverage(query: str, evidence: str) -> tuple[float, list[str], list[str]]:
    terms = _important_terms(query)
    if not terms:
        return 1.0, [], []

    evidence_lower = evidence.lower()
    present = [term for term in terms if _term_present(term, evidence_lower)]
    return len(present) / len(terms), terms, present


def _has_partial_table_chunk(sources: list[dict[str, Any]]) -> bool:
    """Detect that a split table is only PARTIALLY present in retrieval (Tahap C).

    `structured_chunker.append_chunk_with_limit` tags oversized table blocks
    with `chunk_part` / `chunk_parts_total` when a single table had to be cut
    into multiple pieces. The table is provably incomplete only when some
    sibling parts are MISSING from the retrieved sources — when every part of
    the split table was retrieved, aggregation over it may proceed.
    """
    groups: dict[tuple[str, str], dict[str, Any]] = {}
    for src in sources:
        if not src.get("is_table"):
            continue
        try:
            total = int(src.get("chunk_parts_total") or 0)
        except (TypeError, ValueError):
            continue
        if total <= 1:
            continue

        part = src.get("chunk_part")
        try:
            part_number = int(part or 0)
        except (TypeError, ValueError):
            # Split table without part info: completeness cannot be proven.
            return True

        # Sibling parts share the same table label (or base hierarchy) within a document.
        base_hierarchy = _BAGIAN_SUFFIX_PATTERN.sub("", str(src.get("hierarchy") or ""))
        key = (
            str(src.get("document") or ""),
            str(src.get("table_label") or "") or base_hierarchy,
        )
        group = groups.setdefault(key, {"total": total, "parts": set()})
        group["total"] = max(group["total"], total)
        group["parts"].add(part_number)

    return any(len(group["parts"]) < group["total"] for group in groups.values())


def _contains_full_table_or_aggregate_evidence(
    query: str, evidence: str, sources: list[dict[str, Any]] | None = None
) -> bool:
    query_l = query.lower()
    if re.search(r"\b(?:belum\s+tentu\s+lengkap|tidak\s+lengkap|parsial|sebagian)\b", query_l):
        return False
    if sources and _has_partial_table_chunk(sources):
        return False
    if "nasional" in query_l:
        return bool(re.search(r"\b(?:agregat|rata[-\s]?rata|rekapitulasi|ringkasan\s+nasional|nasional\s+secara\s+lengkap)\b", evidence))
    if re.search(r"\b(?:semua|seluruh|ranking|urutkan)\b", query_l):
        return bool(re.search(r"\b(?:rekapitulasi|daftar\s+lengkap|seluruh|semua)\b", evidence))
    return True


def _ayat_present_in_scope(content_text: str, pasal_scope: list[str], ayat: str) -> bool:
    """True when `ayat` appears in the chunk other than as a cross-reference
    to a pasal outside `pasal_scope` (e.g. 'sebagaimana dimaksud dalam Pasal
    12 ayat (5)' inside a Pasal 7 chunk must not validate Pasal 7 ayat (5))."""

    def _drop_foreign(match: re.Match) -> str:
        return match.group(0) if match.group(1) in pasal_scope else " "

    cleaned = re.sub(r"\bpasal\s+(\d+)\s*ayat\s*\(?\d+\)?", _drop_foreign, content_text)
    return bool(
        re.search(rf"\bayat\s*\(?{re.escape(ayat)}\)?\b", cleaned)
        or re.search(rf"\({re.escape(ayat)}\)", cleaned)
    )


def _legal_reference_is_supported(
    query: str,
    evidence: str,
    sources: list[dict[str, Any]] | None = None,
    context: str = "",
) -> tuple[bool, str]:
    pasal_refs = PASAL_PATTERN.findall(query)
    ayat_refs = AYAT_PATTERN.findall(query)
    if not pasal_refs and not ayat_refs:
        return True, ""

    # LLM09 Tahap I fix: if the user names a specific regulation (e.g.
    # "Perpres 95/2018") AND a Pasal number, the evidence must contain that
    # Pasal number within the NAMED regulation — not just any chunk that
    # happens to have the same Pasal number from a different document.
    # Without this, the LLM happily "corrects" the user by citing Pasal 99
    # from PP 71/2019 when asked about Pasal 99 of Perpres 95/2018, producing
    # a confident but wrong answer (false positive).
    query_regulation_match = re.search(
        r"\b(Perpres|PP|Peraturan\s+Pemerintah|Peraturan\s+BSSN|Peraturan\s+Presiden|PERATURAN\s+KEPALA)"
        r"\s*(?:Nomor\.?\s*)?(\d+)\s*/?\s*(?:Tahun\s*)?(\d{4})",
        query,
        re.IGNORECASE,
    )
    query_regulation = ""
    regulation_pattern = None
    regulation_type_variants: tuple[str, ...] = ()
    if query_regulation_match:
        type_token = re.sub(r"\s+", " ", query_regulation_match.group(1).lower()).strip()
        number = query_regulation_match.group(2)
        year = query_regulation_match.group(3)
        query_regulation = f"{number}/{year}"
        # LLM09 review fix K2: production titles read 'Nomor 95 Tahun 2018' —
        # match number/year tolerantly ('95/2018', '95 Tahun 2018', 'Nomor 95
        # Tahun 2018') instead of exact substring containment that can never
        # match ingested metadata. The regulation TYPE must also match (via
        # aliases): number+year alone would accept 'PP 71/2019' for a query
        # about 'Perpres 71/2019'.
        regulation_pattern = re.compile(
            rf"(?:\bnomor\s+)?\b{re.escape(number)}\s*(?:/|\s+tahun\s+)\s*{re.escape(year)}\b"
        )
        regulation_type_variants = _REGULATION_TYPE_ALIASES.get(type_token, (type_token,))

    # Per-source texts: metadata label FIELDS for regulation identity, plus
    # snippet and the source's full context block for content-level pasal/ayat
    # presence (md_fallback/table chunks often carry the Pasal only in the body).
    block_map = _build_context_source_blocks(context) if context else {}
    source_texts: list[tuple[list[str], str]] = []
    for src in sources or []:
        label_fields = [
            str(value).lower()
            for value in (
                src.get("document") or src.get("document_short"),
                src.get("section"),
                src.get("hierarchy"),
            )
            if value
        ]
        try:
            source_id = int(str(src.get("id")))
        except (TypeError, ValueError):
            source_id = None
        block_text = block_map.get(source_id, "") if source_id is not None else ""
        content_text = "\n".join([*label_fields, str(src.get("snippet") or ""), block_text]).lower()
        source_texts.append((label_fields, content_text))

    def _source_is_named_regulation(label_fields: list[str]) -> bool:
        # Number/year AND a regulation-type alias must co-occur within the SAME
        # metadata field, so unrelated numbers across fields cannot combine and
        # a different regulation type sharing number/year cannot match.
        if regulation_pattern is None:
            return False
        for field in label_fields:
            if regulation_pattern.search(field) and any(
                re.search(rf"\b{re.escape(variant)}\b", field)
                for variant in regulation_type_variants
            ):
                return True
        return False

    for pasal in pasal_refs:
        if not re.search(rf"\bpasal\s+{re.escape(pasal)}\b", evidence, re.IGNORECASE):
            return False, f"Pasal {pasal} tidak ditemukan dalam evidence retrieval"

        # If user named a specific regulation, verify the Pasal comes from THAT
        # regulation, not a different one that happens to share the number.
        if regulation_pattern and source_texts:
            pasal_in_named_regulation = False
            for label_fields, content_text in source_texts:
                if _source_is_named_regulation(label_fields) and re.search(
                    rf"\bpasal\s+{re.escape(pasal)}\b", content_text
                ):
                    pasal_in_named_regulation = True
                    break
            if not pasal_in_named_regulation:
                return False, f"Pasal {pasal} tidak ditemukan dalam {query_regulation} yang disebut pertanyaan"

    # Pair each ayat with the pasal that directly precedes it in the query, so
    # 'Pasal 7 dan Pasal 12 ayat (2)' scopes ayat (2) to Pasal 12 only.
    ayat_pasal_pairs: dict[str, set[str]] = {}
    for pair in re.finditer(r"\bpasal\s+(\d+)\s*ayat\s*\(?(\d+)\)?", query, re.IGNORECASE):
        ayat_pasal_pairs.setdefault(pair.group(2), set()).add(pair.group(1))

    for ayat in ayat_refs:
        ayat_word_pattern = rf"\bayat\s*\(?{re.escape(ayat)}\)?\b"
        if pasal_refs and source_texts:
            # LLM09 review fix H2: when the query names a Pasal, the ayat must
            # exist within a source that actually carries that Pasal — an
            # 'ayat (n)' cross-reference in an unrelated chunk is not evidence.
            # Bare '(n)' numbering inside the pasal-bearing chunk counts, since
            # legal bodies enumerate ayat as '(1) ...' without the word 'ayat'.
            pasal_scope = sorted(ayat_pasal_pairs.get(ayat) or set()) or list(pasal_refs)
            ayat_ok = False
            for _, content_text in source_texts:
                has_scoped_pasal = any(
                    re.search(rf"\bpasal\s+{re.escape(p)}\b", content_text) for p in pasal_scope
                )
                if has_scoped_pasal and _ayat_present_in_scope(content_text, pasal_scope, ayat):
                    ayat_ok = True
                    break
            if not ayat_ok:
                return False, f"Ayat ({ayat}) tidak ditemukan pada Pasal yang disebut dalam evidence retrieval"
        elif not re.search(ayat_word_pattern, evidence, re.IGNORECASE):
            return False, f"Ayat ({ayat}) tidak ditemukan dalam evidence retrieval"

    return True, ""


def _comparison_entities_supported(query: str, evidence: str) -> tuple[bool, str]:
    if not COMPARISON_PATTERN.search(query):
        return True, ""
    evidence_lower = evidence.lower()
    # LLM09 review fix H7: the trigger word expresses intent and must not be
    # required in evidence; entity matching reuses the word-boundary +
    # acronym-expansion matcher instead of raw substring containment.
    terms = [term for term in _important_terms(query) if term.lower() not in _COMPARISON_TRIGGER_TERMS]
    missing = [term for term in terms if not _term_present(term, evidence_lower)]
    if missing:
        return False, f"Entitas/istilah pembanding tidak ditemukan dalam evidence: {', '.join(missing[:4])}"
    return True, ""


def assess_llm09_pre_generation_guard(query: str, context: str, sources: list[dict[str, Any]]) -> LLM09GuardDecision:
    """Return whether generation is allowed for the retrieved evidence.

    This is a conservative guard for known LLM09 risk patterns. Normal factual
    questions are allowed unless explicit legal references are unsupported.
    """
    if not sources:
        return LLM09GuardDecision(False, "Tidak ada sumber retrieval", "no_sources")

    query_text = str(query or "")
    evidence = _combined_evidence(sources, context)
    query_l = query_text.lower()
    coverage, terms, present_terms = _focus_coverage(query_text, evidence)

    legal_ok, legal_reason = _legal_reference_is_supported(query_text, evidence, sources, context)
    if not legal_ok:
        return LLM09GuardDecision(
            False,
            legal_reason,
            "legal_reference",
            {"focus_terms": terms, "present_terms": present_terms, "focus_coverage": coverage},
        )

    comparison_ok, comparison_reason = _comparison_entities_supported(query_text, evidence)
    if not comparison_ok:
        return LLM09GuardDecision(
            False,
            comparison_reason,
            "comparison",
            {"focus_terms": terms, "present_terms": present_terms, "focus_coverage": coverage},
        )

    if AGGREGATION_PATTERN.search(query_text) and not _contains_full_table_or_aggregate_evidence(query_text, evidence, sources):
        return LLM09GuardDecision(
            False,
            "Pertanyaan meminta agregasi/kesimpulan, tetapi evidence tidak menunjukkan data lengkap/agregat",
            "aggregation_completeness",
            {"focus_terms": terms, "present_terms": present_terms, "focus_coverage": coverage},
        )

    high_risk_missing_context = bool(OUT_OF_DOMAIN_PATTERN.search(query_text))
    if high_risk_missing_context and coverage < 0.4:
        return LLM09GuardDecision(
            False,
            "Istilah inti pertanyaan berisiko tidak tersedia dalam evidence retrieval",
            "evidence_sufficiency",
            {"focus_terms": terms, "present_terms": present_terms, "focus_coverage": coverage},
        )

    if re.search(r"\b(?:tidak\s+disebutkan|belum\s+ada|tidak\s+ada\s+di\s+dokumen|di\s+luar\s+dokumen)\b", query_l) and coverage < 0.4:
        return LLM09GuardDecision(
            False,
            "Pertanyaan eksplisit meminta fakta yang tidak tersedia dan evidence tidak cukup",
            "evidence_sufficiency",
            {"focus_terms": terms, "present_terms": present_terms, "focus_coverage": coverage},
        )

    # NOTE: a generic "coverage == 0.0 => block" catch-all was intentionally
    # removed here. It fired for ANY query with zero literal term overlap
    # regardless of risk category, which made the guard reject perfectly
    # answerable questions (e.g. paraphrased definitional queries) whenever
    # the evidence happened to use different wording. Per LLM09 hardening
    # PRD ("jangan terlalu agresif menolak pertanyaan yang answerable"),
    # zero-coverage-without-a-specific-risk-trigger is now left to the
    # Answerability Gate (PARTIAL classification) and the post-generation
    # claim verifier (Tahap G) to catch downstream instead of failing closed
    # here.

    return LLM09GuardDecision(
        True,
        "Evidence cukup untuk generation",
        "normal",
        {"focus_terms": terms, "present_terms": present_terms, "focus_coverage": coverage},
    )
