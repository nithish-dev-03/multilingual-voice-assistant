import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.config import get_settings
from app.core.gemini import close_gemini_client, create_gemini_client
from app.repositories.conversation_repository import InMemoryConversationRepository
from app.services.audio_service import AudioValidationService
from app.services.chat_service import ChatService
from app.services.conversation_service import ConversationService
from app.services.transcription_service import TranscriptionService
from app.services.tts_service import TTSService

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Initialize and clean up shared application resources."""
    settings = get_settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    client = create_gemini_client(settings)
    repository = InMemoryConversationRepository(
        max_turns=settings.max_conversation_history_turns
    )

    app.state.settings = settings
    app.state.gemini_client = client
    app.state.conversation_repository = repository
    app.state.audio_service = AudioValidationService(settings)
    app.state.transcription_service = TranscriptionService(client, settings)
    app.state.chat_service = ChatService(client, settings)
    app.state.conversation_service = ConversationService(repository)
    app.state.tts_service = TTSService(client, settings)

    logger.info(
        "Application started (transcription=%s, chat=%s, tts=%s)",
        settings.transcription_model,
        settings.chat_model,
        settings.tts_model,
    )
    try:
        yield
    finally:
        await close_gemini_client(client)
        logger.info("Application shut down and Gemini client closed")
