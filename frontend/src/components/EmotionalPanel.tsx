import type { AgentState, DebateEvent, EmotionalState } from "../types";
import { EMOTION_COLORS, EMOTION_LABELS, getInitials } from "../types";

interface EmotionalPanelProps {
  agents: AgentState[];
  events: DebateEvent[];
  topic: string;
  theme?: string | null;
}

const ALL_EMOTIONS: (keyof EmotionalState)[] = [
  "anger",
  "confidence",
  "enthusiasm",
  "frustration",
  "agreement",
  "resentment",
  "withdrawal",
];

function buildPrintHtml(topic: string, theme: string | null | undefined, events: DebateEvent[], agents: AgentState[]): string {
  const agentMap = new Map(agents.map((a) => [a.persona.id, a]));

  function name(agentId: string): string {
    return agentMap.get(agentId)?.persona.name ?? "Unknown";
  }

  let body = "";

  for (const event of events) {
    switch (event.type) {
      case "leader-announcement":
        body += `<div class="entry leader"><strong>Debate Leader:</strong> ${event.content}</div>\n`;
        break;
      case "leader-prompt":
        body += `<div class="entry leader"><strong>Debate Leader</strong> (to ${event.agent_name}): ${event.content}</div>\n`;
        break;
      case "statement":
        body += `<div class="entry"><strong>${event.statement.agent_name}:</strong> ${event.statement.content}</div>\n`;
        break;
      case "interruption":
        body += `<div class="entry interruption"><strong>${event.statement.agent_name}</strong> <em>(interrupting ${name(event.interrupted_agent_id)}):</em> ${event.statement.content}</div>\n`;
        break;
      case "closing-phase-started":
        body += `<div class="entry system">— Closing Phase —</div>\n`;
        break;
      case "closing-argument":
        body += `<div class="entry closing"><strong>${event.statement.agent_name}</strong> (closing argument): ${event.statement.content}</div>\n`;
        break;
      case "debate-ended":
        body += `<div class="entry system">— Debate ended: ${event.summary.total_statements} statements, ${event.summary.total_interruptions} interruptions —</div>\n`;
        break;
      default:
        break;
    }
  }

  return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Debate: ${topic}</title>
<style>
  body { font-family: Georgia, 'Times New Roman', serif; max-width: 700px; margin: 40px auto; padding: 0 20px; color: #222; line-height: 1.6; }
  h1 { font-size: 22px; margin-bottom: 4px; }
  .meta { color: #666; font-size: 14px; margin-bottom: 24px; }
  .entry { margin-bottom: 14px; font-size: 15px; }
  .entry strong { font-weight: 600; }
  .entry.leader { color: #444; font-style: italic; border-left: 3px solid #888; padding-left: 12px; }
  .entry.interruption { border-left: 3px solid #c00; padding-left: 12px; }
  .entry.closing { border-left: 3px solid #060; padding-left: 12px; }
  .entry.system { text-align: center; color: #888; font-style: italic; margin: 20px 0; }
  @media print { body { margin: 20px; } }
</style>
</head>
<body>
<h1>${topic}</h1>
<div class="meta">${theme ? `Theme: ${theme} · ` : ""}${agents.length} agents · ${new Date().toLocaleDateString()}</div>
${body}
</body>
</html>`;
}

export function EmotionalPanel({ agents, events, topic, theme }: EmotionalPanelProps) {
  function handlePrint() {
    const html = buildPrintHtml(topic, theme, events, agents);
    const win = window.open("", "_blank");
    if (win) {
      win.document.write(html);
      win.document.close();
    }
  }

  return (
    <div className="sidebar">
      <h3>Emotional States</h3>

      {agents.map((agent, idx) => (
        <div key={agent.persona.id}>
          {idx > 0 && <hr className="divider" />}
          <div className="agent-emo">
            <div className="agent-row">
              <div
                className="mini-avatar"
                style={{ background: agent.persona.avatar_color }}
              >
                {getInitials(agent.persona.name)}
              </div>
              <div className="agent-label">{agent.persona.name}</div>
            </div>
            <div className="emo-bars">
              {ALL_EMOTIONS.map((dim) => {
                const val = agent.current_emotional_state[dim];
                return (
                  <div className="emo-row" key={dim}>
                    <span className="emo-name">{EMOTION_LABELS[dim]}</span>
                    <div className="bar-bg">
                      <div
                        className="bar-fill"
                        style={{
                          width: `${val * 100}%`,
                          background: EMOTION_COLORS[dim],
                        }}
                      />
                    </div>
                    <span className="emo-val">.{String(Math.round(val * 100)).padStart(2, "0")}</span>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      ))}

      <hr className="divider" />
      <button
        className="ctrl-btn"
        onClick={handlePrint}
        style={{ width: "100%", marginTop: 4 }}
      >
        🖨 Print Debate
      </button>
    </div>
  );
}
