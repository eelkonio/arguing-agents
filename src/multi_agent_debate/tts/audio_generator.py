"""Audio generator pipeline — orchestrates TTS for full debate audio.

Supports both Polly (AWS cloud) and Kokoro (local) backends.
"""

from __future__ import annotations

import io
import logging
import pathlib
from dataclasses import dataclass

import numpy as np
from pydub import AudioSegment as PydubSegment  # type: ignore[import-untyped]

from multi_agent_debate.models.agent import AgentPersona
from multi_agent_debate.models.audio import AudioJobStatus
from multi_agent_debate.storage.store import DebateStore
from multi_agent_debate.tts.voice_assigner import VoiceAssigner, VoiceConfig

logger = logging.getLogger(__name__)

_PAUSE_BETWEEN_SPEAKERS_MS = 400


@dataclass
class ScriptSegment:
    """A single segment of the audio script."""

    text: str
    voice: VoiceConfig
    segment_type: str  # "narrator", "agent", "intro", "ack"


class AudioGenerator:
    """Orchestrates the full audio generation pipeline."""

    def __init__(
        self,
        voice_assigner: VoiceAssigner,
        store: DebateStore,
        output_dir: str = "./data/audio",
        polly_adapter: object | None = None,
        kokoro_adapter: object | None = None,
        tts_backend: str = "polly",
    ) -> None:
        self._voice_assigner = voice_assigner
        self._store = store
        self._output_dir = output_dir
        self._polly = polly_adapter
        self._kokoro = kokoro_adapter
        self._tts_backend = tts_backend

    async def _generate_segment_audio(self, text: str, voice: VoiceConfig) -> PydubSegment:
        """Generate audio for a single segment using the configured backend."""
        if self._tts_backend == "kokoro" and self._kokoro is not None:
            return await self._generate_kokoro(text, voice)
        if self._polly is not None:
            return await self._generate_polly(text, voice)
        msg = "No TTS backend available"
        raise RuntimeError(msg)

    async def _generate_polly(self, text: str, voice: VoiceConfig) -> PydubSegment:
        """Generate audio via Polly (returns MP3 directly)."""
        mp3_bytes = await self._polly.generate_audio(text, voice.voice_id)  # type: ignore[union-attr]
        return PydubSegment.from_mp3(io.BytesIO(mp3_bytes))

    async def _generate_kokoro(self, text: str, voice: VoiceConfig) -> PydubSegment:
        """Generate audio via Kokoro (returns numpy array)."""
        import asyncio

        loop = asyncio.get_running_loop()
        audio_array: np.ndarray = await loop.run_in_executor(
            None,
            self._kokoro.generate_audio,  # type: ignore[union-attr]
            text,
            voice.voice_id,
            voice.speed,
        )
        return self._numpy_to_pydub(audio_array, 24000)

    async def generate_debate_audio(self, session_id: str) -> None:
        """Generate audio for a completed debate session."""
        try:
            await self._store.update_audio_status(
                session_id, AudioJobStatus.GENERATING.value
            )

            detail = await self._store.get_session_detail(session_id)
            if detail is None:
                await self._store.update_audio_status(
                    session_id, AudioJobStatus.FAILED.value,
                    error_message=f"Session '{session_id}' not found",
                )
                return

            timeline = await self._store.get_session_timeline(session_id)

            agents: list[AgentPersona] = []
            for a in detail.get("agents", []):
                agents.append(AgentPersona(**a["persona"]))

            voice_map = self._voice_assigner.assign_voices(agents)
            narrator_voice = self._voice_assigner.get_narrator_voice()

            for agent in agents:
                vc = voice_map.get(agent.id)
                logger.info(
                    "Voice assignment: %s → %s (speed=%.2f, gender=%s)",
                    agent.name,
                    vc.voice_id if vc else "?",
                    vc.speed if vc else 1.0,
                    getattr(agent, "gender", "unknown"),
                )

            script = self._build_audio_script(detail, timeline, voice_map, narrator_voice)

            if not script:
                await self._store.update_audio_status(
                    session_id, AudioJobStatus.FAILED.value,
                    error_message="No audio segments to generate",
                )
                return

            total = len(script)
            audio_segments: list[PydubSegment] = []

            for i, seg in enumerate(script):
                try:
                    pydub_seg = await self._generate_segment_audio(seg.text, seg.voice)
                    audio_segments.append(pydub_seg)
                except Exception:
                    logger.exception(
                        "Failed segment %d/%d (voice=%s, text=%s...)",
                        i + 1, total, seg.voice.voice_id, seg.text[:50],
                    )
                    audio_segments.append(PydubSegment.silent(duration=1000))

                progress = self.calculate_progress(i + 1, total)
                await self._store.update_audio_progress(session_id, progress)
                logger.info(
                    "Audio %d/%d (%d%%) voice=%s backend=%s",
                    i + 1, total, progress, seg.voice.voice_id, self._tts_backend,
                )

            silence = PydubSegment.silent(duration=_PAUSE_BETWEEN_SPEAKERS_MS)
            combined = audio_segments[0]
            for seg in audio_segments[1:]:
                combined = combined + silence + seg

            out_dir = pathlib.Path(self._output_dir)
            out_dir.mkdir(parents=True, exist_ok=True)
            mp3_path = out_dir / f"{session_id}.mp3"
            combined.export(str(mp3_path), format="mp3")

            await self._store.set_audio_path(session_id, str(mp3_path))
            await self._store.update_audio_status(session_id, AudioJobStatus.COMPLETED.value)
            logger.info("Audio completed: session '%s' → %s", session_id, mp3_path)

        except Exception as exc:
            logger.exception("Audio generation failed for session '%s'", session_id)
            await self._store.update_audio_status(
                session_id, AudioJobStatus.FAILED.value, error_message=str(exc),
            )

    def _build_audio_script(
        self,
        session_detail: dict,
        timeline: list[dict],
        voice_map: dict[str, VoiceConfig],
        narrator_voice: VoiceConfig,
    ) -> list[ScriptSegment]:
        """Build the ordered list of audio script segments."""
        segments: list[ScriptSegment] = []
        topic = session_detail.get("topic", "this topic")
        agents_data = session_detail.get("agents", [])

        segments.append(ScriptSegment(
            text=f"Welcome to today's debate on {topic}.",
            voice=narrator_voice,
            segment_type="narrator",
        ))

        ack_phrases = [
            "Thank you for having me.",
            "Glad to be here.",
            "Happy to participate.",
            "Looking forward to this discussion.",
            "Thank you.",
        ]

        for idx, agent_data in enumerate(agents_data):
            persona = agent_data.get("persona", {})
            name = persona.get("name", "Unknown")
            expertise = persona.get("expertise", "")
            background = persona.get("background", "")
            agent_id = agent_data.get("id", "")

            intro_text = f"Let me introduce {name}"
            if expertise:
                intro_text += f", {expertise}"
            if background:
                intro_text += f". {background}"

            segments.append(ScriptSegment(
                text=intro_text, voice=narrator_voice, segment_type="intro",
            ))

            voice = voice_map.get(agent_id, narrator_voice)
            segments.append(ScriptSegment(
                text=ack_phrases[idx % len(ack_phrases)],
                voice=voice,
                segment_type="ack",
            ))

        segments.append(ScriptSegment(
            text="Let the debate begin.",
            voice=narrator_voice,
            segment_type="narrator",
        ))

        for entry in timeline:
            entry_type = entry.get("type", "")
            content = entry.get("content", "")
            agent_id = entry.get("agent_id")
            agent_name = entry.get("agent_name", "")

            if entry_type in ("leader-announcement", "leader-prompt"):
                segments.append(ScriptSegment(
                    text=content, voice=narrator_voice, segment_type="narrator",
                ))
            elif entry_type in ("statement", "interruption", "closing-argument"):
                if agent_name:
                    segments.append(ScriptSegment(
                        text=f"{agent_name}.",
                        voice=narrator_voice,
                        segment_type="narrator",
                    ))

                voice = voice_map.get(agent_id or "", narrator_voice)
                segments.append(ScriptSegment(
                    text=content, voice=voice, segment_type="agent",
                ))

        return segments

    @staticmethod
    def _numpy_to_pydub(audio_array: np.ndarray, sample_rate: int) -> PydubSegment:
        """Convert a numpy float32 audio array to a pydub AudioSegment."""
        import scipy.io.wavfile as wavfile  # type: ignore[import-untyped]

        audio_int16 = np.int16(audio_array / (np.max(np.abs(audio_array)) + 1e-9) * 32767)
        buf = io.BytesIO()
        wavfile.write(buf, sample_rate, audio_int16)
        buf.seek(0)
        return PydubSegment.from_wav(buf)

    @staticmethod
    def calculate_progress(processed: int, total: int) -> int:
        """Calculate progress percentage."""
        if total == 0:
            return 0
        return int(processed / total * 100)
