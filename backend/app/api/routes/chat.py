"""
Chat endpoints - placeholder for RAG integration
"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.db_models import Session as DBSession, Conversation
from app.models.schemas import ChatRequest, ChatResponse, ConversationMessage
from app.core.rag.langchain_engine import langchain_engine
from datetime import datetime
from typing import List
import json
import time
import uuid

router = APIRouter()


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
    Chat endpoint using SSE streaming and LCEL LangChain RAG.
    """
    model = "qwen3.5:4b"

    async def event_generator():
        try:
            # 1. Verify/Create Session
            if not request.session_id:
                # Provide a generic user_id since there's no auth currently implemented
                new_session_id = str(uuid.uuid4())
                new_session = DBSession(id=new_session_id, user_id=1, title="New Conversation")
                db.add(new_session)
                db.flush()
                request.session_id = new_session.id
                db.commit()
                
            session = db.query(DBSession).filter(DBSession.id == request.session_id).first()
            if not session:
                yield f"event: error\ndata: {json.dumps({'error': 'Session not found'})}\n\n"
                return

            # Save user message
            user_msg = Conversation(
                session_id=request.session_id,
                role="user",
                content=request.message,
                timestamp=datetime.utcnow(),
            )
            db.add(user_msg)
            db.commit()

            # 2. Invoke LangChain RAG
            chain = langchain_engine.get_chain(model)
            config = {"configurable": {"session_id": request.session_id}}
            
            sources_for_response = []
            full_response = ""
            start_time = time.perf_counter()
            
            # Streaming Events (v2) ensures metadata payload emits before tokens
            async for event in chain.astream_events({"input": request.message}, config=config, version="v2"):
                kind = event["event"]
                name = event["name"]

                # A. Metadata Stage
                if kind == "on_chain_end" and name == "retrieve_and_format":
                    raw_docs = event["data"]["output"].get("raw_docs", [])
                    for i, doc in enumerate(raw_docs, 1):
                        meta = doc.metadata or {}
                        sources_for_response.append({
                            "id": i,
                            "document": meta.get("judul_dokumen", "Unknown Document"),
                            "section": meta.get("hierarchy_path", ""),
                            "score": 1.0, 
                        })
                    yield f"event: retrieval\ndata: {json.dumps({'count': len(sources_for_response)})}\n\n"
                
                # B. Text Parsing Stage
                elif kind == "on_chat_model_stream":
                    chunk = event["data"]["chunk"]
                    if chunk.content:
                        full_response += chunk.content
                        yield f"event: token\ndata: {json.dumps({'t': chunk.content}, ensure_ascii=False)}\n\n"

            # 3. Post-process: sanitize invalid citations
            from app.core.formatting import sanitize_citations
            full_response = sanitize_citations(full_response, len(sources_for_response))

            # 4. Request Finalization
            latency = int((time.perf_counter() - start_time) * 1000)
            
            assistant_message = Conversation(
                session_id=request.session_id,
                role="assistant",
                content=full_response,
                sources=json.dumps(sources_for_response),
                timestamp=datetime.utcnow(),
                latency_ms=latency,
            )
            db.add(assistant_message)
            session.updated_at = datetime.utcnow()
            db.commit()
            
            complete_data = {
                "session_id": request.session_id,
                "answer": full_response,
                "sources": sources_for_response,
                "timing": {"total_ms": latency},
                "model_used": model,
            }
            yield f"event: complete\ndata: {json.dumps(complete_data, ensure_ascii=False)}\n\n"

        except Exception as e:
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
