import pytest

from app.core.config import get_settings
from app.core.gemini import close_gemini_client, create_gemini_client
from app.schemas.voice import ValidatedAudio
from app.services.chat_service import ChatService
from app.services.transcription_service import TranscriptionService
from app.services.tts_service import TTSService


@pytest.mark.integration
@pytest.mark.anyio
async def test_live_tts_transcribe_chat_roundtrip() -> None:
    """Opt-in integration test exercising live Gemini TTS, Transcribe, and Chat."""
    settings = get_settings()
    client = create_gemini_client(settings)
    try:
        tts = TTSService(client, settings)
        transcriber = TranscriptionService(client, settings)
        chat = ChatService(client, settings)

        wav_bytes, mime_type = await tts.synthesize("Hello! How can I help you today?")
        assert mime_type == "audio/wav"
        assert wav_bytes[:4] == b"RIFF"

        audio = ValidatedAudio(
            filename="live_roundtrip.wav",
            mime_type=mime_type,
            size_bytes=len(wav_bytes),
            duration_seconds=None,
            data=wav_bytes,
        )
        tr = await transcriber.transcribe(audio)
        assert tr.text
        assert tr.language_code == "en"

        reply = await chat.generate_reply(tr.text)
        assert reply
    finally:
        await close_gemini_client(client)
