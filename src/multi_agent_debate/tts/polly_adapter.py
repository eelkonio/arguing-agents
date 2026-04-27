"""Amazon Polly TTS adapter using AWS CLI subprocess."""

from __future__ import annotations

import asyncio
import logging
import os
import tempfile

logger = logging.getLogger(__name__)


class PollyAdapter:
    """Generates speech audio via AWS Polly's generative engine.

    Uses the AWS CLI ``polly synthesize-speech`` command, following the
    same subprocess pattern as the Bedrock adapter.
    """

    def __init__(self, region: str = "eu-central-1") -> None:
        self._region = region

    async def generate_audio(self, text: str, voice_id: str) -> bytes:
        """Generate MP3 audio bytes for the given text and voice.

        Args:
            text: The text to synthesize.
            voice_id: Polly voice ID (e.g., "Matthew", "Ruth").

        Returns:
            Raw MP3 bytes.
        """
        fd, tmp_path = tempfile.mkstemp(suffix=".mp3", prefix="polly_")
        os.close(fd)

        try:
            proc = await asyncio.create_subprocess_exec(
                "aws", "polly", "synthesize-speech",
                "--text", text,
                "--output-format", "mp3",
                "--voice-id", voice_id,
                "--engine", "generative",
                "--region", self._region,
                "--output", "json",
                tmp_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)

            if proc.returncode != 0:
                error_msg = stderr.decode().strip() if stderr else "unknown error"
                msg = f"Polly CLI error (voice={voice_id}): {error_msg}"
                raise RuntimeError(msg)

            with open(tmp_path, "rb") as f:
                return f.read()
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    @property
    def is_available(self) -> bool:
        """Check if AWS CLI is available."""
        import shutil
        return shutil.which("aws") is not None
