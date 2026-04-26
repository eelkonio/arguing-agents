"""Interruption detection logic.

Detects agents whose emotional state exceeds configurable thresholds on
specified dimensions, and selects the highest-intensity candidate for
interruption. Also supports cascade detection after emotional updates.
"""

from __future__ import annotations

import logging

from multi_agent_debate.models.agent import AgentState, EmotionalState
from multi_agent_debate.models.config import DebateThresholds

logger = logging.getLogger(__name__)


def _get_intensity(agent: AgentState, dimensions: list[str]) -> float:
    """Return the maximum emotional value across the configured dimensions."""
    values: list[float] = []
    for dim in dimensions:
        value = getattr(agent.current_emotional_state, dim, None)
        if value is not None:
            values.append(float(value))
    return max(values) if values else 0.0


def detect_interruptions(
    agents: list[AgentState],
    thresholds: DebateThresholds,
) -> list[AgentState]:
    """Return agents exceeding the interruption threshold on configured dimensions.

    Agents that have already reached the maximum consecutive interruptions are
    excluded from the result.

    Args:
        agents: All agents in the current debate session.
        thresholds: The debate threshold configuration.

    Returns:
        A list of agents that qualify as potential interrupters.
    """
    candidates: list[AgentState] = []
    for agent in agents:
        # Check if any configured dimension exceeds the threshold
        for dim in thresholds.interruption_dimensions:
            value = getattr(agent.current_emotional_state, dim, None)
            if value is not None and float(value) > thresholds.interruption_threshold:
                candidates.append(agent)
                break

    return candidates


def select_interrupter(
    candidates: list[AgentState],
    thresholds: DebateThresholds,
) -> AgentState | None:
    """Select the candidate with the highest emotional intensity.

    Args:
        candidates: Agents that exceed the interruption threshold.
        thresholds: The debate threshold configuration (used for dimension list).

    Returns:
        The agent with the highest intensity, or ``None`` if *candidates* is empty.
    """
    if not candidates:
        return None

    best = max(
        candidates,
        key=lambda a: _get_intensity(a, thresholds.interruption_dimensions),
    )
    logger.info(
        "Selected interrupter: '%s' (intensity=%.2f)",
        best.persona.name,
        _get_intensity(best, thresholds.interruption_dimensions),
    )
    return best


def _exceeds_threshold(
    emotional_state: EmotionalState,
    thresholds: DebateThresholds,
) -> bool:
    """Check if an emotional state exceeds the interruption threshold."""
    for dim in thresholds.interruption_dimensions:
        value = getattr(emotional_state, dim, None)
        if value is not None and float(value) > thresholds.interruption_threshold:
            return True
    return False


def detect_cascade_candidates(
    agents: list[AgentState],
    thresholds: DebateThresholds,
    just_interrupted_id: str,
    pre_update_states: dict[str, EmotionalState],
) -> list[AgentState]:
    """Find agents that newly exceed the threshold after an emotional update.

    Identifies agents that:
    - Were NOT above the threshold before the update
    - ARE above the threshold after the update
    - Are NOT the agent who just interrupted

    Args:
        agents: All agents with their updated emotional states.
        thresholds: The debate threshold configuration.
        just_interrupted_id: The ID of the agent who just interrupted.
        pre_update_states: Emotional states before the update, keyed by agent ID.

    Returns:
        A list of agents that are new cascade candidates.
    """
    candidates: list[AgentState] = []
    for agent in agents:
        agent_id = agent.persona.id

        # Exclude the agent who just interrupted
        if agent_id == just_interrupted_id:
            continue

        # Check if they were already above threshold before the update
        pre_state = pre_update_states.get(agent_id)
        if pre_state is not None:
            # Create a temporary AgentState-like check using the pre-update state
            was_above = _exceeds_threshold(pre_state, thresholds)
            if was_above:
                continue

        # Check if they now exceed the threshold
        is_above = _exceeds_threshold(agent.current_emotional_state, thresholds)
        if is_above:
            candidates.append(agent)

    if candidates:
        logger.info(
            "Cascade candidates detected: %s",
            [c.persona.name for c in candidates],
        )
    return candidates
