from unittest.mock import MagicMock

import pytest
from langchain_core.documents import Document

from app.core.rag.engine.rankers import RAGRanker
from app.core.rag.prompts import validate_answer


def _doc(text: str, doc_id: str, chunk_id: str) -> Document:
    return Document(page_content=text, metadata={"doc_id": doc_id, "chunk_id": chunk_id})


def _ranked_docs(count: int) -> list[Document]:
    docs = [_doc(f"candidate {index}", str(index), str(index)) for index in range(count)]
    for index, doc in enumerate(docs):
        doc.metadata["rrf_score"] = 1.0 - (index * 0.01)
    return docs


def _recording_reranker() -> MagicMock:
    reranker = MagicMock()
    reranker.predict.side_effect = lambda pairs, batch_size: [float(index) for index in range(len(pairs))]
    return reranker


def test_weighted_rrf_bounds_expansion_family_and_traces_contributions():
    ranker = RAGRanker()
    original = [_doc("original hit", "1", "a")]
    expansion_one = [_doc("expansion hit", "2", "b")]
    expansion_two = [_doc("expansion hit", "2", "b")]

    results = ranker.rrf_fusion(
        [original, expansion_one, expansion_two],
        max_candidates=10,
        list_families=["original", "expansion", "expansion"],
        family_weights={"original": 1.0, "expansion": 0.6},
    )

    assert results[0].metadata["doc_id"] == "1"
    assert results[0].metadata["rrf_contributions"][0]["family"] == "original"
    expansion = next(doc for doc in results if doc.metadata["doc_id"] == "2")
    assert sum(item["weighted_score"] for item in expansion.metadata["rrf_contributions"]) <= (0.6 / 61) + 1e-12


def test_rerank_normalizes_cross_encoder_and_clamps_metadata_adjustment():
    reranker = MagicMock()
    reranker.predict.return_value = [-10.0, 10.0]
    ranker = RAGRanker(reranker_instance=reranker)
    ranker.query_metadata_boost = MagicMock(side_effect=[-100.0, 100.0])

    results = ranker.rerank("query", [_doc("a", "1", "a"), _doc("b", "2", "b")], 2)

    assert all(0.0 <= doc.metadata["rerank_base_score"] <= 1.0 for doc in results)
    assert all(-0.15 <= doc.metadata["query_boost"] <= 0.15 for doc in results)


def test_rerank_deduplicates_canonical_chunks_and_caps_two_contexts_per_document():
    ranker = RAGRanker(deduplicate_contexts=True)
    docs = [
        _doc("same", "1", "a"),
        _doc("same", "1", "a"),
        _doc("other", "1", "b"),
        _doc("third", "1", "c"),
        _doc("different doc", "2", "d"),
    ]
    for index, doc in enumerate(docs):
        doc.metadata["rrf_score"] = 1.0 - index * 0.01

    results = ranker.rerank("query", docs, 5)

    assert len([doc for doc in results if doc.metadata["doc_id"] == "1"]) == 2
    assert len({doc.metadata["canonical_context_id"] for doc in results}) == len(results)


def test_rerank_uses_24_cross_encoder_candidates_for_general_queries():
    reranker = _recording_reranker()
    ranker = RAGRanker(reranker_instance=reranker)

    results = ranker.rerank("query", _ranked_docs(40), 5, retrieval_type="general")

    assert len(reranker.predict.call_args.args[0]) == 24
    assert results[0].metadata["rerank_candidate_limit"] == 24
    assert results[0].metadata["rerank_candidate_count"] == 24
    assert results[0].metadata["rerank_candidate_policy"] == "adaptive-default"
    assert results[0].metadata["rerank_elapsed_ms"] >= 0.0


@pytest.mark.parametrize("retrieval_type", ["pasal", "table", "indikator"])
def test_rerank_uses_32_cross_encoder_candidates_for_specialized_queries(retrieval_type):
    reranker = _recording_reranker()
    ranker = RAGRanker(reranker_instance=reranker)

    results = ranker.rerank("query", _ranked_docs(40), 5, retrieval_type=retrieval_type)

    assert len(reranker.predict.call_args.args[0]) == 32
    assert results[0].metadata["rerank_candidate_policy"] == "adaptive-specialized"


def test_rerank_uses_16_candidates_only_at_clear_rrf_boundary():
    reranker = _recording_reranker()
    ranker = RAGRanker(reranker_instance=reranker)
    docs = _ranked_docs(40)
    docs[15].metadata["rrf_score"] = 0.80
    docs[16].metadata["rrf_score"] = 0.50

    results = ranker.rerank("query", docs, 5, retrieval_type="general")

    assert len(reranker.predict.call_args.args[0]) == 16
    assert results[0].metadata["rerank_candidate_policy"] == "adaptive-clear-boundary"


def test_rerank_keeps_24_candidates_when_rrf_boundary_is_not_clear():
    reranker = _recording_reranker()
    ranker = RAGRanker(reranker_instance=reranker)

    ranker.rerank("query", _ranked_docs(40), 5, retrieval_type="general")

    assert len(reranker.predict.call_args.args[0]) == 24


def test_rerank_candidate_limit_override_supports_64_candidate_baseline():
    reranker = _recording_reranker()
    ranker = RAGRanker(reranker_instance=reranker)

    results = ranker.rerank(
        "query",
        _ranked_docs(70),
        5,
        retrieval_type="general",
        candidate_limit_override=64,
    )

    assert len(reranker.predict.call_args.args[0]) == 64
    assert results[0].metadata["rerank_candidate_policy"] == "override"


def test_rerank_without_cross_encoder_keeps_all_candidates():
    ranker = RAGRanker()
    ranker.query_metadata_boost = MagicMock(return_value=0.0)

    results = ranker.rerank("query", _ranked_docs(40), 5, retrieval_type="general")

    assert ranker.query_metadata_boost.call_count == 40
    assert results[0].metadata["rerank_candidate_count"] == 40
    assert results[0].metadata["rerank_candidate_policy"] == "degraded-all"


def test_validation_never_reports_high_confidence_with_zero_checked_claims():
    result = validate_answer("SPBE tersedia [1].", "[1] SPBE tersedia.", [{"id": 1}])
    assert result["metadata_audit"]["checked_claims"] == 0
    assert result["confidence"] != "high"


def test_validation_rejects_unsupported_acronym_expansion():
    result = validate_answer(
        "BSrE adalah Balai Sertifikasi Elektronik [1].",
        "[1] Layanan BSrE tersedia.",
        [{"id": 1}],
    )
    assert result["is_valid"] is False
    assert any("akronim" in warning.lower() for warning in result["warnings"])


def test_validation_rejects_inline_cited_claim_not_supported_by_cited_source():
    result = validate_answer(
        "SPBE menyediakan layanan teleportasi nasional [1].",
        "[1] SPBE adalah penyelenggaraan pemerintahan yang memanfaatkan teknologi informasi dan komunikasi.",
        [{"id": 1}],
    )

    assert result["is_valid"] is False
    assert result["confidence"] == "low"
    assert result["claim_grounding"]["checked_claims"] == 1
    assert result["claim_grounding"]["unsupported_claims"] == 1
