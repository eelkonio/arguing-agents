"""Silent agent detection logic.

Tracks consecutive silent turns per agent and detects agents that have
exceeded the configurable silence threshold.
"""

from __future__ import annotations

import logging

from multi_agent_debate.models.agent import AgentState

logger = logging.getLogger(__name__)


def detect_silent_agents(
    agents: list[AgentState],
    threshold: int,
) -> list[AgentState]:
    """Return agents whose consecutive silent turns exceed *threshold*.

    Args:
        agents: All agents in the current debate session.
        threshold: The number of consecutive silent turns after which an
            agent is considered silent and should be prompted.

    Returns:
        A list of agents that have been silent for more than *threshold* turns.
    """
    silent: list[AgentState] = []
    for agent in agents:
        if agent.consecutive_silent_turns > threshold:
            silent.append(agent)
    return silent


def update_silent_counters(
    agents: list[AgentState],
    speaker_id: str,
) -> None:
    """Update consecutive silent turn counters after a turn.

    The speaker's counter is reset to 0; all other agents have their
    counter incremented by 1.

    Args:
        agents: All agents in the current debate session (mutated in place).
        speaker_id: The ``persona.id`` of the agent who just spoke.
    """
    for agent in agents:
        if agent.persona.id == speaker_id:
            agent.consecutive_silent_turns = 0
        else:
            agent.consecutive_silent_turns += 1
