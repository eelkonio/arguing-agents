"""Debate models: Statement, DebateStatus, DebateSession, AgentSummary, DebateSummary, EmotionalStateUpdate."""

from enum import Enum

from pydantic import BaseModel

from multi_agent_debate.models.agent import AgentState, EmotionalState
from multi_agent_debate.models.config import DebateConfig


class Statement(BaseModel):
    id: str
    agent_id: str
    agent_name: str
    content: str
    is_interruption: bool = False
    is_closing_argument: bool = False
    timestamp: float
    emotional_state_at_time: EmotionalState


class DebateStatus(str, Enum):
    CONFIGURING = "configuring"
    PERSONAS_READY = "personas-ready"
    RUNNING = "running"
    PAUSED = "paused"
    CLOSING_PHASE = "closing-phase"
    ENDED = "ended"


class DebateSession(BaseModel):
    id: str
    config: DebateConfig
    agents: list[AgentState] = []
    statements: list[Statement] = []
    status: DebateStatus = DebateStatus.CONFIGURING
    turn_count: int = 0
    created_at: float
    started_at: float | None = None
    ended_at: float | None = None


class AgentSummary(BaseModel):
    agent_id: str
    agent_name: str
    statement_count: int
    interruption_count: int
    final_emotional_state: EmotionalState


class DebateSummary(BaseModel):
    total_statements: int
    total_interruptions: int
    agent_summaries: list[AgentSummary]
    duration: float


class EmotionalStateUpdate(BaseModel):
    agent_id: str
    new_state: EmotionalState
