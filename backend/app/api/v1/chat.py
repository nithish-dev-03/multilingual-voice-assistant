import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies import (
    get_chat_service,
    get_conversation_service,
    get_tts_service,
)
from app.core.exceptions import AppError
from app.schemas.chat import ChatInputInfo, ChatRequest, ChatResponse
from app.schemas.common import ErrorResponse
from app.schemas.voice import AssistantOutput
from app.services.chat_service import ChatService
from app.services.conversation_service import ConversationService
from app.services.tts_service import TTSService
from app.utils.response_utils import encode_audio_output

router = APIRouter(tags=["chat"])

_CHAT_ERROR_RESPONSES = {
    400: {"model": ErrorResponse, "description": "Invalid conversation_id UUID"},
    422: {"model": ErrorResponse, "description": "Request validation failed or blank message"},
    429: {"model": ErrorResponse, "description": "Gemini API rate limit exceeded"},
    502: {"model": ErrorResponse, "description": "Upstream Gemini processing error"},
    503: {"model": ErrorResponse, "description": "Gemini service temporarily unavailable"},
    504: {"model": ErrorResponse, "description": "Gemini request timed out"},
}


@router.post(
    "/chat",
    response_model=ChatResponse,
    responses=_CHAT_ERROR_RESPONSES,
)
async def text_conversation(
    payload: ChatRequest,
    chat_service: Annotated[ChatService, Depends(get_chat_service)],
    conversation_service: Annotated[ConversationService, Depends(get_conversation_service)],
    tts_service: Annotated[TTSService, Depends(get_tts_service)],
) -> ChatResponse:
    """Process a direct text turn with optional TTS audio output."""
    cleaned_message = payload.message.strip()
    if not cleaned_message:
        raise AppError(
            "Message must not be empty or whitespace only.",
            status_code=422,
            error_code="empty_message",
        )

    resolved_id = conversation_service.resolve_conversation_id(payload.conversation_id)
    history = await conversation_service.get_history(resolved_id)

    reply_text, (lang_code, lang_name) = await asyncio.gather(
        chat_service.generate_reply(cleaned_message, history=history),
        chat_service.detect_text_language(cleaned_message),
    )
    await conversation_service.save_turn(resolved_id, cleaned_message, reply_text)

    audio_output = None
    if payload.generate_audio:
        audio_bytes, audio_mime = await tts_service.synthesize(reply_text)
        audio_output = encode_audio_output(audio_bytes, audio_mime)

    return ChatResponse(
        conversation_id=resolved_id,
        input=ChatInputInfo(
            message=cleaned_message,
            language_code=lang_code,
            language_name=lang_name,
        ),
        assistant=AssistantOutput(text=reply_text),
        audio=audio_output,
    )
