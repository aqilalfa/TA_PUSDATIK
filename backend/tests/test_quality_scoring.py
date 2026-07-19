import inspect

from app.api.routes import chat
from app.core.rag.quality_check import build_answer_quality_report


def test_quality_report_signature_has_no_required_stages_param():
    sig = inspect.signature(build_answer_quality_report)
    assert "required_stages" not in sig.parameters


def test_quality_report_has_no_stage_fields():
    report = build_answer_quality_report(
        query="apa isi tabel 13?",
        context="Tabel 13: data nilai 80 [1]",
        answer="- Nilai 80 [1].",
        source_count=1,
    )
    for deprecated_key in (
        "required_stages",
        "missing_stages",
        "stage_hits",
        "has_unavailable_stage_claim",
    ):
        assert deprecated_key not in report


def test_quality_report_basic_score_runs():
    report = build_answer_quality_report(
        query="apa itu SPBE?",
        context="SPBE adalah sistem pemerintahan berbasis elektronik [1]",
        answer="SPBE adalah sistem pemerintahan berbasis elektronik [1].",
        source_count=1,
    )
    for key in ("score", "needs_retry", "retry_reasons", "focus_coverage"):
        assert key in report


def test_atomic_answer_is_not_retried_only_for_being_short():
    report = build_answer_quality_report(
        query="Siapa Pelaksana Audit Keamanan SPBE?",
        context="Tim Audit Keamanan SPBE adalah pelaksana audit.",
        answer="Tim Audit Keamanan SPBE [1].",
        source_count=1,
    )

    assert "jawaban terlalu ringkas" not in report["retry_reasons"]
    assert report["needs_retry"] is False


def test_explanation_answer_can_still_be_retried_when_too_short():
    report = build_answer_quality_report(
        query="Jelaskan proses Audit Keamanan SPBE secara rinci.",
        context="Audit memiliki tahap persiapan, pelaksanaan, dan pelaporan.",
        answer="Audit memiliki beberapa tahap [1].",
        source_count=1,
    )

    assert "jawaban terlalu ringkas" in report["retry_reasons"]


def test_chat_computes_quality_after_final_output_contract():
    source = inspect.getsource(chat.chat_stream)

    quality_position = source.rfind("build_answer_quality_report(")
    output_contract_position = source.rfind("validate_llm_output_contract(")
    save_position = source.rfind("_persist_exchange(")

    assert output_contract_position < quality_position < save_position


def test_removed_quality_helpers_do_not_exist():
    for fn_name in (
        "_extract_required_table_stages",
        "_count_stage_hits",
        "_has_unavailable_stage_claim",
        "_quality_rank_key",
        "_build_answer_quality_report",
    ):
        assert not hasattr(chat, fn_name)


def test_table_stage_markers_constant_removed():
    assert not hasattr(chat, "TABLE_STAGE_MARKERS")
