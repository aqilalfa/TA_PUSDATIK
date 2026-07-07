import re
from dataclasses import dataclass
from typing import Any

from app.core.rag.guardrails import (
    OUT_OF_SCOPE_REFUSAL,
    PROMPT_INJECTION_REFUSAL,
    SOURCE_BYPASS_REFUSAL,
    PromptInjectionCheck,
    scan_llm_output_for_leakage,
)


@dataclass(frozen=True)
class OutputGuardResult:
    allowed: bool
    categories: list[str]
    severity: str
    safe_response: str | None = None
    details: dict[str, Any] | None = None


def _has_inline_citation(answer: str) -> bool:
    return bool(re.search(r"\[\d+\]", str(answer or "")))


def _looks_like_safe_refusal_or_source_limited(answer: str) -> bool:
    normalized = " ".join(str(answer or "").lower().split())
    markers = (
        "maaf, saya tidak dapat",
        "tidak ditemukan dalam dokumen",
        "tidak ditemukan dalam konteks",
        "tidak tersedia dalam dokumen",
        "dokumen tidak memuat",
        "berdasarkan dokumen referensi",
        "instruksi tidak tepercaya",
    )
    return any(marker in normalized for marker in markers)


def _detect_source_bypass_output(answer: str) -> bool:
    normalized = " ".join(str(answer or "").lower().split())
    bypass = re.search(r"\b(?:tanpa dokumen|tanpa sumber|tanpa sitasi|pengetahuan umum|asumsi)\b", normalized)
    negated = re.search(
        r"\b(?:tidak dapat|tidak boleh|dilarang|menolak)\b.{0,120}"
        r"\b(?:tanpa dokumen|tanpa sumber|tanpa sitasi|pengetahuan umum|asumsi)\b",
        normalized,
    )
    return bool(bypass and not negated)


def _detect_out_of_scope_artifact(answer: str) -> bool:
    if _looks_like_safe_refusal_or_source_limited(answer):
        return False
    return bool(
        re.search(
            r"(?:```(?:html|javascript|js|python)?|<!doctype html>|<script|function\s+\w+\s*\(|const\s+\w+\s*=|let\s+\w+\s*=|class\s+\w+)",
            str(answer or ""),
            re.IGNORECASE,
        )
    )


def _severity_for(categories: list[str]) -> str:
    category_set = set(categories)
    if category_set & {"system_prompt_leak", "secret_leak", "internal_tool_leak", "internal_instruction_leak"}:
        return "critical"
    if category_set & {"source_bypass_output"}:
        return "high"
    if category_set & {"out_of_scope_artifact", "missing_citation"}:
        return "medium"
    return "low" if categories else "none"


def validate_llm_output_contract(
    answer: str,
    *,
    requires_citation: bool = True,
    allow_refusal_without_citation: bool = True,
) -> OutputGuardResult:
    """Validate the post-LLM answer against the SPBE RAG output safety contract.

    This complements streaming leakage scanning and LLM09 citation validation. It is deliberately
    conservative for source-bypass, internal leakage, and out-of-scope artifacts while allowing
    safe refusals/source-limited answers.
    """
    categories: list[str] = []
    leakage: PromptInjectionCheck = scan_llm_output_for_leakage(answer)
    categories.extend(leakage.categories)

    if _detect_source_bypass_output(answer):
        categories.append("source_bypass_output")
    if _detect_out_of_scope_artifact(answer):
        categories.append("out_of_scope_artifact")

    safe_refusal = _looks_like_safe_refusal_or_source_limited(answer)
    if requires_citation and not _has_inline_citation(answer) and not (allow_refusal_without_citation and safe_refusal):
        categories.append("missing_citation")

    categories = list(dict.fromkeys(categories))
    if not categories:
        return OutputGuardResult(allowed=True, categories=[], severity="none", details={"has_citation": _has_inline_citation(answer)})

    severity = _severity_for(categories)
    if set(categories) & {"system_prompt_leak", "secret_leak", "internal_tool_leak", "internal_instruction_leak"}:
        safe_response = PROMPT_INJECTION_REFUSAL
    elif "source_bypass_output" in categories:
        safe_response = SOURCE_BYPASS_REFUSAL
    elif "out_of_scope_artifact" in categories:
        safe_response = OUT_OF_SCOPE_REFUSAL
    else:
        safe_response = (
            "Maaf, saya belum dapat memverifikasi jawaban ini secara aman berdasarkan sitasi "
            "dan konteks dokumen yang tersedia. Silakan ajukan ulang pertanyaan dengan cakupan yang lebih spesifik."
        )

    return OutputGuardResult(
        allowed=False,
        categories=categories,
        severity=severity,
        safe_response=safe_response,
        details={"has_citation": _has_inline_citation(answer), "safe_refusal": safe_refusal},
    )
