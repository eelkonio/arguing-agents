"""Session manager — manages debate session lifecycle and state."""

from __future__ import annotations

import logging
import time
import uuid
from typing import TYPE_CHECKING

from multi_agent_debate.models.agent import AgentState
from multi_agent_debate.models.config import DebateConfig, LLMBackendConfig
from multi_agent_debate.models.debate import (
    AgentSummary,
    DebateSession,
    DebateStatus,
    DebateSummary,
)
from multi_agent_debate.llm.services.creator import DebateCreatorService

if TYPE_CHECKING:
    from multi_agent_debate.storage.store import DebateStore

logger = logging.getLogger(__name__)


def generate_summary(session: DebateSession) -> DebateSummary:
    """Build a :class:`DebateSummary` from the current session state.

    Counts total statements, total interruptions, and per-agent statistics.
    """
    total_statements = len(session.statements)
    total_interruptions = sum(1 for s in session.statements if s.is_interruption)

    agent_summaries: list[AgentSummary] = []
    for agent in session.agents:
        agent_stmts = [s for s in session.statements if s.agent_id == agent.persona.id]
        agent_summaries.append(
            AgentSummary(
                agent_id=agent.persona.id,
                agent_name=agent.persona.name,
                statement_count=len(agent_stmts),
                interruption_count=sum(1 for s in agent_stmts if s.is_interruption),
                final_emotional_state=agent.current_emotional_state.model_copy(),
            )
        )

    started = session.started_at or session.created_at
    ended = session.ended_at or time.time()
    duration = ended - started

    return DebateSummary(
        total_statements=total_statements,
        total_interruptions=total_interruptions,
        agent_summaries=agent_summaries,
        duration=duration,
    )


