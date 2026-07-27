"""Post-generation per-claim verifier for OWASP LLM09 hardening (Tahap G).

Replaces the previous all-or-nothing behavior (any unsupported claim -> discard
the ENTIRE answer and replace with a generic fallback) with claim-level editing:

    SUPPORTED            -> keep as-is
    PARTIALLY_SUPPORTED  -> keep but flag (narrowing free text deterministically
                             is unreliable, so we surface it for audit instead of
                             silently rewriting the sentence)
    UNSUPPORTED          -> remove from the final answer

If, after removing UNSUPPORTED claims, no substantive claim remains, the caller
should fall back to a safe "insufficient context" response instead of shipping
an empty/broken answer.

This module is deterministic (token-overlap grounding), consistent with the
existing `_audit_claim_grounding` in `app.core.rag.prompts`, but exposes a
3-tier verdict and an answer-rewriting step per PRD Tahap G.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

SUPPORTED = "SUPPORTED"
PARTIALLY_SUPPORTED = "PARTIALLY_SUPPORTED"
UNSUPPORTED = "UNSUPPORTED"

# Claims below this many matched content tokens can never be SUPPORTED, even
# with a high overlap ratio (guards against short claims trivially matching).
MIN_MATCHED_TOKENS_FOR_SUPPORT = 2

SUPPORTED_OVERLAP_THRESHOLD = 0.6
PARTIAL_OVERLAP_THRESHOLD = 0.3

_GROUNDING_STOPWORDS = {
    "adalah", "atau", "bahwa", "dalam", "dan", "dari", "dengan", "di", "ini",
    "itu", "ke", "oleh", "pada", "sebagai", "serta", "tersebut", "untuk", "yang",
}

# Sentences that are structural/navigational, not factual claims requiring
# grounding. Mirrors the PRD's "non-claim" exclusion list (Tahap G/PRD V3).
_NON_CLAIM_MARKERS = (
    "maaf, saya belum dapat memverifikasi",
    "silakan ajukan ulang pertanyaan",
    "silakan ajukan pertanyaan",
    "berikut adalah jawaban",
    "berikut adalah penjelasan",
    "saya hanya dapat menjawab",
    "informasi tersebut tidak ditemukan",
    "konteks dokumen yang tersedia belum cukup",
    # Mandated PARTIAL-answer disclosure (answerability.build_partial_answer_instruction).
    # Deliberately the FULL mandated phrase: a bare 'tidak dapat dikonfirmasi'
    # would also exempt hedged hallucinations ('...tidak dapat dikonfirmasi,
    # namun umumnya bernilai 5 tahun') from grading entirely.
    "tidak dapat dikonfirmasi dari retrieved context",
)

_REFERENCE_HEADER_PATTERN = re.compile(
    r"(?im)^(?:referensi\s+dokumen|daftar\s+sumber\s+resmi|daftar\s+referensi|sumber)\s*:",
)


@dataclass
class ClaimVerdict:
    claim_id: str
    text: str
    citation_ids: List[int]
    status: str
    overlap: float
    matched_terms: List[str] = field(default_factory=list)
    reason: str = ""


def _coerce_source_id(value: Any) -> Optional[int]:
    """Best-effort numeric source id (ints, numeric strings; None otherwise)."""
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None


def _strip_reference_block_for_claims(answer: str) -> str:
    match = _REFERENCE_HEADER_PATTERN.search(answer or "")
    if not match:
        return answer or ""
    return (answer or "")[: match.start()].strip()


def _is_non_claim(sentence: str) -> bool:
    lowered = sentence.lower()
    return any(marker in lowered for marker in _NON_CLAIM_MARKERS)


def _grounding_tokens(text: str) -> set[str]:
    lowered = str(text or "").lower()
    tokens = {
        token
        for token in re.findall(r"[a-z0-9]+", lowered)
        if len(token) >= 3 and token not in _GROUNDING_STOPWORDS
    }
    # Numbers are first-class grounding tokens regardless of length: pasal/ayat
    # numbers, quantities, and intervals are exactly what misinformation gets wrong.
    tokens |= set(re.findall(r"\d+", lowered))
    return tokens


# LLM09 Tahap H: phrases that claim multiple citations describe ONE shared
# legal unit (pasal/ketentuan/peraturan). When such a claim cites sources
# from more than one distinct document, it is a cross-document mixing
# hallucination — two separate regulations do not become "the same pasal"
# just because both were retrieved together.
_CROSS_DOCUMENT_UNIFICATION_MARKERS = (
    "pasal yang sama",
    "satu pasal yang sama",
    "ketentuan yang sama",
    "seolah-olah berasal dari satu pasal",
    "diatur dalam pasal yang sama",
    "sama-sama diatur dalam",
    "berasal dari peraturan yang sama",
)


def _claim_mixes_documents(
    claim_text: str, citation_ids: List[int], sources_by_id: Dict[int, Dict[str, Any]]
) -> bool:
    if len(citation_ids) < 2:
        return False

    documents = {
        str(sources_by_id[cid].get("document") or sources_by_id[cid].get("document_short") or "")
        for cid in citation_ids
        if cid in sources_by_id
    }
    documents.discard("")
    if len(documents) < 2:
        return False

    lowered = claim_text.lower()
    return any(marker in lowered for marker in _CROSS_DOCUMENT_UNIFICATION_MARKERS)


def _build_context_source_blocks(context: str) -> Dict[int, str]:
    """Collect each numbered context block, including repeated source sections."""
    blocks: Dict[int, List[str]] = {}
    matches = list(re.finditer(r"(?m)^\[(\d+)\]\s*", str(context or "")))
    for index, match in enumerate(matches):
        source_id = int(match.group(1))
        end = matches[index + 1].start() if index + 1 < len(matches) else len(context)
        blocks.setdefault(source_id, []).append(context[match.end():end].strip())
    return {source_id: "\n".join(parts) for source_id, parts in blocks.items()}


def extract_claims(answer: str) -> List[Dict[str, Any]]:
    """Split the answer core (excluding reference block) into claim candidates.

    Each factual claim requires an inline citation to be considered gradeable;
    non-claim sentences (apologies, meta-instructions, fallback boilerplate)
    are excluded entirely rather than penalized.
    """
    core = _strip_reference_block_for_claims(answer)
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", core) if s.strip()]

    claims: List[Dict[str, Any]] = []
    counter = 1
    for sentence in sentences:
        if len(sentence) < 15:
            continue
        if _is_non_claim(sentence):
            continue

        citation_ids = sorted({int(c) for c in re.findall(r"\[(\d+)\]", sentence)})
        if not citation_ids:
            # A factual-looking sentence with no citation at all is always
            # UNSUPPORTED — handled by the caller via claim status, not skipped,
            # so it still counts against Citation Support Rate.
            claims.append(
                {
                    "claim_id": f"claim-{counter:03d}",
                    "text": sentence,
                    "citation_ids": [],
                }
            )
            counter += 1
            continue

        claims.append(
            {
                "claim_id": f"claim-{counter:03d}",
                "text": sentence,
                "citation_ids": citation_ids,
            }
        )
        counter += 1

    return claims


def _grade_claim(
    claim_text: str,
    citation_ids: List[int],
    source_blocks: Dict[int, str],
    valid_source_ids: set[int],
    sources_by_id: Optional[Dict[int, Dict[str, Any]]] = None,
) -> Tuple[str, float, List[str], str]:
    if not citation_ids:
        return UNSUPPORTED, 0.0, [], "Klaim faktual tanpa sitasi inline."

    if sources_by_id and _claim_mixes_documents(claim_text, citation_ids, sources_by_id):
        return (
            UNSUPPORTED,
            0.0,
            [],
            "Klaim mencampurkan sitasi dari dokumen berbeda seolah-olah satu ketentuan yang sama.",
        )

    invalid_ids = [cid for cid in citation_ids if cid not in valid_source_ids]
    if invalid_ids and len(invalid_ids) == len(citation_ids):
        return (
            UNSUPPORTED,
            0.0,
            [],
            f"Seluruh sitasi {invalid_ids} tidak merujuk sumber yang valid.",
        )

    cited_text = "\n".join(source_blocks.get(cid, "") for cid in citation_ids if cid in valid_source_ids)
    claim_body = re.sub(r"\[\d+\]", "", claim_text)
    claim_tokens = _grounding_tokens(claim_body)
    source_tokens = _grounding_tokens(cited_text)
    matched_tokens = claim_tokens & source_tokens
    overlap = len(matched_tokens) / len(claim_tokens) if claim_tokens else 0.0

    if not cited_text:
        return UNSUPPORTED, overlap, sorted(matched_tokens)[:12], "Sumber yang dikutip tidak memiliki konten yang bisa diverifikasi."

    if overlap >= SUPPORTED_OVERLAP_THRESHOLD and len(matched_tokens) >= MIN_MATCHED_TOKENS_FOR_SUPPORT:
        # A claim whose numeric value is absent from the cited source can never
        # be fully SUPPORTED — wrong pasal/ayat numbers and quantities are the
        # highest-risk misinformation and word overlap alone cannot catch them.
        missing_numbers = sorted(
            set(re.findall(r"\d+", claim_body)) - set(re.findall(r"\d+", cited_text)),
            key=int,
        )
        if missing_numbers:
            return (
                PARTIALLY_SUPPORTED,
                overlap,
                sorted(matched_tokens)[:12],
                f"Angka {', '.join(missing_numbers)} dalam klaim tidak ditemukan pada sumber yang dikutip.",
            )
        return SUPPORTED, overlap, sorted(matched_tokens)[:12], ""

    if overlap >= PARTIAL_OVERLAP_THRESHOLD and len(matched_tokens) >= 1:
        return (
            PARTIALLY_SUPPORTED,
            overlap,
            sorted(matched_tokens)[:12],
            "Sebagian unsur klaim cocok dengan sumber, tetapi tidak seluruhnya.",
        )

    return UNSUPPORTED, overlap, sorted(matched_tokens)[:12], "Klaim tidak cukup didukung oleh sumber yang dikutip."


def verify_claims(
    answer: str,
    context: str,
    sources: Optional[List[Dict[str, Any]]] = None,
) -> List[ClaimVerdict]:
    """Grade every extractable claim in `answer` against `context`/`sources`.

    This is intentionally deterministic (no extra LLM roundtrip) to keep
    latency and auditability predictable, matching the rest of the LLM09
    guardrail stack.
    """
    sources = sources or []
    sources_by_id: Dict[int, Dict[str, Any]] = {}
    for src in sources:
        source_id = _coerce_source_id(src.get("id"))
        if source_id is not None:
            sources_by_id[source_id] = src
    valid_source_ids = set(sources_by_id)
    raw_blocks = _build_context_source_blocks(context)

    # LLM09 review fix K1: citations in the answer use RENUMBERED ids while the
    # context string keeps the retrieval-layer numbering. Resolve each cited id
    # to its original context block (via original_id) and fall back to the
    # source's own snippet when that block is unavailable — otherwise claims
    # are graded against the wrong source text.
    source_blocks: Dict[int, str] = {}
    for cid, src in sources_by_id.items():
        original_id = _coerce_source_id(src.get("original_id"))
        block_id = original_id if original_id is not None else cid
        block_text = raw_blocks.get(block_id, "")
        if not block_text:
            block_text = str(src.get("snippet") or "")
        source_blocks[cid] = block_text

    verdicts: List[ClaimVerdict] = []
    for claim in extract_claims(answer):
        status, overlap, matched, reason = _grade_claim(
            claim["text"], claim["citation_ids"], source_blocks, valid_source_ids, sources_by_id
        )
        verdicts.append(
            ClaimVerdict(
                claim_id=claim["claim_id"],
                text=claim["text"],
                citation_ids=claim["citation_ids"],
                status=status,
                overlap=round(overlap, 4),
                matched_terms=matched,
                reason=reason,
            )
        )

    return verdicts


def apply_verifier_edits(answer: str, verdicts: List[ClaimVerdict]) -> Tuple[str, bool]:
    """Remove UNSUPPORTED claim sentences from `answer`.

    Returns (edited_answer, has_remaining_substantive_claim). When the second
    value is False, the caller MUST replace the answer with a safe fallback —
    an answer with nothing left after verification is not safe to ship, even
    if it looks non-empty (e.g., only headers/boilerplate remain).
    """
    unsupported_texts = {v.text for v in verdicts if v.status == UNSUPPORTED}
    remaining = any(v.status in (SUPPORTED, PARTIALLY_SUPPORTED) for v in verdicts)
    if not unsupported_texts:
        return answer, remaining

    full_answer = answer or ""
    header_match = _REFERENCE_HEADER_PATTERN.search(full_answer)
    if header_match:
        core = full_answer[: header_match.start()]
        reference_suffix = full_answer[header_match.start():]
    else:
        core = full_answer
        reference_suffix = ""

    # LLM09 review fix H4: remove unsupported claims per whole SENTENCE while
    # keeping the original newline/list formatting. Removal is by exact match
    # of the stripped sentence — never by raw substring search, which could
    # excise the unsupported text from inside a longer supported sentence.
    edited_lines: List[str] = []
    for line in core.split("\n"):
        segments = re.split(r"((?<=[.!?])\s+)", line)
        kept_parts: List[str] = []
        index = 0
        while index < len(segments):
            sentence = segments[index]
            separator = segments[index + 1] if index + 1 < len(segments) else ""
            if sentence.strip() and sentence.strip() in unsupported_texts:
                pass  # drop the sentence together with its trailing separator
            else:
                kept_parts.append(sentence)
                kept_parts.append(separator)
            index += 2
        edited_lines.append("".join(kept_parts))
    edited_core = "\n".join(edited_lines)

    # Drop list markers whose sentence was removed and collapse leftover blank runs.
    edited_core = re.sub(r"(?m)^[ \t]*(?:\d+[\.)]|[-*])[ \t]*$\n?", "", edited_core)
    edited_core = re.sub(r"[ \t]+(?=\n)", "", edited_core)
    edited_core = re.sub(r"\n{3,}", "\n\n", edited_core).strip()

    if not edited_core:
        logger.info("[LLM09 Verifier] All claims removed after grading; caller should fall back")
        return "", False

    edited_answer = f"{edited_core}\n\n{reference_suffix}" if reference_suffix else edited_core
    return edited_answer, remaining


def summarize_verdicts(verdicts: List[ClaimVerdict]) -> Dict[str, Any]:
    """Compact summary for logging/persistence — used by observability + CSR metric."""
    counts = {SUPPORTED: 0, PARTIALLY_SUPPORTED: 0, UNSUPPORTED: 0}
    for v in verdicts:
        counts[v.status] = counts.get(v.status, 0) + 1

    return {
        "claim_count": len(verdicts),
        "supported_claims": counts[SUPPORTED],
        "partially_supported_claims": counts[PARTIALLY_SUPPORTED],
        "unsupported_claims": counts[UNSUPPORTED],
        "claims": [
            {
                "claim_id": v.claim_id,
                "text": v.text,
                "citation_ids": v.citation_ids,
                "status": v.status,
                "overlap": v.overlap,
                "reason": v.reason,
            }
            for v in verdicts
        ],
    }
