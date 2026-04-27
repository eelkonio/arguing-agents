"""Dependency helpers for accessing shared state from ``app.state``."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastapi import FastAPI

if TYPE_CHECKING:
    from multi_agent_debate.api.stream import EventStreamManager
    from multi_agent_debate.debate.session import SessionManager
    from multi_agent_debate.storage.store import DebateStore


def get_session_manager(app: FastAPI) -> "SessionManager":
    """Retrieve the :class:`SessionManager` from ``app.state``."""
    return app.state.session_manager  # type: ignore[no-any-return]


def get_event_stream_manager(app: FastAPI) -> "EventStreamManager":
    """Retrieve the :class:`EventStreamManager` from ``app.state``."""
    return app.state.event_stream_manager  # type: ignore[no-any-return]


def get_adapter_factory(app: FastAPI) -> Any:
    """Retrieve the adapter factory callable from ``app.state``."""
    return app.state.adapter_factory


def get_services(app: FastAPI) -> dict[str, Any]:
    """Retrieve the services dict from ``app.state``."""
    return app.state.services  # type: ignore[no-any-return]


def get_debate_store(app: FastAPI) -> "DebateStore":
    """Retrieve the :class:`DebateStore` from ``app.state``."""
    return app.state.debate_store  # type: ignore[no-any-return]


def get_audio_generator(app: FastAPI) -> Any:
    """Retrieve the :class:`AudioGenerator` from ``app.state``."""
    return app.state.audio_generator
