"""Audio generation API endpoints."""

from __future__ import annotations

import asyncio
import logging
import pathlib

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse

from multi_agent_debate.api._deps import get_debate_store

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")

# In-memory lock to prevent duplicate background tasks for the same session.
# This is checked BEFORE the database, so even rapid clicks can't spawn duplicates.
_generating_locks: set[str] = set()


@router.post("/debates/{debate_id}/generate-audio", status_code=202)
async def generate_audio(debate_id: str, request: Request) -> dict:
    """Start background TTS audio generation for a completed debate."""
    store = get_debate_store(request.app)
    audio_generator = getattr(request.app.state, "audio_generator", None)

    if audio_generator is None:
        raise HTTPException(503, "Audio generation is not configured")

    # Check TTS backend availability
    tts_backend = getattr(request.app.state, "settings", None)
    backend_name = tts_backend.tts_backend if tts_backend else "polly"
    if backend_name == "kokoro":
        kokoro = getattr(request.app.state, "kokoro_adapter", None)
        if kokoro is not None and not kokoro.is_available:
            raise HTTPException(503, "Kokoro TTS is not installed — audio generation unavailable")
    else:
        polly = getattr(request.app.state, "polly_adapter", None)
        if polly is not None and not polly.is_available:
            raise HTTPException(503, "AWS CLI is not installed — audio generation unavailable")

    # In-memory lock — prevents duplicate tasks even with rapid clicks
    if debate_id in _generating_locks:
        raise HTTPException(409, "Audio generation already in progress")

    # Validate session exists and is ended
    detail = await store.get_session_detail(debate_id)
    if detail is None:
        raise HTTPException(404, f"Debate '{debate_id}' not found")
    if detail.get("status") != "ended":
        raise HTTPException(409, "Audio can only be generated for ended debates")

    # Check database for existing job
    existing_job = await store.get_audio_job(debate_id)
    if existing_job is not None:
        if existing_job["status"] in ("pending", "generating"):
            raise HTTPException(409, "Audio generation already in progress")
        if existing_job["status"] == "completed":
            return existing_job

    # Acquire lock and create job
    _generating_locks.add(debate_id)

    job = await store.create_audio_job(debate_id)
    if job is None:
        _generating_locks.discard(debate_id)
        raise HTTPException(500, "Failed to create audio job")

    # Launch background task that releases the lock when done
    async def _run_and_release() -> None:
        try:
            await audio_generator.generate_debate_audio(debate_id)
        finally:
            _generating_locks.discard(debate_id)

    asyncio.create_task(_run_and_release())

    return job


@router.get("/debates/{debate_id}/audio-status")
async def audio_status(debate_id: str, request: Request) -> dict:
    """Return current audio job status and progress."""
    store = get_debate_store(request.app)

    job = await store.get_audio_job(debate_id)
    if job is None:
        return {
            "session_id": debate_id,
            "status": "none",
            "progress": 0,
            "audio_path": None,
            "error_message": None,
            "created_at": None,
            "completed_at": None,
        }

    return job


@router.get("/debates/{debate_id}/audio")
async def serve_audio(debate_id: str, request: Request) -> FileResponse:
    """Serve the generated MP3 file."""
    store = get_debate_store(request.app)

    job = await store.get_audio_job(debate_id)
    if job is None or job.get("status") != "completed":
        raise HTTPException(404, "Audio not available for this debate")

    audio_path = job.get("audio_path")
    if audio_path is None or not pathlib.Path(audio_path).is_file():
        raise HTTPException(404, "Audio file not found")

    return FileResponse(
        audio_path,
        media_type="audio/mpeg",
        filename=f"debate-{debate_id}.mp3",
    )
