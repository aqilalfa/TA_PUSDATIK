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

QUALITY_DEBUG = os.getenv("QUALITY_DEBUG", "").strip() == "1"

HARD_UNAVAILABLE_CLAIM_PATTERNS = (
    "tidak tercantum",
    "tidak tersedia",
    "tidak ditemukan",
    "tidak ada informasi",
    "belum tersedia",
    "tidak secara eksplisit",
    "belum dijelaskan",
)

# Phrases like "hanya memuat" can be descriptive (valid) or indicate missing coverage.
# Treat them as unavailable signals only when coupled with explicit negation nearby.
CONTEXTUAL_PARTIAL_CLAIM_PATTERNS = (
    "hanya mencantumkan",
    "hanya memuat",
)

CONTEXTUAL_PARTIAL_NEGATION_PATTERN = re.compile(
    r"hanya\s+(?:mencantumkan|memuat)[^\n\r\.;:]{0,140}\b(?:tanpa|tidak|belum|sementara)\b",
    re.IGNORECASE,
)

# Evidence-local suppression: an "unavailable" phrase surrounded by concrete
# structural data (numbers, stage markers, indicator/aspek/domain refs, ratings,
# bobot values) is usually descriptive of table content, not a claim of absence.
LOCAL_EVIDENCE_PATTERNS = (
    re.compile(r"\b\d+(?:[.,]\d+)?\b"),
    re.compile(r"tahap\s+(?:persiapan|pelaksanaan|pelaporan)", re.IGNORECASE),
    re.compile(r"indikator\s*\d", re.IGNORECASE),
    re.compile(r"aspek\s*\d", re.IGNORECASE),
    re.compile(r"domain\s*\d", re.IGNORECASE),
    re.compile(r"\b(?:sangat\s+baik|baik|cukup|kurang|memuaskan)\b", re.IGNORECASE),
    re.compile(r"bobot[^\n]{0,40}\d", re.IGNORECASE),
    re.compile(r"\[\d+\]"),
)

LOCAL_EVIDENCE_WINDOW = 140


def _has_local_evidence(window: str) -> bool:
    if not window:
        return False
    return any(pat.search(window) for pat in LOCAL_EVIDENCE_PATTERNS)


def _find_unavailable_triggers(text: str) -> List[Dict[str, Any]]:
    """Scan text for unavailable-claim hits and return per-hit debug info.

    Each entry includes the matched phrase, pattern type, surrounding window,
    whether local structural evidence is present, and whether the hit is
    suppressed by that evidence. Callers may filter by ``suppressed`` to
    distinguish active claims from descriptive mentions.
    """
    content = str(text or "")
    if not content:
        return []
    content_l = content.lower()
    triggers: List[Dict[str, Any]] = []

    for phrase in HARD_UNAVAILABLE_CLAIM_PATTERNS:
        start = 0
        while True:
            pos = content_l.find(phrase, start)
            if pos < 0:
                break
            wstart = max(0, pos - LOCAL_EVIDENCE_WINDOW)
            wend = min(len(content), pos + len(phrase) + LOCAL_EVIDENCE_WINDOW)
            window = content[wstart:wend]
            suppressed = _has_local_evidence(window)
            triggers.append(
                {
                    "phrase": phrase,
                    "pattern_type": "hard",
                    "position": pos,
                    "window": window,
                    "local_evidence_present": suppressed,
                    "suppressed": suppressed,
                }
            )
            start = pos + len(phrase)

    for match in CONTEXTUAL_PARTIAL_NEGATION_PATTERN.finditer(content_l):
        pos = match.start()
        wstart = max(0, pos - LOCAL_EVIDENCE_WINDOW)
        wend = min(len(content), match.end() + LOCAL_EVIDENCE_WINDOW)
        window = content[wstart:wend]
        suppressed = _has_local_evidence(window)
        triggers.append(
            {
                "phrase": match.group(0),
                "pattern_type": "contextual",
                "position": pos,
                "window": window,
                "local_evidence_present": suppressed,
                "suppressed": suppressed,
            }
        )

    return triggers


