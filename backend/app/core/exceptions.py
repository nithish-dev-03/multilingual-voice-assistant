from typing import Any


class AppError(Exception):
    """Base application exception mapped to structured HTTP error responses."""

    status_code: int = 500
    error_code: str = "internal_error"

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        error_code: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        if error_code is not None:
            self.error_code = error_code
        self.details = details


class AudioValidationError(AppError):
    """Base class for uploaded audio validation errors."""

    status_code = 400
    error_code = "invalid_audio"


class EmptyAudioError(AudioValidationError):
    status_code = 400
    error_code = "empty_audio"


class InvalidAudioError(AudioValidationError):
    status_code = 400
    error_code = "invalid_audio"


class UnsupportedAudioFormatError(AudioValidationError):
    status_code = 415
    error_code = "unsupported_audio_format"


class AudioTooLargeError(AudioValidationError):
    status_code = 413
    error_code = "audio_too_large"


class AudioDurationExceededError(AudioValidationError):
    status_code = 422
    error_code = "audio_duration_exceeded"


class InvalidConversationIdError(AppError):
    status_code = 400
    error_code = "invalid_conversation_id"


class ExternalServiceError(AppError):
    """Base class for failures originating from external AI APIs."""

    status_code = 502
    error_code = "external_service_error"


class TranscriptionError(ExternalServiceError):
    status_code = 502
    error_code = "transcription_failed"


class ChatServiceError(ExternalServiceError):
    status_code = 502
    error_code = "chat_generation_failed"


class TTSServiceError(ExternalServiceError):
    status_code = 502
    error_code = "tts_generation_failed"


class GeminiAuthenticationError(ExternalServiceError):
    status_code = 502
    error_code = "gemini_authentication_error"


class GeminiRateLimitError(ExternalServiceError):
    status_code = 429
    error_code = "gemini_rate_limit"


class GeminiServiceUnavailableError(ExternalServiceError):
    status_code = 503
    error_code = "gemini_service_unavailable"


class GeminiTimeoutError(ExternalServiceError):
    status_code = 504
    error_code = "gemini_timeout"
