# Multi-Agent Debate System

A web-based system where AI agents debate topics in real time. You enter a topic, a number of agents, and an optional theme (e.g., "Greek gods", "farm yard cattle", "members of the A-team"), and the system generates unique characters that argue the topic with evolving emotions, interruptions, and dynamic turn management.

![Debate Screenshot](mockups/03-debate-live.html)

## How It Works

- **Debate Creator** — an LLM generates unique agent personas with backgrounds, expertise, character traits, and initial emotional states
- **Debate Leader** — an LLM orchestrates who speaks next, prompts silent agents, detects topic drift, manages closing arguments, and controls interrupt cascades
- **Psycho Pusher** — an LLM analyzes each statement and updates every agent's emotional state (anger, enthusiasm, frustration, agreement, resentment, confidence, withdrawal)
- **Agents** — each agent generates statements reflecting their persona and current emotional state, powered by configurable LLM backends

## Features

- **Themed debates** — "Greek gods discuss modern civilization", "A-team members debate violence in movies"
- **Dynamic emotions** — 7 emotional dimensions that shift after every statement, driving who speaks next and who interrupts
- **Interruptions & cascades** — agents interrupt when emotions run high; cascades can develop when one interruption provokes others
- **Silent agent engagement** — withdrawn agents get drawn back in by the debate leader
- **Topic drift detection** — the debate leader steers the discussion back when it veers off-topic
- **Graceful closing** — configurable max turns with ±10% leniency, closing arguments from each agent
- **Profanity handling** — agents use "[CENSURED]" for profanity, based on their character
- **Debate history** — all debates stored in SQLite, browsable and replayable
- **Audio debates** — generate MP3 audio of completed debates with distinct voices per agent (Polly or Kokoro)
- **Print view** — clean printable version of any debate
- **Multiple LLM backends** — Claude (via AWS Bedrock) or local models (via Ollama)
- **Per-agent model selection** — assign different models to different agents
- **Real-time streaming** — debate unfolds live in the browser via Server-Sent Events

## Quick Start

### Prerequisites

- Python 3.12+
- Node.js 20+
- [Poetry](https://python-poetry.org/docs/#installation)
- AWS CLI v2 (for Bedrock and Polly TTS) or [Ollama](https://ollama.ai/) (for local models)
- `ffmpeg` (for audio MP3 export): `brew install ffmpeg`
- `espeak-ng` (for Kokoro TTS): `brew install espeak-ng`

### Setup

```bash
# Clone the repo
git clone https://github.com/your-username/multi-agent-debate.git
cd multi-agent-debate

# Install Python dependencies
poetry install

# Install and build the frontend
cd frontend && npm install && npm run build && cd ..

# Copy built frontend to static/
cp -r frontend/dist static

# Set up AWS credentials for Bedrock (or use Ollama)
cp aws-access.sh.example aws-access.sh
# Edit aws-access.sh with your AWS credentials
```

### Run

```bash
# With AWS Bedrock
source aws-access.sh && poetry run python -m multi_agent_debate.entrypoint

# Or without Bedrock (use Ollama for local models)
poetry run python -m multi_agent_debate.entrypoint
```

Open http://localhost:8080 in your browser.

### Using Ollama (Local Models)

If you don't have AWS access, you can use Ollama with local models:

```bash
# Install Ollama: https://ollama.ai/
ollama pull llama3

# Start the debate system
poetry run python -m multi_agent_debate.entrypoint
```

In the config form, select "Ollama — llama3" for all backends.

## Architecture

- **Backend**: FastAPI (Python) with async debate loop engine
- **Frontend**: React + TypeScript (Vite)
- **Streaming**: Server-Sent Events (SSE)
- **Storage**: SQLite via aiosqlite
- **LLM Adapters**: AWS Bedrock (CLI subprocess) and Ollama (httpx)

```
Browser (React) ←—SSE—→ FastAPI Backend
                              ├── Debate Loop Engine
                              ├── LLM Services (Creator, Leader, Pusher, Agent)
                              ├── LLM Adapters (Bedrock, Ollama)
                              └── SQLite Store
```

## Configuration

Environment variables (prefix `DEBATE_`):

| Variable | Default | Description |
|---|---|---|
| `DEBATE_PORT` | `8080` | Server port |
| `DEBATE_LOG_LEVEL` | `info` | Log level (debug, info, warn, error) |
| `DEBATE_DEFAULT_BEDROCK_REGION` | `eu-central-1` | AWS region for Bedrock |
| `DEBATE_DEFAULT_BEDROCK_MODEL_ID` | `eu.anthropic.claude-sonnet-4-20250514-v1:0` | Default Bedrock model |
| `DEBATE_DEFAULT_OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server URL |
| `DEBATE_DATABASE_PATH` | `./data/debates.db` | SQLite database path |
| `DEBATE_INTERRUPTION_THRESHOLD` | `0.8` | Emotional threshold for interruptions |
| `DEBATE_SILENT_TURN_THRESHOLD` | `3` | Turns before prompting a silent agent |
| `DEBATE_TOPIC_DRIFT_CHECK_INTERVAL` | `5` | Check for topic drift every N turns |
| `DEBATE_TTS_BACKEND` | `polly` | TTS engine: `polly` (AWS cloud) or `kokoro` (local, free) |
| `DEBATE_AUDIO_OUTPUT_DIR` | `./data/audio` | Directory for generated MP3 files |

## Audio Debate Generation

After a debate ends, you can generate an MP3 audio version from the debate history view. The audio includes:

1. **Introduction** — the debate leader announces the topic and introduces each agent
2. **Voice identification** — each agent responds to their introduction so you learn their voice
3. **Full debate** — the leader announces each speaker by name before their statement

### TTS Backend: Polly (default)

Uses AWS Polly's generative engine. Fast (~1-2 seconds per statement), high quality, costs ~$0.30 per debate.

```bash
# Polly is the default — just needs AWS credentials
source aws-access.sh && poetry run python -m multi_agent_debate.entrypoint
```

Voices: Matthew, Stephen, Gregory, Kevin (male) / Ruth, Danielle, Joanna, Amy (female). Narrator: Matthew.

### TTS Backend: Kokoro (free, local)

Uses Kokoro-82M, an open-source 82M parameter TTS model. Runs locally, no API costs, Apache 2.0 licensed. Slower than Polly but free.

```bash
# Switch to Kokoro
DEBATE_TTS_BACKEND=kokoro poetry run python -m multi_agent_debate.entrypoint
```

Requires `espeak-ng`: `brew install espeak-ng` (Mac) or `apt install espeak-ng` (Linux).

Voices: 8 male American English voices, 11 female American English voices. Narrator: female (`af_heart`), freeing up male voices for debaters. When there are more agents than available voices, voices are reused with speed variations (0.9x, 1.1x, etc.) to sound distinct.

## Development

```bash
# Backend (auto-reload)
source aws-access.sh && poetry run python -m multi_agent_debate.entrypoint

# Frontend dev server (separate terminal, hot reload)
cd frontend && npm run dev
# Then open http://localhost:5173 (proxies API to :8080)

# Run tests
poetry run pytest tests/ -v

# Lint & type check
poetry run ruff check .
poetry run mypy src/
```

## License

MIT
