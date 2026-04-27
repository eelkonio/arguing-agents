"""Debate Creator service — generates agent personas."""

from __future__ import annotations

import logging
import random
import uuid

from multi_agent_debate.llm.adapters.base import (
    ChatMessage,
    ChatRequest,
    ChatResponse,
    LLMAdapter,
)
from multi_agent_debate.llm.services._json_utils import extract_json
from multi_agent_debate.models.agent import AgentPersona, EmotionalState
from multi_agent_debate.profanity import PROFANITY_INSTRUCTION

logger = logging.getLogger(__name__)

_AVATAR_COLORS = [
    "#E57373",
    "#F06292",
    "#BA68C8",
    "#9575CD",
    "#7986CB",
    "#64B5F6",
    "#4FC3F7",
    "#4DD0E1",
    "#4DB6AC",
    "#81C784",
    "#AED581",
    "#DCE775",
    "#FFD54F",
    "#FFB74D",
    "#FF8A65",
    "#A1887F",
]


def _build_system_prompt(topic: str, agent_count: int, theme: str | None) -> str:
    """Build the system prompt for persona generation."""
    theme_instruction = ""
    if theme:
        theme_instruction = (
            f"\nThe agents should be themed as: {theme}. "
            "Derive their names, backgrounds, and character traits from this theme."
        )

    return f"""{PROFANITY_INSTRUCTION}

You are a debate persona generator. Generate exactly {agent_count} unique debate agent personas for the following topic:

Topic: "{topic}"{theme_instruction}

Each persona must have:
- "name": A unique, memorable name
- "gender": Either "male" or "female"
- "background": A brief background description (1-2 sentences)
- "expertise": Their area of expertise relevant to the topic
- "character_traits": A list of 2-4 personality traits (e.g., "confrontational", "empathetic", "analytical")
- "initial_emotional_state": An object with these dimensions, each a float between 0.0 and 1.0:
  anger, enthusiasm, frustration, agreement, resentment, confidence, withdrawal

The personas should represent diverse and contrasting viewpoints on the topic.

Respond with ONLY a JSON array of {agent_count} persona objects. No other text."""


def _deduplicate_names(personas: list[dict[str, object]]) -> list[dict[str, object]]:
    """Append numeric suffixes to duplicate names."""
    seen: dict[str, int] = {}
    for persona in personas:
        name = str(persona.get("name", "Agent"))
        if name in seen:
            seen[name] += 1
            persona["name"] = f"{name}_{seen[name]}"
        else:
            seen[name] = 1
    return personas


def _enrich_persona(raw: dict[str, object]) -> AgentPersona:
    """Convert a raw dict into an AgentPersona, filling defaults for missing fields."""
    # Parse emotional state, defaulting missing dimensions to a small random value
    raw_emotions = raw.get("initial_emotional_state", {})
    if not isinstance(raw_emotions, dict):
        raw_emotions = {}

    emotion_fields = {
        "anger": float(raw_emotions.get("anger", round(random.uniform(0.0, 0.3), 2))),
        "enthusiasm": float(raw_emotions.get("enthusiasm", round(random.uniform(0.2, 0.6), 2))),
        "frustration": float(raw_emotions.get("frustration", round(random.uniform(0.0, 0.3), 2))),
        "agreement": float(raw_emotions.get("agreement", round(random.uniform(0.2, 0.5), 2))),
        "resentment": float(raw_emotions.get("resentment", round(random.uniform(0.0, 0.2), 2))),
        "confidence": float(raw_emotions.get("confidence", round(random.uniform(0.3, 0.7), 2))),
        "withdrawal": float(raw_emotions.get("withdrawal", round(random.uniform(0.0, 0.2), 2))),
    }
    # Clamp to [0, 1]
    for key in emotion_fields:
        emotion_fields[key] = max(0.0, min(1.0, emotion_fields[key]))

    emotional_state = EmotionalState(**emotion_fields)

    # Ensure character_traits is a list
    traits = raw.get("character_traits", [])
    if not isinstance(traits, list) or len(traits) == 0:
        traits = ["analytical"]

    return AgentPersona(
        id=str(uuid.uuid4()),
        name=str(raw.get("name", f"Agent-{uuid.uuid4().hex[:6]}")),
        background=str(raw.get("background", "A knowledgeable debate participant.")),
        expertise=str(raw.get("expertise", "General knowledge")),
        character_traits=[str(t) for t in traits],
        initial_emotional_state=emotional_state,
        avatar_color=random.choice(_AVATAR_COLORS),
        gender=str(raw.get("gender", "unknown")).lower(),
    )


class DebateCreatorService:
    """Generates agent personas for a debate session using an LLM."""

    def __init__(self, adapter: LLMAdapter) -> None:
        self._adapter = adapter

    async def generate_personas(
        self,
        topic: str,
        agent_count: int,
        theme: str | None = None,
    ) -> list[AgentPersona]:
        """Generate *agent_count* unique personas for the given topic.

        Handles:
        - Persona count mismatch (re-prompts once)
        - Missing fields (fills defaults via Pydantic)
        - Duplicate names (appends numeric suffix)
        """
        system_prompt = _build_system_prompt(topic, agent_count, theme)

        response = await self._adapter.chat(
            ChatRequest(
                messages=[
                    ChatMessage(role="system", content=system_prompt),
                    ChatMessage(
                        role="user",
                        content=f"Generate {agent_count} debate personas now.",
                    ),
                ],
                temperature=0.9,
                max_tokens=4096,
            )
        )

        raw_personas = self._parse_personas(response)

        # Re-prompt once if count mismatch
        if len(raw_personas) != agent_count:
            logger.warning(
                "Persona count mismatch: expected %d, got %d. Re-prompting.",
                agent_count,
                len(raw_personas),
            )
            retry_response = await self._adapter.chat(
                ChatRequest(
                    messages=[
                        ChatMessage(role="system", content=system_prompt),
                        ChatMessage(
                            role="user",
                            content=f"Generate {agent_count} debate personas now.",
                        ),
                        ChatMessage(role="assistant", content=response.content),
                        ChatMessage(
                            role="user",
                            content=(
                                f"You generated {len(raw_personas)} personas but I need "
                                f"exactly {agent_count}. Please regenerate exactly "
                                f"{agent_count} personas as a JSON array."
                            ),
                        ),
                    ],
                    temperature=0.9,
                    max_tokens=4096,
                )
            )
            raw_personas = self._parse_personas(retry_response)

        # Deduplicate names
        raw_personas = _deduplicate_names(raw_personas)

        # Convert to AgentPersona objects
        personas = [_enrich_persona(p) for p in raw_personas]

        # Ensure unique avatar colors where possible
        used_colors: set[str] = set()
        for persona in personas:
            if persona.avatar_color in used_colors:
                available = [c for c in _AVATAR_COLORS if c not in used_colors]
                if available:
                    persona.avatar_color = random.choice(available)
            used_colors.add(persona.avatar_color)

        logger.info(
            "Generated %d personas for topic '%s'",
            len(personas),
            topic,
        )
        return personas

    @staticmethod
    def _parse_personas(response: ChatResponse) -> list[dict[str, object]]:
        """Extract a list of persona dicts from the LLM response."""
        data = extract_json(response.content)

        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]

        if isinstance(data, dict):
            # LLM might wrap in {"personas": [...]}
            for key in ("personas", "agents", "participants"):
                if key in data and isinstance(data[key], list):
                    return [item for item in data[key] if isinstance(item, dict)]
            # Single persona wrapped in an object
            return [data]

        return []
