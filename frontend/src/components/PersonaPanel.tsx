import { useState } from "react";
import type {
  AgentState,
  DebateSession,
  EmotionalState,
  LLMBackendConfig,
} from "../types";
import {
  EMOTION_COLORS,
  EMOTION_LABELS,
  MODEL_OPTIONS,
  getInitials,
  modelOptionToBackendConfig,
} from "../types";
import { TruncatedTopic } from "./TruncatedTopic";

interface PersonaPanelProps {
  session: DebateSession;
  onUpdateAgentBackend: (agentId: string, backend: LLMBackendConfig) => void;
  onStartDebate: () => void;
  onBack: () => void;
  loading: boolean;
}

const MINI_EMOTIONS: (keyof EmotionalState)[] = [
  "confidence",
  "enthusiasm",
  "anger",
  "withdrawal",
];

export function PersonaPanel({
  session,
  onUpdateAgentBackend,
  onStartDebate,
  onBack,
  loading,
}: PersonaPanelProps) {
  return (
    <div className="container" style={{ maxWidth: 900, margin: "32px auto" }}>
      <div className="topic-banner">
        <div className="topic-label">Debate Topic</div>
        <div className="topic-text"><TruncatedTopic topic={session.config.topic} /></div>
        {session.config.agent_theme && (
          <div className="topic-theme">
            🎨 Theme: {session.config.agent_theme}
          </div>
        )}
      </div>

      <div className="agents-grid">
        {session.agents.map((agent) => (
          <AgentCard
            key={agent.persona.id}
            agent={agent}
            onUpdateBackend={(backend) =>
              onUpdateAgentBackend(agent.persona.id, backend)
            }
          />
        ))}
      </div>

      <div className="actions">
        <button className="btn btn-secondary" onClick={onBack}>
          ← Back to Config
        </button>
        <button
          className="btn btn-primary"
          onClick={onStartDebate}
          disabled={loading}
        >
          {loading ? "Starting…" : "▶ Start Debate"}
        </button>
      </div>
    </div>
  );
}

function AgentCard({
  agent,
  onUpdateBackend,
}: {
  agent: AgentState;
  onUpdateBackend: (backend: LLMBackendConfig) => void;
}) {
  const { persona } = agent;
  const [modelIdx, setModelIdx] = useState(0);

  function handleModelChange(idx: number) {
    setModelIdx(idx);
    onUpdateBackend(modelOptionToBackendConfig(MODEL_OPTIONS[idx]));
  }

  return (
    <div className="agent-card">
      <div className="agent-header">
        <div
          className="avatar"
          style={{ background: persona.avatar_color }}
        >
          {getInitials(persona.name)}
        </div>
        <div>
          <div className="agent-name">{persona.name}</div>
          <div className="agent-role">{persona.expertise}</div>
        </div>
      </div>

      <div className="agent-bg">{persona.background}</div>

      <div className="traits">
        {persona.character_traits.map((trait, i) => (
          <span className="trait" key={i}>
            {trait}
          </span>
        ))}
      </div>

      <div className="emotions-mini">
        {MINI_EMOTIONS.map((dim) => (
          <div className="emo-item" key={dim}>
            <div className="emo-label">{EMOTION_LABELS[dim]}</div>
            <div className="emo-bar">
              <div
                className="emo-fill"
                style={{
                  width: `${(persona.initial_emotional_state[dim] ?? 0) * 100}%`,
                  background: EMOTION_COLORS[dim],
                }}
              />
            </div>
          </div>
        ))}
      </div>

      <div className="model-select">
        <label>LLM Model</label>
        <select
          value={modelIdx}
          onChange={(e) => handleModelChange(Number(e.target.value))}
          aria-label={`LLM model for ${persona.name}`}
        >
          {MODEL_OPTIONS.map((opt, i) => (
            <option key={i} value={i}>
              {opt.label}
            </option>
          ))}
        </select>
      </div>
    </div>
  );
}
