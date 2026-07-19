from __future__ import annotations

from typing import Any, Mapping

MAX_QUALITY_RETRIES = 2
NON_RETRYABLE_OUTCOMES = frozenset({"security", "no_evidence", "infrastructure", "cancelled"})


def bounded_retry_limit(requested: int | None) -> int:
    if requested is None:
        return MAX_QUALITY_RETRIES
    return max(0, min(MAX_QUALITY_RETRIES, int(requested)))


def should_retry_quality(
    quality: Mapping[str, Any],
    *,
    attempt: int,
    limit: int,
    outcome: str = "quality",
) -> bool:
    if outcome in NON_RETRYABLE_OUTCOMES:
        return False
    return bool(quality.get("needs_retry")) and attempt < bounded_retry_limit(limit)
