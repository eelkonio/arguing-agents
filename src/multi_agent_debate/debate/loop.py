"""Debate loop engine (async generator).

Orchestrates the full debate flow: open → loop(statement → emotions →
interruptions → silence → next speaker) → end. Yields :class:`DebateEvent`
objects for each step so the event stream manager can forward them to SSE
clients.
"""

from __future__ import annotations

import asyncio
import logging
import math
import time
import uuid
from collections.abc import AsyncGenerator, Callable
from typing import TYPE_CHECKING

from multi_agent_debate.debate.interruption import (
    detect_cascade_candidates,
    detect_interruptions,
    select_interrupter,
)
from multi_agent_debate.debate.session import generate_summary
from multi_agent_debate.debate.silence import detect_silent_agents, update_silent_counters
from multi_agent_debate.models.agent import AgentState, EmotionalState
from multi_agent_debate.models.config import DebateThresholds, LLMBackendConfig
from multi_agent_debate.models.debate import (
    DebateSession,
    DebateStatus,
    DebateSummary,
    EmotionalStateUpdate,
    Statement,
)
from multi_agent_debate.models.events import (
    AgentSelectedEvent,
    ClosingArgumentEvent,
    ClosingPhaseStartedEvent,
    DebateEndedEvent,
    DebateEvent,
    DebatePausedEvent,
    DebateResumedEvent,
    DebateStartedEvent,
    EmotionsUpdatedEvent,
    ErrorEvent,
    InterruptionEvent,
    LeaderAnnouncementEvent,
    LeaderPromptEvent,
    StatementEvent,
)
from multi_agent_debate.llm.adapters.base import LLMAdapter
from multi_agent_debate.llm.services.agent import AgentStatementService
from multi_agent_debate.llm.services.leader import DebateLeaderService
from multi_agent_debate.llm.services.pusher import PsychoPusherService

if TYPE_CHECKING:
    from multi_agent_debate.storage.store import DebateStore

logger = logging.getLogger(__name__)


class DebateServices:
    """Container for the LLM services used by the debate loop."""

    def __init__(
        self,
        leader: DebateLeaderService,
        pusher: PsychoPusherService,
    ) -> None:
        self.leader = leader
        self.pusher = pusher


# Type alias for a factory that creates an LLMAdapter from a backend config.
AdapterFactory = Callable[[LLMBackendConfig], LLMAdapter]


def _find_agent(agents: list[AgentState], agent_id: str) -> AgentState | None:
    """Find an agent by persona ID."""
    for agent in agents:
        if agent.persona.id == agent_id:
            return agent
    return None


def _apply_emotional_updates(
    agents: list[AgentState],
    updates: list[EmotionalStateUpdate],
) -> dict[str, EmotionalState]:
    """Apply emotional state updates to agents and return the new states dict."""
    states: dict[str, EmotionalState] = {}
    update_map = {u.agent_id: u.new_state for u in updates}
    for agent in agents:
        if agent.persona.id in update_map:
            agent.current_emotional_state = update_map[agent.persona.id]
        states[agent.persona.id] = agent.current_emotional_state
    return states


def _get_agent_backend(
    session: DebateSession,
    agent_id: str,
) -> LLMBackendConfig:
    """Resolve the LLM backend for a specific agent."""
    assignments = session.config.backend_assignments
    return assignments.agents.get(agent_id, assignments.default_agent_backend)


def _in_leniency_window(turn_count: int, max_turns: int) -> bool:
    """Check if the turn count is within the ±10% leniency window."""
    lower = math.floor(0.9 * max_turns)
    upper = math.ceil(1.1 * max_turns)
    return lower <= turn_count <= upper


def _force_close(turn_count: int, max_turns: int) -> bool:
    """Check if the turn count has reached the hard cutoff at 110%."""
    return turn_count >= math.ceil(1.1 * max_turns)


