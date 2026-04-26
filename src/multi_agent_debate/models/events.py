"""SSE event models: DebateEventType and discriminated union DebateEvent."""

from enum import Enum
from typing import Annotated, Literal, Union

from pydantic import BaseModel, Discriminator

from multi_agent_debate.models.agent import EmotionalState
from multi_agent_debate.models.debate import DebateSummary, Statement


class DebateEventType(str, Enum):
    LEADER_ANNOUNCEMENT = "leader-announcement"
    AGENT_SELECTED = "agent-selected"
    STATEMENT = "statement"
    INTERRUPTION = "interruption"
    EMOTIONS_UPDATED = "emotions-updated"
    LEADER_PROMPT = "leader-prompt"
    DEBATE_STARTED = "debate-started"
    DEBATE_PAUSED = "debate-paused"
    DEBATE_RESUMED = "debate-resumed"
    DEBATE_ENDED = "debate-ended"
    CLOSING_PHASE_STARTED = "closing-phase-started"
    CLOSING_ARGUMENT = "closing-argument"
    ERROR = "error"


class LeaderAnnouncementEvent(BaseModel):
    type: Literal["leader-announcement"] = "leader-announcement"
    content: str
    timestamp: float


class AgentSelectedEvent(BaseModel):
    type: Literal["agent-selected"] = "agent-selected"
    agent_id: str
    agent_name: str
    timestamp: float


class StatementEvent(BaseModel):
    type: Literal["statement"] = "statement"
    statement: Statement
    timestamp: float


class InterruptionEvent(BaseModel):
    type: Literal["interruption"] = "interruption"
    statement: Statement
    interrupted_agent_id: str
    timestamp: float


class EmotionsUpdatedEvent(BaseModel):
    type: Literal["emotions-updated"] = "emotions-updated"
    states: dict[str, EmotionalState]
    timestamp: float


class LeaderPromptEvent(BaseModel):
    type: Literal["leader-prompt"] = "leader-prompt"
    agent_id: str
    agent_name: str
    content: str
    timestamp: float


class DebateStartedEvent(BaseModel):
    type: Literal["debate-started"] = "debate-started"
    timestamp: float


class DebatePausedEvent(BaseModel):
    type: Literal["debate-paused"] = "debate-paused"
    timestamp: float


class DebateResumedEvent(BaseModel):
    type: Literal["debate-resumed"] = "debate-resumed"
    timestamp: float


class DebateEndedEvent(BaseModel):
    type: Literal["debate-ended"] = "debate-ended"
    summary: DebateSummary
    timestamp: float


class ErrorEvent(BaseModel):
    type: Literal["error"] = "error"
    message: str
    backend_id: str | None = None
    agent_id: str | None = None
    timestamp: float


class ClosingPhaseStartedEvent(BaseModel):
    type: Literal["closing-phase-started"] = "closing-phase-started"
    timestamp: float


class ClosingArgumentEvent(BaseModel):
    type: Literal["closing-argument"] = "closing-argument"
    statement: Statement
    timestamp: float


DebateEvent = Annotated[
    Union[
        LeaderAnnouncementEvent,
        AgentSelectedEvent,
        StatementEvent,
        InterruptionEvent,
        EmotionsUpdatedEvent,
        LeaderPromptEvent,
        DebateStartedEvent,
        DebatePausedEvent,
        DebateResumedEvent,
        DebateEndedEvent,
        ClosingPhaseStartedEvent,
        ClosingArgumentEvent,
        ErrorEvent,
    ],
    Discriminator("type"),
]
