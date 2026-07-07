import os
import sys


sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_unauthorized_retrieval_matrix_blocks_every_probe():
    """LLM08 evidence matrix must show no unauthorized retrieval bypass."""
    from scripts.llm08_evidence_audit import build_unauthorized_retrieval_matrix

    rows = build_unauthorized_retrieval_matrix()

    assert len(rows) >= 5
    assert all(row["status"] == "PASS" for row in rows)
    assert all(row["actual_leaked_items"] == 0 for row in rows)


def test_citation_leak_rate_counts_only_forbidden_cited_sources():
    """Citation leak rate must count cited forbidden sources, not merely retrieved ones."""
    from scripts.llm08_evidence_audit import calculate_citation_leak_rate

    result = calculate_citation_leak_rate(
        answer="Ringkasan memakai sumber evaluator [1], bukan admin.",
        sources=[
            {"id": 1, "doc_id": "eval-doc", "allowed_roles": ["staff"]},
            {"id": 2, "doc_id": "admin-doc", "allowed_roles": ["admin_pusdatik"]},
        ],
        forbidden_doc_ids={"admin-doc"},
    )

    assert result == {
        "total_cited_sources": 1,
        "forbidden_cited_sources": 0,
        "citation_leak_rate": 0.0,
        "status": "PASS",
    }


def test_metadata_completeness_summary_reports_rates_by_storage():
    """Metadata completeness must be computed per storage surface."""
    from scripts.llm08_evidence_audit import summarize_metadata_completeness

    rows = summarize_metadata_completeness(
        {
            "SQLite documents": [
                {"allowed_roles": ["admin_pusdatik"], "classification": "internal", "source_hash": "sha256:abc"},
                {"allowed_roles": ["staff"], "classification": "internal", "source_hash": "sha256:def"},
            ],
            "Qdrant payload": [
                {"allowed_roles": ["admin_pusdatik"], "classification": "restricted_audit", "source_hash": "sha256:ghi"},
            ],
        }
    )

    assert rows == [
        {
            "storage": "SQLite documents",
            "total_checked": 2,
            "complete": 2,
            "missing": 0,
            "completeness_rate": 100.0,
            "status": "PASS",
        },
        {
            "storage": "Qdrant payload",
            "total_checked": 1,
            "complete": 1,
            "missing": 0,
            "completeness_rate": 100.0,
            "status": "PASS",
        },
    ]


def test_malicious_chunk_scenario_blocks_poisoned_admin_context_for_evaluator():
    """A poisoned admin-only chunk must not enter evaluator retrieval context/citations."""
    from scripts.llm08_evidence_audit import run_malicious_chunk_scenario

    result = run_malicious_chunk_scenario()

    assert result["status"] == "PASS"
    assert result["retrieved_by_evaluator"] is False
    assert result["entered_llm_context"] is False
    assert result["leaked_as_citation"] is False