class DebateLoop:
    """Core debate orchestration engine.

    Implements ``run()`` as an async generator that yields
    :data:`DebateEvent` objects. Supports pause, resume, and stop via
    asyncio events.
    """

    def __init__(
        self,
        session: DebateSession,
        services: DebateServices,
        adapter_factory: AdapterFactory,
        thresholds: DebateThresholds,
        topic_drift_check_interval: int = 5,
        store: DebateStore | None = None,
    ) -> None:
        self._session = session
        self._services = services
        self._adapter_factory = adapter_factory
        self._thresholds = thresholds
        self._topic_drift_check_interval = topic_drift_check_interval
        self._store = store

        # Control flags
        self._pause_event = asyncio.Event()
        self._pause_event.set()  # Not paused initially
        self._stop_requested = False
        self._close_requested = False

    def pause(self) -> None:
        """Signal the loop to pause at the next safe point."""
        self._pause_event.clear()

    def resume(self) -> None:
        """Signal the loop to resume from a paused state."""
        self._pause_event.set()

    def stop(self) -> None:
        """Signal the loop to stop gracefully."""
        self._stop_requested = True
        # Also resume in case we're paused, so the loop can exit
        self._pause_event.set()

    def request_close(self) -> None:
        """Signal the loop to initiate the closing sequence."""
        self._close_requested = True
        # Also resume in case we're paused
        self._pause_event.set()

    async def _persist_statement(self, session_id: str, statement: Statement) -> None:
        """Persist a statement to the store, logging errors without raising."""
        if self._store is not None:
            try:
                await self._store.save_statement(session_id, statement)
            except Exception:
                logger.exception("Failed to persist statement '%s'", statement.id)

    async def _persist_leader_event(
        self,
        session_id: str,
        event_type: str,
        content: str,
        agent_id: str | None = None,
        agent_name: str | None = None,
        timestamp: float = 0.0,
    ) -> None:
        """Persist a leader event to the store, logging errors without raising."""
        if self._store is not None:
            try:
                await self._store.save_leader_event(
                    session_id, event_type, content, agent_id, agent_name, timestamp,
                )
            except Exception:
                logger.exception("Failed to persist leader event for session '%s'", session_id)

    async def _persist_session_end(self, session_id: str, summary: DebateSummary, ended_at: float) -> None:
        """Persist session end to the store, logging errors without raising."""
        if self._store is not None:
            try:
                await self._store.update_session_end(session_id, summary, ended_at)
            except Exception:
                logger.exception("Failed to persist session end for '%s'", session_id)

    async def _wait_if_paused(self) -> AsyncGenerator[DebateEvent, None]:
        """If paused, yield pause/resume events and wait."""
        if not self._pause_event.is_set():
            yield DebatePausedEvent(type="debate-paused", timestamp=time.time())
            self._session.status = DebateStatus.PAUSED
            await self._pause_event.wait()
            if not self._stop_requested:
                self._session.status = DebateStatus.RUNNING
                yield DebateResumedEvent(type="debate-resumed", timestamp=time.time())

    async def _run_closing_sequence(self) -> AsyncGenerator[DebateEvent, None]:
        """Run the closing sequence: announcement → closing arguments → end."""
        session = self._session
        agents = session.agents

        session.status = DebateStatus.CLOSING_PHASE

        # Yield closing phase started event
        yield ClosingPhaseStartedEvent(
            type="closing-phase-started",
            timestamp=time.time(),
        )

        # Leader announces closing
        try:
            announcement = await self._services.leader.announce_closing(
                topic=session.config.topic,
                agents=agents,
            )
            yield LeaderAnnouncementEvent(
                type="leader-announcement",
                content=announcement,
                timestamp=time.time(),
            )
            await self._persist_leader_event(
                session.id, "leader-announcement", announcement, timestamp=time.time(),
            )
        except Exception as exc:
            logger.exception("Failed to generate closing announcement")
            yield ErrorEvent(
                type="error",
                message=f"Closing announcement failed: {exc}",
                timestamp=time.time(),
            )

        # Each agent delivers a closing argument
        for agent in agents:
            if self._stop_requested:
                break

            try:
                backend = _get_agent_backend(session, agent.persona.id)
                adapter = self._adapter_factory(backend)
                agent_service = AgentStatementService(adapter)
                closing_text = await agent_service.generate_closing_argument(
                    agent=agent,
                    recent_history=session.statements[-10:],
                )
            except Exception as exc:
                logger.exception(
                    "Failed to generate closing argument for '%s'",
                    agent.persona.name,
                )
                yield ErrorEvent(
                    type="error",
                    message=f"Closing argument failed for {agent.persona.name}: {exc}",
                    agent_id=agent.persona.id,
                    timestamp=time.time(),
                )
                continue

            closing_statement = Statement(
                id=str(uuid.uuid4()),
                agent_id=agent.persona.id,
                agent_name=agent.persona.name,
                content=closing_text,
                is_interruption=False,
                is_closing_argument=True,
                timestamp=time.time(),
                emotional_state_at_time=agent.current_emotional_state.model_copy(),
            )
            session.statements.append(closing_statement)
            agent.total_statements += 1

            yield ClosingArgumentEvent(
                type="closing-argument",
                statement=closing_statement,
                timestamp=time.time(),
            )
            await self._persist_statement(session.id, closing_statement)

        # End the debate
        session.status = DebateStatus.ENDED
        session.ended_at = time.time()
        summary = generate_summary(session)

        yield DebateEndedEvent(
            type="debate-ended",
            summary=summary,
            timestamp=time.time(),
        )
        await self._persist_session_end(session.id, summary, session.ended_at)

    async def run(self) -> AsyncGenerator[DebateEvent, None]:
        """Run the debate loop, yielding events for each step.

        The flow is:
        1. Emit debate-started
        2. Leader opens the debate (announcement + first speaker)
        3. Loop: generate statement → update emotions → check interruptions
           → check cascades → check silent agents → check topic drift
           → check max turns → select next speaker
        4. On close: run closing sequence
        5. On stop: emit debate-ended with summary
        """
        session = self._session
        agents = session.agents

        # --- Debate started ---
        yield DebateStartedEvent(type="debate-started", timestamp=time.time())

        # --- Leader opens the debate ---
        try:
            announcement, first_speaker_id = await self._services.leader.open_debate(
                topic=session.config.topic,
                agents=[a.persona for a in agents],
            )
        except Exception as exc:
            logger.exception("Failed to open debate")
            yield ErrorEvent(
                type="error",
                message=f"Failed to open debate: {exc}",
                timestamp=time.time(),
            )
            return

        yield LeaderAnnouncementEvent(
            type="leader-announcement",
            content=announcement,
            timestamp=time.time(),
        )
        await self._persist_leader_event(
            session.id, "leader-announcement", announcement, timestamp=time.time(),
        )

        current_speaker_id = first_speaker_id
        current_speaker = _find_agent(agents, current_speaker_id)
        if current_speaker is None and agents:
            current_speaker_id = agents[0].persona.id
            current_speaker = agents[0]

        yield AgentSelectedEvent(
            type="agent-selected",
            agent_id=current_speaker_id,
            agent_name=current_speaker.persona.name if current_speaker else "Unknown",
            timestamp=time.time(),
        )

        # --- Main debate loop ---
        while not self._stop_requested:
            # Check for close request
            if self._close_requested:
                async for event in self._run_closing_sequence():
                    yield event
                return

            # --- Check max turns BEFORE generating next statement ---
            max_turns = session.config.max_turns
            if max_turns is not None and session.status == DebateStatus.RUNNING:
                if _force_close(session.turn_count, max_turns):
                    # Hard cutoff — force closing immediately, no LLM call needed
                    logger.warning(
                        "FORCE CLOSE: turn_count=%d >= ceil(1.1 * %d)=%d — initiating closing sequence",
                        session.turn_count,
                        max_turns,
                        math.ceil(1.1 * max_turns),
                    )
                    async for event in self._run_closing_sequence():
                        yield event
                    return

                if _in_leniency_window(session.turn_count, max_turns):
                    # In leniency window — ask leader if we should close
                    logger.info(
                        "In leniency window: turn_count=%d, max_turns=%d, window=[%d, %d]",
                        session.turn_count,
                        max_turns,
                        math.floor(0.9 * max_turns),
                        math.ceil(1.1 * max_turns),
                    )
                    try:
                        should_close = await self._services.leader.should_close_debate(
                            turn_count=session.turn_count,
                            max_turns=max_turns,
                            agents=agents,
                            recent_history=session.statements[-10:],
                        )
                        if should_close:
                            logger.info(
                                "Leader decided to close at turn %d (leniency window of %d)",
                                session.turn_count,
                                max_turns,
                            )
                            async for event in self._run_closing_sequence():
                                yield event
                            return
                        else:
                            logger.info("Leader decided NOT to close at turn %d", session.turn_count)
                    except Exception as exc:
                        logger.exception("Failed to check should_close_debate at turn %d", session.turn_count)
                        yield ErrorEvent(
                            type="error",
                            message=f"Close check failed: {exc}",
                            timestamp=time.time(),
                        )

            # Check for pause
            async for event in self._wait_if_paused():
                yield event
            if self._stop_requested:
                break

            # --- Generate statement ---
            if current_speaker is None:
                break

            try:
                backend = _get_agent_backend(session, current_speaker_id)
                adapter = self._adapter_factory(backend)
                agent_service = AgentStatementService(adapter)
                statement_text = await agent_service.generate_statement(
                    agent=current_speaker,
                    recent_history=session.statements[-10:],
                    is_interruption=False,
                )
            except Exception as exc:
                logger.exception("Failed to generate statement for '%s'", current_speaker.persona.name)
                yield ErrorEvent(
                    type="error",
                    message=f"Statement generation failed: {exc}",
                    agent_id=current_speaker_id,
                    timestamp=time.time(),
                )
                break

            statement = Statement(
                id=str(uuid.uuid4()),
                agent_id=current_speaker_id,
                agent_name=current_speaker.persona.name,
                content=statement_text,
                is_interruption=False,
                timestamp=time.time(),
                emotional_state_at_time=current_speaker.current_emotional_state.model_copy(),
            )
            session.statements.append(statement)
            current_speaker.total_statements += 1

            # Increment turn count for non-interruption, non-closing statements
            session.turn_count += 1
            logger.info(
                "Turn %d completed (max_turns=%s, status=%s)",
                session.turn_count,
                session.config.max_turns,
                session.status.value,
            )

            yield StatementEvent(
                type="statement",
                statement=statement,
                timestamp=time.time(),
            )
            await self._persist_statement(session.id, statement)

            # Update silent counters
            update_silent_counters(agents, current_speaker_id)

            # Reset interruption tracking for the speaker
            current_speaker.consecutive_interruptions = 0

            # --- Update emotions ---
            async for event in self._wait_if_paused():
                yield event
            if self._stop_requested:
                break

            try:
                updates = await self._services.pusher.update_emotional_states(
                    statement=statement,
                    recent_history=session.statements[-10:],
                    agents=agents,
                )
                states = _apply_emotional_updates(agents, updates)
                yield EmotionsUpdatedEvent(
                    type="emotions-updated",
                    states=states,
                    timestamp=time.time(),
                )
            except Exception as exc:
                logger.exception("Failed to update emotions")
                yield ErrorEvent(
                    type="error",
                    message=f"Emotion update failed: {exc}",
                    timestamp=time.time(),
                )

            # --- Check interruptions ---
            async for event in self._wait_if_paused():
                yield event
            if self._stop_requested:
                break

            # Skip interruptions during closing phase
            if session.status != DebateStatus.CLOSING_PHASE:
                candidates = detect_interruptions(agents, self._thresholds)
                # Exclude the current speaker from interrupting themselves
                candidates = [c for c in candidates if c.persona.id != current_speaker_id]
                interrupter = select_interrupter(candidates, self._thresholds)

                if interrupter is not None:
                    async for event in self._handle_interruption(
                        interrupter, current_speaker_id
                    ):
                        yield event

            # --- Check silent agents ---
            async for event in self._wait_if_paused():
                yield event
            if self._stop_requested:
                break

            # Skip silent agent prompting during closing phase
            if session.status != DebateStatus.CLOSING_PHASE:
                silent_agents = detect_silent_agents(agents, self._thresholds.silent_turn_threshold)
                for silent_agent in silent_agents:
                    try:
                        prompt_text = await self._services.leader.prompt_silent_agent(
                            agent=silent_agent,
                            recent_history=session.statements[-10:],
                        )
                        yield LeaderPromptEvent(
                            type="leader-prompt",
                            agent_id=silent_agent.persona.id,
                            agent_name=silent_agent.persona.name,
                            content=prompt_text,
                            timestamp=time.time(),
                        )
                        await self._persist_leader_event(
                            session.id, "leader-prompt", prompt_text,
                            agent_id=silent_agent.persona.id,
                            agent_name=silent_agent.persona.name,
                            timestamp=time.time(),
                        )

                        # Generate a statement from the silent agent
                        sa_backend = _get_agent_backend(session, silent_agent.persona.id)
                        sa_adapter = self._adapter_factory(sa_backend)
                        sa_service = AgentStatementService(sa_adapter)
                        sa_text = await sa_service.generate_statement(
                            agent=silent_agent,
                            recent_history=session.statements[-10:],
                            is_interruption=False,
                        )

                        sa_statement = Statement(
                            id=str(uuid.uuid4()),
                            agent_id=silent_agent.persona.id,
                            agent_name=silent_agent.persona.name,
                            content=sa_text,
                            is_interruption=False,
                            timestamp=time.time(),
                            emotional_state_at_time=silent_agent.current_emotional_state.model_copy(),
                        )
                        session.statements.append(sa_statement)
                        silent_agent.total_statements += 1

                        yield StatementEvent(
                            type="statement",
                            statement=sa_statement,
                            timestamp=time.time(),
                        )
                        await self._persist_statement(session.id, sa_statement)

                        # Update silent counters
                        update_silent_counters(agents, silent_agent.persona.id)

                        # Update emotions after silent agent speaks
                        try:
                            sa_updates = await self._services.pusher.update_emotional_states(
                                statement=sa_statement,
                                recent_history=session.statements[-10:],
                                agents=agents,
                            )
                            sa_states = _apply_emotional_updates(agents, sa_updates)
                            yield EmotionsUpdatedEvent(
                                type="emotions-updated",
                                states=sa_states,
                                timestamp=time.time(),
                            )
                        except Exception as exc:
                            logger.exception("Failed to update emotions after silent agent spoke")
                            yield ErrorEvent(
                                type="error",
                                message=f"Emotion update after silent agent failed: {exc}",
                                timestamp=time.time(),
                            )

                    except Exception as exc:
                        logger.exception("Failed to prompt silent agent '%s'", silent_agent.persona.name)
                        yield ErrorEvent(
                            type="error",
                            message=f"Silent agent prompt failed: {exc}",
                            agent_id=silent_agent.persona.id,
                            timestamp=time.time(),
                        )

            # --- Check topic drift ---
            if (
                self._topic_drift_check_interval > 0
                and session.turn_count > 0
                and session.turn_count % self._topic_drift_check_interval == 0
                and session.status != DebateStatus.CLOSING_PHASE
            ):
                drift_detected, steering_message = await self._services.leader.check_topic_drift(
                    topic=session.config.topic,
                    recent_history=session.statements[-10:],
                )
                if drift_detected and steering_message:
                    yield LeaderAnnouncementEvent(
                        type="leader-announcement",
                        content=steering_message,
                        timestamp=time.time(),
                    )
                    await self._persist_leader_event(
                        session.id, "leader-announcement", steering_message, timestamp=time.time(),
                    )

            # --- Check close request (may have been set during this iteration) ---
            if self._close_requested:
                async for event in self._run_closing_sequence():
                    yield event
                return

            # --- Select next speaker ---
            async for event in self._wait_if_paused():
                yield event
            if self._stop_requested:
                break

            try:
                next_speaker_id = await self._services.leader.select_next_speaker(
                    agents=agents,
                    recent_history=session.statements[-10:],
                )
            except Exception as exc:
                logger.exception("Failed to select next speaker")
                yield ErrorEvent(
                    type="error",
                    message=f"Next speaker selection failed: {exc}",
                    timestamp=time.time(),
                )
                break

            next_speaker = _find_agent(agents, next_speaker_id)
            if next_speaker is None and agents:
                next_speaker_id = agents[0].persona.id
                next_speaker = agents[0]

            current_speaker_id = next_speaker_id
            current_speaker = next_speaker

            yield AgentSelectedEvent(
                type="agent-selected",
                agent_id=current_speaker_id,
                agent_name=current_speaker.persona.name if current_speaker else "Unknown",
                timestamp=time.time(),
            )

        # --- Debate ended (stop requested) ---
        session.status = DebateStatus.ENDED
        session.ended_at = time.time()
        summary = generate_summary(session)

        yield DebateEndedEvent(
            type="debate-ended",
            summary=summary,
            timestamp=time.time(),
        )
        await self._persist_session_end(session.id, summary, session.ended_at)

    async def _handle_interruption(
        self,
        interrupter: AgentState,
        interrupted_speaker_id: str,
    ) -> AsyncGenerator[DebateEvent, None]:
        """Handle an interruption and potential cascade."""
        session = self._session
        agents = session.agents

        try:
            int_backend = _get_agent_backend(session, interrupter.persona.id)
            int_adapter = self._adapter_factory(int_backend)
            int_service = AgentStatementService(int_adapter)
            int_text = await int_service.generate_statement(
                agent=interrupter,
                recent_history=session.statements[-10:],
                is_interruption=True,
            )
        except Exception as exc:
            logger.exception("Failed to generate interruption for '%s'", interrupter.persona.name)
            yield ErrorEvent(
                type="error",
                message=f"Interruption generation failed: {exc}",
                agent_id=interrupter.persona.id,
                timestamp=time.time(),
            )
            return

        int_statement = Statement(
            id=str(uuid.uuid4()),
            agent_id=interrupter.persona.id,
            agent_name=interrupter.persona.name,
            content=int_text,
            is_interruption=True,
            timestamp=time.time(),
            emotional_state_at_time=interrupter.current_emotional_state.model_copy(),
        )
        session.statements.append(int_statement)
        interrupter.total_statements += 1
        interrupter.consecutive_interruptions += 1

        yield InterruptionEvent(
            type="interruption",
            statement=int_statement,
            interrupted_agent_id=interrupted_speaker_id,
            timestamp=time.time(),
        )
        await self._persist_statement(session.id, int_statement)

        # Update silent counters for the interrupter
        update_silent_counters(agents, interrupter.persona.id)

        # Capture pre-update emotional states for cascade detection
        pre_update_states = {
            a.persona.id: a.current_emotional_state.model_copy() for a in agents
        }

        # Update emotions after interruption
        try:
            int_updates = await self._services.pusher.update_emotional_states(
                statement=int_statement,
                recent_history=session.statements[-10:],
                agents=agents,
            )
            int_states = _apply_emotional_updates(agents, int_updates)
            yield EmotionsUpdatedEvent(
                type="emotions-updated",
                states=int_states,
                timestamp=time.time(),
            )
        except Exception as exc:
            logger.exception("Failed to update emotions after interruption")
            yield ErrorEvent(
                type="error",
                message=f"Emotion update after interruption failed: {exc}",
                timestamp=time.time(),
            )
            return

        # --- Check for cascade interruptions ---
        cascade_candidates = detect_cascade_candidates(
            agents=agents,
            thresholds=self._thresholds,
            just_interrupted_id=interrupter.persona.id,
            pre_update_states=pre_update_states,
        )

        if cascade_candidates:
            cascade_interrupter = select_interrupter(cascade_candidates, self._thresholds)
            if cascade_interrupter is not None:
                # Ask the leader whether to allow the cascade
                allow = await self._services.leader.should_allow_cascade(
                    agents=agents,
                    recent_history=session.statements[-10:],
                )

                if allow:
                    # Recursively handle the cascade interruption
                    async for event in self._handle_interruption(
                        cascade_interrupter, interrupter.persona.id
                    ):
                        yield event
                else:
                    # Calm things down with a leader announcement
                    calming_msg = "Let's take a moment to collect ourselves. The discussion is getting heated — let's return to a more measured exchange of ideas."
                    yield LeaderAnnouncementEvent(
                        type="leader-announcement",
                        content=calming_msg,
                        timestamp=time.time(),
                    )
                    await self._persist_leader_event(
                        session.id, "leader-announcement", calming_msg, timestamp=time.time(),
                    )
