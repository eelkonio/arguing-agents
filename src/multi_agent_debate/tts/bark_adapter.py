"""Bark TTS adapter for generating audio segments."""

from __future__ import annotations

import logging
import os

import numpy as np

logger = logging.getLogger(__name__)

# Bark's native sample rate
_BARK_SAMPLE_RATE = 24000

# All speaker presets we use
_ALL_PRESETS = [f"v2/en_speaker_{i}" for i in range(10)]


class BarkAdapter:
    """Wraps the Bark TTS model for generating individual audio segments."""

    def __init__(self, device: str = "auto") -> None:
        self._device = device
        self._model_loaded = False
        self._cached_presets: dict[str, np.ndarray] = {}

    def _resolve_device(self) -> str:
        """Detect the best available device: cuda > mps > cpu."""
        if self._device != "auto":
            return self._device
        import torch

        if torch.cuda.is_available():
            return "cuda"
        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            return "mps"
        return "cpu"

    def load_model(self) -> None:
        """Load the Bark model and pre-download all speaker presets."""
        import functools

        import torch

        resolved_device = self._resolve_device()
        logger.info("Bark: resolved device=%s (requested=%s)", resolved_device, self._device)

        _original_load = torch.load
        torch.load = functools.partial(_original_load, weights_only=False)  # type: ignore[assignment]

        os.environ["SUNO_USE_SMALL_MODELS"] = "1"

        if resolved_device in ("cuda", "mps"):
            os.environ["SUNO_ENABLE_GPU"] = "1"
            if resolved_device == "mps":
                os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"

        try:
            from bark import preload_models  # type: ignore[import-untyped]

            preload_models()

            # After loading, set transformers to offline mode so it stops
            # checking HuggingFace for tokenizer updates on every call.
            os.environ["TRANSFORMERS_OFFLINE"] = "1"
            os.environ["HF_HUB_OFFLINE"] = "1"

            self._model_loaded = True
            logger.info("Bark model loaded on device=%s (now offline)", resolved_device)
        finally:
            torch.load = _original_load  # type: ignore[assignment]

    def generate_audio(self, text: str, speaker_preset: str) -> np.ndarray:
        """Generate a WAV audio array for the given text.

        Splits long text into sentence-sized chunks to avoid Bark's
        ~13-second generation limit, then concatenates the results.

        Note: We pass history_prompt=None to avoid Bark downloading
        speaker presets from HuggingFace on every call. Voice variation
        comes from the text content and Bark's natural randomness.
        """
        if not self._model_loaded:
            self.load_model()

        from bark import generate_audio as bark_generate  # type: ignore[import-untyped]

        chunks = self._split_text(text)
        audio_parts: list[np.ndarray] = []

        for chunk in chunks:
            part: np.ndarray = bark_generate(chunk, history_prompt=None)
            audio_parts.append(part)

        if len(audio_parts) == 1:
            return audio_parts[0]

        # Concatenate with a tiny pause (0.15s silence) between chunks
        silence = np.zeros(int(0.15 * _BARK_SAMPLE_RATE), dtype=np.float32)
        combined: list[np.ndarray] = []
        for i, part in enumerate(audio_parts):
            combined.append(part)
            if i < len(audio_parts) - 1:
                combined.append(silence)
        return np.concatenate(combined)

    @staticmethod
    def _split_text(text: str, max_chars: int = 200) -> list[str]:
        """Split text into chunks that Bark can handle without cutoff.

        Splits on sentence boundaries (. ! ?) first, then on commas,
        keeping each chunk under max_chars.
        """
        if len(text) <= max_chars:
            return [text]

        import re

        # Split on sentence endings
        sentences = re.split(r"(?<=[.!?])\s+", text)

        chunks: list[str] = []
        current = ""

        for sentence in sentences:
            if len(current) + len(sentence) + 1 <= max_chars:
                current = f"{current} {sentence}".strip() if current else sentence
            else:
                if current:
                    chunks.append(current)
                # If a single sentence is too long, split on commas
                if len(sentence) > max_chars:
                    parts = re.split(r",\s*", sentence)
                    sub = ""
                    for part in parts:
                        if len(sub) + len(part) + 2 <= max_chars:
                            sub = f"{sub}, {part}".strip(", ") if sub else part
                        else:
                            if sub:
                                chunks.append(sub)
                            sub = part
                    current = sub
                else:
                    current = sentence

        if current:
            chunks.append(current)

        return chunks if chunks else [text]

    @property
    def sample_rate(self) -> int:
        """Bark's native sample rate (24 kHz)."""
        return _BARK_SAMPLE_RATE

    @property
    def is_available(self) -> bool:
        """Check if Bark is installed and importable."""
        try:
            import bark  # type: ignore[import-untyped]  # noqa: F401

            return True
        except ImportError:
            return False
