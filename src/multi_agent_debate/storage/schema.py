"""SQL schema definitions for the debate persistence layer."""

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    topic TEXT NOT NULL,
    agent_theme TEXT,
    agent_count INTEGER NOT NULL,
    max_turns INTEGER,
    config_json TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'configuring',
    created_at REAL NOT NULL,
    started_at REAL,
    ended_at REAL,
    summary_json TEXT
);

CREATE TABLE IF NOT EXISTS agents (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES sessions(id),
    name TEXT NOT NULL,
    persona_json TEXT NOT NULL,
    final_emotional_state_json TEXT
);

CREATE TABLE IF NOT EXISTS statements (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES sessions(id),
    agent_id TEXT NOT NULL,
    agent_name TEXT NOT NULL,
    content TEXT NOT NULL,
    is_interruption BOOLEAN NOT NULL DEFAULT 0,
    is_closing_argument BOOLEAN NOT NULL DEFAULT 0,
    timestamp REAL NOT NULL,
    emotional_state_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS leader_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES sessions(id),
    event_type TEXT NOT NULL,
    content TEXT NOT NULL,
    agent_id TEXT,
    agent_name TEXT,
    timestamp REAL NOT NULL
);
"""
