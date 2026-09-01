"""
ClipForge AI — LLM Client Service

All LLM calls route through an OpenAI-compatible client pointed at the local
OmniRoute/FreeLLMAPI gateway. Zero-cost inference — no paid API keys.

Per PRD constraint: "Never hardcode a paid API key or assume OpenAI/Anthropic billing."

Usage:
    from clipforge_core.services.llm_client import llm_client

    # Simple completion
    response = await llm_client.complete("Summarize this text...")

    # Structured JSON completion
    result = await llm_client.complete_json(
        prompt="Select highlight clips...",
        system="You are a video editor...",
    )
"""

import asyncio
import json
import logging
from typing import Any

import httpx

from clipforge_core.config import settings

logger = logging.getLogger(__name__)


class LLMClientError(Exception):
    """Raised when the LLM gateway returns an error or is unreachable."""

    def __init__(self, message: str, provider_info: str | None = None, retryable: bool = False):
        self.message = message
        self.provider_info = provider_info
        self.retryable = retryable
        super().__init__(message)


class LLMClient:
    """
    OpenAI-compatible client for OmniRoute/FreeLLMAPI gateway.

    Handles:
    - Structured JSON output via response_format
    - Rate limit detection and clear error surfacing
    - Retry logic with exponential backoff
    - Provider fallback info from OmniRoute headers
    """

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        timeout: float = 120.0,
        max_retries: int = 3,
    ):
        self._default_base_url = (base_url or settings.LLM_BASE_URL).rstrip("/")
        self._default_api_key = api_key or settings.LLM_API_KEY
        self._default_model = model or settings.LLM_MODEL
        self.timeout = timeout
        self.max_retries = max_retries

    async def _get_dynamic_settings(self):
        """Fetch latest settings from DB or use defaults."""
        from sqlalchemy import text

        from clipforge_core.database import async_session_factory

        try:
            async with async_session_factory() as session:
                # Check if table exists
                res = await session.execute(
                    text("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'settings')")
                )
                if not res.scalar():
                    return self._default_base_url, self._default_api_key, self._default_model

                # Fetch
                base_url = await session.execute(text("SELECT value FROM settings WHERE key = 'llm_base_url'"))
                base_url = base_url.scalar()

                api_key = await session.execute(text("SELECT value FROM settings WHERE key = 'llm_api_key'"))
                api_key = api_key.scalar()

                model = await session.execute(text("SELECT value FROM settings WHERE key = 'llm_model'"))
                model = model.scalar()

                return (
                    base_url.strip('"') if base_url else self._default_base_url,
                    api_key.strip('"') if api_key else self._default_api_key,
                    model.strip('"') if model else self._default_model,
                )
        except Exception as e:
            logger.warning(f"Failed to fetch dynamic settings, using defaults: {e}")
            return self._default_base_url, self._default_api_key, self._default_model

    def _get_headers(self, api_key: str) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
        }
        if api_key and api_key != "not-needed":
            headers["Authorization"] = f"Bearer {api_key}"
        return headers

    async def complete(
        self,
        prompt: str,
        system: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> str:
        """
        Send a chat completion request and return the text response.

        Args:
            prompt: The user message content
            system: Optional system message
            temperature: Sampling temperature (lower = more deterministic)
            max_tokens: Maximum tokens in response

        Returns:
            The assistant's response text

        Raises:
            LLMClientError: If the gateway returns an error or is unreachable
        """
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        return await self._chat_completion(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    async def complete_json(
        self,
        prompt: str,
        system: str | None = None,
        temperature: float = 0.1,
        max_tokens: int = 4096,
    ) -> dict[str, Any] | list[Any]:
        """
        Send a chat completion request expecting JSON output.

        Instructs the model to respond in JSON format. Parses and validates
        the response as JSON before returning.

        Returns:
            Parsed JSON response (dict or list)

        Raises:
            LLMClientError: If the response is not valid JSON
        """
        # Reinforce JSON instruction in the system prompt
        json_system = (
            system or ""
        ) + "\n\nYou MUST respond with valid JSON only. No markdown, no code fences, no explanation."

        messages = []
        messages.append({"role": "system", "content": json_system.strip()})
        messages.append({"role": "user", "content": prompt})

        raw_response = await self._chat_completion(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
        )

        # Parse JSON response
        try:
            # Strip markdown code fences if the model ignores our instruction
            cleaned = raw_response.strip()
            if cleaned.startswith("```"):
                lines = cleaned.split("\n")
                # Remove first line (```json) and last line (```)
                lines = [line for line in lines[1:] if not line.strip().startswith("```")]
                cleaned = "\n".join(lines)
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            logger.error(f"LLM returned invalid JSON: {raw_response[:500]}")
            raise LLMClientError(
                message=f"LLM response was not valid JSON: {e}",
                retryable=True,
            )

    async def _chat_completion(
        self,
        messages: list[dict],
        temperature: float = 0.3,
        max_tokens: int = 4096,
        response_format: dict | None = None,
    ) -> str:
        """Internal method to make the actual API call with retry logic."""
        base_url, api_key, model = await self._get_dynamic_settings()

        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        if response_format:
            payload["response_format"] = response_format

        url = f"{base_url}/chat/completions"
        headers = self._get_headers(api_key)

        for attempt in range(1, self.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(
                        url,
                        json=payload,
                        headers=headers,
                    )

                provider_info = response.headers.get("x-provider")

                if response.status_code == 200:
                    data = response.json()
                    content = data["choices"][0]["message"]["content"]
                    if provider_info:
                        logger.info(f"LLM Success: {model} via {provider_info}")
                    return content

                if response.status_code == 429:
                    retry_after = int(response.headers.get("retry-after", 2**attempt))
                    logger.warning(f"Rate limited. Retrying in {retry_after}s...")
                    await asyncio.sleep(retry_after)
                    continue

                raise LLMClientError(
                    f"LLM gateway returned HTTP {response.status_code}: {response.text[:100]}",
                    provider_info=provider_info,
                    retryable=response.status_code >= 500,
                )

            except (httpx.ConnectError, httpx.TimeoutException) as e:
                if attempt == self.max_retries:
                    raise LLMClientError(f"Connection failed after {self.max_retries} attempts: {e}")
                await asyncio.sleep(2**attempt)

        raise LLMClientError(f"Failed to get completion after {self.max_retries} retries")

    async def health_check(self) -> dict[str, Any]:
        """Check if the LLM gateway is reachable and responding."""
        base_url, api_key, model = await self._get_dynamic_settings()

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{base_url}/models",
                    headers=self._get_headers(api_key),
                )
                if response.status_code == 200:
                    return {
                        "status": "ok",
                        "base_url": base_url,
                        "model": model,
                        "models_available": True,
                    }
                return {
                    "status": "degraded",
                    "base_url": base_url,
                    "model": model,
                    "http_status": response.status_code,
                }
        except Exception as e:
            return {
                "status": "error",
                "base_url": base_url,
                "model": model,
                "error": str(e),
            }


# Singleton instance — import this in workers and API routes
llm_client = LLMClient()
