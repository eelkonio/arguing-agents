import { useCallback, useState } from "react";
import { ConfigForm } from "./components/ConfigForm";
import { DebateControls } from "./components/DebateControls";
import { DebateHistory } from "./components/DebateHistory";
import { DebateReplay } from "./components/DebateReplay";
import { DebateTimeline } from "./components/DebateTimeline";
import { EmotionalPanel } from "./components/EmotionalPanel";
import { PersonaPanel } from "./components/PersonaPanel";
import { useDebateStream } from "./hooks/useDebateStream";
import type { DebateConfig, DebateSession, LLMBackendConfig } from "./types";

type View = "config" | "persona-review" | "debate" | "history" | "replay";

export default function App() {
  const [view, setView] = useState<View>("config");
  const [session, setSession] = useState<DebateSession | null>(null);
  const [loading, setLoading] = useState(false);
  const [appError, setAppError] = useState<string | null>(null);
  const [replayDebateId, setReplayDebateId] = useState<string | null>(null);

  const {
    events,
    agents,
    status: debateStatus,
    error: streamError,
    summary,
    typingAgent,
    turn,
  } = useDebateStream(
    view === "debate" ? session?.id ?? null : null,
    session?.agents ?? [],
  );

  // ---- Config form submit ----
  const handleConfigSubmit = useCallback(async (config: DebateConfig) => {
    setLoading(true);
    setAppError(null);
    try {
      const res = await fetch("/api/sessions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(config),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(body.detail || "Failed to create session");
      }
      const newSession: DebateSession = await res.json();
      setSession(newSession);
      setView("persona-review");
    } catch (err) {
      setAppError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, []);

  // ---- Update agent backend ----
  const handleUpdateAgentBackend = useCallback(
    async (agentId: string, backend: LLMBackendConfig) => {
      if (!session) return;
      try {
        await fetch(
          `/api/sessions/${session.id}/agents/${agentId}/backend`,
          {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(backend),
          },
        );
      } catch {
        // Silently ignore — the default backend will be used
      }
    },
    [session],
  );

  // ---- Start debate ----
  const handleStartDebate = useCallback(async () => {
    if (!session) return;
    setLoading(true);
    setAppError(null);
    try {
      const res = await fetch(`/api/sessions/${session.id}/start`, {
        method: "POST",
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(body.detail || "Failed to start debate");
      }
      setView("debate");
    } catch (err) {
      setAppError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, [session]);

  // ---- Pause / Resume / Stop / Close ----
  const handlePause = useCallback(async () => {
    if (!session) return;
    await fetch(`/api/sessions/${session.id}/pause`, { method: "POST" });
  }, [session]);

  const handleResume = useCallback(async () => {
    if (!session) return;
    await fetch(`/api/sessions/${session.id}/resume`, { method: "POST" });
  }, [session]);

  const handleStop = useCallback(async () => {
    if (!session) return;
    await fetch(`/api/sessions/${session.id}/stop`, { method: "POST" });
  }, [session]);

  const handleClose = useCallback(async () => {
    if (!session) return;
    await fetch(`/api/sessions/${session.id}/close`, { method: "POST" });
  }, [session]);

  // ---- Navigation ----
  const handleBackToConfig = useCallback(() => {
    setSession(null);
    setView("config");
    setAppError(null);
  }, []);

  const handleGoToHistory = useCallback(() => {
    setView("history");
    setAppError(null);
  }, []);

  const handleSelectDebate = useCallback((debateId: string) => {
    setReplayDebateId(debateId);
    setView("replay");
  }, []);

  const handleBackToHistory = useCallback(() => {
    setReplayDebateId(null);
    setView("history");
  }, []);

  const error = appError || streamError;

  // ---- Render views ----
  if (view === "history") {
    return (
      <div className="app">
        <header className="header">
          <span className="icon">🎭</span>
          <h1>Multi-Agent Debate</h1>
        </header>
        <DebateHistory onSelectDebate={handleSelectDebate} onNewDebate={handleBackToConfig} />
      </div>
    );
  }

  if (view === "replay" && replayDebateId) {
    return (
      <div className="app">
        <header className="header">
          <span className="icon">🎭</span>
          <h1>Multi-Agent Debate</h1>
        </header>
        <DebateReplay debateId={replayDebateId} onBack={handleBackToHistory} />
      </div>
    );
  }

  if (view === "config") {
    return (
      <div className="app">
        <header className="header">
          <span className="icon">🎭</span>
          <h1>Multi-Agent Debate</h1>
          <button
            className="ctrl-btn"
            onClick={handleGoToHistory}
            style={{ marginLeft: "auto" }}
          >
            📜 History
          </button>
        </header>
        {error && <div className="global-error">{error}</div>}
        <ConfigForm onSubmit={handleConfigSubmit} loading={loading} />
      </div>
    );
  }

  if (view === "persona-review" && session) {
    return (
      <div className="app">
        <header className="header">
          <span className="icon">🎭</span>
          <h1>Multi-Agent Debate</h1>
        </header>
        {error && <div className="global-error">{error}</div>}
        <PersonaPanel
          session={session}
          onUpdateAgentBackend={handleUpdateAgentBackend}
          onStartDebate={handleStartDebate}
          onBack={handleBackToConfig}
          loading={loading}
        />
      </div>
    );
  }

  if (view === "debate" && session) {
    return (
      <div className="app debate-view">
        <DebateControls
          session={session}
          status={debateStatus}
          turn={turn}
          summary={summary}
          onPause={handlePause}
          onResume={handleResume}
          onStop={handleStop}
          onClose={handleClose}
        />
        {error && <div className="global-error">{error}</div>}
        <div className="main">
          <DebateTimeline
            events={events}
            agents={agents}
            typingAgent={typingAgent}
          />
          <EmotionalPanel
            agents={agents}
            events={events}
            topic={session.config.topic}
            theme={session.config.agent_theme}
          />
        </div>
      </div>
    );
  }

  return null;
}
