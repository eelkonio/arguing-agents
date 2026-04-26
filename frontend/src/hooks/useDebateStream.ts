import { useCallback, useEffect, useRef, useState } from "react";
import type {
  AgentState,
  DebateEvent,
  DebateStatus,
  DebateSummary,
  EmotionalState,
} from "../types";

export interface UseDebateStreamResult {
  events: DebateEvent[];
  agents: AgentState[];
  status: DebateStatus;
  error: string | null;
  summary: DebateSummary | null;
  /** The agent currently typing (selected but no statement yet) */
  typingAgent: { id: string; name: string } | null;
  /** Current turn number */
  turn: number;
}

/**
 * Custom hook that manages an EventSource connection to the debate SSE stream.
 * Parses incoming events and maintains local state for the debate UI.
 */
export function useDebateStream(
  sessionId: string | null,
  initialAgents: AgentState[],
): UseDebateStreamResult {
  const [events, setEvents] = useState<DebateEvent[]>([]);
  const [agents, setAgents] = useState<AgentState[]>(initialAgents);
  const [status, setStatus] = useState<DebateStatus>("personas-ready");
  const [error, setError] = useState<string | null>(null);
  const [summary, setSummary] = useState<DebateSummary | null>(null);
  const [typingAgent, setTypingAgent] = useState<{
    id: string;
    name: string;
  } | null>(null);
  const [turn, setTurn] = useState(0);
  const eventSourceRef = useRef<EventSource | null>(null);

  // Update agents when initialAgents changes (e.g. session loaded)
  useEffect(() => {
    setAgents(initialAgents);
  }, [initialAgents]);

  const handleEvent = useCallback(
    (event: DebateEvent) => {
      setEvents((prev) => [...prev, event]);

      switch (event.type) {
        case "debate-started":
          setStatus("running");
          break;

        case "debate-paused":
          setStatus("paused");
          break;

        case "debate-resumed":
          setStatus("running");
          break;

        case "debate-ended":
          setStatus("ended");
          setSummary(event.summary);
          setTypingAgent(null);
          break;

        case "closing-phase-started":
          setStatus("closing-phase");
          setTypingAgent(null);
          break;

        case "closing-argument":
          setTypingAgent(null);
          // Update agent statement count
          setAgents((prev) =>
            prev.map((a) =>
              a.persona.id === event.statement.agent_id
                ? { ...a, total_statements: a.total_statements + 1 }
                : a,
            ),
          );
          break;

        case "agent-selected":
          setTypingAgent({ id: event.agent_id, name: event.agent_name });
          break;

        case "statement":
          setTypingAgent(null);
          setTurn((t) => t + 1);
          // Update agent statement count
          setAgents((prev) =>
            prev.map((a) =>
              a.persona.id === event.statement.agent_id
                ? { ...a, total_statements: a.total_statements + 1 }
                : a,
            ),
          );
          break;

        case "interruption":
          setTypingAgent(null);
          setTurn((t) => t + 1);
          setAgents((prev) =>
            prev.map((a) =>
              a.persona.id === event.statement.agent_id
                ? { ...a, total_statements: a.total_statements + 1 }
                : a,
            ),
          );
          break;

        case "emotions-updated":
          setAgents((prev) =>
            prev.map((a) => {
              const newState: EmotionalState | undefined =
                event.states[a.persona.id];
              if (newState) {
                return { ...a, current_emotional_state: newState };
              }
              return a;
            }),
          );
          break;

        case "error":
          setError(event.message);
          break;

        default:
          // leader-announcement, leader-prompt — no state change needed beyond events list
          break;
      }
    },
    [],
  );

  useEffect(() => {
    if (!sessionId) return;

    const es = new EventSource(`/api/sessions/${sessionId}/stream`);
    eventSourceRef.current = es;

    es.onmessage = (msg) => {
      try {
        const parsed: DebateEvent = JSON.parse(msg.data);
        handleEvent(parsed);
      } catch {
        console.error("Failed to parse SSE event:", msg.data);
      }
    };

    es.onerror = () => {
      // EventSource auto-reconnects; only set error if connection is closed
      if (es.readyState === EventSource.CLOSED) {
        setError("Connection to debate stream lost.");
      }
    };

    return () => {
      es.close();
      eventSourceRef.current = null;
    };
  }, [sessionId, handleEvent]);

  return { events, agents, status, error, summary, typingAgent, turn };
}
