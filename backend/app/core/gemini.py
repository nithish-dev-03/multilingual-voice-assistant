import asyncio
import logging
import re
from typing import NoReturn

import httpx
from google import genai
from google.genai import errors as genai_errors

from app.core.config import Settings, settings
from app.core.exceptions import (
    ExternalServiceError,
    GeminiAuthenticationError,
    GeminiRateLimitError,
    GeminiServiceUnavailableError,
    GeminiTimeoutError,
)

logger = logging.getLogger(__name__)

_SECRET_PATTERN = re.compile(r"(AIza[0-9A-Za-z_-]{20,}|key=[^&\s]+)")


def _sanitize_error_message(message: str) -> str:
    return _SECRET_PATTERN.sub("[REDACTED]", message).strip()


def create_gemini_client(app_settings: Settings) -> genai.Client:
    """Create a configured Google Gen AI client using Google AI Studio API key."""
    return genai.Client(
        api_key=app_settings.gemini_api_key.get_secret_value(),
        http_options={
            "api_version": app_settings.gemini_api_version,
            "retry_options": {
                "attempts": app_settings.gemini_max_retries + 1,
                "max_delay": 5.0,
            },
        },
    )


async def close_gemini_client(client: genai.Client | None) -> None:
    """Close async and sync transports held by a ``genai.Client``."""
    if client is None:
        return
    try:
        await client.aio.aclose()
    except Exception:
        logger.debug("Error closing async Gemini client", exc_info=True)
    try:
        client.close()
    except Exception:
        logger.debug("Error closing sync Gemini client", exc_info=True)


def _extract_status_and_message(exc: Exception) -> tuple[int | None, str]:
    if isinstance(exc, genai_errors.APIError):
        return exc.code, exc.message or str(exc)

    status_code = getattr(exc, "status_code", None)
    raw_response = getattr(exc, "raw_response", None)
    if status_code is None and raw_response is not None:
        status_code = getattr(raw_response, "status_code", None)

    data = getattr(exc, "data", None)
    if data is not None:
        err_obj = getattr(data, "error", None)
        if err_obj is not None and getattr(err_obj, "message", None):
            return status_code, str(err_obj.message)

    return status_code, str(exc)


def raise_mapped_gemini_error(
    exc: Exception,
    default_error_cls: type[ExternalServiceError],
    operation: str,
) -> NoReturn:
    """Translate Gemini SDK, HTTP, and timeout errors into application exceptions."""
    if isinstance(exc, (TimeoutError, asyncio.TimeoutError, httpx.TimeoutException)):
        raise GeminiTimeoutError(
            f"Gemini {operation} request timed out."
        ) from exc

    status_code, raw_message = _extract_status_and_message(exc)
    safe_message = _sanitize_error_message(raw_message) or f"Gemini {operation} failed."

    if status_code in {401, 403}:
        raise GeminiAuthenticationError(
            f"Gemini authentication failed during {operation}. Check GEMINI_API_KEY configuration."
        ) from exc

    if status_code == 429:
        raise GeminiRateLimitError(
            f"Gemini rate limit exceeded during {operation}. Please retry shortly."
        ) from exc

    if status_code in {500, 502, 503, 504}:
        raise GeminiServiceUnavailableError(
            f"Gemini service is temporarily unavailable during {operation} (HTTP {status_code})."
        ) from exc

    if status_code is not None:
        raise default_error_cls(
            f"Gemini {operation} failed (HTTP {status_code}): {safe_message}"
        ) from exc

    raise default_error_cls(f"Gemini {operation} failed: {safe_message}") from exc


# Preserved module-level client for standalone scripts and backward compatibility.
gemini_client = create_gemini_client(settings)
