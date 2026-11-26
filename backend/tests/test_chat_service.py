import pytest
from google.genai import errors as genai_errors

from app.core.config import Settings
from app.core.exceptions import (
    ChatServiceError,
    GeminiServiceUnavailableError,
    InvalidConversationIdError,
)
from app.repositories.conversation_repository import InMemoryConversationRepository
from app.schemas.chat import ChatMessage
from app.services.chat_service import ChatService
from app.services.conversation_service import ConversationService
from tests.conftest import FakeGeminiClient, FakeInteractionResponse


@pytest.mark.anyio
async def test_chat_service_generates_reply_with_history(test_settings: Settings) -> None:
    async def handler(**kwargs):
        assert len(kwargs["input"]) == 3
        assert kwargs["input"][0]["type"] == "user_input"
        assert kwargs["input"][1]["type"] == "model_output"
        assert kwargs["input"][2]["type"] == "user_input"
        return FakeInteractionResponse(output_text="நான் நலமாக இருக்கிறேன்!")

    client = FakeGeminiClient(handler)
    service = ChatService(client, test_settings)  # type: ignore[arg-type]
    history = [
        ChatMessage(role="user", content="வணக்கம்"),
        ChatMessage(role="assistant", content="வணக்கம்! எப்படி உதவலாம்?"),
    ]

    reply = await service.generate_reply("நீங்கள் எப்படி இருக்கிறீர்கள்?", history=history)

    assert reply == "நான் நலமாக இருக்கிறேன்!"


@pytest.mark.anyio
async def test_chat_service_empty_response_raises(test_settings: Settings) -> None:
    async def handler(**_kwargs):
        return FakeInteractionResponse(output_text="   ")

    client = FakeGeminiClient(handler)
    service = ChatService(client, test_settings)  # type: ignore[arg-type]

    with pytest.raises(ChatServiceError):
        await service.generate_reply("Hello")


@pytest.mark.anyio
async def test_chat_service_maps_server_error(test_settings: Settings) -> None:
    async def handler(**_kwargs):
        raise genai_errors.ServerError(503, {"error": {"message": "Overloaded"}})

    client = FakeGeminiClient(handler)
    service = ChatService(client, test_settings)  # type: ignore[arg-type]

    with pytest.raises(GeminiServiceUnavailableError):
        await service.generate_reply("Hello")


@pytest.mark.anyio
async def test_conversation_service_history_isolation_and_limit() -> None:
    repo = InMemoryConversationRepository(max_turns=2)
    service = ConversationService(repo)

    conv1 = service.resolve_conversation_id(None)
    conv2 = service.resolve_conversation_id(None)
    assert conv1 != conv2

    await service.save_turn(conv1, "u1", "a1")
    await service.save_turn(conv1, "u2", "a2")
    await service.save_turn(conv1, "u3", "a3")
    await service.save_turn(conv2, "other-u1", "other-a1")

    h1 = await service.get_history(conv1)
    h2 = await service.get_history(conv2)

    assert [m.content for m in h1] == ["u2", "a2", "u3", "a3"]
    assert [m.content for m in h2] == ["other-u1", "other-a1"]


def test_conversation_service_rejects_invalid_uuid() -> None:
    service = ConversationService(InMemoryConversationRepository())
    with pytest.raises(InvalidConversationIdError):
        service.resolve_conversation_id("not-a-uuid")
