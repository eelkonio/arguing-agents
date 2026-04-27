"""Voice assignment for TTS — supports both Polly and Kokoro voices."""

from __future__ import annotations

from dataclasses import dataclass

from multi_agent_debate.models.agent import AgentPersona

# --- Polly voices (generative engine) ---
POLLY_MALE_VOICES = ["Matthew", "Stephen", "Gregory", "Kevin"]
POLLY_FEMALE_VOICES = ["Ruth", "Danielle", "Joanna", "Amy"]
POLLY_NARRATOR_VOICE = "Matthew"

# --- Kokoro voices (American English) ---
KOKORO_MALE_VOICES = [
    "am_fenrir", "am_michael", "am_puck", "am_adam",
    "am_echo", "am_eric", "am_liam", "am_onyx",
]
KOKORO_FEMALE_VOICES = [
    "af_heart", "af_bella", "af_nicole", "af_aoede",
    "af_kore", "af_sarah", "af_alloy", "af_nova",
    "af_sky", "af_jessica", "af_river",
]
# Narrator is female (as requested) so male voices are freed up for debaters
KOKORO_NARRATOR_VOICE = "af_heart"

# Speed variations when we run out of unique voices — makes them sound different
_SPEED_VARIATIONS = [1.0, 0.9, 1.1, 0.85, 1.15, 0.95, 1.05]

# Keywords for gender inference (fallback for old debates without gender field)
_FEMALE_HINTS = frozenset({
    "female", "woman", "girl", "she", "her", "mother", "sister",
    "queen", "princess", "actress", "goddess", "lady", "madam",
    "mrs", "ms", "miss", "feminine", "matriarch", "priestess",
    "empress", "duchess", "countess", "baroness", "heroine",
    "aunt", "niece", "grandmother", "wife", "daughter",
    "athena", "hera", "aphrodite", "artemis", "demeter", "persephone",
    "mary", "elizabeth", "victoria", "cleopatra", "joan",
    "margaret", "catherine", "anne", "jane", "sarah", "emily",
    "maria", "rosa", "isabella", "sophia", "olivia", "emma",
    "charlotte", "amelia", "alice", "helen", "ruth", "rachel",
    "rebecca", "martha", "eve", "miriam", "esther", "naomi",
})


@dataclass
class VoiceConfig:
    """Voice configuration for a single agent."""

    voice_id: str
    speed: float = 1.0


def _infer_gender(persona: AgentPersona) -> str:
    """Infer gender from persona fields when the gender field is missing."""
    if hasattr(persona, "gender") and persona.gender in ("male", "female"):
        return persona.gender

    text = " ".join([
        persona.name.lower(),
        persona.background.lower(),
        " ".join(t.lower() for t in persona.character_traits),
    ])
    words = set(text.split())
    if words & _FEMALE_HINTS:
        return "female"

    name_lower = persona.name.lower()
    for hint in _FEMALE_HINTS:
        if hint in name_lower:
            return "female"

    return "male"


class VoiceAssigner:
    """Assigns distinct voices to debate agents for either Polly or Kokoro."""

    def __init__(self, backend: str = "polly") -> None:
        self._backend = backend

    def assign_voices(self, agents: list[AgentPersona]) -> dict[str, VoiceConfig]:
        """Map each agent_id to a VoiceConfig (voice_id + speed).

        When there are more agents of one gender than available voices,
        voices are reused with different speed values to make them
        sound distinct.
        """
        if self._backend == "kokoro":
            male_pool = KOKORO_MALE_VOICES
            female_pool = KOKORO_FEMALE_VOICES
        else:
            male_pool = POLLY_MALE_VOICES
            female_pool = POLLY_FEMALE_VOICES

        male_idx = 0
        female_idx = 0
        mapping: dict[str, VoiceConfig] = {}

        for agent in agents:
            gender = _infer_gender(agent)
            if gender == "female":
                voice = female_pool[female_idx % len(female_pool)]
                speed = _SPEED_VARIATIONS[female_idx // len(female_pool) % len(_SPEED_VARIATIONS)]
                female_idx += 1
            else:
                voice = male_pool[male_idx % len(male_pool)]
                speed = _SPEED_VARIATIONS[male_idx // len(male_pool) % len(_SPEED_VARIATIONS)]
                male_idx += 1
            mapping[agent.id] = VoiceConfig(voice_id=voice, speed=speed)

        return mapping

    def get_narrator_voice(self) -> VoiceConfig:
        """Return the voice config for the debate leader / narrator."""
        if self._backend == "kokoro":
            return VoiceConfig(voice_id=KOKORO_NARRATOR_VOICE, speed=1.0)
        return VoiceConfig(voice_id=POLLY_NARRATOR_VOICE, speed=1.0)
