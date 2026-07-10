"""
Chat endpoints - placeholder for RAG integration
"""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.dependencies.auth_dependencies import get_current_user, require_roles
from app.auth.login_rate_limiter import chat_rate_limiter
from app.core.security_metrics import security_metrics
from app.core.audit_service import AuditEventType, get_audit_logger
from app.models.db_models import Session as DBSession, Conversation
from app.models.db_models import User
from app.models.schemas import ChatRequest, ChatResponse, ConversationMessage
from app.core.rag.langchain_engine import langchain_engine, classify_query
from app.core.rag.prompts import validate_answer
from app.core.rag.llm09_guard import assess_llm09_pre_generation_guard
from app.core.rag.structured_facts import (
    find_structured_fact_answer,
    format_structured_fact_answer,
)
from app.core.rag.guardrails import PROMPT_INJECTION_REFUSAL, build_security_warning, detect_prompt_injection, scan_llm_output_for_leakage
from app.core.rag.output_guardrails import validate_llm_output_contract
from app.core.formatting import (
    sanitize_citations,
    strip_markdown_emphasis,
    append_citation_reference_block,
    renumber_citations_and_sources,
)
from datetime import datetime
from typing import List, Dict, Any
from loguru import logger
from app.api.routes.models import get_default_model
from functools import partial
import json
import os
import time
import uuid
import re

router = APIRouter()


def _chat_rate_limit_key(request: Request, current_user: User | None) -> str:
    if current_user and current_user.id is not None:
        return f"user:{current_user.id}"
    client_ip = request.client.host if request.client else "unknown"
    return f"ip:{client_ip}"


def _enforce_chat_rate_limit(request: Request, current_user: User | None, endpoint: str) -> None:
    key = _chat_rate_limit_key(request, current_user)
    retry_after = chat_rate_limiter.get_retry_after(key)
    if retry_after is not None:
        security_metrics.increment("http.429", endpoint=endpoint)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many chatbot requests. Please try again later.",
            headers={"Retry-After": str(retry_after)},
        )
    chat_rate_limiter.record_failure(key)


def _audit_llm_security_block(
    db: Session,
    request: Request,
    current_user: User,
    event_type: AuditEventType,
    action: str,
    resource: str,
    categories: list[str],
    prompt_preview: str,
) -> None:
    try:
        audit_logger = get_audit_logger(session=db)
        audit_logger.log_llm_security_event(
            event_type=event_type,
            user_id=getattr(current_user, "id", None),
            username=getattr(current_user, "email", None) or "unknown",
            action=action,
            resource=resource,
            categories=categories,
            prompt_preview=prompt_preview,
            ip_address=request.client.host if request.client else None,
        )
    except Exception as audit_error:
        logger.warning(f"Failed to persist LLM security audit event: {audit_error}")


from app.core.rag.quality_check import (
    build_answer_quality_report,
    find_unavailable_triggers,
)

QUALITY_DEBUG = os.getenv("QUALITY_DEBUG", "").strip() == "1"


def _build_llm09_safe_fallback(validation: Dict[str, Any] | None) -> str:
    """Return a safe user-facing fallback when a generated answer fails LLM09 validation."""
    warnings = []
    if validation:
        warnings = [str(w) for w in validation.get("warnings", []) if str(w).strip()]

    reason = ""
    if warnings:
        reason = f" Alasan validasi: {warnings[0]}."

    return (
        "Maaf, saya belum dapat memverifikasi jawaban ini secara aman berdasarkan "
        f"sitasi inline dan konteks dokumen yang tersedia.{reason} "
        "Silakan ajukan ulang pertanyaan dengan cakupan yang lebih spesifik."
    )


def _build_llm09_insufficient_context_answer() -> str:
    """Return fail-closed answer when retrieval cannot provide verifiable context."""
    return (
        "Maaf, konteks dokumen yang tersedia belum cukup untuk menjawab pertanyaan ini "
        "secara terverifikasi. Silakan ajukan pertanyaan yang lebih spesifik atau pastikan "
        "dokumen sumber yang relevan sudah tersedia dan dapat diakses."
    )


