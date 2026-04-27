import { useCallback, useEffect, useState } from "react";
import type { AudioJob, DebateDetail, DebateTimelineEntry, EmotionalState } from "../types";
import { EMOTION_LABELS, getInitials } from "../types";

interface DebateReplayProps {
  debateId: string;
  onBack: () => void;
}

export function DebateReplay({ debateId, onBack }: DebateReplayProps) {
  const [detail, setDetail] = useState<DebateDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [audioJob, setAudioJob] = useState<AudioJob | null>(null);

  const fetchDetail = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`/api/debates/${debateId}`);
      if (!res.ok) throw new Error("Failed to fetch debate");
      const data: DebateDetail = await res.json();
      setDetail(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, [debateId]);

  const fetchAudioStatus = useCallback(async () => {
    try {
      const res = await fetch(`/api/debates/${debateId}/audio-status`);
      if (!res.ok) return;
      const job: AudioJob = await res.json();
      setAudioJob(job);
    } catch {
      // ignore
    }
  }, [debateId]);

  useEffect(() => {
    fetchDetail();
    fetchAudioStatus();
  }, [fetchDetail, fetchAudioStatus]);

  if (loading) {
    return (
      <div className="container" style={{ maxWidth: 900, margin: "48px auto" }}>
        <p style={{ color: "#8b949e" }}>Loading debate…</p>
      </div>
    );
  }

  if (error || !detail) {
    return (
      <div className="container" style={{ maxWidth: 900, margin: "48px auto" }}>
        <div className="error-box">{error || "Debate not found"}</div>
        <button className="btn-primary" onClick={onBack} style={{ marginTop: 16 }}>
          ← Back to History
        </button>
      </div>
    );
  }

  const { session, timeline } = detail;
  const agentMap = new Map(session.agents.map((a) => [a.id, a]));

  function agentColor(agentId: string): string {
    const agent = agentMap.get(agentId);
    return agent?.persona.avatar_color ?? "#30363d";
  }

  function agentInitials(agentId: string): string {
    const agent = agentMap.get(agentId);
    return agent ? getInitials(agent.persona.name) : "?";
  }

  const hasAudio = audioJob?.status === "completed";

  return (
    <div className="container" style={{ maxWidth: 900, margin: "48px auto" }}>
      <button className="btn-primary" onClick={onBack} style={{ marginBottom: 16 }}>
        ← Back to History
      </button>

      <div className="card" style={{ marginBottom: 24 }}>
        <h2>{session.topic}</h2>
        <div style={{ color: "#8b949e", marginBottom: 12 }}>
          {session.agent_theme && <>Theme: {session.agent_theme} · </>}
          {session.agent_count} agents
          {session.started_at && (
            <> · {new Date(session.started_at * 1000).toLocaleString()}</>
          )}
        </div>

        {session.summary && (
          <div className="summary-bar" style={{ marginBottom: 16 }}>
            <strong>Summary:</strong> {session.summary.total_statements} statements,{" "}
            {session.summary.total_interruptions} interruptions,{" "}
            {session.summary.duration.toFixed(1)}s duration
          </div>
        )}

        {/* Audio player */}
        {hasAudio && (
          <div style={{ marginBottom: 16, padding: "12px", background: "#161b22", borderRadius: 8 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 8 }}>
              <span style={{ fontSize: "1.1em" }}>🔊</span>
              <strong>Debate Audio</strong>
              <a
                href={`/api/debates/${debateId}/audio`}
                download={`debate-${debateId}.mp3`}
                style={{ color: "#58a6ff", textDecoration: "none", fontSize: "0.9em", marginLeft: "auto" }}
              >
                ⬇ Download MP3
              </a>
            </div>
            <audio
              controls
              src={`/api/debates/${debateId}/audio`}
              style={{ width: "100%" }}
            >
              Your browser does not support the audio element.
            </audio>
          </div>
        )}

        <h3 style={{ marginTop: 16 }}>Agents</h3>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 12 }}>
          {session.agents.map((agent) => (
            <div
              key={agent.id}
              style={{
                padding: "8px 12px",
                border: "1px solid #30363d",
                borderRadius: 8,
                borderLeft: `4px solid ${agent.persona.avatar_color}`,
                flex: "1 1 200px",
              }}
            >
              <strong>{agent.persona.name}</strong>
              <div style={{ color: "#8b949e", fontSize: "0.85em" }}>
                {agent.persona.expertise}
              </div>
              {agent.final_emotional_state && (
                <div style={{ fontSize: "0.8em", marginTop: 4, color: "#8b949e" }}>
                  {(Object.keys(EMOTION_LABELS) as (keyof EmotionalState)[]).map((dim) => (
                    <span key={dim} style={{ marginRight: 8 }}>
                      {EMOTION_LABELS[dim]}: {agent.final_emotional_state![dim].toFixed(2)}
                    </span>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      <div className="card">
        <h3>Timeline</h3>
        <div className="timeline" style={{ maxHeight: "none" }}>
          {timeline.map((entry, i) => (
            <ReplayEntry key={i} entry={entry} agentColor={agentColor} agentInitials={agentInitials} />
          ))}
        </div>
      </div>
    </div>
  );
}

function ReplayEntry({
  entry,
  agentColor,
  agentInitials,
}: {
  entry: DebateTimelineEntry;
  agentColor: (id: string) => string;
  agentInitials: (id: string) => string;
}) {
  if (entry.type === "leader-announcement" || entry.type === "leader-prompt") {
    return (
      <div className="msg leader">
        <div className="avatar" style={{ background: "#30363d" }}>🎙</div>
        <div className="bubble">
          <div className="name">Debate Leader</div>
          <div className="text">{entry.content}</div>
        </div>
      </div>
    );
  }

  if (entry.type === "statement" || entry.type === "interruption" || entry.type === "closing-argument") {
    const isInterruption = entry.type === "interruption";
    const isClosing = entry.type === "closing-argument";
    const color = entry.agent_id ? agentColor(entry.agent_id) : "#30363d";
    const initials = entry.agent_id ? agentInitials(entry.agent_id) : "?";

    return (
      <div className={`msg ${isInterruption ? "interruption" : ""} ${isClosing ? "closing-argument" : ""}`}>
        <div className="avatar" style={{ background: color }}>{initials}</div>
        <div className="bubble">
          {isInterruption && <div className="tag">⚡ Interruption</div>}
          {isClosing && <div className="tag">🏁 Closing Argument</div>}
          <div className="name">{entry.agent_name ?? "Unknown"}</div>
          <div className="text">{entry.content}</div>
          {entry.emotional_state && (
            <div className="meta">
              Confidence: {entry.emotional_state.confidence.toFixed(2)} ·
              Enthusiasm: {entry.emotional_state.enthusiasm.toFixed(2)}
            </div>
          )}
        </div>
      </div>
    );
  }

  return null;
}
