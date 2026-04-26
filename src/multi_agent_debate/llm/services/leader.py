"""Debate Leader service — manages turn order and prompts."""

from __future__ import annotations

import logging

from multi_agent_debate.llm.adapters.base import (
    ChatMessage,
    ChatRequest,
    LLMAdapter,
)
from multi_agent_debate.llm.services._json_utils import extract_json
from multi_agent_debate.models.agent import AgentPersona, AgentState
from multi_agent_debate.models.debate import Statement
from multi_agent_debate.profanity import PROFANITY_INSTRUCTION

logger = logging.getLogger(__name__)


def _format_agents_summary(agents: list[AgentPersona] | list[AgentState]) -> str:
    """Build a concise text summary of agents for inclusion in prompts."""
    lines: list[str] = []
    for agent in agents:
        persona = agent.persona if isinstance(agent, AgentState) else agent
        line = (
            f"- {persona.name} (ID: {persona.id}): "
            f"{persona.expertise}. Traits: {', '.join(persona.character_traits)}"
        )
        if isinstance(agent, AgentState):
            es = agent.current_emotional_state
            line += (
                f" | Emotions: anger={es.anger:.2f}, enthusiasm={es.enthusiasm:.2f}, "
                f"frustration={es.frustration:.2f}, agreement={es.agreement:.2f}, "
                f"confidence={es.confidence:.2f}, withdrawal={es.withdrawal:.2f}"
            )
        lines.append(line)
    return "\n".join(lines)


def _format_recent_history(history: list[Statement], limit: int = 10) -> str:
    """Format recent statements for inclusion in prompts."""
    if not history:
        return "(No statements yet.)"
    recent = history[-limit:]
    lines: list[str] = []
    for stmt in recent:
        prefix = "[INTERRUPTION] " if stmt.is_interruption else ""
        lines.append(f"{prefix}{stmt.agent_name}: {stmt.content}")
    return "\n".join(lines)


