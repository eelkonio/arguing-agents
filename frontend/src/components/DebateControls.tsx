import type { DebateSession, DebateStatus, DebateSummary } from "../types";

interface DebateControlsProps {
  session: DebateSession;
  status: DebateStatus;
  turn: number;
  summary: DebateSummary | null;
  onPause: () => void;
  onResume: () => void;
  onStop: () => void;
  onClose: () => void;
}

export function DebateControls({
  session,
  status,
  turn,
  summary,
  onPause,
  onResume,
  onStop,
  onClose,
}: DebateControlsProps) {
  const maxTurns = session.config.max_turns;

  return (
    <div className="debate-header">
      <div className="header-left">
        <span className="icon">🎭</span>
        <div>
          <h1 className="debate-title">{session.config.topic}</h1>
          <div className="debate-meta">
            {session.config.agent_theme && (
              <>Theme: {session.config.agent_theme} · </>
            )}
            {session.agents.length} agents · Turn {turn}
            {maxTurns != null && <> / {maxTurns}</>}
          </div>
        </div>
      </div>
      <div className="controls">
        {status === "running" && (
          <>
            <div className="status-live">
              <span className="live-dot" />
              Live
            </div>
            <button className="ctrl-btn" onClick={onClose}>
              🏁 Close Debate
            </button>
            <button className="ctrl-btn" onClick={onPause}>
              ⏸ Pause
            </button>
            <button className="ctrl-btn stop" onClick={onStop}>
              ⏹ Stop
            </button>
          </>
        )}
        {status === "closing-phase" && (
          <>
            <div className="status-live">
              <span className="live-dot" />
              Closing
            </div>
            <button className="ctrl-btn stop" onClick={onStop}>
              ⏹ Stop
            </button>
          </>
        )}
        {status === "paused" && (
          <>
            <div className="status-paused">⏸ Paused</div>
            <button className="ctrl-btn" onClick={onResume}>
              ▶ Resume
            </button>
            <button className="ctrl-btn stop" onClick={onStop}>
              ⏹ Stop
            </button>
          </>
        )}
        {status === "ended" && (
          <div className="status-ended">Ended</div>
        )}
      </div>

      {status === "ended" && summary && (
        <div className="summary-bar">
          <strong>Summary:</strong> {summary.total_statements} statements,{" "}
          {summary.total_interruptions} interruptions, {summary.duration.toFixed(1)}s
          duration
        </div>
      )}
    </div>
  );
}
