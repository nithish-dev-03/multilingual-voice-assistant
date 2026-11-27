from pathlib import Path

from fastapi import UploadFile

from app.core.config import Settings
from app.core.exceptions import (
    AudioDurationExceededError,
    AudioTooLargeError,
    EmptyAudioError,
    InvalidAudioError,
    UnsupportedAudioFormatError,
)
from app.schemas.voice import ValidatedAudio
from app.utils.audio_utils import (
    FORMAT_ACCEPTED_MIMES,
    GENERIC_BINARY_MIMES,
    SUPPORTED_AUDIO_EXTENSIONS,
    detect_audio_format_from_bytes,
    inspect_audio_duration,
    normalize_mime_type,
)

_UPLOAD_CHUNK_SIZE = 256 * 1024


class AudioValidationService:
    """Validates uploaded audio size, format signatures, MIME types, and duration."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def validate_upload(self, upload_file: UploadFile) -> ValidatedAudio:
        """Stream-read and validate a FastAPI ``UploadFile`` safely."""
        filename = Path(upload_file.filename or "audio").name
        content_type = upload_file.content_type
        max_bytes = self._settings.max_audio_size_bytes

        chunks: list[bytes] = []
        total_bytes = 0
        try:
            while True:
                chunk = await upload_file.read(_UPLOAD_CHUNK_SIZE)
                if not chunk:
                    break
                total_bytes += len(chunk)
                if total_bytes > max_bytes:
                    raise AudioTooLargeError(
                        f"Audio file exceeds maximum allowed size of "
                        f"{self._settings.max_audio_size_mb} MB."
                    )
                chunks.append(chunk)
        finally:
            await upload_file.close()

        data = b"".join(chunks)
        return await self.validate_bytes(
            data,
            filename=filename,
            content_type=content_type,
        )

    async def validate_bytes(
        self,
        data: bytes,
        *,
        filename: str,
        content_type: str | None = None,
    ) -> ValidatedAudio:
        """Validate raw audio bytes against size, format, MIME, and duration rules."""
        safe_filename = Path(filename or "audio").name
        if not data:
            raise EmptyAudioError("Uploaded audio file is empty.")

        max_bytes = self._settings.max_audio_size_bytes
        if len(data) > max_bytes:
            raise AudioTooLargeError(
                f"Audio file exceeds maximum allowed size of "
                f"{self._settings.max_audio_size_mb} MB."
            )

        extension = Path(safe_filename).suffix.lower()
        if extension and extension not in SUPPORTED_AUDIO_EXTENSIONS:
            raise UnsupportedAudioFormatError(
                f"Unsupported audio file extension '{extension}'. "
                f"Supported extensions: {', '.join(sorted(SUPPORTED_AUDIO_EXTENSIONS))}."
            )

        detected = detect_audio_format_from_bytes(data, extension=extension)
        if detected is None:
            raise UnsupportedAudioFormatError(
                "Unrecognized or unsupported audio file content. "
                "Provide valid WAV, MP3, M4A, AAC, OGG, FLAC, or WebM audio."
            )

        format_key, canonical_mime = detected

        # Verify declared Content-Type does not contradict the inspected container bytes.
        declared_mime = normalize_mime_type(content_type)
        if declared_mime and declared_mime not in GENERIC_BINARY_MIMES:
            accepted_mimes = FORMAT_ACCEPTED_MIMES[format_key]
            if declared_mime not in accepted_mimes:
                raise UnsupportedAudioFormatError(
                    f"Declared MIME type '{declared_mime}' does not match detected "
                    f"audio format '{format_key}'."
                )

        # Verify file extension, if present, matches the detected format.
        if extension:
            ext_format = SUPPORTED_AUDIO_EXTENSIONS[extension]
            compatible = {ext_format}
            if ext_format in {"ogg", "opus"}:
                compatible = {"ogg", "opus"}
            if format_key not in compatible:
                raise InvalidAudioError(
                    f"File extension '{extension}' does not match detected "
                    f"audio content ({format_key})."
                )

        duration = await inspect_audio_duration(
            data,
            format_key,
            extension or f".{format_key}",
            backend=self._settings.audio_duration_backend,
            ffprobe_path=self._settings.ffprobe_path,
        )
        if duration is None and self._settings.require_audio_duration_check:
            raise InvalidAudioError(
                "Unable to determine audio duration. Install ffprobe or upload WAV/FLAC/OGG audio."
            )

        if duration is not None and duration <= 0:
            raise EmptyAudioError("Audio recording contains zero seconds of audio.")

        if duration is not None and duration > self._settings.max_audio_duration_seconds:
            raise AudioDurationExceededError(
                f"Audio duration ({duration:.1f}s) exceeds maximum allowed duration of "
                f"{self._settings.max_audio_duration_seconds}s."
            )

        return ValidatedAudio(
            filename=safe_filename,
            mime_type=canonical_mime,
            size_bytes=len(data),
            duration_seconds=round(duration, 3) if duration is not None else None,
            data=data,
        )
