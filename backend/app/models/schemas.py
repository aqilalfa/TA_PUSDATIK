"""
Pydantic schemas for request/response validation
"""

from pydantic import BaseModel, ConfigDict, Field
from typing import List, Optional, Dict, Any, Union
from datetime import datetime

class ModelInfo(BaseModel):
    name: str
    size: str
    family: str
    quantization: str

# ============== User Schemas ==============================================================
# User Schemas
# ============================================================================


class UserCreate(BaseModel):
    name: str
    email: Optional[str] = None


class UserResponse(BaseModel):
    id: int
    name: str
    email: Optional[str]
    created_at: datetime
    last_active: datetime

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Session Schemas
# ============================================================================


class SessionCreate(BaseModel):
    user_id: int
    title: Optional[str] = "New Conversation"


class SessionResponse(BaseModel):
    id: str
    user_id: int
    title: str
    created_at: datetime
    updated_at: datetime
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Chat Schemas
# ============================================================================


class ChatRequest(BaseModel):
    session_id: Optional[str] = None
    message: str = Field(..., min_length=1, max_length=5000)
    model: Optional[str] = None
    use_structured_fact: bool = False
    top_k: int = Field(default=5, ge=1, le=20)
    max_tokens: int = Field(default=2048, ge=128, le=4096)
    document_id: Optional[str] = None
    max_quality_retries: Optional[int] = Field(default=None, ge=0, le=3)  # override MAX_QUALITY_RETRY_ATTEMPTS; 0 = skip retries


class ChatResponse(BaseModel):
    response: str
    sources: List[Dict[str, Any]] = []
    tokens_used: Optional[int] = None
    latency_ms: Optional[int] = None


class ConversationMessage(BaseModel):
    role: str
    content: str
    sources: Optional[List[Dict[str, Any]]] = []
    timestamp: datetime

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Document Schemas
# ============================================================================


class DocumentUpload(BaseModel):
    filename: str
    doc_type: Optional[str] = None


class DocumentResponse(BaseModel):
    id: int
    filename: str
    doc_type: Optional[str]
    status: str
    ocr_needed: bool
    uploaded_at: datetime
    processed_at: Optional[datetime]
    error_message: Optional[str]

    model_config = ConfigDict(from_attributes=True)


class DocumentStatus(BaseModel):
    id: int
    status: str
    error_message: Optional[str]


# ============================================================================
# Evaluation Schemas
# ============================================================================


class BUS11Request(BaseModel):
    session_id: Optional[str] = None
    responses: List[int] = Field(..., min_length=11, max_length=11)


class BUS11Response(BaseModel):
    score: float
    interpretation: str
    raw_responses: List[int]


class RAGASEvalRequest(BaseModel):
    test_cases: List[Dict[str, Any]]


class RAGASEvalResponse(BaseModel):
    faithfulness: float
    answer_relevancy: float
    context_precision: float
    context_recall: float
    average_score: float


# ============================================================================
# Health Schemas
# ============================================================================


class HealthResponse(BaseModel):
    status: str
    version: str
    environment: str
    services: Dict[str, str]


# ============================================================================
# Error Schemas
# ============================================================================


class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
