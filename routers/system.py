from typing import Annotated

from fastapi import APIRouter, Depends

from config import get_settings
from security import CurrentUser
from services.ollama import OllamaClient, get_ollama

router = APIRouter(tags=["System"])


@router.get("/api/system/status")
def status(user: CurrentUser, ollama: Annotated[OllamaClient, Depends(get_ollama)]):
    settings = get_settings()
    return {
        "ollama": {"model": settings.ollama_model, "available": ollama.available()},
        "github": {"configured": settings.github_configured},
    }
