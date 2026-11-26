from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.voice import AssistantOutput, AudioOutput


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=16000)
    conversation_id: str | None = Field(
        default=None,
        description="Optional UUID of an existing conversation. Omit or set null for a new one.",
    )
    generate_audio: bool = True


class ChatInputInfo(BaseModel):
    type: Literal["text"] = "text"
    message: str
    language_code: str | None = None
    language_name: str | None = None


class ChatResponse(BaseModel):
    conversation_id: str
    input: ChatInputInfo
    assistant: AssistantOutput
    audio: AudioOutput | None = None
