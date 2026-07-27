import pytest
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))
from evaluate_llm09_v4 import evaluate_response, calculate_metrics

def test_evidence_based_abstention():
    response = {
        "id": "test-eba",
        "response": {
            "answer": "Informasi tersebut tidak ditemukan dalam dokumen.",
            "sources": [],
            "model_used": "qwen3.5:9b"
        }
    }
    gold_label = {
        "id": "test-eba",
        "answerable": False,
        "should_fallback": True,
        "allowed_final_behaviors": ["safe_fallback"]
    }
    res = evaluate_response(response, gold_label)
    assert res["actual_final_behavior"] == "evidence_based_abstention"
    assert res["final_outcome"] == "correct_fallback"

def test_citation_support_rate_is_null_if_not_evaluated():
    res1 = {"final_outcome": "not_evaluated", "not_evaluated_claims": 1, "supported_claims": 1, "should_fallback": False, "answerable": True}
    res2 = {"final_outcome": "supported_answer", "supported_claims": 2, "not_evaluated_claims": 0, "should_fallback": False, "answerable": True}
    metrics = calculate_metrics([res1, res2])
    # The requirement: "Citation Support Rate menjadi null apabila masih ada not_evaluated"
    assert metrics["main_metrics"]["citation_support_rate"]["value"] is None

def test_safe_fallback_accuracy_only_counts_should_fallback_true():
    # One false refusal (should_fallback=False, but fell back) -> This should NOT be in the denominator for SFA
    res1 = {"final_outcome": "false_refusal", "should_fallback": False, "answerable": True}
    # One correct fallback (should_fallback=True, fell back) -> Numerator=1, Denominator=1
    res2 = {"final_outcome": "correct_fallback", "should_fallback": True, "answerable": False}
    
    metrics = calculate_metrics([res1, res2])
    assert metrics["main_metrics"]["safe_fallback_accuracy"]["denominator"] == 1
    assert metrics["main_metrics"]["safe_fallback_accuracy"]["numerator"] == 1
    assert metrics["main_metrics"]["safe_fallback_accuracy"]["value"] == 1.0
    
def test_table_headers_are_ignored():
    from evaluate_llm09_v4 import clean_answer_text
    ans = "Ini jawabannya.\n| Kolom 1 | Kolom 2 |\n|---|---|\n| Data | Data |\nTabel 1: Data SPBE\nFakta berikutnya."
    cleaned = clean_answer_text(ans)
    assert "| Kolom 1 | Kolom 2 |" not in cleaned
    assert "Tabel 1: Data SPBE" not in cleaned
    assert "Ini jawabannya" in cleaned
    assert "Fakta berikutnya" in cleaned

def test_abbreviation_not_split():
    from evaluate_llm09_v4 import sentence_split
    text = "Peraturan Menteri PANRB No. 59 Tahun 2020. Ini kalimat dua. Prof. Budi berkata."
    sentences = sentence_split(text)
    assert len(sentences) == 3
    assert sentences[0] == "Peraturan Menteri PANRB No. 59 Tahun 2020."
    assert sentences[2] == "Prof. Budi berkata."

def test_list_items_combined():
    from evaluate_llm09_v4 import sentence_split
    text = "Syaratnya adalah:\n- Satu\n- Dua\n- Tiga."
    sentences = sentence_split(text)
    # The logic replaces '\n- ' with ' ' so it becomes one big sentence
    assert len(sentences) == 1
    assert "Syaratnya adalah: Satu Dua Tiga." in sentences[0]
