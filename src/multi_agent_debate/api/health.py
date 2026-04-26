"""Health check endpoint.

Reports application readiness and LLM backend availability.
"""

from __future__ import annotations

import logging

import httpx
from fastapi import APIRouter, Request
from pydantic import BaseModel

from multi_agent_debate.config import get_settings
from multi_agent_debate.llm.adapters.bedrock import BedrockAdapter
from multi_agent_debate.llm.adapters.ollama import OllamaAdapter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")


class BackendHealth(BaseModel):
    """Health status for all LLM backends."""

    bedrock: dict[str, object]
    ollama: dict[str, object]


@router.get("/health")
async def health_check(request: Request) -> BackendHealth:
    """Check application readiness and LLM backend availability.

    Returns availability status for Bedrock and Ollama backends.
    """
    settings = get_settings()

    # --- Bedrock health ---
    bedrock_status: dict[str, object]
    try:
        bedrock = BedrockAdapter(
            model_id=settings.default_bedrock_model_id,
            region=settings.default_bedrock_region,
            cross_account_role_arn=settings.cross_account_role_arn,
            cli_timeout=30,
        )
        bedrock_ok = await bedrock.health_check()
        bedrock_status = {"available": bedrock_ok, "error": None}
    except Exception as exc:
        logger.warning("Bedrock health check error: %s", exc)
        bedrock_status = {"available": False, "error": str(exc)}

    # --- Ollama health ---
    ollama_status: dict[str, object]
    try:
        ollama = OllamaAdapter(
            model_id="",
            base_url=settings.default_ollama_base_url,
        )
        ollama_ok = await ollama.health_check()
        models: list[str] = []
        if ollama_ok:
            models = await _list_ollama_models(settings.default_ollama_base_url)
        ollama_status = {"available": ollama_ok, "models": models, "error": None}
    except Exception as exc:
        logger.warning("Ollama health check error: %s", exc)
        ollama_status = {"available": False, "models": [], "error": str(exc)}

    return BackendHealth(bedrock=bedrock_status, ollama=ollama_status)


async def _list_ollama_models(base_url: str) -> list[str]:
    """Fetch the list of available models from Ollama."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(f"{base_url.rstrip('/')}/api/tags")
            if response.status_code == 200:
                data = response.json()
                return [m["name"] for m in data.get("models", [])]
    except Exception:
        logger.warning("Failed to list Ollama models", exc_info=True)
    return []
