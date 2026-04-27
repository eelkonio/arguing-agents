"""Kokoro TTS adapter — local, free, fast text-to-speech."""

from __future__ import annotations

import logging
import os

import numpy as np

logger = logging.getLogger(__name__)

_KOKORO_SAMPLE_RATE = 24000

# American English voices — sorted by quality grade
KOKORO_FEMALE_VOICES = [
    "af_heart",    # A grade — best female voice
    "af_bella",    # A- grade
    "af_nicole",   # B- grade
    "af_aoede",    # C+ grade
    "af_kore",     # C+ grade
    "af_sarah",    # C+ grade
    "af_alloy",    # C grade
    "af_nova",     # C grade
    "af_sky",      # C- grade
    "af_jessica",  # D grade
    "af_river",    # D grade
]

KOKORO_MALE_VOICES = [
    "am_fenrir",   # C+ grade — best male voice
    "am_michael",  # C+ grade
    "am_puck",     # C+ grade
    "am_adam",      # F+ grade (limited data but distinct)
    "am_echo",     # D grade
    "am_eric",     # D grade
    "am_liam",     # D grade
    "am_onyx",     # D grade
]

# Narrator is female (as requested) — use the best female voice
KOKORO_NARRATOR_VOICE = "af_heart"


class KokoroAdapter:
    """Generates speech audio via Kokoro-82M running locally.

    Kokoro is an 82M parameter TTS model that runs fast on CPU and
    even faster on Apple Silicon (MPS). Apache 2.0 licensed.
    """

    def __init__(self) -> None:
        self._pipeline: object | None = None

    def _ensure_loaded(self) -> None:
        """Lazily initialize the Kokoro pipeline on first use."""
        if self._pipeline is not None:
            return

        os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"

        from kokoro import KPipeline  # type: ignore[import-untyped]

        self._pipeline = KPipeline(lang_code="a", repo_id="hexgrad/Kokoro-82M")
        logger.info("Kokoro pipeline initialized")

    def generate_audio(self, text: str, voice: str, speed: float = 1.0) -> np.ndarray:
        """Generate audio for the given text.

        Args:
            text: Text to synthesize.
            voice: Kokoro voice ID (e.g., "af_heart", "am_michael").
            speed: Playback speed multiplier (0.8 = slower, 1.2 = faster).

        Returns:
            NumPy float32 array of audio samples at 24 kHz.
        """
        self._ensure_loaded()

        from kokoro import KPipeline  # type: ignore[import-untyped]

        pipeline: KPipeline = self._pipeline  # type: ignore[assignment]

        # Kokoro yields segments — collect and concatenate them all
        audio_parts: list[np.ndarray] = []
        for _gs, _ps, audio in pipeline(text, voice=voice, speed=speed):
            audio_parts.append(audio)

        if not audio_parts:
            # Return 0.5s of silence if nothing was generated
            return np.zeros(int(0.5 * _KOKORO_SAMPLE_RATE), dtype=np.float32)

        return np.concatenate(audio_parts)

    @property
    def sample_rate(self) -> int:
        """Kokoro's native sample rate (24 kHz)."""
        return _KOKORO_SAMPLE_RATE

    @property
    def is_available(self) -> bool:
        """Check if Kokoro is installed."""
        try:
            import kokoro  # type: ignore[import-untyped]  # noqa: F401
            return True
        except ImportError:
            return False
