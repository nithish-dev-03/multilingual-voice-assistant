import base64

import pytest
from google.genai import errors as genai_errors

from app.core.config import Settings
from app.core.exceptions import GeminiRateLimitError, TTSServiceError
from app.services.tts_service import TTSService
from tests.conftest import (
    FakeAudioOutput,
    FakeGeminiClient,
    FakeInteractionResponse,
    build_wav_bytes,
)


@pytest.mark.anyio
async def test_tts_returns_wav_bytes_and_mime_type(test_settings: Settings) -> None:
    wav_bytes = build_wav_bytes(duration_seconds=0.3)

    async def handler(**kwargs):
        assert kwargs["model"] == test_settings.tts_model
        assert kwargs["generation_config"]["speech_config"] == [{"voice": test_settings.tts_voice}]
        return FakeInteractionResponse(
            output_audio=FakeAudioOutput(
                data=base64.b64encode(wav_bytes).decode("ascii"),
                mime_type="audio/wav",
            )
        )

    client = FakeGeminiClient(handler)
    service = TTSService(client, test_settings)  # type: ignore[arg-type]

    audio_bytes, mime_type = await service.synthesize("Hello!")

    assert audio_bytes == wav_bytes
    assert mime_type == "audio/wav"


@pytest.mark.anyio
async def test_tts_wraps_raw_pcm_as_valid_wav(test_settings: Settings) -> None:
    raw_pcm = b"\x00\x01" * 2400  # 2400 16-bit samples

    async def handler(**_kwargs):
        return FakeInteractionResponse(
            output_audio=FakeAudioOutput(
                data=base64.b64encode(raw_pcm).decode("ascii"),
                mime_type="audio/l16;rate=24000;channels=1",
            )
        )

    client = FakeGeminiClient(handler)
    service = TTSService(client, test_settings)  # type: ignore[arg-type]

    audio_bytes, mime_type = await service.synthesize("Hello!")

    assert mime_type == "audio/wav"
    assert audio_bytes[:4] == b"RIFF"
    assert audio_bytes[8:12] == b"WAVE"
    assert len(audio_bytes) > len(raw_pcm)


@pytest.mark.anyio
async def test_tts_missing_audio_raises(test_settings: Settings) -> None:
    async def handler(**_kwargs):
        return FakeInteractionResponse(output_audio=None)

    client = FakeGeminiClient(handler)
    service = TTSService(client, test_settings)  # type: ignore[arg-type]

    with pytest.raises(TTSServiceError):
        await service.synthesize("Hello!")


@pytest.mark.anyio
async def test_tts_malformed_base64_raises(test_settings: Settings) -> None:
    async def handler(**_kwargs):
        return FakeInteractionResponse(
            output_audio=FakeAudioOutput(data="!!!not-base64!!!", mime_type="audio/wav")
        )

    client = FakeGeminiClient(handler)
    service = TTSService(client, test_settings)  # type: ignore[arg-type]

    with pytest.raises(TTSServiceError):
        await service.synthesize("Hello!")


@pytest.mark.anyio
async def test_tts_api_error_is_mapped(test_settings: Settings) -> None:
    async def handler(**_kwargs):
        raise genai_errors.ClientError(429, {"error": {"message": "Rate limit"}})

    client = FakeGeminiClient(handler)
    service = TTSService(client, test_settings)  # type: ignore[arg-type]

    with pytest.raises(GeminiRateLimitError):
        await service.synthesize("Hello!")
