"""CLI entrypoint for uvicorn startup."""

from __future__ import annotations

import uvicorn

from multi_agent_debate.config import get_settings


def run_application() -> None:
    """Start the application with uvicorn.

    Reads host/port from :func:`get_settings` and launches a single
    uvicorn worker.  This function is registered as the
    ``run_application`` console script in ``pyproject.toml``.
    """
    settings = get_settings()
    uvicorn.run(
        "multi_agent_debate.main:create_app",
        factory=True,
        host="0.0.0.0",  # noqa: S104
        port=settings.port,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    run_application()
