"""Psycho Pusher service — updates emotional states."""

from __future__ import annotations

import logging

from multi_agent_debate.llm.adapters.base import (
    ChatMessage,
    ChatRequest,
    LLMAdapter,
)
from multi_agent_debate.llm.services._json_utils import extract_json
from multi_agent_debate.models.agent import AgentState, EmotionalState
from multi_agent_debate.models.debate import EmotionalStateUpdate, Statement
from multi_agent_debate.profanity import PROFANITY_INSTRUCTION

logger = logging.getLogger(__name__)

_EMOTION_DIMS = [
    "anger",
    "enthusiasm",
    "frustration",
    "agreement",
    "resentment",
    "confidence",
    "withdrawal",
]


def _format_agents_for_pusher(agents: list[AgentState]) -> str:
    """Build a detailed summary of agents for the Psycho Pusher prompt."""
    lines: list[str] = []
    for agent in agents:
        p = agent.persona
        es = agent.current_emotional_state
        emotions = ", ".join(f"{d}={getattr(es, d):.2f}" for d in _EMOTION_DIMS)
        lines.append(
            f"- {p.name} (ID: {p.id})\n"
            f"  Traits: {', '.join(p.character_traits)}\n"
            f"  Current emotions: {emotions}"
        )
    return "\n".join(lines)


def _format_recent_history(history: list[Statement], limit: int = 10) -> str:
    """Format recent statements for inclusion in prompts."""
    if not history:
        return "(No prior statements.)"
    recent = history[-limit:]
    lines: list[str] = []
    for stmt in recent:
        prefix = "[INTERRUPTION] " if stmt.is_interruption else ""
        lines.append(f"{prefix}{stmt.agent_name}: {stmt.content}")
    return "\n".join(lines)


def _clamp(value: float) -> float:
    """Clamp a value to [0, 1]."""
    return max(0.0, min(1.0, value))


class PsychoPusherService:
    """Analyses statements and updates emotional states for all agents."""

    def __init__(self, adapter: LLMAdapter) -> None:
        self._adapter = adapter

    async def update_emotional_states(
        self,
        statement: Statement,
        recent_history: list[Statement],
        agents: list[AgentState],
    ) -> list[EmotionalStateUpdate]:
        """Compute updated emotional states for every agent after a statement.

        Returns:
            A list of ``EmotionalStateUpdate`` objects, one per agent.
        """
        agents_text = _format_agents_for_pusher(agents)
        history_text = _format_recent_history(recent_history)
        agent_ids = [a.persona.id for a in agents]

        system_prompt = f"""{PROFANITY_INSTRUCTION}

You are the Psycho Pusher, an emotional dynamics analyst for a debate. Your job is to update every agent's emotional state after a new statement.

The latest statement was by {statement.agent_name}:
"{statement.content}"

Recent discussion history:
{history_text}

All agents and their current emotional states:
{agents_text}

For EACH agent, determine how this statement affects their emotions. Consider:
- How the statement's content relates to each agent's expertise and character traits
- Whether the statement agrees with or challenges each agent's position
- The emotional intensity and tone of the statement
- Each agent's current emotional state (emotions shift gradually, not dramatically)

Emotional dimensions (all values must be between 0.0 and 1.0):
- anger: How angry or hostile the agent feels
- enthusiasm: How excited and engaged the agent is
- frustration: How frustrated the agent feels with the discussion
- agreement: How much the agent agrees with the current direction
- resentment: How much resentment the agent harbors
- confidence: How confident the agent feels in their position
- withdrawal: How withdrawn or disengaged the agent is

Respond with ONLY a JSON array of objects, one per agent:
[
  {{
    "agent_id": "<id>",
    "anger": 0.0,
    "enthusiasm": 0.0,
    "frustration": 0.0,
    "agreement": 0.0,
    "resentment": 0.0,
    "confidence": 0.0,
    "withdrawal": 0.0
  }}
]

You MUST include ALL agents: {agent_ids}"""

        response = await self._adapter.chat(
            ChatRequest(
                messages=[
                    ChatMessage(role="system", content=system_prompt),
                    ChatMessage(
                        role="user",
                        content="Update all agents' emotional states now.",
                    ),
                ],
                temperature=0.6,
                max_tokens=2048,
            )
        )

        raw_updates = self._parse_updates(response.content, agents)
        logger.info("Updated emotional states for %d agents", len(raw_updates))
        return raw_updates

    @staticmethod
    def _parse_updates(
        content: str,
        agents: list[AgentState],
    ) -> list[EmotionalStateUpdate]:
        """Parse the LLM response into EmotionalStateUpdate objects.

        Preserves previous values for any missing dimensions and clamps all
        values to [0, 1].
        """
        # Build a lookup of current states by agent ID
        current_states: dict[str, EmotionalState] = {
            a.persona.id: a.current_emotional_state for a in agents
        }

        data = extract_json(content)

        # Normalise to a list of dicts
        raw_list: list[dict[str, object]]
        if isinstance(data, list):
            raw_list = [item for item in data if isinstance(item, dict)]
        elif isinstance(data, dict):
            # Might be wrapped: {"updates": [...]}
            for key in ("updates", "emotional_states", "agents"):
                if key in data and isinstance(data[key], list):
                    raw_list = [item for item in data[key] if isinstance(item, dict)]
                    break
            else:
                raw_list = [data]
        else:
            raw_list = []

        updates: list[EmotionalStateUpdate] = []
        seen_ids: set[str] = set()

        for raw in raw_list:
            agent_id = str(raw.get("agent_id", ""))
            if not agent_id or agent_id not in current_states:
                continue
            seen_ids.add(agent_id)

            prev = current_states[agent_id]
            new_values: dict[str, float] = {}
            for dim in _EMOTION_DIMS:
                if dim in raw:
                    try:
                        new_values[dim] = _clamp(float(raw[dim]))  # type: ignore[arg-type]
                    except (TypeError, ValueError):
                        new_values[dim] = getattr(prev, dim)
                else:
                    # Preserve previous value for missing dimensions
                    new_values[dim] = getattr(prev, dim)

            updates.append(
                EmotionalStateUpdate(
                    agent_id=agent_id,
                    new_state=EmotionalState(**new_values),
                )
            )

        # For any agents not in the response, preserve their current state
        for agent in agents:
            if agent.persona.id not in seen_ids:
                logger.warning(
                    "Agent '%s' missing from Psycho Pusher response; preserving state.",
                    agent.persona.name,
                )
                updates.append(
                    EmotionalStateUpdate(
                        agent_id=agent.persona.id,
                        new_state=agent.current_emotional_state.model_copy(),
                    )
                )

        return updates
