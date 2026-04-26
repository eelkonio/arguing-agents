"""Session CRUD endpoints.

Provides the REST API for creating, querying, and controlling debate sessions.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from multi_agent_debate.api._deps import (
    get_adapter_factory,
    get_debate_store,
    get_event_stream_manager,
    get_services,
    get_session_manager,
)
from multi_agent_debate.debate.loop import AdapterFactory, DebateLoop, DebateServices
from multi_agent_debate.models.config import DebateConfig, DebateThresholds, LLMBackendConfig
from multi_agent_debate.models.debate import DebateSession, DebateSummary

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")


# ------------------------------------------------------------------
# POST /api/sessions — create session
# ------------------------------------------------------------------


@router.post("/sessions", status_code=201)
async def create_session(config: DebateConfig, request: Request) -> DebateSession:
    """Create a new debate session.

    Validates the config, generates personas via the Debate Creator, and
    returns the session in *personas-ready* status.
    """
    sm = get_session_manager(request.app)
    try:
        session = await sm.create_session(config)
    except Exception as exc:
        logger.exception("Failed to create session")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return session


# ------------------------------------------------------------------
# GET /api/sessions/{session_id} — get session state
# ------------------------------------------------------------------


@router.get("/sessions/{session_id}")
async def get_session(session_id: str, request: Request) -> DebateSession:
    """Return the current state of a debate session."""
    sm = get_session_manager(request.app)
    session = sm.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
    return session


# ------------------------------------------------------------------
# PATCH /api/sessions/{session_id}/agents/{agent_id}/backend
# ------------------------------------------------------------------


@router.patch("/sessions/{session_id}/agents/{agent_id}/backend")
async def update_agent_backend(
    session_id: str,
    agent_id: str,
    backend: LLMBackendConfig,
    request: Request,
) -> dict[str, str]:
    """Update an agent's LLM backend assignment.

    Only allowed when the session is in *personas-ready* status.
    """
    sm = get_session_manager(request.app)
    try:
        sm.update_agent_backend(session_id, agent_id, backend)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"status": "updated"}


# ------------------------------------------------------------------
# POST /api/sessions/{session_id}/start — start debate
# ------------------------------------------------------------------


async def _run_debate_loop(
    session_id: str,
    app: Any,
) -> None:
    """Background task that runs the debate loop and broadcasts events."""
    sm = get_session_manager(app)
    esm = get_event_stream_manager(app)
    adapter_factory: AdapterFactory = get_adapter_factory(app)
    services_dict = get_services(app)
    store = get_debate_store(app)

    session = sm.get_session(session_id)
    if session is None:
        logger.error("Session '%s' not found when starting debate loop", session_id)
        return

    debate_services = DebateServices(
        leader=services_dict["leader"],
        pusher=services_dict["pusher"],
    )

    # Build thresholds from app settings
    settings = app.state.settings
    thresholds = DebateThresholds(
        interruption_threshold=settings.interruption_threshold,
        interruption_dimensions=settings.interruption_dimensions,
        silent_turn_threshold=settings.silent_turn_threshold,
    )

    debate_loop = DebateLoop(
        session=session,
        services=debate_services,
        adapter_factory=adapter_factory,
        thresholds=thresholds,
        topic_drift_check_interval=settings.topic_drift_check_interval,
        store=store,
    )

    # Store the loop on app.state so pause/resume/stop can access it
    if not hasattr(app.state, "debate_loops"):
        app.state.debate_loops = {}
    app.state.debate_loops[session_id] = debate_loop

    try:
        async for event in debate_loop.run():
            await esm.broadcast(session_id, event)
    except Exception:
        logger.exception("Debate loop error for session '%s'", session_id)
    finally:
        # Clean up
        loops: dict[str, DebateLoop] = getattr(app.state, "debate_loops", {})
        loops.pop(session_id, None)
        esm.close_session(session_id)


@router.post("/sessions/{session_id}/start")
async def start_debate(session_id: str, request: Request) -> dict[str, str]:
    """Start the debate for a session.

    Transitions the session to *running* and kicks off the debate loop
    as a background asyncio task.
    """
    sm = get_session_manager(request.app)
    try:
        await sm.start_debate(session_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # Launch the debate loop as a background task
    asyncio.create_task(_run_debate_loop(session_id, request.app))

    return {"status": "started"}


# ------------------------------------------------------------------
# POST /api/sessions/{session_id}/pause — pause debate
# ------------------------------------------------------------------


@router.post("/sessions/{session_id}/pause")
async def pause_debate(session_id: str, request: Request) -> dict[str, str]:
    """Pause an active debate."""
    sm = get_session_manager(request.app)
    try:
        sm.pause_debate(session_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # Signal the debate loop to pause
    loops: dict[str, DebateLoop] = getattr(request.app.state, "debate_loops", {})
    loop = loops.get(session_id)
    if loop is not None:
        loop.pause()

    return {"status": "paused"}


# ------------------------------------------------------------------
# POST /api/sessions/{session_id}/resume — resume debate
# ------------------------------------------------------------------


@router.post("/sessions/{session_id}/resume")
async def resume_debate(session_id: str, request: Request) -> dict[str, str]:
    """Resume a paused debate."""
    sm = get_session_manager(request.app)
    try:
        sm.resume_debate(session_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # Signal the debate loop to resume
    loops: dict[str, DebateLoop] = getattr(request.app.state, "debate_loops", {})
    loop = loops.get(session_id)
    if loop is not None:
        loop.resume()

    return {"status": "resumed"}


# ------------------------------------------------------------------
# POST /api/sessions/{session_id}/stop — stop debate
# ------------------------------------------------------------------


@router.post("/sessions/{session_id}/stop")
async def stop_debate(session_id: str, request: Request) -> DebateSummary:
    """Stop the debate and return a summary."""
    sm = get_session_manager(request.app)

    # Signal the debate loop to stop
    loops: dict[str, DebateLoop] = getattr(request.app.state, "debate_loops", {})
    loop = loops.get(session_id)
    if loop is not None:
        loop.stop()

    try:
        summary = await sm.stop_debate(session_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return summary


# ------------------------------------------------------------------
# POST /api/sessions/{session_id}/close — close debate gracefully
# ------------------------------------------------------------------


@router.post("/sessions/{session_id}/close")
async def close_debate(session_id: str, request: Request) -> dict[str, str]:
    """Initiate the graceful closing sequence for a debate.

    Transitions the session to *closing-phase* and signals the debate loop
    to run the closing sequence (closing announcement + closing arguments).
    """
    sm = get_session_manager(request.app)
    try:
        sm.request_close(session_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # Signal the debate loop to close
    loops: dict[str, DebateLoop] = getattr(request.app.state, "debate_loops", {})
    loop = loops.get(session_id)
    if loop is not None:
        loop.request_close()

    return {"status": "closing"}
