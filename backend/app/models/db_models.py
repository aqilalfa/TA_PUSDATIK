"""
Database models for SPBE RAG System
"""

from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    Boolean,
    DateTime,
    ForeignKey,
    Float,
)
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base


class User(Base):
    """User model - simple tracking without authentication"""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=True)
    hashed_password = Column(String, nullable=True)
    roles = Column(String, default="[]")  # JSON string of roles
    department = Column(String, nullable=True)
    auth_provider = Column(String, default="local")
    external_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_active = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    sessions = relationship(
        "Session", back_populates="user", cascade="all, delete-orphan"
    )

class TokenBlacklist(Base):
    """Stores invalidated JWT tokens until their natural expiration"""
    __tablename__ = "token_blacklist"

    jti = Column(String, primary_key=True)
    expires_at = Column(DateTime, nullable=False)


class Session(Base):
    """Conversation session model"""

    __tablename__ = "sessions"

    id = Column(String, primary_key=True)  # UUID
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String, default="New Conversation")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True)

    # Relationships
    user = relationship("User", back_populates="sessions")
    conversations = relationship(
        "Conversation", back_populates="session", cascade="all, delete-orphan"
    )


class Conversation(Base):
    """Conversation message model"""

    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, ForeignKey("sessions.id"), nullable=False)
    role = Column(String, nullable=False)  # 'user' or 'assistant'
    content = Column(Text, nullable=False)
    sources = Column(Text, nullable=True)  # JSON array of retrieved sources
    timestamp = Column(DateTime, default=datetime.utcnow)
    tokens_used = Column(Integer, nullable=True)
    latency_ms = Column(Integer, nullable=True)

    # Relationships
    session = relationship("Session", back_populates="conversations")


class Document(Base):
    """Document model for uploaded files"""

    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, nullable=False)
    original_path = Column(String, nullable=True)  # path where file is stored
    doc_type = Column(String, nullable=True)  # 'peraturan', 'audit', 'other'
    status = Column(String, default="pending")  # 'pending', 'uploaded', 'indexed', 'failed'
    ocr_needed = Column(Boolean, default=False)
    doc_metadata = Column(Text, nullable=True)  # JSON metadata
    uploaded_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    processed_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)

    # === Kolom tambahan dibutuhkan DocumentManager (Phase 1 consolidation) ===
    # doc_id: UUID text identifier dipakai oleh DocumentManager sebagai primary key lookup
    doc_id = Column(String, unique=True, nullable=True, index=True)
    document_title = Column(String, nullable=True)   # Judul dokumen human-readable
    original_filename = Column(String, nullable=True) # Nama file asli dari user upload
    file_size = Column(Integer, default=0)            # Ukuran file dalam bytes
    file_path = Column(String, nullable=True)         # Path file lengkap di disk
    chunk_count = Column(Integer, default=0)          # Jumlah chunk yang tersimpan

    # Relationships
    chunks = relationship(
        "Chunk", back_populates="document", cascade="all, delete-orphan"
    )


class Chunk(Base):
    """Chunk model for document chunks"""

    __tablename__ = "chunks"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False)
    chunk_text = Column(Text, nullable=False)
    chunk_index = Column(Integer, nullable=False)
    chunk_metadata = Column(Text, nullable=True)  # JSON: bab, pasal, ayat, context_header, dll
    created_at = Column(DateTime, default=datetime.utcnow)

    # === Kolom tambahan untuk rich metadata (Phase 1) ===
    chunk_type = Column(String, default="text", nullable=True)  # 'pasal', 'table', 'section', dll

    # Relationships
    document = relationship("Document", back_populates="chunks")


class EvaluationResult(Base):
    """Evaluation results model"""

    __tablename__ = "evaluation_results"

    id = Column(Integer, primary_key=True, index=True)
    eval_type = Column(String, nullable=False)  # 'ragas' or 'bus11'
    session_id = Column(String, ForeignKey("sessions.id"), nullable=True)
    metrics = Column(Text, nullable=False)  # JSON of metrics
    score = Column(Float, nullable=True)
    notes = Column(Text, nullable=True)
    evaluated_at = Column(DateTime, default=datetime.utcnow)


class AuditLog(Base):
    """Audit logging model - tracks all security-relevant events"""

    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    event_type = Column(String, nullable=False)  # LOGIN_ATTEMPT, LOGIN_SUCCESS, LOGIN_FAILURE, PBAC_DENIAL, TOKEN_REFRESH, LOGOUT, etc.
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # NULL if not yet authenticated
    username = Column(String, nullable=False)  # Email or LDAP DN for traceability
    action = Column(String, nullable=False)  # 'login', 'refresh', 'access_denied', etc.
    resource = Column(String, nullable=False)  # API endpoint or resource accessed
    status = Column(String, nullable=False)  # 'success', 'failure', 'denied', 'pending'
    ip_address = Column(String, nullable=True)  # Client IP for geolocation/abuse detection
    details = Column(Text, nullable=True)  # JSON: provider, reason, attempt_count, etc.
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)  # Indexed for range queries