def _contains_unavailable_signal(text: str) -> bool:
    """Return True when any unsuppressed unavailable signal is present."""
    return any(not t["suppressed"] for t in _find_unavailable_triggers(text))

GENERIC_STOPWORDS = {
    "yang",
    "dan",
    "atau",
    "dari",
    "pada",
    "untuk",
    "dalam",
    "dengan",
    "sebagai",
    "adalah",
    "agar",
    "maka",
    "karena",
    "apa",
    "siapa",
    "bagaimana",
    "kapan",
    "dimana",
    "berdasarkan",
    "menurut",
    "tolong",
    "jelaskan",
    "sebutkan",
    "isi",
    "tentang",
    "nomor",
    "tahun",
    "pasal",
    "ayat",
    "dokumen",
    "peraturan",
    "tersebut",
    "itu",
    "ini",
    "dapat",
    "jika",
    "mohon",
}

LIST_INTENT_PATTERN = re.compile(
    r"\b(?:apa saja|sebutkan|daftar|rincian|langkah|tahap|komponen|indikator|poin)\b",
    re.IGNORECASE,
)
LIST_ITEM_PATTERN = re.compile(r"(?m)^\s*(?:\d+[\.)]|[-*])\s+")
MAX_QUALITY_RETRY_ATTEMPTS = 2

TABLE_QUERY_PATTERN = re.compile(
    r"\b(?:tabel|table)\s*(?:ke[-\s]*)?\d{1,3}\b",
    re.IGNORECASE,
)


def _chunk_text(text: str, chunk_size: int = 180) -> List[str]:
    clean = str(text or "")
    if not clean:
        return []
    return [clean[i : i + chunk_size] for i in range(0, len(clean), chunk_size)]


def _word_in_text(word: str, text: str) -> bool:
    if not word:
        return False
    return bool(re.search(rf"\b{re.escape(word)}\b", text))


def _extract_focus_terms(query: str, max_terms: int = 8) -> List[str]:
    tokens = re.findall(r"[a-zA-Z0-9]{2,}", str(query or "").lower())
    focus_terms: List[str] = []

    for token in tokens:
        if token in GENERIC_STOPWORDS:
            continue
        if token.isdigit() and len(token) < 2:
            continue
        if not token.isdigit() and len(token) < 3:
            continue
        if token not in focus_terms:
            focus_terms.append(token)
        if len(focus_terms) >= max_terms:
            break

    return focus_terms


def _contains_unavailable_claim(answer: str) -> bool:
    return _contains_unavailable_signal(answer)


def _is_list_intent_query(query: str) -> bool:
    text = str(query or "")
    if LIST_INTENT_PATTERN.search(text):
        return True
    return bool(TABLE_QUERY_PATTERN.search(text))


def _answer_has_list_structure(answer: str) -> bool:
    text = str(answer or "")
    if LIST_ITEM_PATTERN.search(text):
        return True

    lower = text.lower()
    ordinal_hits = len(
        re.findall(r"\b(?:pertama|kedua|ketiga|keempat|kelima|keenam)\b", lower)
    )
    return ordinal_hits >= 2


def _citation_count(answer: str) -> int:
    return len(re.findall(r"\[(\d+)\]", str(answer or "")))


