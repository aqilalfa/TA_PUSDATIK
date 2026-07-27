"""Answerability Gate for OWASP LLM09 hardening (Tahap D).

Classifies retrieved evidence into three tiers BEFORE generation:

    COMPLETE  - all main information needed is present in retrieved context.
                Answer directly, concisely, with citations.
    PARTIAL   - only some information is present.
                Answer only the supported part; explicitly state the limitation;
                never fill the gap with model background knowledge.
    NONE      - main information is not present.
                Safe fallback; no speculative answer.

This module does NOT replace `assess_llm09_pre_generation_guard` — it wraps it.
The existing guard's hard-block conditions (unsupported legal reference,
unsupported comparison, incomplete aggregation, out-of-domain risk) map
directly to NONE. When the guard allows generation, focus-term coverage
determines whether the evidence is COMPLETE or merely PARTIAL.

Per PRD Tahap D: "Jangan menentukan answerability hanya dari kemiripan kata" —
literal term coverage is a necessary but not sufficient signal, which is why
COMPLETE requires both high coverage AND the guard's structural checks
(legal reference presence, aggregation completeness, etc.) to have already
passed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from app.core.rag.llm09_guard import assess_llm09_pre_generation_guard

AnswerabilityLevel = Literal["COMPLETE", "PARTIAL", "NONE"]

# Below this focus-term coverage, evidence that technically "passed" the guard
# is still too thin to be treated as a complete answer — the model must be
# told to answer only the supported slice and state the gap explicitly.
COMPLETE_COVERAGE_THRESHOLD = 0.85


@dataclass
class AnswerabilityResult:
    level: AnswerabilityLevel
    reason: str
    focus_coverage: float
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "answerability": self.level,
            "reason": self.reason,
            "focus_coverage": self.focus_coverage,
            "details": self.details,
        }


def assess_answerability(query: str, context: str, sources: list[dict[str, Any]]) -> AnswerabilityResult:
    """Classify evidence sufficiency for `query` given retrieved `context`/`sources`."""
    guard_decision = assess_llm09_pre_generation_guard(query, context, sources)
    coverage = float(guard_decision.details.get("focus_coverage", 0.0) or 0.0)

    if not guard_decision.allowed:
        return AnswerabilityResult(
            level="NONE",
            reason=guard_decision.reason,
            focus_coverage=coverage,
            details={"risk_category": guard_decision.risk_category, **guard_decision.details},
        )

    if coverage >= COMPLETE_COVERAGE_THRESHOLD:
        return AnswerabilityResult(
            level="COMPLETE",
            reason="Seluruh istilah inti pertanyaan didukung evidence retrieval.",
            focus_coverage=coverage,
            details=guard_decision.details,
        )

    return AnswerabilityResult(
        level="PARTIAL",
        reason="Sebagian istilah inti pertanyaan didukung evidence retrieval; jawaban harus dibatasi pada bagian yang tersedia.",
        focus_coverage=coverage,
        details=guard_decision.details,
    )


def build_partial_answer_instruction(result: AnswerabilityResult) -> str:
    """System-prompt addendum injected only when answerability == PARTIAL."""
    return (
        "PERINGATAN CAKUPAN BUKTI PARSIAL:\n"
        "Evidence retrieval hanya mendukung sebagian dari pertanyaan ini "
        f"(cakupan istilah inti: {result.focus_coverage:.0%}).\n"
        "- Jawab HANYA bagian yang benar-benar didukung retrieved context.\n"
        "- Nyatakan secara eksplisit bagian yang belum dapat dikonfirmasi, gunakan redaksi: "
        "\"Bagian lain tidak dapat dikonfirmasi dari retrieved context yang tersedia.\"\n"
        "- JANGAN melengkapi bagian yang hilang dengan pengetahuan umum model."
    )
