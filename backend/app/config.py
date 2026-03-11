"""
Configuration management for SPBE RAG System
"""

from pydantic_settings import BaseSettings
from typing import List
from pathlib import Path


class Settings(BaseSettings):
    """Application settings"""

    # API Settings
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    CORS_ORIGINS: str = "http://localhost,http://localhost:80,http://localhost:5173"

    # Environment
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    RELOAD: bool = True

    # Qdrant
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_HOST: str = "localhost"  # For docker-compose
    QDRANT_PORT: int = 6333
    QDRANT_COLLECTION: str = "spbe_documents"

    # LLM Model
    MODEL_PATH: str = "/app/models/llm/qwen-2.5-7b-instruct-q4_k_m.gguf"
    QWEN_MODEL_PATH: str = (
        "/app/models/llm/Qwen2.5-7B-Instruct-Q4_K_M.gguf"  # Alternative name
    )
    MODEL_N_GPU_LAYERS: int = 35
    MODEL_N_CTX: int = 8192
    MODEL_N_BATCH: int = 512
    MODEL_TEMP: float = 0.1
    MODEL_TOP_P: float = 0.95
    MODEL_TOP_K: int = 40
    MODEL_MAX_TOKENS: int = 2048

    # Embedding Model
    EMBEDDING_MODEL: str = "firqaaa/indo-sentence-bert-base"
    EMBEDDING_MODEL_NAME: str = "firqaaa/indo-sentence-bert-base"  # Alternative name
    EMBEDDING_CACHE_DIR: str = "/app/models/embeddings"
    EMBEDDING_DEVICE: str = "cpu"
    EMBEDDING_BATCH_SIZE: int = 32

    # Reranker Model
    RERANKER_MODEL: str = "BAAI/bge-reranker-base"
    RERANKER_MODEL_NAME: str = "BAAI/bge-reranker-base"  # Alternative name
    RERANKER_CACHE_DIR: str = "/app/models/reranker"
    RERANKER_DEVICE: str = "cpu"
    RERANKER_TOP_K: int = 10

    # Database
    DATABASE_URL: str = "sqlite:////app/database/spbe_rag.db"

    # RAG Configuration
    VECTOR_SEARCH_TOP_K: int = 20
    BM25_TOP_K: int = 20
    HYBRID_ALPHA: float = 0.6
    RETRIEVAL_TOP_K: int = 10
    CHUNK_SIZE: int = 600
    CHUNK_OVERLAP: int = 100
    MIN_CHUNK_SIZE: int = 80  # Minimum chars per chunk (merge smaller ones)
    MAX_CHUNK_SIZE: int = 600  # Maximum chars before splitting

    # OCR Configuration
    OCR_ENGINE: str = "paddleocr"
    OCR_LANG: str = "id"
    OCR_USE_GPU: bool = True

    # Session Configuration
    SESSION_MAX_HISTORY: int = 10
    SESSION_TIMEOUT: int = 3600

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_DIR: str = "/app/logs"
    LOG_FORMAT: str = "json"

    # CUDA
    CUDA_VISIBLE_DEVICES: str = "0"

    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS origins from comma-separated string"""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"


# Global settings instance
settings = Settings()