def _build_answer_quality_report(
    query: str,
    context: str,
    answer: str,
    source_count: int,
) -> Dict[str, Any]:
    answer_text = str(answer or "").strip()
    answer_lower = answer_text.lower()
    context_lower = str(context or "").lower()

    query_focus_terms = _extract_focus_terms(query)
    context_focus_terms = [
        term for term in query_focus_terms if _word_in_text(term, context_lower)
    ]
    answer_focus_terms = [
        term for term in context_focus_terms if _word_in_text(term, answer_lower)
    ]

    if context_focus_terms:
        focus_coverage = len(answer_focus_terms) / len(context_focus_terms)
    else:
        focus_coverage = 1.0

    unavailable_triggers = _find_unavailable_triggers(answer_text)
    active_unavailable_triggers = [t for t in unavailable_triggers if not t["suppressed"]]
    suppressed_unavailable_triggers = [t for t in unavailable_triggers if t["suppressed"]]
    has_unavailable_claim = bool(active_unavailable_triggers)
    conflicting_unavailable_claim = has_unavailable_claim and bool(context_focus_terms)

    list_intent = _is_list_intent_query(query)
    list_structure_ok = (not list_intent) or _answer_has_list_structure(answer_text)

    citations = _citation_count(answer_text)
    length_ok = len(answer_text) >= 180
    source_ok = source_count > 0

    score = 0
    score += min(12, len(answer_text) // 120)
    score += int(10 * focus_coverage)
    score += 4 if citations > 0 else -4
    score += 3 if list_structure_ok else -4
    score += 2 if source_ok else -8

    if has_unavailable_claim:
        score -= 4
    if conflicting_unavailable_claim:
        score -= 6

    retry_reasons: List[str] = []
    if conflicting_unavailable_claim:
        retry_reasons.append("klaim tidak tersedia bertentangan dengan konteks")
    if focus_coverage < 0.45 and context_focus_terms:
        retry_reasons.append("cakupan istilah inti pertanyaan masih rendah")
    if not list_structure_ok:
        retry_reasons.append("format rincian/daftar belum lengkap")
    if citations == 0:
        retry_reasons.append("sitasi [n] belum muncul")
    if not length_ok:
        retry_reasons.append("jawaban terlalu ringkas")

    return {
        "score": score,
        "needs_retry": bool(retry_reasons),
        "retry_reasons": retry_reasons,
        "focus_coverage": round(focus_coverage, 4),
        "query_focus_terms": query_focus_terms,
        "context_focus_terms": context_focus_terms,
        "answer_focus_terms": answer_focus_terms,
        "has_unavailable_claim": has_unavailable_claim,
        "conflicting_unavailable_claim": conflicting_unavailable_claim,
        "list_intent": list_intent,
        "list_structure_ok": list_structure_ok,
        "citation_count": citations,
        "source_count": source_count,
        "answer_length": len(answer_text),
        "unavailable_triggers_active": active_unavailable_triggers,
        "unavailable_triggers_suppressed": suppressed_unavailable_triggers,
    }


def _quality_rank_key(report: Dict[str, Any]):
    """Rank quality reports with hard constraints first, then score and coverage."""
    return (
        0 if not report.get("conflicting_unavailable_claim") else -1,
        0 if report.get("list_structure_ok", True) else -1,
        int(report.get("score", 0)),
        float(report.get("focus_coverage", 0.0)),
        int(report.get("citation_count", 0)),
        int(report.get("answer_length", 0)),
    )


def _build_retry_query(
    original_query: str,
    quality_report: Dict[str, Any],
) -> str:
    instructions = [
        "- Jawab ketat berdasarkan konteks referensi yang sudah diberikan.",
        "- Fokus pada inti pertanyaan pengguna dan hindari detail di luar konteks.",
        "- Gunakan sitasi [n] pada setiap poin informatif.",
    ]

    context_focus_terms = quality_report.get("context_focus_terms") or []
    if context_focus_terms:
        instructions.append(
            "- Pastikan istilah penting berikut terjawab eksplisit bila tersedia di konteks: "
            + ", ".join(context_focus_terms[:8])
            + "."
        )

    if quality_report.get("has_unavailable_claim"):
        instructions.append(
            "- Jangan menulis 'tidak tersedia/tidak ditemukan' jika konteks memuat informasi relevan; "
            "jelaskan bagian yang memang tersedia secara faktual."
        )

    if quality_report.get("list_intent"):
        instructions.append(
            "- Karena pertanyaan meminta rincian/daftar, tulis butir utama secara lengkap dalam format poin."
        )

    return (
        f"{original_query}\n\n"
        "Instruksi tambahan revisi kualitas jawaban:\n"
        + "\n".join(instructions)
    )


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
            selected_quality = _build_answer_quality_report(
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
