from app.core.rag.retry_policy import bounded_retry_limit, should_retry_quality


def test_retry_limit_is_bounded_to_two():
    assert bounded_retry_limit(None) == 2
    assert bounded_retry_limit(9) == 2
    assert bounded_retry_limit(-1) == 0


def test_quality_retry_allows_only_quality_failures():
    assert should_retry_quality({"needs_retry": True}, attempt=0, limit=2, outcome="quality") is True
    assert should_retry_quality({"needs_retry": True}, attempt=1, limit=2, outcome="quality") is True
    assert should_retry_quality({"needs_retry": True}, attempt=2, limit=2, outcome="quality") is False


def test_quality_retry_skips_security_no_evidence_and_infrastructure():
    for outcome in ("security", "no_evidence", "infrastructure"):
        assert should_retry_quality({"needs_retry": True}, attempt=0, limit=2, outcome=outcome) is False
