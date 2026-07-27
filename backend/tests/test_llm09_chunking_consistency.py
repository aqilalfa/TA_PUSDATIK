"""Unit tests for LLM09 hardening — Tahap B (Chunk metadata-vs-content consistency).

Covers PRD unit test item 5:
    5. metadata pasal tidak sesuai isi
"""

from app.core.ingestion.structured_chunker import (
    _adjust_boundary_for_legal_markers,
    find_metadata_text_mismatches,
    split_text_with_overlap,
)


def test_mismatch_detected_when_pasal_metadata_missing_from_text():
    chunks = [
        {
            "chunk_index": 0,
            "text": "Ini adalah teks tanpa kata pasal.",
            "metadata": {"pasal": "Pasal 7"},
        }
    ]
    mismatches = find_metadata_text_mismatches(chunks)
    assert len(mismatches) == 1
    assert mismatches[0]["type"] == "pasal"
    assert mismatches[0]["declared"] == "Pasal 7"


def test_mismatch_detected_when_ayat_metadata_missing_from_text():
    chunks = [
        {
            "chunk_index": 0,
            "text": "Pasal 7 mengatur hal berikut.",
            "metadata": {"pasal": "Pasal 7", "ayat": "Ayat (3)"},
        }
    ]
    mismatches = find_metadata_text_mismatches(chunks)
    assert len(mismatches) == 1
    assert mismatches[0]["type"] == "ayat"
    assert mismatches[0]["declared"] == "Ayat (3)"


def test_no_mismatch_when_pasal_and_ayat_present_in_text():
    chunks = [
        {
            "chunk_index": 0,
            "text": "Pasal 7 mengatur: \n(3) Ayat ini relevan.",
            "metadata": {"pasal": "Pasal 7", "ayat": "Ayat (3)"},
        }
    ]
    mismatches = find_metadata_text_mismatches(chunks)
    assert len(mismatches) == 0


def test_no_mismatch_for_merged_ayat_range():
    # Ranges like (1)-(3) are skipped from this check because they
    # imply the chunk was merged from multiple ayats.
    chunks = [
        {
            "chunk_index": 0,
            "text": "Pasal 7. (1) A. (2) B. (3) C.",
            "metadata": {"pasal": "Pasal 7", "ayat": "Ayat (1)-(3)"},
        }
    ]
    mismatches = find_metadata_text_mismatches(chunks)
    assert len(mismatches) == 0


def test_boundary_adjustment_pulls_back_before_orphaned_marker():
    # The adjustment only fires when end < text_length (not at the very end).
    # Build text where the candidate end lands mid-split, with orphaned marker.
    body = "Bagian pertama dari kalimat panjang yang diakhiri dengan marker:"
    # The marker is isolated, just the letter/number
    marker = "\na."
    text = body + marker + " Substansi." + " " + "X" * 30  # Ensure text_length > end
    end = len(body) + len(marker)  # Proposed split right after marker
    
    adjusted = _adjust_boundary_for_legal_markers(text, start=0, end=end, text_length=len(text))
    assert adjusted < end  # Should pull back before "\na."
    assert text[adjusted:end].strip().startswith("a.")


def test_split_with_overlap_avoids_orphaning_legal_markers():
    # Provide a text slightly over max_size to force a split
    base = "X" * 90
    text = f"{base} Berikut ketentuan:\n(1)\nSubstansi pertama."
    
    # Cut exactly such that the split logic might be tempted to break after (1)
    chunks = split_text_with_overlap(text, max_size=110, overlap=10)
    
    # We want to ensure that no chunk ends with "\n(1)" without its body,
    # and no chunk starts with "Substansi" disconnected from "(1)"
    for c in chunks:
        if "(1)" in c:
            assert "Substansi" in c
