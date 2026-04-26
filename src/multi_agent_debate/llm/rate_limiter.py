"""Rate limiting with exponential backoff for Bedrock."""

import asyncio
import time


class RateLimiter:
    """Enforces minimum delay between LLM calls and adapts on throttling.

    Designed for Bedrock's RPM limits. On ThrottlingException the caller
    should invoke ``on_throttle()`` which increases the minimum delay by
    1.5×, capped at 30 seconds.
    """

    def __init__(self, min_delay: float = 2.0, max_rpm: int = 20) -> None:
        self._min_delay = min_delay
        self._max_rpm = max_rpm
        self._last_call: float = 0.0

    @property
    def min_delay(self) -> float:
        """Current minimum delay between calls in seconds."""
        return self._min_delay

    async def wait(self) -> None:
        """Wait until the minimum delay has elapsed since the last call."""
        if self._last_call > 0:
            elapsed = time.monotonic() - self._last_call
            remaining = self._min_delay - elapsed
            if remaining > 0:
                await asyncio.sleep(remaining)

    def record_call(self) -> None:
        """Record that a call was made (updates the last-call timestamp)."""
        self._last_call = time.monotonic()

    def on_throttle(self) -> None:
        """Increase delay on ThrottlingException (1.5×, capped at 30s)."""
        self._min_delay = min(self._min_delay * 1.5, 30.0)
