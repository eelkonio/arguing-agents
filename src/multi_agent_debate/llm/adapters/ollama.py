"""Ollama httpx adapter.

Uses Ollama's OpenAI-compatible ``/v1/chat/completions`` endpoint via
``httpx.AsyncClient`` for chat completions.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from multi_agent_debate.llm.adapters.base import (
    ChatMessage,
    ChatRequest,
    ChatResponse,
    LLMAdapter,
)

logger = logging.getLogger(__name__)


def _messages_to_openai_format(messages: list[ChatMessage]) -> list[dict[str, str]]:
    """Convert ChatMessage list to OpenAI-compatible message format."""
    return [{"role": msg.role, "content": msg.content} for msg in messages]


class OllamaAdapter(LLMAdapter):
    """Ollama adapter using the OpenAI-compatible chat completions endpoint.

    Args:
        model_id: Ollama model name (e.g. ``llama3``, ``mistral``).
        base_url: Ollama server base URL. Defaults to ``http://localhost:11434``.
        timeout: Request timeout in seconds. Defaults to 60.
    """

    def __init__(
        self,
        model_id: str = "llama3",
        base_url: str = "http://localhost:11434",
        timeout: int = 60,
    ) -> None:
        self._model_id = model_id
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    async def chat(self, request: ChatRequest) -> ChatResponse:
        """Send a chat completion request to Ollama.

        Uses the ``/v1/chat/completions`` OpenAI-compatible endpoint.

        Raises:
            RuntimeError: If the connection fails or the response is invalid.
        """
        payload: dict[str, Any] = {
            "model": self._model_id,
            "messages": _messages_to_openai_format(request.messages),
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "stream": False,
        }

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(
                    f"{self._base_url}/v1/chat/completions",
                    json=payload,
                )
                response.raise_for_status()

        except httpx.ConnectError as exc:
            msg = (
                f"Cannot connect to Ollama at {self._base_url}. "
                "Is the Ollama server running? "
                f"(model: {self._model_id})"
            )
            raise RuntimeError(msg) from exc

        except httpx.TimeoutException as exc:
            msg = (
                f"Ollama request timed out after {self._timeout}s "
                f"(model: {self._model_id}, url: {self._base_url})"
            )
            raise RuntimeError(msg) from exc

        except httpx.HTTPStatusError as exc:
            msg = (
                f"Ollama returned HTTP {exc.response.status_code}: "
                f"{exc.response.text[:500]}"
            )
            raise RuntimeError(msg) from exc

        data = response.json()
        content = data["choices"][0]["message"]["content"]
        usage = data.get("usage")

        return ChatResponse(content=content, usage=usage)

    async def health_check(self) -> bool:
        """Check whether the Ollama server is reachable.

        Calls the Ollama API root endpoint to verify connectivity.
        """
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(f"{self._base_url}/api/tags")
                return response.status_code == 200
        except (httpx.ConnectError, httpx.TimeoutException):
            logger.warning(
                "Ollama health check failed: cannot reach %s",
                self._base_url,
            )
            return False
