"""Agent Statement service — generates agent statements."""

from __future__ import annotations

import logging

from multi_agent_debate.llm.adapters.base import (
    ChatMessage,
    ChatRequest,
    LLMAdapter,
)
from multi_agent_debate.models.agent import AgentState
from multi_agent_debate.models.debate import Statement
from multi_agent_debate.profanity import PROFANITY_INSTRUCTION

logger = logging.getLogger(__name__)


def _format_recent_history(history: list[Statement], limit: int = 10) -> str:
    """Format recent statements for inclusion in prompts."""
    if not history:
        return "(No statements yet — you are the first to speak.)"
    recent = history[-limit:]
    lines: list[str] = []
    for stmt in recent:
        prefix = "[INTERRUPTION] " if stmt.is_interruption else ""
        lines.append(f"{prefix}{stmt.agent_name}: {stmt.content}")
    return "\n".join(lines)


class AgentStatementService:
    """Generates debate statements for individual agents."""

    def __init__(self, adapter: LLMAdapter) -> None:
        self._adapter = adapter

    async def generate_statement(
        self,
        agent: AgentState,
        recent_history: list[Statement],
        is_interruption: bool = False,
    ) -> str:
        """Generate a statement for the given agent.

        Args:
            agent: The agent's current state (persona + emotions).
            recent_history: Recent statements in the debate.
            is_interruption: If True, generate a shorter, more emotionally
                charged interruption statement.

        Returns:
            The generated statement text.
        """
        persona = agent.persona
        es = agent.current_emotional_state
        history_text = _format_recent_history(recent_history)

        emotion_description = (
            f"anger={es.anger:.2f}, enthusiasm={es.enthusiasm:.2f}, "
            f"frustration={es.frustration:.2f}, agreement={es.agreement:.2f}, "
            f"resentment={es.resentment:.2f}, confidence={es.confidence:.2f}, "
            f"withdrawal={es.withdrawal:.2f}"
        )

        if is_interruption:
            style_instruction = (
                "You are INTERRUPTING another speaker. Your statement must be:\n"
                "- SHORT (1-2 sentences maximum)\n"
                "- Emotionally charged and reactive\n"
                "- Directly responding to what was just said\n"
                "- Reflecting your strongest current emotion"
            )
            max_tokens = 256
        else:
            style_instruction = (
                "Generate a brief debate statement (2-4 sentences) that:\n"
                "- Directly responds to the recent discussion\n"
                "- Reflects your current emotional state in tone and word choice\n"
                "- Draws on your expertise and background\n"
                "- Stays true to your character traits"
            )
            max_tokens = 512

        system_prompt = f"""{PROFANITY_INSTRUCTION}

You are {persona.name}, a debate participant.

Your background: {persona.background}
Your expertise: {persona.expertise}
Your character traits: {', '.join(persona.character_traits)}
Your current emotional state: {emotion_description}

{style_instruction}

Recent discussion:
{history_text}

Respond with ONLY your statement text. No quotes, no prefixes, no meta-commentary."""

        response = await self._adapter.chat(
            ChatRequest(
                messages=[
                    ChatMessage(role="system", content=system_prompt),
                    ChatMessage(
                        role="user",
                        content="Deliver your statement now."
                        if not is_interruption
                        else "Interrupt now!",
                    ),
                ],
                temperature=0.8,
                max_tokens=max_tokens,
            )
        )

        statement_text = response.content.strip()

        # Remove common LLM artifacts: leading quotes, name prefixes
        if statement_text.startswith('"') and statement_text.endswith('"'):
            statement_text = statement_text[1:-1]
        if statement_text.startswith(f"{persona.name}:"):
            statement_text = statement_text[len(persona.name) + 1 :].strip()

        logger.info(
            "Generated %s for agent '%s' (%d chars)",
            "interruption" if is_interruption else "statement",
            persona.name,
            len(statement_text),
        )
        return statement_text

    async def generate_closing_argument(
        self,
        agent: AgentState,
        recent_history: list[Statement],
    ) -> str:
        """Generate a closing argument for the given agent.

        Args:
            agent: The agent's current state (persona + emotions).
            recent_history: Recent statements in the debate.

        Returns:
            The generated closing argument text.
        """
        persona = agent.persona
        es = agent.current_emotional_state
        history_text = _format_recent_history(recent_history)

        emotion_description = (
            f"anger={es.anger:.2f}, enthusiasm={es.enthusiasm:.2f}, "
            f"frustration={es.frustration:.2f}, agreement={es.agreement:.2f}, "
            f"resentment={es.resentment:.2f}, confidence={es.confidence:.2f}, "
            f"withdrawal={es.withdrawal:.2f}"
        )

        system_prompt = f"""{PROFANITY_INSTRUCTION}

You are {persona.name}, a debate participant delivering your closing argument.

Your background: {persona.background}
Your expertise: {persona.expertise}
Your character traits: {', '.join(persona.character_traits)}
Your current emotional state: {emotion_description}

This is your CLOSING ARGUMENT. Generate a concluding statement (3-5 sentences) that:
- Summarises your position on the debate topic
- Reflects your final emotional state in tone and word choice
- References key points from the discussion
- Stays true to your character traits
- Provides a memorable conclusion

Recent discussion:
{history_text}

Respond with ONLY your closing argument text. No quotes, no prefixes, no meta-commentary."""

        response = await self._adapter.chat(
            ChatRequest(
                messages=[
                    ChatMessage(role="system", content=system_prompt),
                    ChatMessage(
                        role="user",
                        content="Deliver your closing argument now.",
                    ),
                ],
                temperature=0.8,
                max_tokens=768,
            )
        )

        text = response.content.strip()

        # Remove common LLM artifacts
        if text.startswith('"') and text.endswith('"'):
            text = text[1:-1]
        if text.startswith(f"{persona.name}:"):
            text = text[len(persona.name) + 1 :].strip()

        logger.info(
            "Generated closing argument for agent '%s' (%d chars)",
            persona.name,
            len(text),
        )
        return text
