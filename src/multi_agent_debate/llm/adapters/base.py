"""Abstract LLM adapter interface."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class ChatMessage:
    """A single message in a chat conversation."""

    role: str  # "system", "user", "assistant"
    content: str


@dataclass
class ChatRequest:
    """Request payload for an LLM chat completion."""

    messages: list[ChatMessage]
    temperature: float = 0.7
    max_tokens: int = 2048


@dataclass
class ChatResponse:
    """Response from an LLM chat completion."""

    content: str
    usage: dict[str, int] | None = field(default=None)


class LLMAdapter(ABC):
    """Abstract base class for LLM backend adapters.

    Implementations must provide `chat()` for generating completions
    and `health_check()` for verifying backend availability.
    """

    @abstractmethod
    async def chat(self, request: ChatRequest) -> ChatResponse:
        """Send a chat request and return the model's response.

        Args:
            request: The chat request containing messages and parameters.

        Returns:
            A ChatResponse with the generated content and optional usage info.

        Raises:
            RuntimeError: If the backend call fails.
        """

    @abstractmethod
    async def health_check(self) -> bool:
        """Check whether the LLM backend is reachable and operational.

        Returns:
            True if the backend is healthy, False otherwise.
        """
