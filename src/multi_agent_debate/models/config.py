"""Configuration models: LLMProvider, LLMBackendConfig, BackendAssignments, DebateConfig, DebateThresholds."""

from enum import Enum

from pydantic import BaseModel, Field


class LLMProvider(str, Enum):
    BEDROCK = "bedrock"
    OLLAMA = "ollama"


class LLMBackendConfig(BaseModel):
    provider: LLMProvider
    model_id: str = "eu.anthropic.claude-opus-4-6-v1"
    base_url: str | None = None  # For Ollama, defaults to "http://localhost:11434"
    region: str = "eu-central-1"
    cross_account_role_arn: str | None = None


class BackendAssignments(BaseModel):
    debate_creator: LLMBackendConfig
    debate_leader: LLMBackendConfig
    psycho_pusher: LLMBackendConfig
    agents: dict[str, LLMBackendConfig] = {}
    default_agent_backend: LLMBackendConfig


class DebateConfig(BaseModel):
    topic: str = Field(..., min_length=1, max_length=1024)
    agent_count: int = Field(..., ge=2, le=10)
    agent_theme: str | None = Field(None, max_length=200)
    max_turns: int | None = Field(None, ge=1)
    backend_assignments: BackendAssignments


class DebateThresholds(BaseModel):
    interruption_threshold: float = 0.8
    interruption_dimensions: list[str] = ["anger", "enthusiasm"]
    silent_turn_threshold: int = 3
