import httpx
import json as _json
import time
from typing import List, AsyncIterator, Dict, Any
from loguru import logger
from langchain_core.messages import SystemMessage, AIMessage

from app.config import settings
from app.core.rag.prompts import (
    SYSTEM_PROMPT_TABLE,
    SYSTEM_PROMPT_LEGAL,
    SYSTEM_PROMPT_GENERAL,
)
from app.core.rag.guardrails import build_quality_guardrail

def _role(msg) -> str:
    """Convert LangChain message objects to Ollama role strings."""
    if isinstance(msg, SystemMessage):
        return "system"
    if isinstance(msg, AIMessage):
        return "assistant"
    return "user"

async def stream_answer(
    query: str, 
    context: str, 
    history: List, 
    model_name: str, 
    query_type: str = "general"
) -> AsyncIterator[str]:
    """
    Stream LLM answer token by token via direct Ollama /api/chat call.
    Bypassing LangChain-Ollama ensures fast First Token delivery.
    """
    _PROMPT_MAP = {
        "table": SYSTEM_PROMPT_TABLE,
        "pasal": SYSTEM_PROMPT_LEGAL,
        "indikator": SYSTEM_PROMPT_LEGAL,
        "general": SYSTEM_PROMPT_GENERAL,
    }
    
    system_prompt = _PROMPT_MAP.get(query_type, SYSTEM_PROMPT_GENERAL)
    system_content = system_prompt + "\n\nKonteks Referensi:\n" + context

    ollama_messages = [{"role": "system", "content": system_content}]
    for msg in history:
        ollama_messages.append({"role": _role(msg), "content": msg.content})

    quality_guardrail = build_quality_guardrail(query, context)
    user_content = f"Pertanyaan: {query}"
    if quality_guardrail:
        user_content += f"\n\n{quality_guardrail}"
    ollama_messages.append({"role": "user", "content": user_content})

    options: dict = {
        "temperature": 0.1, 
        "num_predict": 1024,
        "num_ctx": 8192  # Raised from 4096 — 5 docs + system prompt + history needs ~3000+ tokens
    }
    
    # Robust thinking model detection — includes qwen3 family (qwen3:4b, qwen3.5, etc.)
    is_thinking_model = any(kw in model_name.lower() for kw in ["qwen3", "qwen3.5", "r1"])
    extra_params: dict = {}
    if is_thinking_model:
        # Some versions use 'think', some don't. We'll be conservative.
        extra_params["think"] = False

    logger.info(
        f"[LLM] Streaming {model_name} via Ollama API "
        f"({len(ollama_messages)} msgs, ctx {len(context)} chars, ctx_limit=4096)..."
    )

    url = f"{settings.OLLAMA_BASE_URL}/api/chat"
    payload = {
        "model": model_name, 
        "messages": ollama_messages, 
        "stream": True, 
        "options": options,
        **extra_params
    }

    t_llm_start = time.perf_counter()
    async with httpx.AsyncClient(timeout=600.0) as client:
        async with client.stream("POST", url, json=payload) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line:
                    continue
                try:
                    data = _json.loads(line)
                except _json.JSONDecodeError:
                    continue
                
                content = data.get("message", {}).get("content", "")
                if content:
                    yield content

    total_time = time.perf_counter() - t_llm_start
    logger.info(f"[LLM] Response stream completed in {total_time:.2f}s")