class DebateLeaderService:
    """Orchestrates debate turn order, opening, and silent-agent prompting."""

    def __init__(self, adapter: LLMAdapter) -> None:
        self._adapter = adapter

    async def open_debate(
        self,
        topic: str,
        agents: list[AgentPersona],
    ) -> tuple[str, str]:
        """Generate an opening announcement and select the first speaker.

        Returns:
            A tuple of (announcement_text, first_speaker_id).
        """
        agents_summary = _format_agents_summary(agents)
        agent_ids = [a.id for a in agents]

        system_prompt = f"""{PROFANITY_INSTRUCTION}

You are the Debate Leader. Your role is to open the debate, introduce the topic, and select the first speaker.

The debate topic is: "{topic}"

Participants:
{agents_summary}

Respond with JSON containing:
- "announcement": A brief, engaging opening statement that introduces the topic (2-3 sentences).
- "first_speaker_id": The ID of the agent you select to speak first.

You must select one of these agent IDs: {agent_ids}

Respond with ONLY the JSON object."""

        response = await self._adapter.chat(
            ChatRequest(
                messages=[
                    ChatMessage(role="system", content=system_prompt),
                    ChatMessage(role="user", content="Open the debate now."),
                ],
                temperature=0.7,
                max_tokens=1024,
            )
        )

        data = extract_json(response.content)
        if not isinstance(data, dict):
            msg = "Expected JSON object from Debate Leader"
            raise ValueError(msg)

        announcement = str(data.get("announcement", f"Welcome to the debate on: {topic}"))
        first_speaker_id = str(data.get("first_speaker_id", agent_ids[0]))

        # Validate the speaker ID
        if first_speaker_id not in agent_ids:
            logger.warning(
                "Leader selected invalid speaker ID '%s', falling back to first agent.",
                first_speaker_id,
            )
            first_speaker_id = agent_ids[0]

        logger.info("Debate opened. First speaker: %s", first_speaker_id)
        return announcement, first_speaker_id

    async def select_next_speaker(
        self,
        agents: list[AgentState],
        recent_history: list[Statement],
    ) -> str:
        """Select the next speaker based on emotional states and history.

        Returns:
            The agent ID of the next speaker.
        """
        agents_summary = _format_agents_summary(agents)
        history_text = _format_recent_history(recent_history)
        agent_ids = [a.persona.id for a in agents]

        system_prompt = f"""{PROFANITY_INSTRUCTION}

You are the Debate Leader. Select the next speaker for the debate.

Consider:
- Agents with high enthusiasm or confidence who haven't spoken recently should get priority.
- Agents with high withdrawal should be given space unless they've been silent too long.
- Avoid selecting the same agent who just spoke.
- Ensure all agents get a chance to participate.

Participants and their current emotional states:
{agents_summary}

Recent discussion:
{history_text}

Respond with ONLY a JSON object: {{"next_speaker_id": "<agent_id>"}}

You must select one of these agent IDs: {agent_ids}"""

        response = await self._adapter.chat(
            ChatRequest(
                messages=[
                    ChatMessage(role="system", content=system_prompt),
                    ChatMessage(role="user", content="Select the next speaker."),
                ],
                temperature=0.5,
                max_tokens=256,
            )
        )

        data = extract_json(response.content)
        if not isinstance(data, dict):
            msg = "Expected JSON object from Debate Leader"
            raise ValueError(msg)

        next_id = str(data.get("next_speaker_id", agent_ids[0]))

        if next_id not in agent_ids:
            logger.warning(
                "Leader selected invalid speaker ID '%s', falling back to first agent.",
                next_id,
            )
            next_id = agent_ids[0]

        logger.info("Next speaker selected: %s", next_id)
        return next_id

    async def prompt_silent_agent(
        self,
        agent: AgentState,
        recent_history: list[Statement],
    ) -> str:
        """Generate a prompt to draw a withdrawn agent back into the debate.

        Returns:
            The prompt text addressed to the silent agent.
        """
        history_text = _format_recent_history(recent_history)
        persona = agent.persona
        es = agent.current_emotional_state

        system_prompt = f"""{PROFANITY_INSTRUCTION}

You are the Debate Leader. One of the participants has been silent for several turns and needs to be drawn back into the discussion.

Silent agent:
- Name: {persona.name}
- Background: {persona.background}
- Expertise: {persona.expertise}
- Traits: {', '.join(persona.character_traits)}
- Current emotions: anger={es.anger:.2f}, enthusiasm={es.enthusiasm:.2f}, frustration={es.frustration:.2f}, agreement={es.agreement:.2f}, confidence={es.confidence:.2f}, withdrawal={es.withdrawal:.2f}
- Silent for {agent.consecutive_silent_turns} consecutive turns

Recent discussion:
{history_text}

Generate a brief, encouraging prompt (1-2 sentences) that:
- Addresses the agent by name
- References something specific from the recent discussion
- Invites them to share their perspective

Respond with ONLY a JSON object: {{"prompt": "<your prompt text>"}}"""

        response = await self._adapter.chat(
            ChatRequest(
                messages=[
                    ChatMessage(role="system", content=system_prompt),
                    ChatMessage(role="user", content="Prompt the silent agent."),
                ],
                temperature=0.7,
                max_tokens=512,
            )
        )

        data = extract_json(response.content)
        if not isinstance(data, dict):
            msg = "Expected JSON object from Debate Leader"
            raise ValueError(msg)

        prompt_text = str(
            data.get(
                "prompt",
                f"{persona.name}, we'd love to hear your thoughts on the recent discussion.",
            )
        )

        logger.info("Generated prompt for silent agent '%s'", persona.name)
        return prompt_text

    async def announce_closing(
        self,
        topic: str,
        agents: list[AgentState],
    ) -> str:
        """Generate a closing phase announcement.

        Args:
            topic: The debate topic.
            agents: All agents in the debate.

        Returns:
            The closing announcement text.
        """
        agents_summary = _format_agents_summary(agents)

        system_prompt = f"""{PROFANITY_INSTRUCTION}

You are the Debate Leader. The debate is now entering its closing phase.

The debate topic is: "{topic}"

Participants:
{agents_summary}

Generate a brief closing phase announcement (2-3 sentences) that:
- Announces that the debate is entering its final phase
- Thanks the participants for the discussion so far
- Invites each participant to deliver their closing argument

Respond with ONLY a JSON object: {{"announcement": "<your announcement text>"}}"""

        response = await self._adapter.chat(
            ChatRequest(
                messages=[
                    ChatMessage(role="system", content=system_prompt),
                    ChatMessage(role="user", content="Announce the closing phase."),
                ],
                temperature=0.7,
                max_tokens=512,
            )
        )

        data = extract_json(response.content)
        if not isinstance(data, dict):
            msg = "Expected JSON object from Debate Leader"
            raise ValueError(msg)

        announcement = str(
            data.get(
                "announcement",
                f"We are now entering the closing phase of our debate on '{topic}'. Each participant will deliver their closing argument.",
            )
        )

        logger.info("Generated closing announcement")
        return announcement

    async def should_close_debate(
        self,
        turn_count: int,
        max_turns: int,
        agents: list[AgentState],
        recent_history: list[Statement],
    ) -> bool:
        """Assess whether the current moment is a natural stopping point.

        Called during the ±10% leniency window around max_turns.

        Args:
            turn_count: Current turn count.
            max_turns: Configured maximum turns.
            agents: All agents in the debate.
            recent_history: Recent statements.

        Returns:
            True if the debate should close now.
        """
        agents_summary = _format_agents_summary(agents)
        history_text = _format_recent_history(recent_history)

        turns_remaining = int(max_turns * 1.1) - turn_count
        urgency = "LOW" if turns_remaining > max_turns * 0.1 else "HIGH"

        system_prompt = f"""{PROFANITY_INSTRUCTION}

You are the Debate Leader. The debate has reached its turn limit and MUST end soon.

Current turn: {turn_count} / {max_turns} (max turns)
Hard cutoff at turn: {int(max_turns * 1.1)}
Turns remaining before forced close: {turns_remaining}
Urgency: {urgency}

{"The debate is very close to the hard cutoff. You should strongly prefer closing now unless there is an extremely compelling reason to continue." if urgency == "HIGH" else "The debate is in its closing window. Look for a natural stopping point."}

Participants and their current emotional states:
{agents_summary}

Recent discussion:
{history_text}

Decide whether to close the debate NOW. Respond with ONLY a JSON object: {{"should_close": true/false, "reason": "<brief reason>"}}"""

        response = await self._adapter.chat(
            ChatRequest(
                messages=[
                    ChatMessage(role="system", content=system_prompt),
                    ChatMessage(role="user", content="Should we close the debate now?"),
                ],
                temperature=0.3,
                max_tokens=256,
            )
        )

        data = extract_json(response.content)
        if not isinstance(data, dict):
            logger.warning("Failed to parse should_close_debate response, defaulting to CLOSE")
            return True

        should_close = bool(data.get("should_close", True))
        reason = str(data.get("reason", ""))
        logger.info("Should close debate: %s (reason: %s)", should_close, reason)
        return should_close

    async def should_allow_cascade(
        self,
        agents: list[AgentState],
        recent_history: list[Statement],
    ) -> bool:
        """Decide whether to allow a cascading interruption or calm things down.

        On LLM failure, defaults to denying the cascade (safe fallback).

        Args:
            agents: All agents in the debate.
            recent_history: Recent statements including the interruption.

        Returns:
            True if the cascade should be allowed, False to calm down.
        """
        agents_summary = _format_agents_summary(agents)
        history_text = _format_recent_history(recent_history)

        system_prompt = f"""{PROFANITY_INSTRUCTION}

You are the Debate Leader. An interruption has just occurred and another agent is emotionally charged enough to cascade-interrupt.

Participants and their current emotional states:
{agents_summary}

Recent discussion (including the interruption):
{history_text}

Decide whether to allow this cascading interruption or to intervene and calm things down. Consider:
- Is the cascade adding value to the debate or just escalating chaos?
- Are emotions getting too heated for productive discussion?
- Would another interruption help explore an important point?

Respond with ONLY a JSON object: {{"allow_cascade": true/false, "reason": "<brief reason>"}}"""

        try:
            response = await self._adapter.chat(
                ChatRequest(
                    messages=[
                        ChatMessage(role="system", content=system_prompt),
                        ChatMessage(role="user", content="Should we allow this cascade interruption?"),
                    ],
                    temperature=0.3,
                    max_tokens=256,
                )
            )

            data = extract_json(response.content)
            if not isinstance(data, dict):
                logger.warning("Failed to parse should_allow_cascade response, denying cascade")
                return False

            allow = bool(data.get("allow_cascade", False))
            reason = str(data.get("reason", ""))
            logger.info("Allow cascade: %s (reason: %s)", allow, reason)
            return allow
        except Exception:
            logger.exception("LLM call failed for should_allow_cascade, denying cascade")
            return False

    async def check_topic_drift(
        self,
        topic: str,
        recent_history: list[Statement],
    ) -> tuple[bool, str | None]:
        """Check whether the debate has drifted from the original topic.

        On LLM failure, logs the error and skips the check.

        Args:
            topic: The original debate topic.
            recent_history: Recent statements.

        Returns:
            A tuple of (drift_detected, steering_message). If no drift,
            steering_message is None.
        """
        history_text = _format_recent_history(recent_history)

        system_prompt = f"""{PROFANITY_INSTRUCTION}

You are the Debate Leader. Your job is to assess whether the recent discussion has drifted away from the original debate topic.

Original debate topic: "{topic}"

Recent discussion:
{history_text}

Assess whether the discussion has drifted from the original topic. If it has, provide a steering message that:
- Acknowledges the digression
- References the original topic
- Identifies the point of divergence
- Steers the discussion back on track

Respond with ONLY a JSON object: {{"drift_detected": true/false, "steering_message": "<message or null>"}}"""

        try:
            response = await self._adapter.chat(
                ChatRequest(
                    messages=[
                        ChatMessage(role="system", content=system_prompt),
                        ChatMessage(role="user", content="Check for topic drift."),
                    ],
                    temperature=0.3,
                    max_tokens=512,
                )
            )

            data = extract_json(response.content)
            if not isinstance(data, dict):
                logger.warning("Failed to parse check_topic_drift response, skipping check")
                return False, None

            drift = bool(data.get("drift_detected", False))
            message = data.get("steering_message")
            steering = str(message) if message and drift else None

            if drift:
                logger.info("Topic drift detected: %s", steering)
            return drift, steering
        except Exception:
            logger.exception("LLM call failed for check_topic_drift, skipping check")
            return False, None
