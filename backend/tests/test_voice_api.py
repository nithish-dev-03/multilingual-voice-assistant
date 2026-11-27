import base64

import pytest
from google.genai import errors as genai_errors

from tests.conftest import FakeAudioOutput, FakeInteractionResponse, build_wav_bytes


@pytest.mark.anyio
async def test_health_endpoint_hides_secrets(make_test_client, test_settings) -> None:
    client, _fake, _app = make_test_client(lambda **_kwargs: None)
    async with client:
        resp = await client.get("/health")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["gemini_client_ready"] is True
    assert test_settings.gemini_api_key.get_secret_value() not in resp.text


@pytest.mark.anyio
async def test_cors_allows_frontend_origin(make_test_client) -> None:
    client, _fake, _app = make_test_client(lambda **_kwargs: None)
    async with client:
        resp = await client.get("/health", headers={"Origin": "http://localhost:5173"})

    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:5173"


@pytest.mark.anyio
async def test_voice_endpoint_success_and_follow_up_history(
    make_test_client, test_settings
) -> None:
    tts_wav = build_wav_bytes(duration_seconds=0.4)

    async def handler(**kwargs):
        model = kwargs["model"]
        if model == test_settings.transcription_model:
            return FakeInteractionResponse(output_text="இன்று வானிலை எப்படி இருக்கிறது?")
        if model == test_settings.tts_model:
            return FakeInteractionResponse(
                output_audio=FakeAudioOutput(
                    data=base64.b64encode(tts_wav).decode("ascii"),
                    mime_type="audio/wav",
                )
            )
        if kwargs.get("response_format"):
            return FakeInteractionResponse(
                output_text='{"language_code": "ta", "language_name": "Tamil"}'
            )
        return FakeInteractionResponse(output_text="இன்று வானிலை மிகவும் இனிமையாக உள்ளது.")

    client, fake, _app = make_test_client(handler)
    input_wav = build_wav_bytes(duration_seconds=0.5)

    async with client:
        resp1 = await client.post(
            "/api/v1/voice",
            files={"audio": ("query.wav", input_wav, "audio/wav")},
        )
        assert resp1.status_code == 200
        body1 = resp1.json()
        conv_id = body1["conversation_id"]
        assert body1["input"] == {
            "type": "audio",
            "transcription": "இன்று வானிலை எப்படி இருக்கிறது?",
            "language_code": "ta",
            "language_name": "Tamil",
        }
        assert body1["assistant"]["text"] == "இன்று வானிலை மிகவும் இனிமையாக உள்ளது."
        assert body1["audio"]["mime_type"] == "audio/wav"
        assert base64.b64decode(body1["audio"]["data"]) == tts_wav

        # Second turn using same conversation_id should include prior turn in chat input
        resp2 = await client.post(
            "/api/v1/voice",
            data={"conversation_id": conv_id},
            files={"audio": ("query2.wav", input_wav, "audio/wav")},
        )
        assert resp2.status_code == 200
        assert resp2.json()["conversation_id"] == conv_id

    chat_calls = [
        c
        for c in fake.aio.interactions.calls
        if c["model"] == test_settings.chat_model and not c.get("response_format")
    ]
    assert len(chat_calls) == 2
    assert len(chat_calls[1]["input"]) == 3


@pytest.mark.anyio
async def test_voice_endpoint_rejects_invalid_audio(make_test_client) -> None:
    client, _fake, _app = make_test_client(lambda **_kwargs: None)
    async with client:
        empty_resp = await client.post(
            "/api/v1/voice",
            files={"audio": ("empty.wav", b"", "audio/wav")},
        )
        bad_format_resp = await client.post(
            "/api/v1/voice",
            files={"audio": ("evil.txt", b"hello world", "text/plain")},
        )
        bad_uuid_resp = await client.post(
            "/api/v1/voice",
            data={"conversation_id": "bad-id"},
            files={"audio": ("ok.wav", build_wav_bytes(), "audio/wav")},
        )

    assert empty_resp.status_code == 400
    assert empty_resp.json()["error"]["code"] == "empty_audio"
    assert bad_format_resp.status_code == 415
    assert bad_format_resp.json()["error"]["code"] == "unsupported_audio_format"
    assert bad_uuid_resp.status_code == 400
    assert bad_uuid_resp.json()["error"]["code"] == "invalid_conversation_id"


