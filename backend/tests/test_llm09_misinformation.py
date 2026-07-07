import json
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from app.api.routes.chat import _build_llm09_insufficient_context_answer, _build_llm09_safe_fallback
from app.core.rag.prompts import validate_answer


CONTEXT = """
[1] Sumber: Perpres Nomor 95 Tahun 2018
Lokasi: Pasal 1 Ayat (1)
Isi:
Pasal 1 Ayat (1) Sistem Pemerintahan Berbasis Elektronik yang selanjutnya disingkat SPBE adalah penyelenggaraan pemerintahan yang memanfaatkan teknologi informasi dan komunikasi.
---
"""

SOURCES = [
    {
        "id": 1,
        "document": "Perpres Nomor 95 Tahun 2018",
        "section": "Pasal 1 Ayat (1)",
    }
]

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "llm09_misinformation_prompts.json"
REQUIRED_LLM09_CATEGORIES = {
    "unavailable_answer",
    "wrong_pasal_trap",
    "wrong_ayat_trap",
    "citation_bait",
    "cross_document_confusion",
    "partial_context",
    "table_aggregation",
    "source_mismatch",
    "over_answering",
    "out_of_scope_factual_claim",
}


def _load_llm09_fixture():
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def test_llm09_fixture_has_required_schema_and_unique_ids():
    prompts = _load_llm09_fixture()
    ids = [item.get("id") for item in prompts]

    assert len(prompts) >= 20
    assert len(ids) == len(set(ids))
    for item in prompts:
        assert set(item) >= {"id", "category", "prompt", "expected_behavior", "risk"}
        assert item["id"].startswith("llm09-")
        assert item["prompt"].strip()
        assert item["expected_behavior"].strip()
        assert item["risk"].strip()


def test_llm09_fixture_covers_core_misinformation_categories():
    prompts = _load_llm09_fixture()
    categories = {item["category"] for item in prompts}

    assert REQUIRED_LLM09_CATEGORIES <= categories


def test_llm09_fixture_maps_to_current_runtime_safeguards():
    prompts = _load_llm09_fixture()
    expected_behaviors = {item["expected_behavior"] for item in prompts}

    assert "insufficient_context" in expected_behaviors
    assert "require_inline_citations" in expected_behaviors
    assert "detect_source_metadata_mismatch" in expected_behaviors
    assert _build_llm09_insufficient_context_answer()
    assert _build_llm09_safe_fallback({"warnings": ["missing inline citation"]})


def test_llm09_rejects_answer_without_inline_citation():
    result = validate_answer(
        "SPBE adalah penyelenggaraan pemerintahan yang memanfaatkan teknologi informasi dan komunikasi.",
        CONTEXT,
        SOURCES,
    )

    assert result["is_valid"] is False
    assert result["has_citations"] is False
    assert result["confidence"] == "low"
    assert any("sitasi" in warning.lower() for warning in result["warnings"])


def test_llm09_reference_block_does_not_count_as_claim_citation():
    answer = """SPBE adalah penyelenggaraan pemerintahan yang memanfaatkan teknologi informasi dan komunikasi.

Referensi Dokumen:
[1] Perpres Nomor 95 Tahun 2018 | Pasal 1 Ayat (1)"""

    result = validate_answer(answer, CONTEXT, SOURCES)

    assert result["is_valid"] is False
    assert result["has_citations"] is False
    assert result["citation_count"] == 0


def test_llm09_accepts_inline_cited_grounded_answer():
    result = validate_answer(
        "SPBE adalah penyelenggaraan pemerintahan yang memanfaatkan teknologi informasi dan komunikasi [1].",
        CONTEXT,
        SOURCES,
    )

    assert result["is_valid"] is True
    assert result["has_citations"] is True
    assert result["confidence"] == "high"
    assert result["citation_count"] == 1


def test_llm09_rejects_citation_source_metadata_mismatch():
    result = validate_answer(
        "Berdasarkan Pasal 2, SPBE wajib dilaksanakan oleh instansi pusat [1].",
        CONTEXT,
        SOURCES,
    )

    assert result["is_valid"] is False
    assert result["confidence"] == "low"
    assert result["metadata_audit"]["mismatch_count"] >= 1


def test_llm09_safe_fallback_replaces_invalid_generated_answer_with_verification_warning():
    validation = {
        "is_valid": False,
        "has_citations": False,
        "warnings": ["Jawaban tidak memiliki referensi/sitasi inline pada klaim jawaban"],
        "confidence": "low",
        "citation_count": 0,
    }

    fallback = _build_llm09_safe_fallback(validation)

    assert "belum dapat memverifikasi jawaban" in fallback.lower()
    assert "sitasi" in fallback.lower()
    assert "gunakan sumber" not in fallback.lower()
    assert "[1]" not in fallback
