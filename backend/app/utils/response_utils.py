import base64

from app.schemas.voice import AudioOutput


def encode_audio_output(audio_bytes: bytes, mime_type: str) -> AudioOutput:
    """Encode raw audio bytes into a base64 ``AudioOutput`` payload."""
    return AudioOutput(
        mime_type=mime_type,
        data=base64.b64encode(audio_bytes).decode("ascii"),
    )
