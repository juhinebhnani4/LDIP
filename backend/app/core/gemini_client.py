"""Shared Gemini client for google.genai SDK.

Provides a singleton genai.Client instance for all Gemini API calls.
Migrated from deprecated google-generativeai to google-genai SDK.

Usage:
    from app.core.gemini_client import get_gemini_client
    from google.genai import types

    client = get_gemini_client()

    # Sync
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction="...",
            temperature=0.1,
        ),
    )

    # Async
    response = await client.aio.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction="...",
        ),
    )

    print(response.text)
"""

from functools import lru_cache

import structlog

from app.core.config import get_settings

logger = structlog.get_logger(__name__)


class GeminiClientError(Exception):
    """Raised when the Gemini client cannot be created."""


@lru_cache(maxsize=1)
def get_gemini_client():
    """Get singleton Gemini client instance.

    Returns:
        google.genai.Client instance configured with API key.

    Raises:
        GeminiClientError: If GEMINI_API_KEY is not configured.
    """
    settings = get_settings()

    if not settings.gemini_api_key:
        raise GeminiClientError(
            "Gemini API key not configured. Set GEMINI_API_KEY environment variable."
        )

    try:
        from google import genai

        client = genai.Client(api_key=settings.gemini_api_key)
        logger.info("gemini_client_initialized")
        return client
    except Exception as e:
        logger.error("gemini_client_init_failed", error=str(e))
        raise GeminiClientError(f"Failed to initialize Gemini client: {e}") from e
