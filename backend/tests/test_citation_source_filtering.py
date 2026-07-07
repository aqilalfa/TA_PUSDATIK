from app.core.formatting import append_citation_reference_block, renumber_citations_and_sources


SOURCES = [
    {"id": 1, "document": "Dokumen 1", "section": "Pasal 1"},
    {"id": 2, "document": "Dokumen 2", "section": "Pasal 2"},
    {"id": 3, "document": "Dokumen 3", "section": "Pasal 3"},
    {"id": 4, "document": "Dokumen 4", "section": "Pasal 4"},
    {"id": 5, "document": "Dokumen 5", "section": "Pasal 5"},
]


def test_renumber_citations_and_sources_uses_ieee_style_sequence():
    answer = "Domain SPBE dijelaskan pada sumber [4], [2], dan [5]."

    renumbered_answer, renumbered_sources = renumber_citations_and_sources(answer, SOURCES)

    assert renumbered_answer == "Domain SPBE dijelaskan pada sumber [1], [2], dan [3]."
    assert [source["id"] for source in renumbered_sources] == [1, 2, 3]
    assert [source["original_id"] for source in renumbered_sources] == [4, 2, 5]
    assert [source["document"] for source in renumbered_sources] == ["Dokumen 4", "Dokumen 2", "Dokumen 5"]


def test_renumber_citations_and_sources_returns_empty_without_inline_citations():
    answer = "Domain SPBE dijelaskan tanpa sitasi inline.\n\nReferensi Dokumen:\n[1] Dokumen 1"

    renumbered_answer, renumbered_sources = renumber_citations_and_sources(answer, SOURCES)

    assert renumbered_answer == "Domain SPBE dijelaskan tanpa sitasi inline."
    assert renumbered_sources == []



def test_append_citation_reference_block_lists_only_renumbered_cited_sources():
    answer = "Domain SPBE dijelaskan pada sumber [4], [2], dan [5]."
    renumbered_answer, renumbered_sources = renumber_citations_and_sources(answer, SOURCES)

    with_reference_block = append_citation_reference_block(renumbered_answer, renumbered_sources)

    assert "Domain SPBE dijelaskan pada sumber [1], [2], dan [3]." in with_reference_block
    assert "[1] Dokumen 4" in with_reference_block
    assert "[2] Dokumen 2" in with_reference_block
    assert "[3] Dokumen 5" in with_reference_block
    assert "Dokumen 1" not in with_reference_block
    assert "Dokumen 3" not in with_reference_block


def test_append_citation_reference_block_does_not_add_decorative_sources():
    answer = "Domain SPBE dijelaskan tanpa sitasi inline."

    assert append_citation_reference_block(answer, SOURCES) == answer
