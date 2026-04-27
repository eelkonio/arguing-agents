"""TTS module for generating audio from completed debates."""

from multi_agent_debate.tts.audio_generator import AudioGenerator
from multi_agent_debate.tts.kokoro_adapter import KokoroAdapter
from multi_agent_debate.tts.polly_adapter import PollyAdapter
from multi_agent_debate.tts.voice_assigner import VoiceAssigner

__all__ = ["AudioGenerator", "KokoroAdapter", "PollyAdapter", "VoiceAssigner"]
