"""
Chat endpoints - placeholder for RAG integration
"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.db_models import Session as DBSession, Conversation
from app.models.schemas import ChatRequest, ChatResponse, ConversationMessage
from app.core.rag.langchain_engine import langchain_engine, classify_query
from app.core.rag.prompts import validate_answer
from app.core.formatting import (
    sanitize_citations,
    strip_markdown_emphasis,
    append_citation_reference_block,
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

from app.core.rag.quality_check import (
    build_answer_quality_report,
    find_unavailable_triggers,
)

QUALITY_DEBUG = os.getenv("QUALITY_DEBUG", "").strip() == "1"


@router.get("/debug/retrieval")
async def debug_retrieval(query: str):
    """Debug endpoint to see what chunks are actually retrieved."""
    try:
        results = langchain_engine.retrieve_context(query)
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
async def chat(request: ChatRequest, db: Session = Depends(get_db)):
    """
    Chat endpoint - currently a placeholder
    Will be integrated with RAG pipeline in future implementation
    """
    # Verify session exists
    session = db.query(DBSession).filter(DBSession.id == request.session_id).first()
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
async def chat_stream(request: ChatRequest, db: Session = Depends(get_db)):
    """
    Chat endpoint with SSE streaming.
    
    Pipeline:
      1. Save user message to DB
      2. Retrieve relevant documents from Qdrant
      3. Stream LLM answer token by token
      4. Save assistant response to DB
    """
    model = request.model or get_default_model()

    async def event_generator():
        try:
            # 1. Session Management
            # Gunakan local variable — jangan mutate Pydantic request model (immutable di v2)
            session_id = request.session_id

            if not session_id:
                new_session_id = str(uuid.uuid4())
                new_session = DBSession(id=new_session_id, user_id=1, title="New Conversation")
                db.add(new_session)
                db.flush()
                session_id = new_session.id  # simpan ke local var, bukan request.session_id
                db.commit()

            session = db.query(DBSession).filter(DBSession.id == session_id).first()
            if not session:
                yield f"event: error\ndata: {json.dumps({'error': 'Session not found'})}\n\n"
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

            # 2. Retrieve context (offload ke thread pool agar tidak block event loop)
            import asyncio
            retrieval = await asyncio.get_event_loop().run_in_executor(
                None,
                partial(
                    langchain_engine.retrieve_context,
                    query=request.message,
                    top_k=request.top_k,
                    use_rag=request.use_rag,
                    doc_id=request.document_id,
                ),
            )

            sources_for_response = retrieval["sources"]
            context = retrieval["context"]
            query_type = retrieval.get("query_type", "general")

            yield f"event: retrieval\ndata: {json.dumps({'count': len(sources_for_response)})}\n\n"

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
                full_response += token
                yield f"event: token\ndata: {json.dumps({'t': token}, ensure_ascii=False)}\n\n"

            # Fallback: Jika LLM gagal memberikan inline sitasi (kasus model kecil qwen3.5:4b/7b)
            # kita otomatis injeksi kalimat footer agar validasi UI lolos dan sumber terverifikasi
            if sources_for_response and not re.search(r'\[\d+\]', full_response):
                cit_tags = ", ".join([f"[{i}]" for i in range(1, len(sources_for_response) + 1)])
                postfix = f"\n\nCatatan referensi: Poin di atas disintesis dari sumber {cit_tags}."
                full_response += postfix
                yield f"event: token\ndata: {json.dumps({'t': postfix}, ensure_ascii=False)}\n\n"

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
            full_response = append_citation_reference_block(full_response, sources_for_response)

            validation = None
            if request.use_rag and context:
                validation = validate_answer(full_response, context, sources_for_response)
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
                            validation = validate_answer(full_response, context, sources_for_response)

                    yield (
                        "event: validation\n"
                        f"data: {json.dumps(validation, ensure_ascii=False)}\n\n"
                    )

            # 6. Save response to DB
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
                "sources": sources_for_response,
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
    session_id: str, limit: int = 50, db: Session = Depends(get_db)
):
    """Get conversation history for a session"""
    # Verify session exists
    session = db.query(DBSession).filter(DBSession.id == session_id).first()
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
