import io
import struct
import wave
from dataclasses import dataclass
from typing import Any

import httpx
import pytest
from pydantic import SecretStr

from app.api.dependencies import (
    get_audio_service,
    get_chat_service,
    get_conversation_service,
    get_transcription_service,
    get_tts_service,
)
from app.core.config import Settings
from app.main import create_app
from app.repositories.conversation_repository import InMemoryConversationRepository
from app.services.audio_service import AudioValidationService
from app.services.chat_service import ChatService
from app.services.conversation_service import ConversationService
from app.services.transcription_service import TranscriptionService
from app.services.tts_service import TTSService


def build_wav_bytes(
    *,
    duration_seconds: float = 0.5,
    sample_rate: int = 16000,
    channels: int = 1,
    sample_width: int = 2,
) -> bytes:
    """Create a valid silent RIFF/WAV byte payload of exact duration."""
    num_frames = int(duration_seconds * sample_rate)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(sample_rate)
        wf.writeframes(b"\x00" * (num_frames * channels * sample_width))
    return buf.getvalue()


def build_flac_header_bytes(*, sample_rate: int = 44100, total_samples: int = 44100) -> bytes:
    """Create minimal valid fLaC + STREAMINFO bytes for format and duration tests."""
    # STREAMINFO is 34 bytes; bytes 10..17 pack sample_rate, channels, bps, and total_samples.
    packed = (
        (sample_rate << 44)
        | (0 << 41)  # 1 channel - 1
        | (15 << 36)  # 16 bps - 1
        | total_samples
    )
    streaminfo = bytearray(34)
    streaminfo[10:18] = packed.to_bytes(8, "big")
    block_header = bytes([0x80, 0x00, 0x00, 0x22])  # last-metadata=1, type=0, length=34
    return b"fLaC" + block_header + bytes(streaminfo)


def build_ogg_opus_bytes(*, total_samples_48k: int = 48000) -> bytes:
    """Create minimal Ogg Opus header + final OggS page with granule position."""
    page1 = b"OggS" + bytes(23) + b"OpusHead\x01\x01\x00\x00\x80\xbb\x00\x00\x00\x00\x00"
    page2_header = bytearray(27)
    page2_header[0:4] = b"OggS"
    struct.pack_into("<q", page2_header, 6, total_samples_48k)
    return page1 + bytes(page2_header)


@dataclass
class FakeAudioOutput:
    data: str | None
    mime_type: str | None = "audio/wav"


@dataclass
class FakeInteractionResponse:
    output_text: str | None = None
    output_audio: FakeAudioOutput | None = None
    id: str = "interaction_test_1"


@dataclass
class FakeUploadedFile:
    name: str = "files/test-audio"
    uri: str = "https://generativelanguage.googleapis.com/v1beta/files/test-audio"
    mime_type: str = "audio/wav"


class FakeInteractionsResource:
    def __init__(self, handler: Any) -> None:
        self._handler = handler
        self.calls: list[dict[str, Any]] = []

    async def create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        return await self._handler(**kwargs)


class FakeFilesResource:
    def __init__(self) -> None:
        self.uploaded: list[dict[str, Any]] = []
        self.deleted: list[str] = []

    async def upload(self, **kwargs: Any) -> FakeUploadedFile:
        self.uploaded.append(kwargs)
        mime = (kwargs.get("config") or {}).get("mime_type", "audio/wav")
        return FakeUploadedFile(mime_type=mime)

    async def delete(self, *, name: str, **_kwargs: Any) -> None:
        self.deleted.append(name)


class FakeAsyncClient:
    def __init__(self, interaction_handler: Any) -> None:
        self.interactions = FakeInteractionsResource(interaction_handler)
        self.files = FakeFilesResource()
        self.closed = False

    async def aclose(self) -> None:
        self.closed = True


class FakeGeminiClient:
    def __init__(self, interaction_handler: Any) -> None:
        self.aio = FakeAsyncClient(interaction_handler)
        self.sync_closed = False

    def close(self) -> None:
        self.sync_closed = True


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def test_settings() -> Settings:
    return Settings(
        gemini_api_key=SecretStr("test-api-key-not-real"),
        max_audio_size_mb=1,
        max_audio_duration_seconds=10,
        inline_audio_limit_mb=1,
        audio_duration_backend="python",
        max_conversation_history_turns=3,
    )


@pytest.fixture
def make_test_client(test_settings: Settings):
    def _factory(interaction_handler: Any) -> tuple[httpx.AsyncClient, FakeGeminiClient, Any]:
        fake_client = FakeGeminiClient(interaction_handler)
        app = create_app()
        repo = InMemoryConversationRepository(
            max_turns=test_settings.max_conversation_history_turns
        )
        audio_service = AudioValidationService(test_settings)
        transcription_service = TranscriptionService(fake_client, test_settings)  # type: ignore[arg-type]
        chat_service = ChatService(fake_client, test_settings)  # type: ignore[arg-type]
        conversation_service = ConversationService(repo)
        tts_service = TTSService(fake_client, test_settings)  # type: ignore[arg-type]

        app.state.settings = test_settings
        app.state.gemini_client = fake_client
        app.state.conversation_repository = repo
        app.state.audio_service = audio_service
        app.state.transcription_service = transcription_service
        app.state.chat_service = chat_service
        app.state.conversation_service = conversation_service
        app.state.tts_service = tts_service

        app.dependency_overrides[get_audio_service] = lambda: audio_service
        app.dependency_overrides[get_transcription_service] = lambda: transcription_service
        app.dependency_overrides[get_chat_service] = lambda: chat_service
        app.dependency_overrides[get_conversation_service] = lambda: conversation_service
        app.dependency_overrides[get_tts_service] = lambda: tts_service

        client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        )
        return client, fake_client, app

    return _factory
