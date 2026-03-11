from fastapi import APIRouter, HTTPException, Query
import httpx
from typing import List, Dict, Any
from app.models.schemas import ModelInfo

router = APIRouter()

OLLAMA_URL = "http://localhost:11434"

# In-memory storage for default model since the dedicated settings table was deprecated
_default_model = "qwen2.5:3b"

def get_ollama_models() -> List[ModelInfo]:
    """Fetch available models from Ollama."""
    try:
        response = httpx.get(f"{OLLAMA_URL}/api/tags", timeout=10)
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
        print(f"Failed to fetch Ollama models: {e}")
    return []

def get_default_model() -> str:
    """Get default model from memory."""
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
    models = [m.name for m in get_ollama_models()]
    if model not in models:
        raise HTTPException(status_code=400, detail=f"Model '{model}' not available")
    
    _default_model = model
    return {"model": model, "message": "Default model updated"}
