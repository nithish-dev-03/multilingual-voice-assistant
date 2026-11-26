from typing import Literal

from pydantic import BaseModel, Field


class ValidatedAudio(BaseModel):
    """Validated audio payload ready for downstream AI processing."""

    filename: str
    mime_type: str
    size_bytes: int = Field(gt=0)
    duration_seconds: float | None = Field(default=None, ge=0.0)
    data: bytes = Field(repr=False)


class TranscriptionResult(BaseModel):
    """Structured output returned by the transcription service."""

    text: str
    language_code: str | None = None
    language_name: str | None = None


class AudioOutput(BaseModel):
    """Base64-encoded synthesized speech response."""

    mime_type: str
    data: str


class VoiceInputInfo(BaseModel):
    type: Literal["audio"] = "audio"
    transcription: str
    language_code: str | None = None
    language_name: str | None = None


class AssistantOutput(BaseModel):
    text: str


class VoiceConversationResponse(BaseModel):
    conversation_id: str
    input: VoiceInputInfo
    assistant: AssistantOutput
    audio: AudioOutput
