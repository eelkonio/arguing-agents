"""Audio generation models: AudioJobStatus, AudioJob."""

from enum import Enum

from pydantic import BaseModel, Field


class AudioJobStatus(str, Enum):
    PENDING = "pending"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"


class AudioJob(BaseModel):
    session_id: str
    status: AudioJobStatus = AudioJobStatus.PENDING
    progress: int = Field(0, ge=0, le=100)  # 0-100
    audio_path: str | None = None
    error_message: str | None = None
    created_at: float | None = None
    completed_at: float | None = None
