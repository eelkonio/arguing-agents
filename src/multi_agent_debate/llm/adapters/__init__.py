"""LLM backend adapters."""

from multi_agent_debate.llm.adapters.base import (
    ChatMessage,
    ChatRequest,
    ChatResponse,
    LLMAdapter,
)
from multi_agent_debate.llm.adapters.bedrock import BedrockAdapter
from multi_agent_debate.llm.adapters.ollama import OllamaAdapter

__all__ = [
    "ChatMessage",
    "ChatRequest",
    "ChatResponse",
    "LLMAdapter",
    "BedrockAdapter",
    "OllamaAdapter",
]
