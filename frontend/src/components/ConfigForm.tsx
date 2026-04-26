import { useState } from "react";
import type { DebateConfig, LLMBackendConfig } from "../types";
import { MODEL_OPTIONS, modelOptionToBackendConfig } from "../types";

interface ConfigFormProps {
  onSubmit: (config: DebateConfig) => void;
  loading: boolean;
}

export function ConfigForm({ onSubmit, loading }: ConfigFormProps) {
  const [topic, setTopic] = useState("");
  const [agentCount, setAgentCount] = useState(4);
  const [agentTheme, setAgentTheme] = useState("");
  const [maxTurns, setMaxTurns] = useState<number | "">("");
  const [creatorIdx, setCreatorIdx] = useState(0);
  const [leaderIdx, setLeaderIdx] = useState(1);
  const [pusherIdx, setPusherIdx] = useState(2);
  const [defaultAgentIdx, setDefaultAgentIdx] = useState(0);
  const [errors, setErrors] = useState<string[]>([]);

  function validate(): boolean {
    const errs: string[] = [];
    if (!topic.trim()) errs.push("Debate topic is required.");
    if (agentCount < 2 || agentCount > 10)
      errs.push("Agent count must be between 2 and 10.");
    setErrors(errs);
    return errs.length === 0;
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!validate()) return;

    const backendFor = (idx: number): LLMBackendConfig =>
      modelOptionToBackendConfig(MODEL_OPTIONS[idx]);

    const config: DebateConfig = {
      topic: topic.trim(),
      agent_count: agentCount,
      agent_theme: agentTheme.trim() || null,
      max_turns: maxTurns === "" ? null : maxTurns,
      backend_assignments: {
        debate_creator: backendFor(creatorIdx),
        debate_leader: backendFor(leaderIdx),
        psycho_pusher: backendFor(pusherIdx),
        agents: {},
        default_agent_backend: backendFor(defaultAgentIdx),
      },
    };
    onSubmit(config);
  }

  return (
    <div className="container" style={{ maxWidth: 640, margin: "48px auto" }}>
      <form className="card" onSubmit={handleSubmit}>
        <h2>New Debate</h2>
        <p className="subtitle">
          Set up a topic, choose your agents, and let them argue it out.
        </p>

        {errors.length > 0 && (
          <div className="error-box">
            {errors.map((err, i) => (
              <div key={i}>{err}</div>
            ))}
          </div>
        )}

        <div className="form-group">
          <label htmlFor="topic">Debate Topic</label>
          <textarea
            id="topic"
            placeholder="e.g., Should AI replace human artists? You can describe the topic in detail here."
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            maxLength={1024}
            rows={3}
            style={{ resize: "vertical" }}
          />
          <div className="hint">{topic.length} / 1024</div>
        </div>

        <div className="form-group">
          <label htmlFor="agentCount">Number of Agents</label>
          <input
            id="agentCount"
            type="number"
            value={agentCount}
            min={2}
            max={10}
            onChange={(e) => setAgentCount(Number(e.target.value))}
          />
          <div className="hint">Between 2 and 10 agents</div>
        </div>

        <div className="form-group">
          <label htmlFor="agentTheme">
            Agent Theme <span style={{ color: "#8b949e" }}>(optional)</span>
          </label>
          <input
            id="agentTheme"
            type="text"
            placeholder='e.g., Greek gods, A-team members, farm yard cattle'
            value={agentTheme}
            onChange={(e) => setAgentTheme(e.target.value)}
            maxLength={200}
          />
          <div className="hint examples" style={{ marginTop: 8 }}>
            <strong>Examples:</strong> "Greek gods" · "members of the A-team" ·
            "farm yard cattle" · "Renaissance painters"
          </div>
        </div>

        <div className="form-group">
          <label htmlFor="maxTurns">
            Max Turns <span style={{ color: "#8b949e" }}>(optional)</span>
          </label>
          <input
            id="maxTurns"
            type="number"
            placeholder="Leave empty for unlimited"
            value={maxTurns}
            min={1}
            onChange={(e) =>
              setMaxTurns(e.target.value === "" ? "" : Number(e.target.value))
            }
          />
          <div className="hint">
            Maximum number of debate turns. The debate leader gets ±10% leniency
            to find a natural stopping point.
          </div>
        </div>

        <hr className="divider" />

        <div className="form-group">
          <label>Service Backends</label>
          <div className="backend-grid">
            <BackendSelect
              label="Debate Creator"
              value={creatorIdx}
              onChange={setCreatorIdx}
            />
            <BackendSelect
              label="Debate Leader"
              value={leaderIdx}
              onChange={setLeaderIdx}
            />
            <BackendSelect
              label="Psycho Pusher"
              value={pusherIdx}
              onChange={setPusherIdx}
            />
            <BackendSelect
              label="Default Agent Model"
              value={defaultAgentIdx}
              onChange={setDefaultAgentIdx}
            />
          </div>
        </div>

        <button className="btn-primary" type="submit" disabled={loading}>
          {loading ? "Generating Agents…" : "Generate Agents"}
        </button>
      </form>
    </div>
  );
}

function BackendSelect({
  label,
  value,
  onChange,
}: {
  label: string;
  value: number;
  onChange: (idx: number) => void;
}) {
  return (
    <div className="backend-item">
      <div className="backend-label">{label}</div>
      <select
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        aria-label={label}
      >
        {MODEL_OPTIONS.map((opt, i) => (
          <option key={i} value={i}>
            {opt.label}
          </option>
        ))}
      </select>
    </div>
  );
}
