from scripts.collect_llm09_via_api import (
    build_chat_payload,
    collect_responses,
    extract_complete_response,
    parse_sse_events,
    get_bearer_token,
)


def test_build_chat_payload_matches_current_chat_contract():
    item = {"prompt": "Apa aturan SPBE yang tidak ada?"}

    payload = build_chat_payload(item, model_name="qwen-test", session_id="session-1", top_k=3)

    assert payload == {
        "session_id": "session-1",
        "message": "Apa aturan SPBE yang tidak ada?",
        "top_k": 3,
        "use_structured_fact": False,
        "model": "qwen-test",
    }
    assert "use_rag" not in payload


def test_parse_sse_events_extracts_named_events():
    body = 'event: retrieval\ndata: {"count": 2}\n\nevent: token\ndata: {"t": "halo"}\n\n'

    events = parse_sse_events(body)

    assert events == [
        {"event": "retrieval", "data": {"count": 2}},
        {"event": "token", "data": {"t": "halo"}},
    ]


def test_extract_complete_response_prefers_complete_event():
    body = (
        'event: token\ndata: {"t": "draft"}\n\n'
        'event: complete\ndata: {"answer": "final", "sources": [{"id": 1}], "validation": {"is_valid": true}}\n\n'
    )

    response = extract_complete_response(body)

    assert response["answer"] == "final"
    assert response["sources"] == [{"id": 1}]
    assert response["validation"]["is_valid"] is True


def test_extract_complete_response_falls_back_to_tokens():
    body = 'event: token\ndata: {"t": "hello "}\n\nevent: token\ndata: {"t": "world"}\n\n'

    response = extract_complete_response(body)

    assert response["answer"] == "hello world"
    assert response["sources"] == []


def test_get_bearer_token_returns_none_if_no_credentials():
    assert get_bearer_token("http://api", None, "pass") is None
    assert get_bearer_token("http://api", "user", None) is None


def test_get_bearer_token_parses_access_token(monkeypatch):
    import io

    class FakeResponse:
        def read(self):
            return b'{"access_token": "fake-jwt", "token_type": "bearer"}'
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc_val, exc_tb):
            pass

    def fake_urlopen(*args, **kwargs):
        return FakeResponse()

    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    token = get_bearer_token("http://localhost:8000/api/chat/stream", "u", "p")

    assert token == "fake-jwt"
    def fail_post(*_args, **_kwargs):
        raise TimeoutError("slow")

    import scripts.collect_llm09_via_api as module

    monkeypatch.setattr(module, "post_chat_stream", fail_post)
    rows = collect_responses(
        [{"id": "llm09-x", "category": "unavailable_answer", "expected_behavior": "insufficient_context", "prompt": "x"}],
        api_url="http://localhost:8000/api/chat/stream",
        timeout=0.01,
    )

    assert len(rows) == 1
    assert rows[0]["id"] == "llm09-x"
    assert "TimeoutError" in rows[0]["error"]
    assert rows[0]["response"]["answer"] == ""
