"""
Health check endpoint
"""

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.database import get_db
from app.models.schemas import HealthResponse
from app.config import settings
from app.core.rag.langchain_engine import langchain_engine
from app.core.rag.engine.llm_client import PRODUCTION_MODEL
from qdrant_client import QdrantClient
import httpx
import os
import pickle
from pathlib import Path

router = APIRouter()


def _bm25_count() -> int:
    path = Path(__file__).resolve().parents[3] / "data" / "bm25_index.pkl"
    if not path.exists():
        return 0
    with path.open("rb") as handle:
        payload = pickle.load(handle)
    documents = payload.get("documents", []) if isinstance(payload, dict) else []
    return len(documents)


def _ollama_model_status() -> str:
    response = httpx.get(f"{settings.OLLAMA_BASE_URL}/api/tags", timeout=10)
    if response.status_code != 200:
        return f"unhealthy: Ollama HTTP {response.status_code}"
    available = {str(model.get("name", "")).strip() for model in response.json().get("models", [])}
    return "present" if PRODUCTION_MODEL in available else f"missing: {PRODUCTION_MODEL}"


def collect_readiness(db: Session) -> dict[str, str]:
    """Read current component counts and alignment without mutating any index."""
    readiness: dict[str, str] = {}
    counts: dict[str, int] = {}
    try:
        counts["bm25"] = _bm25_count()
        readiness["bm25"] = f"ready: {counts['bm25']} chunks"
    except Exception as exc:
        readiness["bm25"] = f"unhealthy: {type(exc).__name__}"
    try:
        counts["sqlite"] = int(db.execute(text("SELECT COUNT(*) FROM chunks")).scalar() or 0)
        readiness["sqlite"] = f"ready: {counts['sqlite']} chunks"
    except Exception as exc:
        readiness["sqlite"] = f"unhealthy: {type(exc).__name__}"
    try:
        client = QdrantClient(url=settings.QDRANT_URL, check_compatibility=False)
        counts["qdrant"] = int(client.count(collection_name=settings.QDRANT_COLLECTION).count)
        readiness["qdrant"] = f"ready: {counts['qdrant']} chunks"
    except Exception as exc:
        readiness["qdrant"] = f"unhealthy: {type(exc).__name__}"
    reranker = getattr(langchain_engine, "reranker_readiness", {"status": "not_loaded"})
    reranker_status = str(reranker.get("status", "not_loaded"))
    reranker_reason = str(reranker.get("reason", "")).strip()
    readiness["reranker"] = f"{reranker_status}: {reranker_reason}" if reranker_reason else reranker_status
    try:
        readiness["ollama"] = _ollama_model_status()
    except Exception as exc:
        readiness["ollama"] = f"unhealthy: {type(exc).__name__}"
    readiness["alignment"] = "aligned" if len(counts) == 3 and len(set(counts.values())) == 1 else "drift"
    return readiness


def evaluate_readiness(services: dict[str, str]) -> bool:
    """Return true only when every required RAG component is usable and aligned."""
    required_counts = ("bm25", "sqlite", "qdrant")
    return (
        all(str(services.get(name, "")).startswith("ready:") for name in required_counts)
        and services.get("alignment") == "aligned"
        and services.get("reranker") == "ready"
        and services.get("ollama") == "present"
    )


@router.get("/readiness")
async def readiness_check(db: Session = Depends(get_db)):
    services = collect_readiness(db)
    ready = evaluate_readiness(services)
    return JSONResponse(
        status_code=200 if ready else 503,
        content={
            "status": "ready" if ready else "not_ready",
            "model": PRODUCTION_MODEL,
            "services": services,
        },
    )


@router.get("/health", response_model=HealthResponse)
async def health_check(db: Session = Depends(get_db)):
    """
    Health check endpoint to verify all services are running
    """
    services = {}

    # Check database
    try:
        db.execute(text("SELECT 1"))
        services["database"] = "healthy"
    except Exception as e:
        services["database"] = f"unhealthy: {str(e)}"

    # Check Qdrant
    try:
        client = QdrantClient(url=settings.QDRANT_URL)
        client.get_collections()
        services["qdrant"] = "healthy"
    except Exception as e:
        services["qdrant"] = f"unhealthy: {str(e)}"

    # Check default LLM model availability (Ollama-first).
    try:
        response = httpx.get(f"{settings.OLLAMA_BASE_URL}/api/tags", timeout=10)
        if response.status_code == 200:
            data = response.json()
            available_models = {
                str(m.get("name", "")).strip() for m in data.get("models", [])
            }
            if PRODUCTION_MODEL in available_models:
                services["llm_model"] = "present"
            else:
                services["llm_model"] = (
                    f"missing: production model '{PRODUCTION_MODEL}' not found in Ollama"
                )
        else:
            services["llm_model"] = f"unhealthy: Ollama HTTP {response.status_code}"
    except Exception as e:
        # Legacy fallback for direct file-based LLM setups.
        if os.path.exists(settings.MODEL_PATH):
            services["llm_model"] = "present"
        else:
            services["llm_model"] = f"unhealthy: {str(e)}"

    services.update(collect_readiness(db))
    healthy_values = {"healthy", "present", "aligned", "ready"}
    is_healthy = all(
        value in healthy_values or value.startswith("ready:")
        for value in services.values()
    )
    return HealthResponse(
        status="healthy" if is_healthy else "degraded",
        version="1.0.0",
        environment=settings.ENVIRONMENT,
        services=services,
    )
