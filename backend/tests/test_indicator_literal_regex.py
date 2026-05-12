import sys
import re
from pathlib import Path
import pytest

# Add backend to path
sys.path.append(str(Path(__file__).parent.parent))

from app.core.rag.engine.retrievers import HybridRetriever
from app.core.rag.engine.rankers import RAGRanker

def test_indicator_literal_search_regex_variations():
    """
    Test that the regex correctly matches indicator queries with and without 'ke'.
    """
    regex_retriever = r"\b(?:indikator|id)\s*(?:ke[-\s]*)?(\d{1,3})\b"
    
    # Must match:
    queries_should_match = [
        ("indikator 30", "30"),
        ("indikator ke 30", "30"),
        ("indikator ke-30", "30"),
        ("id 30", "30"),
        ("id ke 30", "30"),
        ("jelaskan isi indikator ke 30 yang harus dipenuhi", "30"),
        ("jelaskan mengenai indikator 1", "1")
    ]
    
    for query, expected_id in queries_should_match:
        match = re.search(regex_retriever, query, re.IGNORECASE)
        assert match is not None, f"Regex failed to match valid query: '{query}'"
        assert match.group(1) == expected_id, f"Regex matched wrong ID for '{query}'. Expected {expected_id}, got {match.group(1)}"

    # Must NOT match:
    queries_should_not_match = [
        "pasal 30",
        "tabel 30",
        "indikator xyz"
    ]
    
    for query in queries_should_not_match:
        match = re.search(regex_retriever, query, re.IGNORECASE)
        assert match is None, f"Regex incorrectly matched invalid query: '{query}'"
