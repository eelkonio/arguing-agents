import { useCallback, useEffect, useRef, useState } from "react";
import type { AudioJob, AudioJobStatus, DebateHistoryItem } from "../types";
import { TruncatedTopic } from "./TruncatedTopic";

interface DebateHistoryProps {
  onSelectDebate: (debateId: string) => void;
  onNewDebate: () => void;
}

export function DebateHistory({ onSelectDebate, onNewDebate }: DebateHistoryProps) {
  const [debates, setDebates] = useState<DebateHistoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [audioStates, setAudioStates] = useState<Record<string, AudioJob>>({});
  const pollTimers = useRef<Record<string, ReturnType<typeof setInterval>>>({});

  const fetchDebates = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/debates");
      if (!res.ok) throw new Error("Failed to fetch debates");
      const data: DebateHistoryItem[] = await res.json();
      setDebates(data);

      // Fetch audio status for each debate
      for (const d of data) {
        fetchAudioStatus(d.id);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchAudioStatus = useCallback(async (debateId: string) => {
    try {
      const res = await fetch(`/api/debates/${debateId}/audio-status`);
      if (!res.ok) return;
      const job: AudioJob = await res.json();
      setAudioStates((prev) => ({ ...prev, [debateId]: job }));
    } catch {
      // ignore
    }
  }, []);

  const startPolling = useCallback(
    (debateId: string) => {
      // Clear any existing timer
      if (pollTimers.current[debateId]) {
        clearInterval(pollTimers.current[debateId]);
      }
      pollTimers.current[debateId] = setInterval(async () => {
        try {
          const res = await fetch(`/api/debates/${debateId}/audio-status`);
          if (!res.ok) return;
          const job: AudioJob = await res.json();
          setAudioStates((prev) => ({ ...prev, [debateId]: job }));
          if (job.status === "completed" || job.status === "failed" || job.status === "none") {
            clearInterval(pollTimers.current[debateId]);
            delete pollTimers.current[debateId];
          }
        } catch {
          // ignore
        }
      }, 2000);
    },
    [],
  );

  useEffect(() => {
    fetchDebates();
    return () => {
      // Cleanup all poll timers
      Object.values(pollTimers.current).forEach(clearInterval);
    };
  }, [fetchDebates]);

  const handleGenerateAudio = useCallback(
    async (debateId: string, e: React.MouseEvent) => {
      e.stopPropagation();

      // Immediately show generating state so the button disappears
      setAudioStates((prev) => ({
        ...prev,
        [debateId]: {
          session_id: debateId,
          status: "generating" as AudioJobStatus,
          progress: 0,
          audio_path: null,
          error_message: null,
          created_at: null,
          completed_at: null,
        },
      }));

      try {
        const res = await fetch(`/api/debates/${debateId}/generate-audio`, {
          method: "POST",
        });
        if (!res.ok) {
          const body = await res.json().catch(() => ({ detail: res.statusText }));
          throw new Error(body.detail || "Failed to start audio generation");
        }
        const job: AudioJob = await res.json();
        setAudioStates((prev) => ({ ...prev, [debateId]: { ...job, status: job.status === "pending" ? "generating" as AudioJobStatus : job.status } }));
        startPolling(debateId);
      } catch (err) {
        setAudioStates((prev) => ({
          ...prev,
          [debateId]: {
            session_id: debateId,
            status: "failed" as AudioJobStatus,
            progress: 0,
            audio_path: null,
            error_message: err instanceof Error ? err.message : String(err),
            created_at: null,
            completed_at: null,
          },
        }));
      }
    },
    [startPolling],
  );

  // Start polling for any debates that are already generating
  useEffect(() => {
    for (const [debateId, job] of Object.entries(audioStates)) {
      if (
        (job.status === "pending" || job.status === "generating") &&
        !pollTimers.current[debateId]
      ) {
        startPolling(debateId);
      }
    }
  }, [audioStates, startPolling]);

  return (
    <div className="container" style={{ maxWidth: 800, margin: "48px auto" }}>
      <div className="card">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <h2>Debate History</h2>
          <button className="btn-primary" onClick={onNewDebate}>
            + New Debate
          </button>
        </div>

        {error && <div className="error-box">{error}</div>}

        {loading && <p style={{ color: "#8b949e" }}>Loading debates…</p>}

        {!loading && debates.length === 0 && (
          <p style={{ color: "#8b949e", marginTop: 16 }}>
            No completed debates yet. Start a new debate to see it here.
          </p>
        )}

        {!loading && debates.length > 0 && (
          <div className="history-list" style={{ marginTop: 16 }}>
            {debates.map((d) => {
              const audioJob = audioStates[d.id];
              const audioStatus = audioJob?.status ?? "none";

              return (
                <div
                  key={d.id}
                  className="history-item"
                  onClick={() => onSelectDebate(d.id)}
                  style={{
                    padding: "12px 16px",
                    borderBottom: "1px solid #30363d",
                    cursor: "pointer",
                  }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
                    <strong style={{ fontSize: "1.05em" }}><TruncatedTopic topic={d.topic} /></strong>
                    <span style={{ color: "#8b949e", fontSize: "0.85em" }}>
                      {d.ended_at ? new Date(d.ended_at * 1000).toLocaleDateString() : ""}
                    </span>
                  </div>
                  <div style={{ color: "#8b949e", fontSize: "0.9em", marginTop: 4 }}>
                    {d.agent_theme && <>{d.agent_theme} · </>}
                    {d.agent_count} agents · {d.statement_count} statements
                    {d.summary && <> · {d.summary.total_interruptions} interruptions</>}
                  </div>

                  {/* Audio controls */}
                  <div style={{ marginTop: 8, display: "flex", alignItems: "center", gap: 8 }}>
                    {audioStatus === "none" && (
                      <button
                        className="btn-primary"
                        style={{ fontSize: "0.85em", padding: "4px 10px" }}
                        onClick={(e) => handleGenerateAudio(d.id, e)}
                      >
                        🔊 Generate Audio
                      </button>
                    )}

                    {(audioStatus === "pending" || audioStatus === "generating") && (
                      <div style={{ flex: 1, maxWidth: 300 }}>
                        <div style={{ fontSize: "0.85em", color: "#8b949e", marginBottom: 2 }}>
                          Generating audio… {audioJob?.progress ?? 0}%
                        </div>
                        <div
                          style={{
                            height: 6,
                            background: "#21262d",
                            borderRadius: 3,
                            overflow: "hidden",
                          }}
                        >
                          <div
                            style={{
                              height: "100%",
                              width: `${audioJob?.progress ?? 0}%`,
                              background: "#58a6ff",
                              borderRadius: 3,
                              transition: "width 0.3s ease",
                            }}
                          />
                        </div>
                      </div>
                    )}

                    {audioStatus === "completed" && (
                      <>
                        <button
                          className="btn-primary"
                          style={{ fontSize: "0.85em", padding: "4px 10px" }}
                          onClick={(e) => {
                            e.stopPropagation();
                            const audio = new Audio(`/api/debates/${d.id}/audio`);
                            audio.play();
                          }}
                        >
                          ▶ Play
                        </button>
                        <a
                          href={`/api/debates/${d.id}/audio`}
                          download={`debate-${d.id}.mp3`}
                          onClick={(e) => e.stopPropagation()}
                          style={{
                            fontSize: "0.85em",
                            color: "#58a6ff",
                            textDecoration: "none",
                          }}
                        >
                          ⬇ Download
                        </a>
                      </>
                    )}

                    {audioStatus === "failed" && (
                      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                        <span style={{ color: "#f85149", fontSize: "0.85em" }}>
                          ⚠ {audioJob?.error_message || "Audio generation failed"}
                        </span>
                        <button
                          className="btn-primary"
                          style={{ fontSize: "0.85em", padding: "4px 10px" }}
                          onClick={(e) => handleGenerateAudio(d.id, e)}
                        >
                          Retry
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
