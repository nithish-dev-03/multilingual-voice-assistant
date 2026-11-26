import asyncio
import base64
import io
import logging
from typing import Any

from google import genai
from pydantic import BaseModel, Field, ValidationError

from app.core.config import Settings
from app.core.exceptions import TranscriptionError
from app.core.gemini import raise_mapped_gemini_error
from app.schemas.voice import TranscriptionResult, ValidatedAudio

logger = logging.getLogger(__name__)


class _DetectedLanguageSchema(BaseModel):
    language_code: str | None = Field(
        default=None,
        description="Primary ISO 639-1 or BCP-47 language code (e.g. 'en', 'ta', 'hi'), or null.",
    )
    language_name: str | None = Field(
        default=None,
        description="English name of the primary language (e.g. 'English', 'Tamil'), or null.",
    )


class TranscriptionService:
    """Speech-to-text service backed by Gemini 3.5 Transcribe."""

    def __init__(self, client: genai.Client, settings: Settings) -> None:
        self._client = client
        self._settings = settings

    async def transcribe(self, audio: ValidatedAudio) -> TranscriptionResult:
        """Transcribe validated audio verbatim and extract language metadata.

        Note:
            ``gemini-3.5-transcribe`` detects the spoken language internally to
            transcribe speech (including code-switching), but its Interactions API
            response only exposes ``output_text`` (and optional word-level timing
            annotations), without a structured language code field. Language
            metadata is therefore identified in an explicit follow-up structured
            output call using ``settings.chat_model``.
        """
        uploaded_file: Any = None
        try:
            if audio.size_bytes <= self._settings.inline_audio_limit_bytes:
                audio_part: dict[str, Any] = {
                    "type": "audio",
                    "data": base64.b64encode(audio.data).decode("ascii"),
                    "mime_type": audio.mime_type,
                }
            else:
                uploaded_file = await self._client.aio.files.upload(
                    file=io.BytesIO(audio.data),
                    config={"mime_type": audio.mime_type},
                )
                audio_part = {
                    "type": "audio",
                    "uri": uploaded_file.uri,
                    "mime_type": uploaded_file.mime_type or audio.mime_type,
                }

            response = await asyncio.wait_for(
                self._client.aio.interactions.create(
                    model=self._settings.transcription_model,
                    input=[audio_part],
                    generation_config={
                        "transcription_config": {
                            "mode": "verbatim",
                        }
                    },
                    api_version=self._settings.gemini_api_version,
                    timeout=self._settings.gemini_timeout_seconds,
                ),
                timeout=self._settings.gemini_timeout_seconds,
            )
        except Exception as exc:
            raise_mapped_gemini_error(exc, TranscriptionError, "transcription")
        finally:
            if uploaded_file is not None and getattr(uploaded_file, "name", None):
                try:
                    await self._client.aio.files.delete(name=uploaded_file.name)
                except Exception:
                    logger.warning(
                        "Failed to delete temporary Gemini file %s",
                        uploaded_file.name,
                        exc_info=True,
                    )

        transcript_text = (getattr(response, "output_text", None) or "").strip()
        if not transcript_text:
            raise TranscriptionError(
                "Transcription returned empty text. Ensure the audio contains clear speech."
            )

        language_code, language_name = await self._detect_language(transcript_text)
        return TranscriptionResult(
            text=transcript_text,
            language_code=language_code,
            language_name=language_name,
        )

    async def _detect_language(self, text: str) -> tuple[str | None, str | None]:
        """Explicitly identify the primary language of the transcribed text."""
        try:
            response = await self._client.aio.interactions.create(
                model=self._settings.chat_model,
                system_instruction=(
                    "Identify the primary language of the provided transcript. "
                    "If the text contains code-switching (multiple languages), identify "
                    "the primary or dominant language. Return ISO 639-1 code "
                    "(e.g. 'en', 'ta', 'hi') and English language name "
                    "(e.g. 'English', 'Tamil', 'Hindi')."
                ),
                input=text,
                response_format={
                    "type": "text",
                    "mime_type": "application/json",
                    "schema": _DetectedLanguageSchema.model_json_schema(),
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
            parsed = _DetectedLanguageSchema.model_validate_json(raw_json)
            code = parsed.language_code.strip().lower() if parsed.language_code else None
            name = parsed.language_name.strip() if parsed.language_name else None
            return code or None, name or None
        except (ValidationError, ValueError, Exception):
            logger.warning(
                "Language metadata extraction failed; continuing without it",
                exc_info=True,
            )
            return None, None
