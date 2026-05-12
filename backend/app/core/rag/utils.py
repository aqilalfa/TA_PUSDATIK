from typing import List, Any, Optional

def safe_int(value: Any) -> Optional[int]:
    """Best-effort integer conversion for metadata fields."""
    try:
        if value is None or value == "":
            return None
        return int(value)
    except (TypeError, ValueError):
        return None

def append_unique_search_query(queries: List[str], candidate: str):
    """Append candidate query if not already present (case-insensitive)."""
    normalized = " ".join(str(candidate or "").split())
    if not normalized:
        return

    existing = {q.lower() for q in queries}
    if normalized.lower() not in existing:
        queries.append(normalized)

def longest_suffix_prefix_overlap(left: str, right: str, max_window: int = 220) -> int:
    """Return overlap length where suffix(left) == prefix(right)."""
    if not left or not right:
        return 0

    max_len = min(len(left), len(right), max_window)
    for size in range(max_len, 23, -1):
        if left[-size:] == right[:size]:
            return size
    return 0
