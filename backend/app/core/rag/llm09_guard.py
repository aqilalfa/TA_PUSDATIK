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
PASAL_PATTERN = re.compile(r"\b[Pp]asal\s+(\d+)\b")
AYAT_PATTERN = re.compile(r"\b[Aa]yat\s*\(?(\d+)\)?")
DOC_HINT_PATTERN = re.compile(r"\b(?:Perpres|PP|Peraturan\s+BSSN|BSSN|Peraturan\s+Presiden|PERATURAN\s+KEPALA)[^,\.\n]{0,80}", re.IGNORECASE)

GENERIC_FOCUS_TERMS = {
    "spbe", "bssn", "audit", "keamanan", "sistem", "pemerintahan", "elektronik",
    "dokumen", "sumber", "peraturan", "nasional", "pasal", "ayat", "tahun",
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


def _focus_coverage(query: str, evidence: str) -> tuple[float, list[str], list[str]]:
    terms = _important_terms(query)
    if not terms:
        return 1.0, [], []
    present = [term for term in terms if re.search(rf"\b{re.escape(term)}\b", evidence)]
    return len(present) / len(terms), terms, present


def _contains_full_table_or_aggregate_evidence(query: str, evidence: str) -> bool:
    query_l = query.lower()
    if re.search(r"\b(?:belum\s+tentu\s+lengkap|tidak\s+lengkap|parsial|sebagian)\b", query_l):
        return False
    if "nasional" in query_l:
        return bool(re.search(r"\b(?:agregat|rata[-\s]?rata|rekapitulasi|ringkasan\s+nasional|nasional\s+secara\s+lengkap)\b", evidence))
    if re.search(r"\b(?:semua|seluruh|ranking|urutkan)\b", query_l):
        return bool(re.search(r"\b(?:rekapitulasi|daftar\s+lengkap|seluruh|semua)\b", evidence))
    return True


def _legal_reference_is_supported(query: str, evidence: str) -> tuple[bool, str]:
    pasal_refs = PASAL_PATTERN.findall(query)
    ayat_refs = AYAT_PATTERN.findall(query)

    for pasal in pasal_refs:
        if not re.search(rf"\bpasal\s+{re.escape(pasal)}\b", evidence, re.IGNORECASE):
            return False, f"Pasal {pasal} tidak ditemukan dalam evidence retrieval"

    for ayat in ayat_refs:
        if not re.search(rf"\bayat\s*\(?{re.escape(ayat)}\)?\b", evidence, re.IGNORECASE):
            return False, f"Ayat ({ayat}) tidak ditemukan dalam evidence retrieval"

    return True, ""


def _comparison_entities_supported(query: str, evidence: str) -> tuple[bool, str]:
    if not COMPARISON_PATTERN.search(query):
        return True, ""
    terms = _important_terms(query)
    missing = [term for term in terms if term not in evidence]
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

    legal_ok, legal_reason = _legal_reference_is_supported(query_text, evidence)
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

    if AGGREGATION_PATTERN.search(query_text) and not _contains_full_table_or_aggregate_evidence(query_text, evidence):
        return LLM09GuardDecision(
            False,
            "Pertanyaan meminta agregasi/kesimpulan, tetapi evidence tidak menunjukkan data lengkap/agregat",
            "aggregation_completeness",
            {"focus_terms": terms, "present_terms": present_terms, "focus_coverage": coverage},
        )

    high_risk_missing_context = bool(OUT_OF_DOMAIN_PATTERN.search(query_text))
    if high_risk_missing_context and coverage < 0.75:
        return LLM09GuardDecision(
            False,
            "Istilah inti pertanyaan berisiko tidak tersedia dalam evidence retrieval",
            "evidence_sufficiency",
            {"focus_terms": terms, "present_terms": present_terms, "focus_coverage": coverage},
        )

    if re.search(r"\b(?:tidak\s+disebutkan|belum\s+ada|tidak\s+ada\s+di\s+dokumen|di\s+luar\s+dokumen)\b", query_l) and coverage < 0.9:
        return LLM09GuardDecision(
            False,
            "Pertanyaan eksplisit meminta fakta yang tidak tersedia dan evidence tidak cukup",
            "evidence_sufficiency",
            {"focus_terms": terms, "present_terms": present_terms, "focus_coverage": coverage},
        )

    return LLM09GuardDecision(
        True,
        "Evidence cukup untuk generation",
        "normal",
        {"focus_terms": terms, "present_terms": present_terms, "focus_coverage": coverage},
    )