@pytest.mark.anyio
async def test_voice_endpoint_empty_conversation_id_starts_new_conversation(
    make_test_client, test_settings
) -> None:
    tts_wav = build_wav_bytes(duration_seconds=0.2)

    async def handler(**kwargs):
        model = kwargs["model"]
        if model == test_settings.transcription_model:
            return FakeInteractionResponse(output_text="Hello")
        if model == test_settings.tts_model:
            return FakeInteractionResponse(
                output_audio=FakeAudioOutput(
                    data=base64.b64encode(tts_wav).decode("ascii"),
                    mime_type="audio/wav",
                )
            )
        if kwargs.get("response_format"):
            return FakeInteractionResponse(
                output_text='{"language_code": "en", "language_name": "English"}'
            )
        return FakeInteractionResponse(output_text="Hi there!")

    client, _fake, _app = make_test_client(handler)
    async with client:
        resp = await client.post(
            "/api/v1/voice",
            data={"conversation_id": ""},
            files={"audio": ("ok.wav", build_wav_bytes(), "audio/wav")},
        )

    assert resp.status_code == 200
    assert resp.json()["conversation_id"]


@pytest.mark.anyio
async def test_voice_endpoint_with_tts_disabled(make_test_client, test_settings) -> None:
    async def handler(**kwargs):
        if kwargs["model"] == test_settings.transcription_model:
            return FakeInteractionResponse(output_text="Testing voice without TTS")
        if kwargs.get("response_format"):
            return FakeInteractionResponse(
                output_text='{"language_code": "en", "language_name": "English"}'
            )
        return FakeInteractionResponse(output_text="Received your voice message.")

    client, fake, _app = make_test_client(handler)
    async with client:
        resp = await client.post(
            "/api/v1/voice",
            data={"generate_audio": "false"},
            files={"audio": ("voice-recording.wav", build_wav_bytes(), "audio/wav")},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["input"]["transcription"] == "Testing voice without TTS"
    assert body["assistant"]["text"] == "Received your voice message."
    assert body["audio"] is None
    tts_calls = [c for c in fake.aio.interactions.calls if c["model"] == test_settings.tts_model]
    assert len(tts_calls) == 0


@pytest.mark.anyio
async def test_chat_endpoint_with_audio_and_without_audio(make_test_client, test_settings) -> None:
    tts_wav = build_wav_bytes(duration_seconds=0.3)

    async def handler(**kwargs):
        if kwargs["model"] == test_settings.tts_model:
            return FakeInteractionResponse(
                output_audio=FakeAudioOutput(
                    data=base64.b64encode(tts_wav).decode("ascii"),
                    mime_type="audio/wav",
                )
            )
        if kwargs.get("response_format"):
            return FakeInteractionResponse(
                output_text='{"language_code": "en", "language_name": "English"}'
            )
        return FakeInteractionResponse(output_text="I am doing great, thanks!")

    client, fake, _app = make_test_client(handler)
    async with client:
        resp_with_tts = await client.post(
            "/api/v1/chat",
            json={"message": "Hello, how are you?", "generate_audio": True},
        )
        assert resp_with_tts.status_code == 200
        body1 = resp_with_tts.json()
        assert body1["assistant"]["text"] == "I am doing great, thanks!"
        assert body1["audio"]["mime_type"] == "audio/wav"

        resp_no_tts = await client.post(
            "/api/v1/chat",
            json={
                "message": "Tell me more",
                "conversation_id": body1["conversation_id"],
                "generate_audio": False,
            },
        )
        assert resp_no_tts.status_code == 200
        body2 = resp_no_tts.json()
        assert body2["audio"] is None
        assert body2["conversation_id"] == body1["conversation_id"]

    tts_calls = [c for c in fake.aio.interactions.calls if c["model"] == test_settings.tts_model]
    assert len(tts_calls) == 1


@pytest.mark.anyio
async def test_api_handles_gemini_service_failure(make_test_client) -> None:
    async def handler(**_kwargs):
        raise genai_errors.ServerError(503, {"error": {"message": "Service unavailable"}})

    client, _fake, _app = make_test_client(handler)
    async with client:
        resp = await client.post(
            "/api/v1/chat",
            json={"message": "Hello", "generate_audio": False},
        )

    assert resp.status_code == 503
    assert resp.json()["error"]["code"] == "gemini_service_unavailable"
