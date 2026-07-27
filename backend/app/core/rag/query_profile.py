from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal, cast

from app.core.rag.prompts import _classify_question_type

RetrievalType = Literal["general", "pasal", "table", "indikator", "relational"]
AnswerType = Literal[
    "purpose",
    "definition",
    "actor",
    "value_or_time",
    "list",
    "explanation",
    "direct_fact",
    "general",
]
QueryScope = Literal["national", "bssn", "unspecified"]


@dataclass(frozen=True)
class QueryProfile:
    retrieval_type: RetrievalType
    answer_type: AnswerType
    scope: QueryScope


def _classify_retrieval_type(query: str) -> RetrievalType:
    normalized = str(query or "").lower()
    # Specific legal/table/indikator references stay prioritized so grounding
    # rules (SYSTEM_PROMPT_LEGAL, 32-candidate rerank) are not weakened when a
    # relational keyword ("hubungan Pasal X dengan Y") also appears.
    if re.search(r"\btabel\b|\btable\b", normalized):
        return "table"
    if re.search(r"\bindikator\b|\bid[-\s]*\d+", normalized):
        return "indikator"
    if re.search(r"\bpasal\b|\bayat\b|\bperpres\b|\bpermenpan\b|\bpp\s*\d+\b|\bse\s+menteri\b", normalized):
        return "pasal"
    if re.search(r"\b(?:hubungan|kaitan|relasi|perbandingan|dibandingkan|korelasi)\b", normalized):
        return "relational"
    return "general"


def classify_query_profile(query: str) -> QueryProfile:
    normalized = " ".join(str(query or "").lower().split())
    if "bssn" in normalized:
        scope: QueryScope = "bssn"
    elif "spbe" in normalized:
        scope = "national"
    else:
        scope = "unspecified"

    return QueryProfile(
        retrieval_type=_classify_retrieval_type(query),
        answer_type=cast(AnswerType, _classify_question_type(query)),
        scope=scope,
    )
