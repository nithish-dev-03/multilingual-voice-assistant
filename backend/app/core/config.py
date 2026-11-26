from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_DIR = Path(__file__).resolve().parents[2]
_ROOT_DIR = _BACKEND_DIR.parent


class Settings(BaseSettings):
    gemini_api_key: SecretStr

    app_name: str = "Multilingual AI Voice Assistant"
    app_version: str = "0.1.0"
    log_level: str = "INFO"
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://127.0.0.1:5173"]
    )

    gemini_api_version: str = "v1beta"
    gemini_timeout_seconds: float = Field(default=60.0, gt=0)
    gemini_max_retries: int = Field(default=1, ge=0, le=5)

    transcription_model: str = "gemini-3.5-transcribe"
    chat_model: str = "gemini-3.5-flash-lite"
    tts_model: str = "gemini-3.8-flash-lite-tts"

    tts_voice: str = "Kore"

    chat_temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    chat_max_output_tokens: int = Field(default=1024, gt=0)
    max_conversation_history_turns: int = Field(default=10, gt=0)

    max_audio_size_mb: int = Field(default=20, gt=0)
    max_audio_duration_seconds: int = Field(default=300, gt=0)
    inline_audio_limit_mb: int = Field(default=15, gt=0)
    audio_duration_backend: Literal["auto", "python", "ffprobe", "disabled"] = "auto"
    ffprobe_path: str = "ffprobe"
    require_audio_duration_check: bool = False

    model_config = SettingsConfigDict(
        env_file=(str(_ROOT_DIR / ".env"), str(_BACKEND_DIR / ".env"), ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def max_audio_size_bytes(self) -> int:
        return self.max_audio_size_mb * 1024 * 1024

    @property
    def inline_audio_limit_bytes(self) -> int:
        return self.inline_audio_limit_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
