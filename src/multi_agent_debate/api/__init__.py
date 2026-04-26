"""API layer — HTTP endpoints and SSE streaming."""

from multi_agent_debate.api.health import router as health_router
from multi_agent_debate.api.sessions import router as sessions_router
from multi_agent_debate.api.stream import EventStreamManager, router as stream_router

__all__ = [
    "EventStreamManager",
    "health_router",
    "sessions_router",
    "stream_router",
]
