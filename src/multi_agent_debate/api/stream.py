"""SSE streaming — EventStreamManager and streaming endpoint.

Manages per-session client connections using asyncio.Queue for event delivery.
Uses ``sse-starlette`` for SSE responses.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections import defaultdict
from typing import Any

from fastapi import APIRouter, Request
from pydantic import TypeAdapter
from sse_starlette.sse import EventSourceResponse

from multi_agent_debate.models.events import DebateEvent

logger = logging.getLogger(__name__)

# Type adapter for serialising the DebateEvent discriminated union.
_event_adapter: TypeAdapter[Any] = TypeAdapter(DebateEvent)

router = APIRouter(prefix="/api")


class EventStreamManager:
    """Manages SSE connections per session.

    Each connected client gets its own :class:`asyncio.Queue` so events
    can be delivered independently.  ``broadcast()`` pushes to every
    queue registered for a given session.
    """

    def __init__(self) -> None:
        # session_id -> {client_id -> Queue}
        self._clients: dict[str, dict[str, asyncio.Queue[str | None]]] = defaultdict(dict)

    # ------------------------------------------------------------------
    # Client management
    # ------------------------------------------------------------------

    def add_client(self, session_id: str, request: Request) -> EventSourceResponse:
        """Register a new SSE client for *session_id* and return the response.

        The returned ``EventSourceResponse`` streams events from an
        internal queue until the client disconnects or the queue receives
        a ``None`` sentinel.
        """
        client_id = str(uuid.uuid4())
        queue: asyncio.Queue[str | None] = asyncio.Queue()
        self._clients[session_id][client_id] = queue

        logger.info(
            "SSE client '%s' connected to session '%s'",
            client_id,
            session_id,
        )

        async def event_generator() -> Any:  # noqa: ANN401
            try:
                while True:
                    # Check if client disconnected
                    if await request.is_disconnected():
                        break
                    try:
                        data = await asyncio.wait_for(queue.get(), timeout=30.0)
                    except asyncio.TimeoutError:
                        # Send a keep-alive comment to prevent proxy timeouts
                        yield {"comment": "keep-alive"}
                        continue

                    if data is None:
                        # Sentinel — stream is done
                        break

                    yield {"data": data}
            finally:
                self._remove_client(session_id, client_id)

        return EventSourceResponse(event_generator())

    def _remove_client(self, session_id: str, client_id: str) -> None:
        """Remove a client from the session's client set."""
        clients = self._clients.get(session_id)
        if clients and client_id in clients:
            del clients[client_id]
            logger.info(
                "SSE client '%s' disconnected from session '%s'",
                client_id,
                session_id,
            )
            if not clients:
                del self._clients[session_id]

    # ------------------------------------------------------------------
    # Broadcasting
    # ------------------------------------------------------------------

    async def broadcast(self, session_id: str, event: Any) -> None:
        """Send a :class:`DebateEvent` to all clients connected to *session_id*.

        The event is serialised to JSON once and pushed to every client queue.
        """
        clients = self._clients.get(session_id)
        if not clients:
            return

        data = _event_adapter.dump_json(event).decode()

        for client_id, queue in list(clients.items()):
            try:
                queue.put_nowait(data)
            except asyncio.QueueFull:
                logger.warning(
                    "Queue full for client '%s' on session '%s', dropping event",
                    client_id,
                    session_id,
                )

    def close_session(self, session_id: str) -> None:
        """Send a ``None`` sentinel to all clients for *session_id*, closing their streams."""
        clients = self._clients.get(session_id)
        if not clients:
            return

        for queue in clients.values():
            try:
                queue.put_nowait(None)
            except asyncio.QueueFull:
                pass


# ------------------------------------------------------------------
# SSE streaming endpoint (Task 10.3)
# ------------------------------------------------------------------


@router.get("/sessions/{session_id}/stream")
async def stream_session(session_id: str, request: Request) -> EventSourceResponse:
    """SSE endpoint — streams :class:`DebateEvent` objects as JSON.

    Clients connect here to receive real-time debate events for the
    given session.
    """
    from multi_agent_debate.api._deps import get_event_stream_manager

    esm = get_event_stream_manager(request.app)
    return esm.add_client(session_id, request)
