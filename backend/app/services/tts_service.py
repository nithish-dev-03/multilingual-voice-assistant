import asyncio
import base64
import binascii

from google import genai

from app.core.config import Settings
from app.core.exceptions import TTSServiceError
from app.core.gemini import raise_mapped_gemini_error
from app.utils.audio_utils import ensure_wav_or_preserve_mime


class TTSService:
    """Text-to-speech synthesis service backed by Gemini 3.8 TTS models."""

    def __init__(self, client: genai.Client, settings: Settings) -> None:
        self._client = client
        self._settings = settings

    async def synthesize(
        self,
        text: str,
        *,
        voice: str | None = None,
    ) -> tuple[bytes, str]:
        """Convert assistant text into spoken audio bytes and accurate MIME type."""
        cleaned_text = text.strip()
        if not cleaned_text:
            raise TTSServiceError("Cannot synthesize speech from empty text.")

        selected_voice = (voice or self._settings.tts_voice).strip()
        if not selected_voice:
            raise TTSServiceError("TTS voice must not be empty.")

        try:
            response = await asyncio.wait_for(
                self._client.aio.interactions.create(
                    model=self._settings.tts_model,
                    input=[
                        {
                            "type": "user_input",
                            "content": [
                                {
                                    "type": "text",
                                    "text": cleaned_text,
                                }
                            ],
                        }
                    ],
                    response_format={"type": "audio"},
                    generation_config={
                        "speech_config": [
                            {"voice": selected_voice},
                        ]
                    },
                    api_version=self._settings.gemini_api_version,
                    timeout=self._settings.gemini_timeout_seconds,
                ),
                timeout=self._settings.gemini_timeout_seconds,
            )
        except Exception as exc:
            raise_mapped_gemini_error(exc, TTSServiceError, "text-to-speech synthesis")

        output_audio = getattr(response, "output_audio", None)
        encoded_data = getattr(output_audio, "data", None) if output_audio is not None else None
        if not encoded_data:
            raise TTSServiceError("TTS model response did not contain audio data.")

        try:
            raw_bytes = (
                encoded_data
                if isinstance(encoded_data, bytes)
                else base64.b64decode(encoded_data, validate=True)
            )
        except (binascii.Error, ValueError) as exc:
            raise TTSServiceError("TTS model returned malformed base64 audio data.") from exc

        if not raw_bytes:
            raise TTSServiceError("TTS model returned empty audio bytes.")

        raw_mime = getattr(output_audio, "mime_type", None)
        return ensure_wav_or_preserve_mime(raw_bytes, raw_mime)
