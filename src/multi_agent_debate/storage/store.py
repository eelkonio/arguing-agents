"""DebateStore — async SQLite persistence for debate sessions."""

from __future__ import annotations

import json
import logging
import pathlib
import time

import aiosqlite

from multi_agent_debate.models.debate import DebateSession, DebateSummary, Statement
from multi_agent_debate.storage.schema import SCHEMA_SQL

logger = logging.getLogger(__name__)


class DebateStore:
    """Async SQLite store for persisting debate sessions, statements, and events.

    All write methods are wrapped in try/except so that a storage failure
    never interrupts an active debate.
    """

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path

    async def initialize(self) -> None:
        """Create tables if they don't exist and clean up stale audio jobs."""
        pathlib.Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        try:
            async with aiosqlite.connect(self._db_path) as db:
                await db.executescript(SCHEMA_SQL)
                # Reset any audio jobs stuck in pending/generating from a previous crash
                cursor = await db.execute(
                    "UPDATE audio_jobs SET status = 'failed', error_message = 'Server restarted during generation' "
                    "WHERE status IN ('pending', 'generating')"
                )
                if cursor.rowcount and cursor.rowcount > 0:
                    logger.info("Reset %d stale audio jobs from previous run", cursor.rowcount)
                await db.commit()
            logger.info("DebateStore initialized at '%s'", self._db_path)
        except Exception:
            logger.exception("Failed to initialize DebateStore at '%s'", self._db_path)

    # ------------------------------------------------------------------
    # Write helpers
    # ------------------------------------------------------------------

    async def save_session(self, session: DebateSession) -> None:
        """Insert or update a session record."""
        try:
            async with aiosqlite.connect(self._db_path) as db:
                await db.execute(
                    """
                    INSERT INTO sessions (id, topic, agent_theme, agent_count, max_turns,
                                          config_json, status, created_at, started_at, ended_at, summary_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        status = excluded.status,
                        started_at = excluded.started_at,
                        ended_at = excluded.ended_at,
                        summary_json = excluded.summary_json
                    """,
                    (
                        session.id,
                        session.config.topic,
                        session.config.agent_theme,
                        session.config.agent_count,
                        session.config.max_turns,
                        session.config.model_dump_json(),
                        session.status.value,
                        session.created_at,
                        session.started_at,
                        session.ended_at,
                        None,
                    ),
                )
                # Upsert agents
                for agent in session.agents:
                    await db.execute(
                        """
                        INSERT INTO agents (id, session_id, name, persona_json, final_emotional_state_json)
                        VALUES (?, ?, ?, ?, ?)
                        ON CONFLICT(id) DO UPDATE SET
                            final_emotional_state_json = excluded.final_emotional_state_json
                        """,
                        (
                            agent.persona.id,
                            session.id,
                            agent.persona.name,
                            agent.persona.model_dump_json(),
                            agent.current_emotional_state.model_dump_json(),
                        ),
                    )
                await db.commit()
        except Exception:
            logger.exception("Failed to save session '%s'", session.id)

    async def save_statement(self, session_id: str, statement: Statement) -> None:
        """Insert a statement record."""
        try:
            async with aiosqlite.connect(self._db_path) as db:
                await db.execute(
                    """
                    INSERT INTO statements (id, session_id, agent_id, agent_name, content,
                                            is_interruption, is_closing_argument, timestamp, emotional_state_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        statement.id,
                        session_id,
                        statement.agent_id,
                        statement.agent_name,
                        statement.content,
                        statement.is_interruption,
                        statement.is_closing_argument,
                        statement.timestamp,
                        statement.emotional_state_at_time.model_dump_json(),
                    ),
                )
                await db.commit()
        except Exception:
            logger.exception("Failed to save statement '%s' for session '%s'", statement.id, session_id)

    async def save_leader_event(
        self,
        session_id: str,
        event_type: str,
        content: str,
        agent_id: str | None = None,
        agent_name: str | None = None,
        timestamp: float = 0.0,
    ) -> None:
        """Insert a leader event record."""
        try:
            async with aiosqlite.connect(self._db_path) as db:
                await db.execute(
                    """
                    INSERT INTO leader_events (session_id, event_type, content, agent_id, agent_name, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (session_id, event_type, content, agent_id, agent_name, timestamp),
                )
                await db.commit()
        except Exception:
            logger.exception("Failed to save leader event for session '%s'", session_id)

    async def update_session_end(
        self,
        session_id: str,
        summary: DebateSummary,
        ended_at: float,
    ) -> None:
        """Update a session with the final summary and end timestamp."""
        try:
            async with aiosqlite.connect(self._db_path) as db:
                # Update agents with final emotional states
                await db.execute(
                    """
                    UPDATE sessions
                    SET status = 'ended', ended_at = ?, summary_json = ?
                    WHERE id = ?
                    """,
                    (ended_at, summary.model_dump_json(), session_id),
                )
                await db.commit()
        except Exception:
            logger.exception("Failed to update session end for '%s'", session_id)

    # ------------------------------------------------------------------
    # Read helpers
    # ------------------------------------------------------------------

    async def list_sessions(self) -> list[dict]:
        """Return all completed sessions with summary info."""
        try:
            async with aiosqlite.connect(self._db_path) as db:
                db.row_factory = aiosqlite.Row
                cursor = await db.execute(
                    """
                    SELECT s.id, s.topic, s.agent_theme, s.agent_count, s.status,
                           s.created_at, s.started_at, s.ended_at, s.summary_json,
                           (SELECT COUNT(*) FROM statements st WHERE st.session_id = s.id) AS statement_count
                    FROM sessions s
                    WHERE s.status = 'ended'
                    ORDER BY s.ended_at DESC
                    """
                )
                rows = await cursor.fetchall()
                result: list[dict] = []
                for row in rows:
                    summary_data = None
                    if row["summary_json"]:
                        summary_data = json.loads(row["summary_json"])
                    result.append({
                        "id": row["id"],
                        "topic": row["topic"],
                        "agent_theme": row["agent_theme"],
                        "agent_count": row["agent_count"],
                        "status": row["status"],
                        "created_at": row["created_at"],
                        "started_at": row["started_at"],
                        "ended_at": row["ended_at"],
                        "statement_count": row["statement_count"],
                        "summary": summary_data,
                    })
                return result
        except Exception:
            logger.exception("Failed to list sessions")
            return []

    async def get_session_detail(self, session_id: str) -> dict | None:
        """Return full session detail with agents."""
        try:
            async with aiosqlite.connect(self._db_path) as db:
                db.row_factory = aiosqlite.Row
                cursor = await db.execute(
                    "SELECT * FROM sessions WHERE id = ?", (session_id,)
                )
                session_row = await cursor.fetchone()
                if session_row is None:
                    return None

                # Fetch agents
                agent_cursor = await db.execute(
                    "SELECT * FROM agents WHERE session_id = ?", (session_id,)
                )
                agent_rows = await agent_cursor.fetchall()

                agents = []
                for a in agent_rows:
                    persona = json.loads(a["persona_json"])
                    final_state = None
                    if a["final_emotional_state_json"]:
                        final_state = json.loads(a["final_emotional_state_json"])
                    agents.append({
                        "id": a["id"],
                        "name": a["name"],
                        "persona": persona,
                        "final_emotional_state": final_state,
                    })

                summary_data = None
                if session_row["summary_json"]:
                    summary_data = json.loads(session_row["summary_json"])

                return {
                    "id": session_row["id"],
                    "topic": session_row["topic"],
                    "agent_theme": session_row["agent_theme"],
                    "agent_count": session_row["agent_count"],
                    "status": session_row["status"],
                    "created_at": session_row["created_at"],
                    "started_at": session_row["started_at"],
                    "ended_at": session_row["ended_at"],
                    "summary": summary_data,
                    "agents": agents,
                }
        except Exception:
            logger.exception("Failed to get session detail for '%s'", session_id)
            return None

    async def get_session_timeline(self, session_id: str) -> list[dict]:
        """Return all events (statements + leader events) in chronological order."""
        try:
            async with aiosqlite.connect(self._db_path) as db:
                db.row_factory = aiosqlite.Row

                # Fetch statements
                stmt_cursor = await db.execute(
                    """
                    SELECT id, agent_id, agent_name, content, is_interruption,
                           is_closing_argument, timestamp, emotional_state_json
                    FROM statements
                    WHERE session_id = ?
                    """,
                    (session_id,),
                )
                stmt_rows = await stmt_cursor.fetchall()

                # Fetch leader events
                leader_cursor = await db.execute(
                    """
                    SELECT event_type, content, agent_id, agent_name, timestamp
                    FROM leader_events
                    WHERE session_id = ?
                    """,
                    (session_id,),
                )
                leader_rows = await leader_cursor.fetchall()

                timeline: list[dict] = []

                for row in stmt_rows:
                    entry_type = "statement"
                    if row["is_closing_argument"]:
                        entry_type = "closing-argument"
                    elif row["is_interruption"]:
                        entry_type = "interruption"

                    timeline.append({
                        "type": entry_type,
                        "id": row["id"],
                        "agent_id": row["agent_id"],
                        "agent_name": row["agent_name"],
                        "content": row["content"],
                        "timestamp": row["timestamp"],
                        "emotional_state": json.loads(row["emotional_state_json"]),
                    })

                for row in leader_rows:
                    timeline.append({
                        "type": row["event_type"],
                        "content": row["content"],
                        "agent_id": row["agent_id"],
                        "agent_name": row["agent_name"],
                        "timestamp": row["timestamp"],
                    })

                # Sort by timestamp
                timeline.sort(key=lambda e: e["timestamp"])
                return timeline
        except Exception:
            logger.exception("Failed to get timeline for session '%s'", session_id)
            return []

    # ------------------------------------------------------------------
    # Audio job helpers
    # ------------------------------------------------------------------

    async def create_audio_job(self, session_id: str) -> dict | None:
        """Create or reset an audio job record. Returns the job dict or None on failure."""
        try:
            now = time.time()
            async with aiosqlite.connect(self._db_path) as db:
                await db.execute(
                    """
                    INSERT INTO audio_jobs (session_id, status, progress, audio_path, error_message, created_at, completed_at)
                    VALUES (?, 'pending', 0, NULL, NULL, ?, NULL)
                    ON CONFLICT(session_id) DO UPDATE SET
                        status = 'pending',
                        progress = 0,
                        audio_path = NULL,
                        error_message = NULL,
                        created_at = excluded.created_at,
                        completed_at = NULL
                    """,
                    (session_id, now),
                )
                await db.commit()
            return {
                "session_id": session_id,
                "status": "pending",
                "progress": 0,
                "audio_path": None,
                "error_message": None,
                "created_at": now,
                "completed_at": None,
            }
        except Exception:
            logger.exception("Failed to create audio job for session '%s'", session_id)
            return None

    async def update_audio_status(
        self,
        session_id: str,
        status: str,
        error_message: str | None = None,
    ) -> None:
        """Update the status of an audio job."""
        try:
            completed_at = time.time() if status in ("completed", "failed") else None
            async with aiosqlite.connect(self._db_path) as db:
                await db.execute(
                    """
                    UPDATE audio_jobs
                    SET status = ?, error_message = ?, completed_at = ?
                    WHERE session_id = ?
                    """,
                    (status, error_message, completed_at, session_id),
                )
                await db.commit()
        except Exception:
            logger.exception("Failed to update audio status for session '%s'", session_id)

    async def update_audio_progress(self, session_id: str, progress: int) -> None:
        """Update the progress percentage of an audio job."""
        try:
            async with aiosqlite.connect(self._db_path) as db:
                await db.execute(
                    "UPDATE audio_jobs SET progress = ? WHERE session_id = ?",
                    (progress, session_id),
                )
                await db.commit()
        except Exception:
            logger.exception("Failed to update audio progress for session '%s'", session_id)

    async def get_audio_job(self, session_id: str) -> dict | None:
        """Return the audio job for a session, or None if not found."""
        try:
            async with aiosqlite.connect(self._db_path) as db:
                db.row_factory = aiosqlite.Row
                cursor = await db.execute(
                    "SELECT * FROM audio_jobs WHERE session_id = ?",
                    (session_id,),
                )
                row = await cursor.fetchone()
                if row is None:
                    return None
                return {
                    "session_id": row["session_id"],
                    "status": row["status"],
                    "progress": row["progress"],
                    "audio_path": row["audio_path"],
                    "error_message": row["error_message"],
                    "created_at": row["created_at"],
                    "completed_at": row["completed_at"],
                }
        except Exception:
            logger.exception("Failed to get audio job for session '%s'", session_id)
            return None

    async def set_audio_path(self, session_id: str, audio_path: str) -> None:
        """Set the audio file path for a completed audio job."""
        try:
            async with aiosqlite.connect(self._db_path) as db:
                await db.execute(
                    "UPDATE audio_jobs SET audio_path = ? WHERE session_id = ?",
                    (audio_path, session_id),
                )
                await db.commit()
        except Exception:
            logger.exception("Failed to set audio path for session '%s'", session_id)
