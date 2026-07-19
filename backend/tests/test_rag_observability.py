import json
import inspect

from app.core.rag.observability import RagTrace
from app.core.rag.langchain_engine import LangchainRAGEngine


def test_rag_trace_emits_sanitized_structured_stage(caplog):
    caplog.set_level("INFO", logger="app.rag.trace")
    trace = RagTrace.create(
        session_id="session-1",
        user_id=42,
        query="Apa tujuan Tata Kelola SPBE? token-super-rahasia",
    )

    trace.stage(
        "query.classified",
        retrieval_type="general",
        answer_type="purpose",
        status="ok",
        access_token="must-not-be-logged",
        context="full sensitive context must not be logged",
    )

    record = json.loads(caplog.records[-1].message)
    assert record["request_id"] == trace.request_id
    assert record["stage"] == "query.classified"
    assert record["session_id"] == "session-1"
    assert record["user_id"] == 42
    assert record["query_hash"] == trace.query_hash
    assert "query_preview" not in record
    assert "access_token" not in record
    assert "context" not in record
    assert "must-not-be-logged" not in caplog.text
    assert "full sensitive context" not in caplog.text
    assert "token-super-rahasia" not in caplog.text


def test_rag_trace_stage_keeps_only_safe_nested_fields(caplog):
    caplog.set_level("INFO", logger="app.rag.trace")
    trace = RagTrace.create(session_id=None, user_id=None, query="uji")

    trace.stage(
        "fusion.rrf.completed",
        status="ok",
        elapsed_ms=12.5,
        output_count=2,
        documents=[
            {
                "doc_id": "6",
                "rank": 1,
                "score": 0.12,
                "content": "secret document body",
            }
        ],
    )

    record = json.loads(caplog.records[-1].message)
    assert record["documents"] == [{"doc_id": "6", "rank": 1, "score": 0.12}]
    assert "secret document body" not in caplog.text


def test_rag_trace_snapshot_contains_sanitized_stage_records():
    trace = RagTrace.create(session_id="session-1", user_id=42, query="uji")
    trace.stage("query.classified", status="ok", context="secret")

    snapshot = trace.snapshot()

    assert snapshot["request_id"] == trace.request_id
    assert snapshot["stages"][0]["stage"] == "query.classified"
    assert "context" not in snapshot["stages"][0]


def test_retrieval_logging_does_not_include_raw_query_preview():
    source = inspect.getsource(LangchainRAGEngine.retrieve_context)

    assert "query[:" not in source
    assert "query_preview" not in source