def _build_llm09_guard_validation(reason: str, risk_category: str, details: Dict[str, Any] | None = None) -> Dict[str, Any]:
    return {
        "is_valid": False,
        "has_citations": False,
        "warnings": [reason],
        "confidence": "low",
        "citation_count": 0,
        "source_count": 0,
        "llm09_guard": {
            "blocked": True,
            "risk_category": risk_category,
            "details": details or {},
        },
    }


@router.get("/debug/retrieval")
async def debug_retrieval(query: str, current_user: User = Depends(require_roles(["admin_pusdatik"]))):
    """Debug endpoint to see what chunks are actually retrieved."""
    try:
        results = langchain_engine.retrieve_context(query, current_user=current_user)
        return {
            "query": query,
            "query_type": results.get("query_type"),
            "source_count": len(results.get("sources", [])),
            "docs": [
                {
                    "content": d.page_content[:500],
                    "metadata": d.metadata
                } for d in results.get("raw_docs", [])
            ]
        }
    except Exception as e:
        return {"error": str(e)}

@router.post("/", response_model=ChatResponse)
async def chat(
    http_request: Request,
    request: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Chat endpoint - currently a placeholder
    Will be integrated with RAG pipeline in future implementation
    """
    _enforce_chat_rate_limit(http_request, current_user, "chat")

    # Verify session exists
    session = db.query(DBSession).filter(
        DBSession.id == request.session_id,
        DBSession.user_id == current_user.id,
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Save user message
    user_message = Conversation(
        session_id=request.session_id,
        role="user",
        content=request.message,
        timestamp=datetime.utcnow(),
    )
    db.add(user_message)

    # Return placeholder response for non-streaming
    start_time = time.time()
    response_text = f"Anda bertanya: '{request.message}'. Backend mendukung streaming di endpoint `/api/chat/stream` otomatis."
    latency = int((time.time() - start_time) * 1000)

    assistant_message = Conversation(
        session_id=request.session_id,
        role="assistant",
        content=response_text,
        sources=json.dumps([]),
        timestamp=datetime.utcnow(),
        latency_ms=latency,
    )
    db.add(assistant_message)
    session.updated_at = datetime.utcnow()
    db.commit()

    return ChatResponse(response=response_text, sources=[], latency_ms=latency)

@router.post("/stream")
async def chat_stream(
    http_request: Request,
    request: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Chat endpoint with SSE streaming.
    
    Pipeline:
      1. Save user message to DB
      2. Retrieve relevant documents from Qdrant
      3. Stream LLM answer token by token
      4. Save assistant response to DB
    """
    _enforce_chat_rate_limit(http_request, current_user, "chat/stream")
    model = "qwen3.5:4b"

    async def event_generator():
        try:
            # 1. Session Management
            # Gunakan local variable — jangan mutate Pydantic request model (immutable di v2)
            session_id = request.session_id

            if not session_id:
                new_session_id = str(uuid.uuid4())
                new_session = DBSession(id=new_session_id, user_id=current_user.id, title="New Conversation")
                db.add(new_session)
                db.flush()
                session_id = new_session.id  # simpan ke local var, bukan request.session_id
                db.commit()

            session = db.query(DBSession).filter(
                DBSession.id == session_id,
                DBSession.user_id == current_user.id,
            ).first()
            if not session:
                yield f"event: error\ndata: {json.dumps({'error': 'Session not found'})}\n\n"
                return

            injection_check = detect_prompt_injection(request.message)
            if injection_check.is_blocked:
                latency = 0
                refusal = injection_check.refusal
                logger.warning(
                    "[LLM01] Blocked prompt injection attempt categories={} user_id={}".format(
                        injection_check.categories,
                        getattr(current_user, "id", None),
                    )
                )
                _audit_llm_security_block(
                    db=db,
                    request=http_request,
                    current_user=current_user,
                    event_type=AuditEventType.LLM_PROMPT_INJECTION_BLOCKED,
                    action="prompt_injection_blocked",
                    resource="chat/stream",
                    categories=injection_check.categories,
                    prompt_preview=request.message,
                )
                yield f"event: security\ndata: {json.dumps({'blocked': True, 'categories': injection_check.categories}, ensure_ascii=False)}\n\n"
                yield f"event: token\ndata: {json.dumps({'t': refusal}, ensure_ascii=False)}\n\n"
                complete_data = {
                    "session_id": session_id,
                    "answer": refusal,
                    "sources": [],
                    "timing": {"total_ms": latency},
                    "model_used": "llm01-guardrail",
                    "validation": {
                        "is_valid": True,
                        "has_citations": False,
                        "warnings": [build_security_warning(injection_check.categories)],
                        "confidence": "high",
                        "citation_count": 0,
                    },
                    "security": {
                        "blocked": True,
                        "categories": injection_check.categories,
                    },
                }
                yield f"event: complete\ndata: {json.dumps(complete_data, ensure_ascii=False)}\n\n"
                return

            # Save user message
            user_msg = Conversation(
                session_id=session_id,
                role="user",
                content=request.message,
                timestamp=datetime.utcnow(),
            )
            db.add(user_msg)
            db.commit()

            start_time = time.perf_counter()

            structured_fact = (
                find_structured_fact_answer(request.message)
                if request.use_structured_fact
                else None
            )
            if structured_fact:
                sources_for_response = structured_fact.sources
                full_response = format_structured_fact_answer(structured_fact)

                yield f"event: retrieval\ndata: {json.dumps({'count': len(sources_for_response), 'mode': 'structured_fact'})}\n\n"
                yield f"event: token\ndata: {json.dumps({'t': full_response}, ensure_ascii=False)}\n\n"

                latency = int((time.perf_counter() - start_time) * 1000)
                assistant_message = Conversation(
                    session_id=session_id,
                    role="assistant",
                    content=full_response,
                    sources=json.dumps(sources_for_response),
                    timestamp=datetime.utcnow(),
                    latency_ms=latency,
                )
                db.add(assistant_message)
                session.updated_at = datetime.utcnow()
                try:
                    db.commit()
                except Exception as save_error:
                    db.rollback()
                    logger.warning(
                        "Structured fact response was generated but conversation save failed: {}".format(
                            save_error
                        )
                    )

                complete_data = {
                    "session_id": session_id,
                    "answer": full_response,
                    "sources": sources_for_response,
                    "timing": {"total_ms": latency},
                    "model_used": "structured-fact-index",
                    "validation": {
                        "is_valid": True,
                        "has_citations": True,
                        "warnings": [],
                        "confidence": "high",
                        "citation_count": 1,
                    },
                    "quality_check": {
                        "score": 100,
                        "needs_retry": False,
                        "retry_reasons": [],
                        "focus_coverage": 1.0,
                        "has_unavailable_claim": False,
                        "unavailable_triggers_active": [],
                    },
                    "structured_fact": {
                        "matched_nomor": structured_fact.nomor,
                        "score": structured_fact.score,
                    },
                }
                yield f"event: complete\ndata: {json.dumps(complete_data, ensure_ascii=False)}\n\n"
                return

            # 2. Retrieve context (offload ke thread pool agar tidak block event loop)
            import asyncio
            retrieval = await asyncio.get_event_loop().run_in_executor(
                None,
                partial(
                    langchain_engine.retrieve_context,
                    query=request.message,
                    top_k=request.top_k,
                    use_rag=True,
                    doc_id=request.document_id,
                    current_user=current_user,
                ),
            )

            sources_for_response = retrieval["sources"]
            context = retrieval["context"]
            query_type = retrieval.get("query_type", "general")

            yield f"event: retrieval\ndata: {json.dumps({'count': len(sources_for_response)})}\n\n"

            if not sources_for_response:
                full_response = _build_llm09_insufficient_context_answer()
                latency = int((time.perf_counter() - start_time) * 1000)
                validation = {
                    "is_valid": False,
                    "has_citations": False,
                    "warnings": ["Konteks dokumen yang tersedia belum cukup untuk jawaban terverifikasi"],
                    "confidence": "low",
                    "citation_count": 0,
                    "source_count": 0,
                }
                assistant_message = Conversation(
                    session_id=session_id,
                    role="assistant",
                    content=full_response,
                    sources=json.dumps([]),
                    timestamp=datetime.utcnow(),
                    latency_ms=latency,
                )
                db.add(assistant_message)
                session.updated_at = datetime.utcnow()
                db.commit()

                yield f"event: token\ndata: {json.dumps({'t': full_response}, ensure_ascii=False)}\n\n"
                complete_data = {
                    "session_id": session_id,
                    "answer": full_response,
                    "sources": [],
                    "timing": {"total_ms": latency},
                    "model_used": "llm09-insufficient-context",
                    "validation": validation,
                    "quality_check": {
                        "score": None,
                        "needs_retry": False,
                        "retry_reasons": ["insufficient_context"],
                        "focus_coverage": 0.0,
                        "has_unavailable_claim": True,
                        "unavailable_triggers_active": [],
                    },
                }
                yield f"event: complete\ndata: {json.dumps(complete_data, ensure_ascii=False)}\n\n"
                return

            llm09_guard = assess_llm09_pre_generation_guard(
                request.message,
                context,
                sources_for_response,
            )
            if not llm09_guard.allowed:
                full_response = _build_llm09_insufficient_context_answer()
                latency = int((time.perf_counter() - start_time) * 1000)
                validation = _build_llm09_guard_validation(
                    llm09_guard.reason,
                    llm09_guard.risk_category,
                    llm09_guard.details,
                )
                assistant_message = Conversation(
                    session_id=session_id,
                    role="assistant",
                    content=full_response,
                    sources=json.dumps([]),
                    timestamp=datetime.utcnow(),
                    latency_ms=latency,
                )
                db.add(assistant_message)
                session.updated_at = datetime.utcnow()
                db.commit()

                yield f"event: llm09_guard\ndata: {json.dumps({'blocked': True, 'risk_category': llm09_guard.risk_category, 'reason': llm09_guard.reason}, ensure_ascii=False)}\n\n"
                yield f"event: token\ndata: {json.dumps({'t': full_response}, ensure_ascii=False)}\n\n"
                complete_data = {
                    "session_id": session_id,
                    "answer": full_response,
                    "sources": [],
                    "timing": {"total_ms": latency},
                    "model_used": "llm09-pre-generation-guard",
                    "validation": validation,
                    "quality_check": {
                        "score": None,
                        "needs_retry": False,
                        "retry_reasons": [llm09_guard.risk_category],
                        "focus_coverage": llm09_guard.details.get("focus_coverage"),
                        "has_unavailable_claim": True,
                        "unavailable_triggers_active": [],
                    },
                }
                yield f"event: complete\ndata: {json.dumps(complete_data, ensure_ascii=False)}\n\n"
                return

            # 3. Load chat history menggunakan session_id lokal
            history = await asyncio.get_event_loop().run_in_executor(
                None, langchain_engine.load_history, session_id
            )

            # 4. Stream LLM answer token by token — langsung ke client
            # Collect full text sambil streaming untuk quality check & DB save
            full_response = ""
            selected_quality: Dict[str, Any] = {}

            async for token in langchain_engine.stream_answer(
                query=request.message,
                context=context,
                history=history,
                model_name=model,
                query_type=query_type,
            ):
                candidate_response = full_response + token
                output_check = scan_llm_output_for_leakage(candidate_response)
                if output_check.is_blocked:
                    latency = int((time.perf_counter() - start_time) * 1000)
                    full_response = PROMPT_INJECTION_REFUSAL
                    logger.warning(
                        "[LLM01] Blocked unsafe LLM output categories={} user_id={}".format(
                            output_check.categories,
                            getattr(current_user, "id", None),
                        )
                    )
                    _audit_llm_security_block(
                        db=db,
                        request=http_request,
                        current_user=current_user,
                        event_type=AuditEventType.LLM_UNSAFE_OUTPUT_BLOCKED,
                        action="unsafe_output_blocked",
                        resource="chat/stream",
                        categories=output_check.categories,
                        prompt_preview=candidate_response,
                    )
                    yield f"event: security\ndata: {json.dumps({'blocked': True, 'categories': output_check.categories}, ensure_ascii=False)}\n\n"
                    yield f"event: token\ndata: {json.dumps({'t': full_response}, ensure_ascii=False)}\n\n"
                    complete_data = {
                        "session_id": session_id,
                        "answer": full_response,
                        "sources": [],
                        "timing": {"total_ms": latency},
                        "model_used": "llm01-output-guardrail",
                        "validation": {
                            "is_valid": True,
                            "has_citations": False,
                            "warnings": ["Unsafe LLM output blocked before completion"],
                            "confidence": "high",
                            "citation_count": 0,
                        },
                        "security": {
                            "blocked": True,
                            "categories": output_check.categories,
                        },
                    }
                    yield f"event: complete\ndata: {json.dumps(complete_data, ensure_ascii=False)}\n\n"
                    return
                full_response = candidate_response
                yield f"event: token\ndata: {json.dumps({'t': token}, ensure_ascii=False)}\n\n"

            # LLM09: do not add synthetic citations to uncited claims.
            # Missing inline citations must remain visible to validation instead of being masked
            # by a decorative source footer.

            # 5. Post-streaming: quality check & post-process
            # selected_quality diisi setelah streaming selesai (tidak blocking streaming)
            selected_quality = build_answer_quality_report(
                query=request.message,
                context=context,
                answer=full_response,
                source_count=len(sources_for_response),
            )

            # Post-process jawaban: validasi sitasi, plain text emphasis, dan peta referensi
            full_response = sanitize_citations(full_response, len(sources_for_response))
            full_response = strip_markdown_emphasis(full_response)
            full_response, used_sources_for_response = renumber_citations_and_sources(
                full_response,
                sources_for_response,
            )
            full_response = append_citation_reference_block(full_response, used_sources_for_response)

            validation = None
            if context:
                validation = validate_answer(full_response, context, used_sources_for_response)
                if validation.get("warnings"):
                    # Remove Ayat references flagged as not present in context.
                    # This keeps legal citations faithful without altering core content.
                    if any(
                        "Kemungkinan Ayat yang tidak ada di konteks" in w
                        for w in validation.get("warnings", [])
                    ):
                        cleaned = re.sub(r"\s+[Aa]yat\s*\(\d+\)", "", full_response)
                        if cleaned != full_response:
                            full_response = cleaned
                            validation = validate_answer(full_response, context, used_sources_for_response)

                    yield (
                        "event: validation\n"
                        f"data: {json.dumps(validation, ensure_ascii=False)}\n\n"
                    )

                if validation.get("is_valid") is False:
                    full_response = _build_llm09_safe_fallback(validation)
                    yield f"event: token\ndata: {json.dumps({'t': full_response}, ensure_ascii=False)}\n\n"

            if validation and validation.get("is_valid") is False:
                used_sources_for_response = []

            output_contract = validate_llm_output_contract(
                full_response,
                requires_citation=bool(context and used_sources_for_response),
                allow_refusal_without_citation=True,
            )
            if not output_contract.allowed:
                latency = int((time.perf_counter() - start_time) * 1000)
                logger.warning(
                    "[LLM01] Post-generation output contract blocked categories={} severity={} user_id={}".format(
                        output_contract.categories,
                        output_contract.severity,
                        getattr(current_user, "id", None),
                    )
                )
                _audit_llm_security_block(
                    db=db,
                    request=http_request,
                    current_user=current_user,
                    event_type=AuditEventType.LLM_UNSAFE_OUTPUT_BLOCKED,
                    action="output_contract_blocked",
                    resource="chat/stream",
                    categories=output_contract.categories,
                    prompt_preview=full_response,
                )
                full_response = output_contract.safe_response or PROMPT_INJECTION_REFUSAL
                used_sources_for_response = []
                validation = {
                    "is_valid": True,
                    "has_citations": False,
                    "warnings": ["Output contract blocked unsafe or unverifiable answer"],
                    "confidence": "high",
                    "citation_count": 0,
                    "output_guard": {
                        "blocked": True,
                        "categories": output_contract.categories,
                        "severity": output_contract.severity,
                    },
                }
                yield f"event: security\ndata: {json.dumps({'blocked': True, 'categories': output_contract.categories, 'severity': output_contract.severity}, ensure_ascii=False)}\n\n"
                yield f"event: token\ndata: {json.dumps({'t': full_response}, ensure_ascii=False)}\n\n"

            # 6. Save response to DB
            latency = int((time.perf_counter() - start_time) * 1000)

            assistant_message = Conversation(
                session_id=session_id,
                role="assistant",
                content=full_response,
                sources=json.dumps(used_sources_for_response),
                timestamp=datetime.utcnow(),
                latency_ms=latency,
            )
            db.add(assistant_message)
            session.updated_at = datetime.utcnow()
            db.commit()

            quality_payload = {
                "score": selected_quality.get("score"),
                "needs_retry": selected_quality.get("needs_retry"),
                "retry_reasons": selected_quality.get("retry_reasons"),
                "focus_coverage": selected_quality.get("focus_coverage"),
                "has_unavailable_claim": selected_quality.get("has_unavailable_claim"),
                "unavailable_triggers_active": selected_quality.get(
                    "unavailable_triggers_active", []
                ),
            }
            if QUALITY_DEBUG:
                quality_payload["unavailable_triggers_suppressed"] = selected_quality.get(
                    "unavailable_triggers_suppressed", []
                )
                logger.info(
                    "[Chat][QUALITY_DEBUG] active={} suppressed={} score={}".format(
                        len(selected_quality.get("unavailable_triggers_active", [])),
                        len(selected_quality.get("unavailable_triggers_suppressed", [])),
                        selected_quality.get("score"),
                    )
                )
                for trig in selected_quality.get("unavailable_triggers_active", []):
                    logger.info(
                        "[Chat][QUALITY_DEBUG] active trigger phrase={!r} window={!r}".format(
                            trig.get("phrase"), trig.get("window")
                        )
                    )

            complete_data = {
                "session_id": session_id,
                "answer": full_response,
                "sources": used_sources_for_response,
                "timing": {"total_ms": latency},
                "model_used": model,
                "validation": validation,
                "quality_check": quality_payload,
            }
            yield f"event: complete\ndata: {json.dumps(complete_data, ensure_ascii=False)}\n\n"

        except Exception as e:
            import traceback
            logger.error(f"Chat streaming error: {e}\n{traceback.format_exc()}")
            yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/history/{session_id}", response_model=List[ConversationMessage])
def get_conversation_history(
    session_id: str,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get conversation history for a session"""
    # Verify session exists
    session = db.query(DBSession).filter(
        DBSession.id == session_id,
        DBSession.user_id == current_user.id,
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Get conversations
    conversations = (
        db.query(Conversation)
        .filter(Conversation.session_id == session_id)
        .order_by(Conversation.timestamp.desc())
        .limit(limit)
        .all()
    )

    # Reverse to chronological order
    conversations = list(reversed(conversations))

    # Parse sources JSON
    for conv in conversations:
        if conv.sources:
            try:
                conv.sources = json.loads(conv.sources)
            except:
                conv.sources = []

    return conversations