class SessionManager:
    """Manages debate session lifecycle and state transitions.

    Sessions are stored in an in-memory dictionary keyed by session ID.
    """

    def __init__(self, creator_service: DebateCreatorService, store: DebateStore | None = None) -> None:
        self._sessions: dict[str, DebateSession] = {}
        self._creator = creator_service
        self._store = store

    async def create_session(self, config: DebateConfig) -> DebateSession:
        """Create a new session, generate personas, and return it in *personas-ready* status.

        Args:
            config: The validated debate configuration.

        Returns:
            A :class:`DebateSession` with generated agent personas.
        """
        session_id = str(uuid.uuid4())
        session = DebateSession(
            id=session_id,
            config=config,
            status=DebateStatus.CONFIGURING,
            created_at=time.time(),
        )

        # Generate personas via the Debate Creator service
        personas = await self._creator.generate_personas(
            topic=config.topic,
            agent_count=config.agent_count,
            theme=config.agent_theme,
        )

        # Convert personas to AgentState objects
        session.agents = [
            AgentState(
                persona=persona,
                current_emotional_state=persona.initial_emotional_state.model_copy(),
            )
            for persona in personas
        ]

        session.status = DebateStatus.PERSONAS_READY
        self._sessions[session_id] = session

        # Persist to store
        if self._store is not None:
            try:
                await self._store.save_session(session)
            except Exception:
                logger.exception("Failed to persist session '%s' to store", session_id)

        logger.info(
            "Created session '%s' with %d agents for topic '%s'",
            session_id,
            len(session.agents),
            config.topic,
        )
        return session

    def get_session(self, session_id: str) -> DebateSession | None:
        """Return the session with the given ID, or ``None`` if not found."""
        return self._sessions.get(session_id)

    def update_agent_backend(
        self,
        session_id: str,
        agent_id: str,
        backend: LLMBackendConfig,
    ) -> None:
        """Update a specific agent's LLM backend assignment.

        Only allowed when the session is in *personas-ready* status.

        Raises:
            ValueError: If the session is not found, the agent ID is invalid,
                or the session is not in the correct status.
        """
        session = self._sessions.get(session_id)
        if session is None:
            msg = f"Session '{session_id}' not found"
            raise ValueError(msg)

        if session.status != DebateStatus.PERSONAS_READY:
            msg = f"Cannot update agent backend: session status is '{session.status.value}', expected 'personas-ready'"
            raise ValueError(msg)

        # Verify the agent exists
        agent_ids = {a.persona.id for a in session.agents}
        if agent_id not in agent_ids:
            msg = f"Agent '{agent_id}' not found in session '{session_id}'"
            raise ValueError(msg)

        # Update the backend assignment in the config
        session.config.backend_assignments.agents[agent_id] = backend
        logger.info(
            "Updated backend for agent '%s' in session '%s' to %s/%s",
            agent_id,
            session_id,
            backend.provider.value,
            backend.model_id,
        )

    async def start_debate(self, session_id: str) -> None:
        """Transition the session to *running* status.

        Raises:
            ValueError: If the session is not found or not in *personas-ready* status.
        """
        session = self._sessions.get(session_id)
        if session is None:
            msg = f"Session '{session_id}' not found"
            raise ValueError(msg)

        if session.status != DebateStatus.PERSONAS_READY:
            msg = f"Cannot start debate: session status is '{session.status.value}', expected 'personas-ready'"
            raise ValueError(msg)

        session.status = DebateStatus.RUNNING
        session.started_at = time.time()
        logger.info("Debate started for session '%s'", session_id)

    def pause_debate(self, session_id: str) -> None:
        """Transition the session to *paused* status.

        Raises:
            ValueError: If the session is not found or not in *running* status.
        """
        session = self._sessions.get(session_id)
        if session is None:
            msg = f"Session '{session_id}' not found"
            raise ValueError(msg)

        if session.status != DebateStatus.RUNNING:
            msg = f"Cannot pause debate: session status is '{session.status.value}', expected 'running'"
            raise ValueError(msg)

        session.status = DebateStatus.PAUSED
        logger.info("Debate paused for session '%s'", session_id)

    def resume_debate(self, session_id: str) -> None:
        """Transition the session to *running* status from *paused*.

        Raises:
            ValueError: If the session is not found or not in *paused* status.
        """
        session = self._sessions.get(session_id)
        if session is None:
            msg = f"Session '{session_id}' not found"
            raise ValueError(msg)

        if session.status != DebateStatus.PAUSED:
            msg = f"Cannot resume debate: session status is '{session.status.value}', expected 'paused'"
            raise ValueError(msg)

        session.status = DebateStatus.RUNNING
        logger.info("Debate resumed for session '%s'", session_id)

    async def stop_debate(self, session_id: str) -> DebateSummary:
        """End the debate and return a summary.

        Raises:
            ValueError: If the session is not found or already ended.
        """
        session = self._sessions.get(session_id)
        if session is None:
            msg = f"Session '{session_id}' not found"
            raise ValueError(msg)

        if session.status == DebateStatus.ENDED:
            msg = f"Session '{session_id}' has already ended"
            raise ValueError(msg)

        session.status = DebateStatus.ENDED
        session.ended_at = time.time()

        summary = generate_summary(session)
        logger.info(
            "Debate ended for session '%s': %d statements, %d interruptions",
            session_id,
            summary.total_statements,
            summary.total_interruptions,
        )
        return summary

    def request_close(self, session_id: str) -> None:
        """Transition the session to *closing-phase* status.

        Raises:
            ValueError: If the session is not found or not in *running* status.
        """
        session = self._sessions.get(session_id)
        if session is None:
            msg = f"Session '{session_id}' not found"
            raise ValueError(msg)

        if session.status != DebateStatus.RUNNING:
            msg = f"Cannot close debate: session status is '{session.status.value}', expected 'running'"
            raise ValueError(msg)

        session.status = DebateStatus.CLOSING_PHASE
        logger.info("Closing phase requested for session '%s'", session_id)
