import { useEffect, useRef } from "react";
import type { AgentState, DebateEvent } from "../types";
import { getInitials } from "../types";

interface DebateTimelineProps {
  events: DebateEvent[];
  agents: AgentState[];
  typingAgent: { id: string; name: string } | null;
}

/** Find agent color by id from the agents list */
function agentColor(agents: AgentState[], agentId: string): string {
  const agent = agents.find((a) => a.persona.id === agentId);
  return agent?.persona.avatar_color ?? "#30363d";
}

function agentInitials(agents: AgentState[], agentId: string): string {
  const agent = agents.find((a) => a.persona.id === agentId);
  return agent ? getInitials(agent.persona.name) : "?";
}

export function DebateTimeline({
  events,
  agents,
  typingAgent,
}: DebateTimelineProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when new events arrive
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [events, typingAgent]);

  return (
    <div className="timeline">
      {events.map((event, i) => (
        <TimelineEntry key={i} event={event} agents={agents} />
      ))}

      {typingAgent && (
        <div className="typing">
          <div
            className="avatar"
            style={{
              background: agentColor(agents, typingAgent.id),
            }}
          >
            {agentInitials(agents, typingAgent.id)}
          </div>
          <div className="dots">
            <div className="dot" />
            <div className="dot" />
            <div className="dot" />
          </div>
        </div>
      )}

      <div ref={bottomRef} />
    </div>
  );
}

function TimelineEntry({
  event,
  agents,
}: {
  event: DebateEvent;
  agents: AgentState[];
}) {
  switch (event.type) {
    case "leader-announcement":
      return (
        <div className="msg leader">
          <div className="avatar" style={{ background: "#30363d" }}>
            🎙
          </div>
          <div className="bubble">
            <div className="name">Debate Leader</div>
            <div className="text">{event.content}</div>
          </div>
        </div>
      );

    case "leader-prompt":
      return (
        <div className="msg leader">
          <div className="avatar" style={{ background: "#30363d" }}>
            🎙
          </div>
          <div className="bubble">
            <div className="name">Debate Leader</div>
            <div className="text">{event.content}</div>
          </div>
        </div>
      );

    case "statement": {
      const s = event.statement;
      const color = agentColor(agents, s.agent_id);
      return (
        <div className="msg">
          <div className="avatar" style={{ background: color }}>
            {agentInitials(agents, s.agent_id)}
          </div>
          <div className="bubble">
            <div className="name">{s.agent_name}</div>
            <div className="text">{s.content}</div>
            <div className="meta">
              Confidence: {s.emotional_state_at_time.confidence.toFixed(2)} ·
              Enthusiasm: {s.emotional_state_at_time.enthusiasm.toFixed(2)}
            </div>
          </div>
        </div>
      );
    }

    case "interruption": {
      const s = event.statement;
      const color = agentColor(agents, s.agent_id);
      return (
        <div className="msg interruption">
          <div className="avatar" style={{ background: color }}>
            {agentInitials(agents, s.agent_id)}
          </div>
          <div className="bubble">
            <div className="tag">⚡ Interruption</div>
            <div className="name">{s.agent_name}</div>
            <div className="text">{s.content}</div>
            <div className="meta">
              Interruption · Anger:{" "}
              {s.emotional_state_at_time.anger.toFixed(2)} · Confidence:{" "}
              {s.emotional_state_at_time.confidence.toFixed(2)}
            </div>
          </div>
        </div>
      );
    }

    case "closing-phase-started":
      return (
        <div className="msg system-msg">
          <div className="system-text">🏁 Closing phase started</div>
        </div>
      );

    case "closing-argument": {
      const s = event.statement;
      const color = agentColor(agents, s.agent_id);
      return (
        <div className="msg closing-argument">
          <div className="avatar" style={{ background: color }}>
            {agentInitials(agents, s.agent_id)}
          </div>
          <div className="bubble">
            <div className="tag">🏁 Closing Argument</div>
            <div className="name">{s.agent_name}</div>
            <div className="text">{s.content}</div>
            <div className="meta">
              Confidence: {s.emotional_state_at_time.confidence.toFixed(2)} ·
              Enthusiasm: {s.emotional_state_at_time.enthusiasm.toFixed(2)}
            </div>
          </div>
        </div>
      );
    }

    case "debate-started":
      return (
        <div className="msg system-msg">
          <div className="system-text">Debate started</div>
        </div>
      );

    case "debate-paused":
      return (
        <div className="msg system-msg">
          <div className="system-text">⏸ Debate paused</div>
        </div>
      );

    case "debate-resumed":
      return (
        <div className="msg system-msg">
          <div className="system-text">▶ Debate resumed</div>
        </div>
      );

    case "debate-ended":
      return (
        <div className="msg system-msg">
          <div className="system-text">
            Debate ended — {event.summary.total_statements} statements,{" "}
            {event.summary.total_interruptions} interruptions
          </div>
        </div>
      );

    case "error":
      return (
        <div className="msg system-msg error-msg">
          <div className="system-text">⚠ Error: {event.message}</div>
        </div>
      );

    // agent-selected and emotions-updated are state-only events, not rendered in timeline
    default:
      return null;
  }
}
