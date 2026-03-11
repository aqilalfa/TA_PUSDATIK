"""
Health check endpoint
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.schemas import HealthResponse
from app.config import settings
from qdrant_client import QdrantClient
import httpx

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check(db: Session = Depends(get_db)):
    """
    Health check endpoint to verify all services are running
    """
    services = {}

    # Check database
    try:
        db.execute("SELECT 1")
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

    # Check if models exist
    import os

    if os.path.exists(settings.MODEL_PATH):
        services["llm_model"] = "present"
    else:
        services["llm_model"] = "missing"

    return HealthResponse(
        status="healthy"
        if all("healthy" in v or "present" in v for v in services.values())
        else "degraded",
        version="1.0.0",
        environment=settings.ENVIRONMENT,
        services=services,
    )
