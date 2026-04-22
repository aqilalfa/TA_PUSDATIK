import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))


def _entry(id_, expected, baseline_actual=None):
    return {
        "id": id_,
        "request": {"message": "dummy"},
        "expected": expected,
        "baseline_actual": baseline_actual or {"score": 25, "source_count": 5, "answer_length": 500},
    }


def _resp(answer="", sources=None, score=25, has_unavailable=False):
    return {
        "answer": answer,
        "sources": sources or [],
        "quality_check": {"score": score, "has_unavailable_claim": has_unavailable},
    }


def test_pass_when_all_expectations_met():
    import eval_regression_check as m
    entry = _entry("x", {"answer_must_contain_any": ["foo"], "min_score": 20, "has_unavailable_claim": False})
    res = m.evaluate_one(entry, _resp(answer="lorem foo ipsum"))
    assert res["pass"] is True
    assert res["reasons"] == []


def test_fail_on_missing_keyword():
    import eval_regression_check as m
    entry = _entry("x", {"answer_must_contain_any": ["foo", "bar"]})
    res = m.evaluate_one(entry, _resp(answer="lorem ipsum"))
    assert res["pass"] is False
    assert any("missing" in r for r in res["reasons"])


def test_fail_on_leakage_by_doc_id():
    import eval_regression_check as m
    entry = _entry("x", {"sources_allowed_doc_ids": [3]})
    bad = _resp(sources=[{"doc_id": "3"}, {"doc_id": "1"}])
    res = m.evaluate_one(entry, bad)
    assert res["pass"] is False
    assert any("leakage" in r.lower() or "allowed" in r.lower() for r in res["reasons"])


def test_pass_on_exact_allowed_doc_ids():
    import eval_regression_check as m
    entry = _entry("x", {"sources_allowed_doc_ids": [6]})
    ok = _resp(sources=[{"doc_id": "6"}, {"doc_id": "6"}])
    res = m.evaluate_one(entry, ok)
    assert res["pass"] is True


def test_fail_on_score_below_min():
    import eval_regression_check as m
    entry = _entry("x", {"min_score": 20})
    res = m.evaluate_one(entry, _resp(score=15))
    assert res["pass"] is False


def test_fail_on_unavailable_mismatch():
    import eval_regression_check as m
    entry = _entry("x", {"has_unavailable_claim": True})
    res = m.evaluate_one(entry, _resp(has_unavailable=False))
    assert res["pass"] is False


def test_regression_on_score_drop_more_than_15pct():
    import eval_regression_check as m
    entry = _entry("x", {"min_score": 0}, baseline_actual={"score": 20, "source_count": 5, "answer_length": 500})
    # 15% of 20 = 3.0 → anything <17 is regression
    res = m.check_regression(entry, _resp(score=16))
    assert res["regression"] is True
    entry2 = _entry("y", {"min_score": 0}, baseline_actual={"score": 20, "source_count": 5, "answer_length": 500})
    res2 = m.check_regression(entry2, _resp(score=18))
    assert res2["regression"] is False
