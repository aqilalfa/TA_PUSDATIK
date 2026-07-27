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
    build_answer_style_instructions,
)
from app.core.rag.query_profile import QueryProfile, classify_query_profile
from app.core.rag.guardrails import (
    build_llm01_security_instruction,
    build_quality_guardrail,
    sanitize_untrusted_context,
)

PRODUCTION_MODEL = "qwen3.5:4b"


def build_ollama_options(max_tokens: int = 1024) -> Dict[str, Any]:
    return {
        "temperature": 0.1,
        "num_predict": max_tokens,
        "num_ctx": 8192,
    }


def _role(msg) -> str:
    """Convert LangChain message objects to Ollama role strings."""
    if isinstance(msg, SystemMessage):
        return "system"
    if isinstance(msg, AIMessage):
        return "assistant"
    return "user"


def _scope_instruction(profile: QueryProfile) -> str:
    if profile.scope == "national":
        return "Cakupan nasional: gunakan bukti agregat atau regulasi tingkat nasional; jangan substitusi data khusus BSSN."
    if profile.scope == "bssn":
        return "Cakupan jawaban: fokus pada bukti khusus BSSN; jangan menggeneralisasi menjadi kondisi nasional."
    return "Cakupan jawaban: pertahankan cakupan yang dinyatakan sumber dan jangan membuat generalisasi."


def _build_ollama_messages(
    query: str,
    context: str,
    history: List,
    query_profile: QueryProfile,
    extra_system_instruction: str = "",
) -> List[Dict[str, str]]:
    prompt_map = {
        "table": SYSTEM_PROMPT_TABLE,
        "pasal": SYSTEM_PROMPT_LEGAL,
        "indikator": SYSTEM_PROMPT_LEGAL,
        "general": SYSTEM_PROMPT_GENERAL,
    }
    system_prompt = prompt_map.get(query_profile.retrieval_type, SYSTEM_PROMPT_GENERAL)
    safe_context = sanitize_untrusted_context(context)
    system_content = (
        f"{system_prompt}\n\n{build_llm01_security_instruction()}\n\n"
        f"{build_answer_style_instructions(query)}\n\n{_scope_instruction(query_profile)}\n\n"
    )
    if extra_system_instruction:
        system_content += f"{extra_system_instruction}\n\n"
    system_content += f"Konteks Referensi:\n{safe_context}"
    messages = [{"role": "system", "content": system_content}]
    messages.extend({"role": _role(msg), "content": msg.content} for msg in history)
    quality_guardrail = build_quality_guardrail(query, context)
    user_content = f"Pertanyaan: {query}"
    if quality_guardrail:
        user_content += f"\n\n{quality_guardrail}"
    messages.append({"role": "user", "content": user_content})
    return messages


async def stream_answer(
    query: str, 
    context: str, 
    history: List, 
    model_name: str,
    query_type: str = "general",
    max_tokens: int = 1024,
    extra_system_instruction: str = "",
) -> AsyncIterator[str]:
    """
    Stream LLM answer token by token via direct Ollama /api/chat call.
    Bypassing LangChain-Ollama ensures fast First Token delivery.

    `extra_system_instruction` carries the LLM09 Answerability Gate (Tahap D)
    partial-answer directive when evidence coverage is incomplete.
    """
    query_profile = classify_query_profile(query)
    ollama_messages = _build_ollama_messages(
        query, context, history, query_profile, extra_system_instruction=extra_system_instruction
    )

    if model_name != PRODUCTION_MODEL:
        raise ValueError(f"Unsupported model: {model_name}. Expected {PRODUCTION_MODEL}")

    options = build_ollama_options(max_tokens=max_tokens)
    
    # Robust thinking model detection — includes qwen3 family (qwen3:4b, qwen3.5, etc.)
    is_thinking_model = any(kw in model_name.lower() for kw in ["qwen3", "qwen3.5", "r1"])
    extra_params: dict = {}
    if is_thinking_model:
        # Some versions use 'think', some don't. We'll be conservative.
        extra_params["think"] = False

    logger.info(
        f"[LLM] Streaming {model_name} via Ollama API "
        f"({len(ollama_messages)} msgs, ctx {len(context)} chars, ctx_limit={options['num_ctx']}, max_tokens={max_tokens})..."
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
