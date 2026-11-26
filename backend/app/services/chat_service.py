import asyncio
import logging
from typing import Any

from google import genai
from pydantic import BaseModel, Field, ValidationError

from app.core.config import Settings
from app.core.exceptions import ChatServiceError
from app.core.gemini import raise_mapped_gemini_error
from app.schemas.chat import ChatMessage

logger = logging.getLogger(__name__)

MULTILINGUAL_SYSTEM_INSTRUCTION = (
    "You are a helpful, natural, and concise multilingual conversational voice assistant. "
    "Always understand messages in any language (including code-switched speech) and respond "
    "in the same language as the user's message unless the user explicitly asks you to switch "
    "languages. Preserve conversational context across turns, avoid unnecessary translation, "
    "and keep answers clear and well-suited for spoken playback."
)


class _TextLanguageSchema(BaseModel):
    language_code: str | None = Field(default=None)
    language_name: str | None = Field(default=None)


class ChatService:
    """Conversational LLM service backed by Gemini 3.5 Flash-Lite."""

    def __init__(self, client: genai.Client, settings: Settings) -> None:
        self._client = client
        self._settings = settings

    async def generate_reply(
        self,
        user_message: str,
        history: list[ChatMessage] | None = None,
        *,
        detected_language: str | None = None,
    ) -> str:
        """Generate a context-aware multilingual assistant response."""
        cleaned_message = user_message.strip()
        if not cleaned_message:
            raise ChatServiceError("Cannot generate a response for an empty message.")

        steps: list[dict[str, Any]] = []
        for msg in history or []:
            step_type = "user_input" if msg.role == "user" else "model_output"
            steps.append(
                {
                    "type": step_type,
                    "content": [{"type": "text", "text": msg.content}],
                }
            )
        steps.append(
            {
                "type": "user_input",
                "content": [{"type": "text", "text": cleaned_message}],
            }
        )

        system_instruction = MULTILINGUAL_SYSTEM_INSTRUCTION
        if detected_language:
            system_instruction = (
                f"{system_instruction} "
                f"Detected user input language: {detected_language}."
            )

        try:
            response = await asyncio.wait_for(
                self._client.aio.interactions.create(
                    model=self._settings.chat_model,
                    system_instruction=system_instruction,
                    input=steps,
                    generation_config={
                        "temperature": self._settings.chat_temperature,
                        "max_output_tokens": self._settings.chat_max_output_tokens,
                    },
                    api_version=self._settings.gemini_api_version,
                    timeout=self._settings.gemini_timeout_seconds,
                ),
                timeout=self._settings.gemini_timeout_seconds,
            )
        except Exception as exc:
            raise_mapped_gemini_error(exc, ChatServiceError, "chat generation")

        reply_text = (getattr(response, "output_text", None) or "").strip()
        if not reply_text:
            raise ChatServiceError("Chat model returned an empty response.")

        return reply_text

    async def detect_text_language(self, text: str) -> tuple[str | None, str | None]:
        """Detect language metadata for direct text input; returns ``(None, None)`` on failure."""
        cleaned = text.strip()
        if not cleaned:
            return None, None
        try:
            response = await self._client.aio.interactions.create(
                model=self._settings.chat_model,
                system_instruction=(
                    "Identify the primary language of the user text. "
                    "Return ISO 639-1 code and English language name."
                ),
                input=cleaned,
                response_format={
                    "type": "text",
                    "mime_type": "application/json",
                    "schema": _TextLanguageSchema.model_json_schema(),
                },
                generation_config={
                    "temperature": 0.0,
                    "max_output_tokens": 128,
                },
                api_version=self._settings.gemini_api_version,
                timeout=self._settings.gemini_timeout_seconds,
            )
            raw_json = (getattr(response, "output_text", None) or "").strip()
            if not raw_json:
                return None, None
            parsed = _TextLanguageSchema.model_validate_json(raw_json)
            code = parsed.language_code.strip().lower() if parsed.language_code else None
            name = parsed.language_name.strip() if parsed.language_name else None
            return code or None, name or None
        except (ValidationError, ValueError, Exception):
            logger.debug("Text language detection skipped due to error", exc_info=True)
            return None, None
