"""Agent models: EmotionalState, AgentPersona, AgentState."""

from pydantic import BaseModel, Field


class EmotionalState(BaseModel):
    anger: float = Field(0.0, ge=0.0, le=1.0)
    enthusiasm: float = Field(0.0, ge=0.0, le=1.0)
    frustration: float = Field(0.0, ge=0.0, le=1.0)
    agreement: float = Field(0.0, ge=0.0, le=1.0)
    resentment: float = Field(0.0, ge=0.0, le=1.0)
    confidence: float = Field(0.0, ge=0.0, le=1.0)
    withdrawal: float = Field(0.0, ge=0.0, le=1.0)


class AgentPersona(BaseModel):
    id: str
    name: str
    background: str
    expertise: str
    character_traits: list[str]
    initial_emotional_state: EmotionalState
    avatar_color: str


class AgentState(BaseModel):
    persona: AgentPersona
    current_emotional_state: EmotionalState
    consecutive_silent_turns: int = 0
    total_statements: int = 0
    is_interrupting: bool = False
    consecutive_interruptions: int = 0
