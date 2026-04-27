"""Application configuration via pydantic-settings."""

from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    All environment variables are prefixed with DEBATE_, e.g. DEBATE_PORT, DEBATE_LOG_LEVEL.
    """

    port: int = 8080
    log_level: str = "info"
    default_bedrock_region: str = "eu-central-1"
    default_bedrock_model_id: str = "eu.anthropic.claude-sonnet-4-20250514-v1:0"
    default_ollama_base_url: str = "http://localhost:11434"
    interruption_threshold: float = 0.8
    interruption_dimensions: list[str] = ["anger", "enthusiasm"]
    silent_turn_threshold: int = 3
    cross_account_role_arn: str | None = None
    bedrock_cli_timeout: int = 600
    ollama_timeout: int = 60
    max_context_tokens: int = 180000
    max_output_tokens: int = 128000
    database_path: str = "./data/debates.db"
    topic_drift_check_interval: int = 5
    audio_output_dir: str = "./data/audio"
    bark_device: str = "auto"  # "auto", "cpu", "cuda", or "mps"
    tts_backend: str = "polly"  # "polly" or "kokoro"
    model_config = {"env_prefix": "DEBATE_"}


@lru_cache
def get_settings() -> Settings:
    """Return a cached singleton Settings instance."""
    return Settings()
