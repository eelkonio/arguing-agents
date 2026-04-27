/** TypeScript types mirroring backend Pydantic models. */

export type LLMProvider = "bedrock" | "ollama";

export interface LLMBackendConfig {
  provider: LLMProvider;
  model_id: string;
  base_url?: string | null;
  region?: string;
  cross_account_role_arn?: string | null;
}

export interface BackendAssignments {
  debate_creator: LLMBackendConfig;
  debate_leader: LLMBackendConfig;
  psycho_pusher: LLMBackendConfig;
  agents: Record<string, LLMBackendConfig>;
  default_agent_backend: LLMBackendConfig;
}

export interface DebateConfig {
  topic: string;
  agent_count: number;
  agent_theme?: string | null;
  max_turns?: number | null;
  backend_assignments: BackendAssignments;
}

export interface EmotionalState {
  anger: number;
  enthusiasm: number;
  frustration: number;
  agreement: number;
  resentment: number;
  confidence: number;
  withdrawal: number;
}

export const EMOTION_LABELS: Record<keyof EmotionalState, string> = {
  anger: "Anger",
  enthusiasm: "Enthus.",
  frustration: "Frust.",
  agreement: "Agree.",
  resentment: "Resent.",
  confidence: "Confid.",
  withdrawal: "Withdr.",
};

export const EMOTION_COLORS: Record<keyof EmotionalState, string> = {
  anger: "#f85149",
  enthusiasm: "#58a6ff",
  frustration: "#d29922",
  agreement: "#3fb950",
  resentment: "#f85149",
  confidence: "#3fb950",
  withdrawal: "#8b949e",
};

export interface AgentPersona {
  id: string;
  name: string;
  background: string;
  expertise: string;
  character_traits: string[];
  initial_emotional_state: EmotionalState;
  avatar_color: string;
}

export interface AgentState {
  persona: AgentPersona;
  current_emotional_state: EmotionalState;
  consecutive_silent_turns: number;
  total_statements: number;
  is_interrupting: boolean;
  consecutive_interruptions: number;
}

export interface Statement {
  id: string;
  agent_id: string;
  agent_name: string;
  content: string;
  is_interruption: boolean;
  is_closing_argument: boolean;
  timestamp: number;
  emotional_state_at_time: EmotionalState;
}

export type DebateStatus =
  | "configuring"
  | "personas-ready"
  | "running"
  | "paused"
  | "closing-phase"
  | "ended";

export interface DebateSession {
  id: string;
  config: DebateConfig;
  agents: AgentState[];
  statements: Statement[];
  status: DebateStatus;
  turn_count: number;
  created_at: number;
  started_at?: number | null;
  ended_at?: number | null;
}

export interface AgentSummary {
  agent_id: string;
  agent_name: string;
  statement_count: number;
  interruption_count: number;
  final_emotional_state: EmotionalState;
}

export interface DebateSummary {
  total_statements: number;
  total_interruptions: number;
  agent_summaries: AgentSummary[];
  duration: number;
}

export type DebateEvent =
  | {
      type: "leader-announcement";
      content: string;
      timestamp: number;
    }
  | {
      type: "agent-selected";
      agent_id: string;
      agent_name: string;
      timestamp: number;
    }
  | { type: "statement"; statement: Statement; timestamp: number }
  | {
      type: "interruption";
      statement: Statement;
      interrupted_agent_id: string;
      timestamp: number;
    }
  | {
      type: "emotions-updated";
      states: Record<string, EmotionalState>;
      timestamp: number;
    }
  | {
      type: "leader-prompt";
      agent_id: string;
      agent_name: string;
      content: string;
      timestamp: number;
    }
  | { type: "debate-started"; timestamp: number }
  | { type: "debate-paused"; timestamp: number }
  | { type: "debate-resumed"; timestamp: number }
  | { type: "debate-ended"; summary: DebateSummary; timestamp: number }
  | { type: "closing-phase-started"; timestamp: number }
  | { type: "closing-argument"; statement: Statement; timestamp: number }
  | {
      type: "error";
      message: string;
      backend_id?: string;
      agent_id?: string;
      timestamp: number;
    };

export interface BackendHealth {
  bedrock: { available: boolean; error?: string };
  ollama: { available: boolean; models: string[]; error?: string };
}

/** Model option for dropdowns */
export interface ModelOption {
  label: string;
  provider: LLMProvider;
  model_id: string;
  base_url?: string;
}

/** Predefined model options */
export const MODEL_OPTIONS: ModelOption[] = [
  {
    label: "Claude Opus (EU)",
    provider: "bedrock",
    model_id: "eu.anthropic.claude-opus-4-6-v1",
  },
  {
    label: "Claude Sonnet (EU)",
    provider: "bedrock",
    model_id: "eu.anthropic.claude-sonnet-4-20250514-v1:0",
  },
  {
    label: "Claude Haiku (EU)",
    provider: "bedrock",
    model_id: "eu.anthropic.claude-haiku-3-20240307-v1:0",
  },
  {
    label: "Ollama — llama3",
    provider: "ollama",
    model_id: "llama3",
    base_url: "http://localhost:11434",
  },
];

/** Helper to get initials from a name for avatar display */
export function getInitials(name: string): string {
  return name
    .split(/\s+/)
    .map((w) => w[0])
    .join("")
    .toUpperCase()
    .slice(0, 3);
}

/** Helper to build an LLMBackendConfig from a ModelOption */
export function modelOptionToBackendConfig(opt: ModelOption): LLMBackendConfig {
  return {
    provider: opt.provider,
    model_id: opt.model_id,
    base_url: opt.provider === "ollama" ? (opt.base_url ?? null) : null,
    region: opt.provider === "bedrock" ? "eu-central-1" : undefined,
  };
}

/** Debate history list item */
export interface DebateHistoryItem {
  id: string;
  topic: string;
  agent_theme: string | null;
  agent_count: number;
  status: string;
  created_at: number;
  started_at: number | null;
  ended_at: number | null;
  statement_count: number;
  summary: DebateSummary | null;
}

/** Timeline entry from the history API */
export interface DebateTimelineEntry {
  type: string;
  id?: string;
  agent_id?: string | null;
  agent_name?: string | null;
  content: string;
  timestamp: number;
  emotional_state?: EmotionalState;
}

/** Full debate detail from the history API */
export interface DebateDetail {
  session: {
    id: string;
    topic: string;
    agent_theme: string | null;
    agent_count: number;
    status: string;
    created_at: number;
    started_at: number | null;
    ended_at: number | null;
    summary: DebateSummary | null;
    agents: Array<{
      id: string;
      name: string;
      persona: AgentPersona;
      final_emotional_state: EmotionalState | null;
    }>;
  };
  timeline: DebateTimelineEntry[];
}

/** Audio job status type */
export type AudioJobStatus =
  | "none"
  | "pending"
  | "generating"
  | "completed"
  | "failed";

/** Audio job from the backend */
export interface AudioJob {
  session_id: string;
  status: AudioJobStatus;
  progress: number; // 0-100
  audio_path: string | null;
  error_message: string | null;
  created_at: number | null;
  completed_at: number | null;
}
