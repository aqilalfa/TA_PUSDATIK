# backend/tests/test_quality_scoring.py
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import inspect
import pytest


def test_quality_report_signature_has_no_required_stages_param():
    """After cleanup, _build_answer_quality_report must NOT accept required_stages."""
    from app.api.routes.chat import _build_answer_quality_report
    sig = inspect.signature(_build_answer_quality_report)
    assert "required_stages" not in sig.parameters


def test_quality_report_has_no_stage_fields():
    """Return dict must not contain deprecated stage fields."""
    from app.api.routes.chat import _build_answer_quality_report
    report = _build_answer_quality_report(
        query="apa isi tabel 13?",
        context="Tabel 13: data nilai 80 [1]",
        answer="Tabel 13 berisi nilai 80 [1].",
        source_count=1,
    )
    for deprecated_key in ("required_stages", "missing_stages", "stage_hits", "has_unavailable_stage_claim"):
        assert deprecated_key not in report, f"deprecated key still present: {deprecated_key}"


def test_quality_report_basic_score_runs():
    """Smoke test: function runs and returns a dict with required keys."""
    from app.api.routes.chat import _build_answer_quality_report
    report = _build_answer_quality_report(
        query="apa itu SPBE?",
        context="SPBE adalah sistem pemerintahan berbasis elektronik [1]",
        answer="SPBE adalah sistem pemerintahan berbasis elektronik [1].",
        source_count=1,
    )
    for key in ("score", "needs_retry", "retry_reasons", "focus_coverage"):
        assert key in report


def test_quality_rank_key_has_no_missing_stages_constraint():
    """_quality_rank_key tuple must not include missing_stages — should have 6 elements."""
    from app.api.routes.chat import _quality_rank_key
    report = {
        "conflicting_unavailable_claim": False,
        "list_structure_ok": True,
        "score": 10,
        "focus_coverage": 0.8,
        "citation_count": 2,
        "answer_length": 300,
    }
    key = _quality_rank_key(report)
    assert isinstance(key, tuple)
    assert len(key) == 6


def test_removed_functions_do_not_exist():
    """Confirm deprecated functions are removed from chat module."""
    import app.api.routes.chat as chat_module
    for fn_name in ("_extract_required_table_stages", "_count_stage_hits", "_has_unavailable_stage_claim"):
        assert not hasattr(chat_module, fn_name), f"deprecated function still exists: {fn_name}"


def test_table_stage_markers_constant_removed():
    """Confirm TABLE_STAGE_MARKERS constant is removed."""
    import app.api.routes.chat as chat_module
    assert not hasattr(chat_module, "TABLE_STAGE_MARKERS")
