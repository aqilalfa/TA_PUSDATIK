import pytest
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))
from evaluate_llm09_v5 import (
    evaluate_response,
    calculate_metrics,
    extract_claims,
    matches_evidence_abstention_patterns,
    is_negative_existential,
    has_citation_placeholder
)

def test_p1_evidence_based_abstention_regex():
    # Production template pattern matching
    ans1 = "Informasi mengenai arsitektur SPBE tidak ditemukan dalam dokumen yang tersedia."
    assert matches_evidence_abstention_patterns(ans1) is True

    ans2 = "Dokumen referensi yang tersedia tidak memuat informasi mengenai anggaran SPBE."
    assert matches_evidence_abstention_patterns(ans2) is True

    ans3 = "Sistem ini hanya membahas tata kelola tanpa menyebutkan audit keamanan."
    assert matches_evidence_abstention_patterns(ans3) is True

    ans4 = "Ini adalah jawaban biasa dengan informasi lengkap [1]."
    assert matches_evidence_abstention_patterns(ans4) is False


def test_p2_claim_status_always_not_evaluated_initially():
    sources = [{"id": 1}]
    answer = "Sistem SPBE diatur oleh Peraturan Presiden No. 95 Tahun 2018."
    claims = extract_claims(answer, sources)
    assert len(claims) == 1
    assert claims[0]["status"] == "not_evaluated"
    assert claims[0]["requires_citation"] is True
    assert claims[0]["has_inline_citation"] is False


def test_p3_missing_fallback_outcome():
    response = {
        "id": "test-mf",
        "response": {
            "answer": "Berikut penjelasan mengenai sistem SPBE [1].",
            "sources": [{"id": 1, "content": "teks"}]
        }
    }
    gold_label = {
        "id": "test-mf",
        "answerable": False,
        "should_fallback": True,
        "allowed_final_behaviors": ["safe_fallback"]
    }
    res = evaluate_response(response, gold_label)
    assert res["final_outcome"] == "missing_fallback"
    assert res["actual_final_behavior"] == "substantive_answer"
    assert any("should_fallback=true" in r for r in res["reasons"])


def test_p4_negative_existential_not_applicable():
    sources = [{"id": 1}]
    answer = "Informasi mengenai audit SPBE tidak ditemukan dalam dokumen yang tersedia."
    claims = extract_claims(answer, sources)
    assert len(claims) == 1
    assert claims[0]["status"] == "not_applicable"
    assert claims[0]["requires_citation"] is False


def test_citation_placeholder_detection():
    assert has_citation_placeholder("Berikut informasinya [n].") is True
    assert has_citation_placeholder("Data dari sumber [x].") is True
    assert has_citation_placeholder("Referensi resmi [1].") is False


def test_citation_support_rate_is_null_if_not_evaluated():
    res1 = {"final_outcome": "not_evaluated", "not_evaluated_claims": 1, "supported_claims": 1, "unsupported_claims": 0, "partially_supported_claims": 0, "should_fallback": False, "answerable": True}
    res2 = {"final_outcome": "supported_answer", "supported_claims": 2, "not_evaluated_claims": 0, "unsupported_claims": 0, "partially_supported_claims": 0, "should_fallback": False, "answerable": True}
    metrics = calculate_metrics([res1, res2])
    assert metrics["main_metrics"]["citation_support_rate"]["value"] is None
    assert metrics["main_metrics"]["citation_support_rate"]["pending_claims"] == 1


def test_safe_fallback_accuracy_only_counts_should_fallback_true():
    res1 = {"final_outcome": "false_refusal", "should_fallback": False, "answerable": True}
    res2 = {"final_outcome": "correct_fallback", "should_fallback": True, "answerable": False}
    
    metrics = calculate_metrics([res1, res2])
    assert metrics["main_metrics"]["safe_fallback_accuracy"]["denominator"] == 1
    assert metrics["main_metrics"]["safe_fallback_accuracy"]["numerator"] == 1
    assert metrics["main_metrics"]["safe_fallback_accuracy"]["value"] == 1.0
