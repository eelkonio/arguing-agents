"""FastAPI application factory.

Creates and configures the FastAPI application with all routers,
shared services, and middleware.
"""

from __future__ import annotations

import logging
import pathlib

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from multi_agent_debate.api.debates import router as debates_router
from multi_agent_debate.api.health import router as health_router
from multi_agent_debate.api.sessions import router as sessions_router
from multi_agent_debate.api.stream import EventStreamManager
from multi_agent_debate.api.stream import router as stream_router
from multi_agent_debate.api.audio import router as audio_router
from multi_agent_debate.config import Settings, get_settings
from multi_agent_debate.debate.session import SessionManager
from multi_agent_debate.llm.adapters.base import LLMAdapter
from multi_agent_debate.llm.adapters.bedrock import BedrockAdapter
from multi_agent_debate.llm.adapters.ollama import OllamaAdapter
from multi_agent_debate.llm.rate_limiter import RateLimiter
from multi_agent_debate.llm.services.creator import DebateCreatorService
from multi_agent_debate.llm.services.leader import DebateLeaderService
from multi_agent_debate.llm.services.pusher import PsychoPusherService
from multi_agent_debate.debate.loop import AdapterFactory
from multi_agent_debate.logging import setup_logging
from multi_agent_debate.models.config import LLMBackendConfig, LLMProvider
from multi_agent_debate.storage import DebateStore
from multi_agent_debate.tts.audio_generator import AudioGenerator
from multi_agent_debate.tts.kokoro_adapter import KokoroAdapter
from multi_agent_debate.tts.polly_adapter import PollyAdapter
from multi_agent_debate.tts.voice_assigner import VoiceAssigner

logger = logging.getLogger(__name__)


def _create_adapter_factory(settings: Settings) -> AdapterFactory:
    """Build a factory function that maps :class:`LLMBackendConfig` to an adapter.

    A shared :class:`RateLimiter` is used for all Bedrock adapters.
    """
    rate_limiter = RateLimiter()

    def factory(config: LLMBackendConfig) -> LLMAdapter:
        if config.provider == LLMProvider.BEDROCK:
            return BedrockAdapter(
                model_id=config.model_id,
                region=config.region,
                cross_account_role_arn=config.cross_account_role_arn or settings.cross_account_role_arn,
                rate_limiter=rate_limiter,
                cli_timeout=settings.bedrock_cli_timeout,
            )
        if config.provider == LLMProvider.OLLAMA:
            return OllamaAdapter(
                model_id=config.model_id,
                base_url=config.base_url or settings.default_ollama_base_url,
                timeout=settings.ollama_timeout,
            )
        msg = f"Unsupported LLM provider: {config.provider}"
        raise ValueError(msg)

    return factory


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure the FastAPI application.

    Args:
        settings: Optional settings override. When *None* the default
            singleton from :func:`get_settings` is used.

    Returns:
        A fully configured :class:`FastAPI` instance.
    """
    if settings is None:
        settings = get_settings()

    # Set up structured JSON logging
    setup_logging(settings.log_level)

    app = FastAPI(
        title="Multi-Agent Debate System",
        version="0.1.0",
        description="Real-time AI debate orchestration with dynamic emotional states",
    )

    # --- Adapter factory ---
    adapter_factory = _create_adapter_factory(settings)

    # --- Service instances ---
    # The creator, leader, and pusher each get a default adapter built from
    # the settings.  During a debate the loop uses the per-agent backend
    # assignments via the adapter factory.
    default_bedrock_config = LLMBackendConfig(
        provider=LLMProvider.BEDROCK,
        model_id=settings.default_bedrock_model_id,
        region=settings.default_bedrock_region,
        cross_account_role_arn=settings.cross_account_role_arn,
    )

    creator_service = DebateCreatorService(adapter_factory(default_bedrock_config))
    leader_service = DebateLeaderService(adapter_factory(default_bedrock_config))
    pusher_service = PsychoPusherService(adapter_factory(default_bedrock_config))

    # --- Debate store ---
    debate_store = DebateStore(settings.database_path)

    # --- Session manager ---
    session_manager = SessionManager(creator_service, store=debate_store)

    # --- Event stream manager ---
    event_stream_manager = EventStreamManager()

    # --- Store shared state on app.state ---
    app.state.settings = settings
    app.state.session_manager = session_manager
    app.state.event_stream_manager = event_stream_manager
    app.state.adapter_factory = adapter_factory
    app.state.debate_store = debate_store
    app.state.services = {
        "creator": creator_service,
        "leader": leader_service,
        "pusher": pusher_service,
    }

    # --- Audio generator ---
    tts_backend = settings.tts_backend
    polly_adapter = PollyAdapter(region=settings.default_bedrock_region) if tts_backend == "polly" else None
    kokoro_adapter = KokoroAdapter() if tts_backend == "kokoro" else None
    voice_assigner = VoiceAssigner(backend=tts_backend)
    audio_generator = AudioGenerator(
        voice_assigner=voice_assigner,
        store=debate_store,
        output_dir=settings.audio_output_dir,
        polly_adapter=polly_adapter,
        kokoro_adapter=kokoro_adapter,
        tts_backend=tts_backend,
    )
    app.state.polly_adapter = polly_adapter
    app.state.kokoro_adapter = kokoro_adapter
    app.state.audio_generator = audio_generator

    # --- Register routers ---
    app.include_router(sessions_router)
    app.include_router(stream_router)
    app.include_router(health_router)
    app.include_router(debates_router)
    app.include_router(audio_router)

    # --- CORS ---
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # --- Static files (frontend build output) ---
    static_dir = pathlib.Path("static")
    if static_dir.is_dir():
        app.mount("/", StaticFiles(directory="static", html=True), name="static")
        logger.info("Mounted static files from '%s'", static_dir)

    # --- Startup: initialize debate store ---
    @app.on_event("startup")
    async def _startup() -> None:
        await debate_store.initialize()

    logger.info("Application created — port=%d, log_level=%s", settings.port, settings.log_level)
    return app
