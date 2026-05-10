import json
from pathlib import Path
from typing import List

import httpx
from fastapi import APIRouter, HTTPException, Query
from loguru import logger

from app.config import settings
from app.models.schemas import ModelInfo

router = APIRouter()

DEFAULT_MODEL_FALLBACK = "qwen3.5:4b"


def _default_model_path() -> Path:
    configured_path = Path(settings.DEFAULT_MODEL_FILE)
    if configured_path.is_absolute():
        return configured_path
    backend_root = Path(__file__).resolve().parents[3]
    return backend_root / configured_path


def _load_persisted_default_model() -> str:
    path = _default_model_path()
    try:
        if not path.exists():
            return DEFAULT_MODEL_FALLBACK
        data = json.loads(path.read_text(encoding="utf-8"))
        model = data.get("model", "").strip()
        return model or DEFAULT_MODEL_FALLBACK
    except Exception as e:
        logger.warning(f"Failed to load persisted default model: {e}")
        return DEFAULT_MODEL_FALLBACK


def _save_persisted_default_model(model: str) -> None:
    path = _default_model_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"model": model}, ensure_ascii=False, indent=2), encoding="utf-8")


# Keep in-memory cache, but persist to disk for restart safety.
_default_model = _load_persisted_default_model()


def get_ollama_models() -> List[ModelInfo]:
    """Fetch available models from Ollama."""
    try:
        response = httpx.get(f"{settings.OLLAMA_BASE_URL}/api/tags", timeout=10)
        if response.status_code == 200:
            data = response.json()
            models = []
            for m in data.get("models", []):
                details = m.get("details", {})
                models.append(
                    ModelInfo(
                        name=m["name"],
                        size=details.get("parameter_size", "Unknown"),
                        family=details.get("family", "Unknown"),
                        quantization=details.get("quantization_level", "Unknown"),
                    )
                )
            return models
    except Exception as e:
        logger.warning(f"Failed to fetch Ollama models: {e}")
    return []


def get_default_model() -> str:
    """Get current default model."""
    return _default_model


@router.get("/", response_model=List[ModelInfo])
async def list_models():
    """List available Ollama models."""
    models = get_ollama_models()
    if not models:
        raise HTTPException(status_code=503, detail="Ollama not available")
    return models


@router.get("/default")
async def get_default():
    """Get current default model."""
    return {"model": get_default_model()}


@router.post("/default")
async def set_default(model: str = Query(...)):
    """Set default model."""
    global _default_model

    available_models = [m.name for m in get_ollama_models()]
    if not available_models:
        raise HTTPException(status_code=503, detail="Ollama not available")
    if model not in available_models:
        raise HTTPException(status_code=400, detail=f"Model '{model}' not available")

    _default_model = model
    _save_persisted_default_model(model)
    return {"model": model, "message": "Default model updated"}
