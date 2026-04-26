"""AWS CLI subprocess adapter for Bedrock (workaround for boto3 EU inference profile issue).

Invokes ``aws bedrock-runtime converse`` via asyncio subprocess. Messages are
written to a temp file with the ``file://`` prefix to avoid ARG_MAX limits.
Supports cross-account access via STS AssumeRole with credential caching and
automatic refresh on ``ExpiredToken`` errors.

Designed behind the ``LLMAdapter`` abstract interface so it can be replaced
with a boto3-based implementation when the inference profile issue is resolved.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import tempfile
from typing import Any

from multi_agent_debate.llm.adapters.base import (
    ChatMessage,
    ChatRequest,
    ChatResponse,
    LLMAdapter,
)
from multi_agent_debate.llm.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

# Default EU inference profiles in eu-central-1
EU_MODELS = [
    "eu.anthropic.claude-opus-4-6-v1",
    "eu.anthropic.claude-sonnet-4-20250514-v1:0",
    "eu.anthropic.claude-haiku-3-20240307-v1:0",
]


def _messages_to_converse_format(messages: list[ChatMessage]) -> tuple[list[dict[str, Any]], str | None]:
    """Convert ChatMessage list to Bedrock Converse API format.

    Returns a tuple of (converse_messages, system_prompt).
    The Converse API takes system prompts separately from messages.
    """
    system_prompt: str | None = None
    converse_messages: list[dict[str, Any]] = []

    for msg in messages:
        if msg.role == "system":
            system_prompt = msg.content
        else:
            converse_messages.append(
                {
                    "role": msg.role,
                    "content": [{"text": msg.content}],
                }
            )

    return converse_messages, system_prompt


class BedrockAdapter(LLMAdapter):
    """Bedrock adapter using AWS CLI subprocess.

    Args:
        model_id: Bedrock model identifier. Defaults to the EU Opus profile.
        region: AWS region. Defaults to ``eu-central-1``.
        cross_account_role_arn: Optional IAM role ARN for cross-account access.
        rate_limiter: Optional RateLimiter instance for throttle management.
        cli_timeout: Timeout in seconds for CLI subprocess calls.
    """

    def __init__(
        self,
        model_id: str = "eu.anthropic.claude-opus-4-6-v1",
        region: str = "eu-central-1",
        cross_account_role_arn: str | None = None,
        rate_limiter: RateLimiter | None = None,
        cli_timeout: int = 600,
    ) -> None:
        self._model_id = model_id
        self._region = region
        self._cross_account_role_arn = cross_account_role_arn
        self._rate_limiter = rate_limiter
        self._cli_timeout = cli_timeout

        # Cached STS credentials
        self._cached_credentials: dict[str, str] | None = None

    # ------------------------------------------------------------------
    # Cross-account STS AssumeRole (Task 4.3)
    # ------------------------------------------------------------------

    async def _get_credentials(self) -> dict[str, str] | None:
        """Obtain temporary credentials via STS AssumeRole.

        Returns environment variable dict with AWS_ACCESS_KEY_ID,
        AWS_SECRET_ACCESS_KEY, and AWS_SESSION_TOKEN, or None when
        no cross-account role is configured.

        Credentials are cached and reused until an ``ExpiredToken``
        error triggers a refresh.
        """
        if self._cross_account_role_arn is None:
            return None

        if self._cached_credentials is not None:
            return self._cached_credentials

        return await self._refresh_credentials()

    async def _refresh_credentials(self) -> dict[str, str]:
        """Call ``aws sts assume-role`` and cache the result."""
        if self._cross_account_role_arn is None:
            msg = "Cannot refresh credentials without a cross-account role ARN"
            raise RuntimeError(msg)

        logger.info("Assuming cross-account role: %s", self._cross_account_role_arn)

        proc = await asyncio.create_subprocess_exec(
            "aws",
            "sts",
            "assume-role",
            "--role-arn",
            self._cross_account_role_arn,
            "--role-session-name",
            "multi-agent-debate",
            "--output",
            "json",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)

        if proc.returncode != 0:
            error_msg = stderr.decode().strip() if stderr else "unknown error"
            msg = f"STS assume-role failed: {error_msg}"
            raise RuntimeError(msg)

        result = json.loads(stdout.decode())
        creds = result["Credentials"]

        self._cached_credentials = {
            "AWS_ACCESS_KEY_ID": creds["AccessKeyId"],
            "AWS_SECRET_ACCESS_KEY": creds["SecretAccessKey"],
            "AWS_SESSION_TOKEN": creds["SessionToken"],
        }
        return self._cached_credentials

    def _invalidate_credentials(self) -> None:
        """Clear cached credentials so the next call triggers a refresh."""
        self._cached_credentials = None

    # ------------------------------------------------------------------
    # Chat implementation
    # ------------------------------------------------------------------

    async def chat(self, request: ChatRequest) -> ChatResponse:
        """Invoke Bedrock via ``aws bedrock-runtime converse``.

        Writes messages to a temp file, executes the CLI subprocess,
        and parses the JSON response. Retries up to 3 times on
        ``ThrottlingException`` with doubling delay.
        """
        max_retries = 3
        initial_backoff = 2.0

        for attempt in range(max_retries + 1):
            if self._rate_limiter is not None:
                await self._rate_limiter.wait()

            try:
                response = await self._invoke(request)
                if self._rate_limiter is not None:
                    self._rate_limiter.record_call()
                return response

            except RuntimeError as exc:
                error_text = str(exc)
                logger.warning(
                    "Bedrock call failed on attempt %d/%d (model=%s): %s",
                    attempt + 1,
                    max_retries + 1,
                    self._model_id,
                    error_text,
                )

                # Handle expired STS credentials
                if "ExpiredToken" in error_text:
                    logger.warning("STS credentials expired, refreshing")
                    self._invalidate_credentials()
                    continue

                # Handle throttling with exponential backoff
                if "ThrottlingException" in error_text:
                    if self._rate_limiter is not None:
                        self._rate_limiter.on_throttle()

                    if attempt < max_retries:
                        backoff = initial_backoff * (2**attempt)
                        logger.warning(
                            "ThrottlingException on attempt %d/%d, retrying in %.1fs",
                            attempt + 1,
                            max_retries,
                            backoff,
                        )
                        await asyncio.sleep(backoff)
                        continue

                # Non-retryable error or retries exhausted
                raise

        # Should not reach here, but satisfy type checker
        msg = "Bedrock call failed after all retries"
        raise RuntimeError(msg)

    async def _invoke(self, request: ChatRequest) -> ChatResponse:
        """Execute a single Bedrock CLI call."""
        converse_messages, system_prompt = _messages_to_converse_format(request.messages)

        # Write messages to temp file to avoid ARG_MAX limits
        fd, tmp_path = tempfile.mkstemp(suffix=".json", prefix="bedrock_msg_")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(converse_messages, f)

            cmd: list[str] = [
                "aws",
                "bedrock-runtime",
                "converse",
                "--model-id",
                self._model_id,
                "--messages",
                f"file://{tmp_path}",
                "--inference-config",
                json.dumps(
                    {
                        "maxTokens": request.max_tokens,
                        "temperature": request.temperature,
                    }
                ),
                "--region",
                self._region,
                "--cli-read-timeout",
                str(self._cli_timeout),
                "--cli-connect-timeout",
                "30",
                "--output",
                "json",
            ]

            # Add system prompt if present
            if system_prompt is not None:
                cmd.extend(
                    [
                        "--system",
                        json.dumps([{"text": system_prompt}]),
                    ]
                )

            # Build environment with optional cross-account credentials
            env = os.environ.copy()
            credentials = await self._get_credentials()
            if credentials is not None:
                env.update(credentials)

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=self._cli_timeout + 30,
            )

            if proc.returncode != 0:
                error_msg = stderr.decode().strip() if stderr else "unknown error"
                logger.error(
                    "Bedrock CLI failed (exit code %d, model=%s, region=%s): %s",
                    proc.returncode,
                    self._model_id,
                    self._region,
                    error_msg,
                )
                msg = f"Bedrock CLI error: {error_msg}"
                raise RuntimeError(msg)

            result = json.loads(stdout.decode())
            content_blocks = result["output"]["message"]["content"]
            content = "\n".join(block["text"] for block in content_blocks if "text" in block)

            usage = result.get("usage")

            return ChatResponse(content=content, usage=usage)

        finally:
            # Always clean up the temp file
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    # ------------------------------------------------------------------
    # Health check
    # ------------------------------------------------------------------

    async def health_check(self) -> bool:
        """Verify Bedrock is reachable with a lightweight call.

        Sends a minimal prompt and checks for a successful response.
        """
        try:
            request = ChatRequest(
                messages=[ChatMessage(role="user", content="Hi")],
                max_tokens=10,
                temperature=0.0,
            )
            await self._invoke(request)
            return True
        except Exception:
            logger.warning("Bedrock health check failed", exc_info=True)
            return False
