import { useCallback, useEffect, useState } from "react";
import type { DebateHistoryItem } from "../types";

interface DebateHistoryProps {
  onSelectDebate: (debateId: string) => void;
  onNewDebate: () => void;
}

export function DebateHistory({ onSelectDebate, onNewDebate }: DebateHistoryProps) {
  const [debates, setDebates] = useState<DebateHistoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchDebates = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/debates");
      if (!res.ok) throw new Error("Failed to fetch debates");
      const data: DebateHistoryItem[] = await res.json();
      setDebates(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchDebates();
  }, [fetchDebates]);

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
            {debates.map((d) => (
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
                  <strong style={{ fontSize: "1.05em" }}>{d.topic}</strong>
                  <span style={{ color: "#8b949e", fontSize: "0.85em" }}>
                    {d.ended_at ? new Date(d.ended_at * 1000).toLocaleDateString() : ""}
                  </span>
                </div>
                <div style={{ color: "#8b949e", fontSize: "0.9em", marginTop: 4 }}>
                  {d.agent_theme && <>{d.agent_theme} · </>}
                  {d.agent_count} agents · {d.statement_count} statements
                  {d.summary && <> · {d.summary.total_interruptions} interruptions</>}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
