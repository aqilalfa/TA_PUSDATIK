import pytest
from pydantic import ValidationError

from app.core.rag.engine.llm_client import build_ollama_options
from app.models.schemas import ChatRequest


def test_chat_request_accepts_only_production_model():
    request = ChatRequest(message="uji", model="qwen3.5:4b")
    assert request.model == "qwen3.5:4b"

    with pytest.raises(ValidationError):
        ChatRequest(message="uji", model="qwen2.5:3b-instruct")


def test_chat_request_defaults_to_production_model():
    request = ChatRequest(message="uji")
    assert request.model == "qwen3.5:4b"


def test_ollama_options_use_requested_max_tokens():
    options = build_ollama_options(max_tokens=128)
    assert options["num_predict"] == 128
    assert options["num_ctx"] == 8192
    assert options["temperature"] == 0.1
