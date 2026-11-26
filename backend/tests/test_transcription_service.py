import httpx
import pytest
from google.genai import errors as genai_errors
from pydantic import SecretStr

from app.core.config import Settings
from app.core.exceptions import (
    GeminiAuthenticationError,
    GeminiRateLimitError,
    GeminiTimeoutError,
    TranscriptionError,
)
from app.schemas.voice import ValidatedAudio
from app.services.transcription_service import TranscriptionService
from tests.conftest import FakeGeminiClient, FakeInteractionResponse, build_wav_bytes


def _validated_wav(size_override_bytes: bytes | None = None) -> ValidatedAudio:
    data = (
        size_override_bytes
        if size_override_bytes is not None
        else build_wav_bytes(duration_seconds=0.5)
    )
    return ValidatedAudio(
        filename="sample.wav",
        mime_type="audio/wav",
        size_bytes=len(data),
        duration_seconds=0.5,
        data=data,
    )


@pytest.mark.anyio
async def test_transcription_success_with_language_metadata(test_settings: Settings) -> None:
    async def handler(**kwargs):
        if kwargs["model"] == test_settings.transcription_model:
            return FakeInteractionResponse(output_text="இன்று வானிலை எப்படி இருக்கிறது?")
        return FakeInteractionResponse(
            output_text='{"language_code": "ta", "language_name": "Tamil"}'
        )

    client = FakeGeminiClient(handler)
    service = TranscriptionService(client, test_settings)  # type: ignore[arg-type]

    result = await service.transcribe(_validated_wav())

    assert result.text == "இன்று வானிலை எப்படி இருக்கிறது?"
    assert result.language_code == "ta"
    assert result.language_name == "Tamil"
    assert len(client.aio.interactions.calls) == 2
    assert client.aio.interactions.calls[0]["input"][0]["type"] == "audio"


@pytest.mark.anyio
async def test_transcription_uses_files_api_for_large_audio_and_cleans_up() -> None:
    small_limit_settings = Settings(
        gemini_api_key=SecretStr("test-key"),
        inline_audio_limit_mb=1,
        max_audio_size_mb=5,
    )

    async def handler(**kwargs):
        if kwargs["model"] == small_limit_settings.transcription_model:
            return FakeInteractionResponse(output_text="Hello world")
        return FakeInteractionResponse(
            output_text='{"language_code": "en", "language_name": "English"}'
        )

    client = FakeGeminiClient(handler)
    service = TranscriptionService(client, small_limit_settings)  # type: ignore[arg-type]
    big_audio = _validated_wav(build_wav_bytes(duration_seconds=35.0, sample_rate=16000))
    assert big_audio.size_bytes > small_limit_settings.inline_audio_limit_bytes

    result = await service.transcribe(big_audio)

    assert result.text == "Hello world"
    assert len(client.aio.files.uploaded) == 1
    assert client.aio.files.deleted == ["files/test-audio"]
    assert "uri" in client.aio.interactions.calls[0]["input"][0]


@pytest.mark.anyio
async def test_transcription_empty_text_raises(test_settings: Settings) -> None:
    async def handler(**_kwargs):
        return FakeInteractionResponse(output_text="   ")

    client = FakeGeminiClient(handler)
    service = TranscriptionService(client, test_settings)  # type: ignore[arg-type]

    with pytest.raises(TranscriptionError):
        await service.transcribe(_validated_wav())


@pytest.mark.anyio
async def test_transcription_language_metadata_failure_falls_back_gracefully(
    test_settings: Settings,
) -> None:
    async def handler(**kwargs):
        if kwargs["model"] == test_settings.transcription_model:
            return FakeInteractionResponse(output_text="Bonjour tout le monde")
        return FakeInteractionResponse(output_text="not-valid-json")

    client = FakeGeminiClient(handler)
    service = TranscriptionService(client, test_settings)  # type: ignore[arg-type]

    result = await service.transcribe(_validated_wav())

    assert result.text == "Bonjour tout le monde"
    assert result.language_code is None
    assert result.language_name is None


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("exc", "expected_cls"),
    [
        (
            genai_errors.ClientError(401, {"error": {"message": "Invalid API key"}}),
            GeminiAuthenticationError,
        ),
        (
            genai_errors.ClientError(429, {"error": {"message": "Quota exceeded"}}),
            GeminiRateLimitError,
        ),
        (httpx.ReadTimeout("timed out"), GeminiTimeoutError),
    ],
)
async def test_transcription_api_error_mapping(
    test_settings: Settings,
    exc: Exception,
    expected_cls: type[Exception],
) -> None:
    async def handler(**_kwargs):
        raise exc

    client = FakeGeminiClient(handler)
    service = TranscriptionService(client, test_settings)  # type: ignore[arg-type]

    with pytest.raises(expected_cls):
        await service.transcribe(_validated_wav())
