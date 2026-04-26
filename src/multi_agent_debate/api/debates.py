"""Debate history browsing endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from multi_agent_debate.api._deps import get_debate_store

router = APIRouter(prefix="/api")


@router.get("/debates")
async def list_debates(request: Request) -> list[dict]:
    """List all completed debate sessions with summary info."""
    store = get_debate_store(request.app)
    return await store.list_sessions()


@router.get("/debates/{debate_id}")
async def get_debate(debate_id: str, request: Request) -> dict:
    """Get full debate detail with timeline."""
    store = get_debate_store(request.app)
    detail = await store.get_session_detail(debate_id)
    if detail is None:
        raise HTTPException(404, f"Debate '{debate_id}' not found")
    timeline = await store.get_session_timeline(debate_id)
    return {"session": detail, "timeline": timeline}
