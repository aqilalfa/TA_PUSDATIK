"""
Health check endpoint
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.database import get_db
from app.models.schemas import HealthResponse
from app.config import settings
from app.api.routes.models import get_default_model
from qdrant_client import QdrantClient
import httpx
import os

router = APIRouter()


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
        default_model = get_default_model()
        response = httpx.get(f"{settings.OLLAMA_BASE_URL}/api/tags", timeout=10)
        if response.status_code == 200:
            data = response.json()
            available_models = {
                str(m.get("name", "")).strip() for m in data.get("models", [])
            }
            if default_model in available_models:
                services["llm_model"] = "present"
            else:
                services["llm_model"] = (
                    f"missing: default model '{default_model}' not found in Ollama"
                )
        else:
            services["llm_model"] = f"unhealthy: Ollama HTTP {response.status_code}"
    except Exception as e:
        # Legacy fallback for direct file-based LLM setups.
        if os.path.exists(settings.MODEL_PATH):
            services["llm_model"] = "present"
        else:
            services["llm_model"] = f"unhealthy: {str(e)}"

    return HealthResponse(
        status="healthy"
        if all("healthy" in v or "present" in v for v in services.values())
        else "degraded",
        version="1.0.0",
        environment=settings.ENVIRONMENT,
        services=services,
    )
