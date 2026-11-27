from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, UploadFile

from app.api.dependencies import (
    get_audio_service,
    get_chat_service,
    get_conversation_service,
    get_transcription_service,
    get_tts_service,
)
from app.schemas.common import ErrorResponse
from app.schemas.voice import (
    AssistantOutput,
    VoiceConversationResponse,
    VoiceInputInfo,
)
from app.services.audio_service import AudioValidationService
from app.services.chat_service import ChatService
from app.services.conversation_service import ConversationService
from app.services.transcription_service import TranscriptionService
from app.services.tts_service import TTSService
from app.utils.response_utils import encode_audio_output

router = APIRouter(tags=["voice"])

_VOICE_ERROR_RESPONSES = {
    400: {"model": ErrorResponse, "description": "Empty audio or invalid conversation_id UUID"},
    413: {"model": ErrorResponse, "description": "Uploaded audio exceeds MAX_AUDIO_SIZE_MB"},
    415: {"model": ErrorResponse, "description": "Unsupported audio format or MIME type"},
    422: {"model": ErrorResponse, "description": "Validation error or audio duration exceeded"},
    429: {"model": ErrorResponse, "description": "Gemini API rate limit exceeded"},
    502: {"model": ErrorResponse, "description": "Upstream Gemini processing error"},
    503: {"model": ErrorResponse, "description": "Gemini service temporarily unavailable"},
    504: {"model": ErrorResponse, "description": "Gemini request timed out"},
}


@router.post(
    "/voice",
    response_model=VoiceConversationResponse,
    responses=_VOICE_ERROR_RESPONSES,
)
async def voice_conversation(
    audio: Annotated[UploadFile, File(description="Audio file containing user speech")],
    audio_service: Annotated[AudioValidationService, Depends(get_audio_service)],
    transcription_service: Annotated[TranscriptionService, Depends(get_transcription_service)],
    chat_service: Annotated[ChatService, Depends(get_chat_service)],
    conversation_service: Annotated[ConversationService, Depends(get_conversation_service)],
    tts_service: Annotated[TTSService, Depends(get_tts_service)],
    conversation_id: Annotated[
        str | None,
        Form(
            description=(
                "Optional UUID of an existing conversation. "
                "Leave blank/omitted to start a new conversation."
            ),
        ),
    ] = None,
    generate_audio: Annotated[
        bool,
        Form(description="Whether to synthesize TTS audio for the assistant reply."),
    ] = True,
) -> VoiceConversationResponse:
    """Process an uploaded audio turn: validate, transcribe, chat, and synthesize speech."""
    normalized_id = conversation_id.strip() if conversation_id else None
    if normalized_id == "":
        normalized_id = None

    try:
        resolved_id = conversation_service.resolve_conversation_id(normalized_id)
        validated_audio = await audio_service.validate_upload(audio)
    finally:
        await audio.close()

    transcription = await transcription_service.transcribe(validated_audio)
    history = await conversation_service.get_history(resolved_id)

    reply_text = await chat_service.generate_reply(
        transcription.text,
        history=history,
        detected_language=transcription.language_name or transcription.language_code,
    )
    await conversation_service.save_turn(resolved_id, transcription.text, reply_text)

    audio_output = None
    if generate_audio:
        audio_bytes, audio_mime = await tts_service.synthesize(reply_text)
        audio_output = encode_audio_output(audio_bytes, audio_mime)

    return VoiceConversationResponse(
        conversation_id=resolved_id,
        input=VoiceInputInfo(
            transcription=transcription.text,
            language_code=transcription.language_code,
            language_name=transcription.language_name,
        ),
        assistant=AssistantOutput(text=reply_text),
        audio=audio_output,
    )
