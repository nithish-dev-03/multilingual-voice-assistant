from fastapi import Request

from app.core.config import Settings
from app.services.audio_service import AudioValidationService
from app.services.chat_service import ChatService
from app.services.conversation_service import ConversationService
from app.services.transcription_service import TranscriptionService
from app.services.tts_service import TTSService


def get_app_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_audio_service(request: Request) -> AudioValidationService:
    return request.app.state.audio_service


def get_transcription_service(request: Request) -> TranscriptionService:
    return request.app.state.transcription_service


def get_chat_service(request: Request) -> ChatService:
    return request.app.state.chat_service


def get_conversation_service(request: Request) -> ConversationService:
    return request.app.state.conversation_service


def get_tts_service(request: Request) -> TTSService:
    return request.app.state.tts_service
