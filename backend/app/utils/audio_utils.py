import asyncio
import io
import logging
import shutil
import struct
import tempfile
import wave
from pathlib import Path
from typing import Literal

logger = logging.getLogger(__name__)

# Canonical audio format definitions aligned with Gemini 3.5 Transcribe supported MIME types.
SUPPORTED_AUDIO_EXTENSIONS: dict[str, str] = {
    ".wav": "wav",
    ".mp3": "mp3",
    ".m4a": "m4a",
    ".aac": "aac",
    ".ogg": "ogg",
    ".oga": "ogg",
    ".opus": "opus",
    ".flac": "flac",
    ".webm": "webm",
}

FORMAT_CANONICAL_MIME: dict[str, str] = {
    "wav": "audio/wav",
    "mp3": "audio/mp3",
    "m4a": "audio/m4a",
    "aac": "audio/aac",
    "ogg": "audio/ogg",
    "opus": "audio/opus",
    "flac": "audio/flac",
    "webm": "audio/webm",
}

FORMAT_ACCEPTED_MIMES: dict[str, set[str]] = {
    "wav": {"audio/wav", "audio/x-wav", "audio/wave", "audio/vnd.wave"},
    "mp3": {"audio/mp3", "audio/mpeg", "audio/x-mp3", "audio/mpeg3"},
    "m4a": {"audio/m4a", "audio/x-m4a", "audio/mp4"},
    "aac": {"audio/aac", "audio/aacp", "audio/x-aac"},
    "ogg": {"audio/ogg", "application/ogg", "audio/vorbis", "audio/opus"},
    "opus": {"audio/opus", "audio/ogg", "application/ogg"},
    "flac": {"audio/flac", "audio/x-flac"},
    "webm": {"audio/webm", "video/webm"},
}

GENERIC_BINARY_MIMES: set[str] = {"", "application/octet-stream", "binary/octet-stream"}


def normalize_mime_type(mime_type: str | None) -> str:
    if not mime_type:
        return ""
    return mime_type.split(";", 1)[0].strip().lower()


def detect_audio_format_from_bytes(
    data: bytes,
    extension: str | None = None,
) -> tuple[str, str] | None:
    """Inspect magic bytes / container headers to identify the real audio format.

    Returns ``(format_key, canonical_mime_type)`` or ``None`` if unrecognized.
    """
    if len(data) < 4:
        return None

    ext = (extension or "").lower()

    # WAV: RIFF....WAVE
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WAVE":
        return ("wav", FORMAT_CANONICAL_MIME["wav"])

    # FLAC: fLaC
    if data[:4] == b"fLaC":
        return ("flac", FORMAT_CANONICAL_MIME["flac"])

    # OGG / Opus: OggS
    if data[:4] == b"OggS":
        if b"OpusHead" in data[:128] or ext == ".opus":
            return ("opus", FORMAT_CANONICAL_MIME["opus"])
        return ("ogg", FORMAT_CANONICAL_MIME["ogg"])

    # MP3 with ID3v2 tag
    if data[:3] == b"ID3":
        return ("mp3", FORMAT_CANONICAL_MIME["mp3"])

    # MPEG / ADTS frame sync (11 bits set: 0xFF 0xE0)
    if data[0] == 0xFF and (data[1] & 0xE0) == 0xE0:
        layer_bits = (data[1] >> 1) & 0x03
        # ADTS AAC uses layer == 0 (0b00); MPEG audio layer I/II/III uses 1, 2, or 3.
        if layer_bits == 0:
            return ("aac", FORMAT_CANONICAL_MIME["aac"])
        return ("mp3", FORMAT_CANONICAL_MIME["mp3"])

    # ISO Base Media File Format (M4A / MP4 audio): ....ftyp<brand>
    if len(data) >= 12 and data[4:8] == b"ftyp":
        brand = data[8:12]
        m4a_brands = {b"M4A ", b"M4B ", b"F4A ", b"mp42", b"isom", b"iso2", b"M4P "}
        if brand in m4a_brands or ext == ".m4a":
            return ("m4a", FORMAT_CANONICAL_MIME["m4a"])

    # WebM / Matroska EBML header
    if data[:4] == b"\x1a\x45\xdf\xa3" and (b"webm" in data[:128].lower() or ext == ".webm"):
        return ("webm", FORMAT_CANONICAL_MIME["webm"])

    return None


def _wav_duration_seconds(data: bytes) -> float | None:
    try:
        with wave.open(io.BytesIO(data), "rb") as wf:
            frames = wf.getnframes()
            rate = wf.getframerate()
            if rate > 0:
                return frames / float(rate)
    except (wave.Error, EOFError, struct.error):
        return None
    return None


def _flac_duration_seconds(data: bytes) -> float | None:
    # STREAMINFO block is 34 bytes following the 4-byte "fLaC" magic and 4-byte block header.
    if len(data) < 42 or data[:4] != b"fLaC":
        return None
    block_type = data[4] & 0x7F
    if block_type != 0:
        return None
    # Bytes 18..25 inside STREAMINFO (bytes 8..41 of file):
    # sample_rate: 20 bits, channels: 3 bits, bits_per_sample: 5 bits, total_samples: 36 bits
    sample_rate = (data[18] << 12) | (data[19] << 4) | (data[20] >> 4)
    total_samples = (
        ((data[21] & 0x0F) << 32)
        | (data[22] << 24)
        | (data[23] << 16)
        | (data[24] << 8)
        | data[25]
    )
    if sample_rate <= 0:
        return None
    return total_samples / float(sample_rate)


def _ogg_duration_seconds(data: bytes) -> float | None:
    if len(data) < 64 or data[:4] != b"OggS":
        return None

    sample_rate: int | None = None
    opus_pos = data.find(b"OpusHead", 0, 512)
    if opus_pos != -1:
        # RFC 7845: Opus granule position always runs at 48 kHz.
        sample_rate = 48000
    else:
        vorbis_pos = data.find(b"\x01vorbis", 0, 512)
        if vorbis_pos != -1 and vorbis_pos + 16 <= len(data):
            sample_rate = struct.unpack_from("<I", data, vorbis_pos + 12)[0]

    if not sample_rate or sample_rate <= 0:
        return None

    last_page = data.rfind(b"OggS")
    if last_page == -1 or last_page + 14 > len(data):
        return None
    granule_pos = struct.unpack_from("<q", data, last_page + 6)[0]
    if granule_pos < 0:
        return None
    return granule_pos / float(sample_rate)


def extract_duration_python(data: bytes, format_key: str) -> float | None:
    """Extract duration in seconds using pure-Python header parsers where supported."""
    if format_key == "wav":
        return _wav_duration_seconds(data)
    if format_key == "flac":
        return _flac_duration_seconds(data)
    if format_key in {"ogg", "opus"}:
        return _ogg_duration_seconds(data)
    return None


async def extract_duration_ffprobe(
    data: bytes,
    extension: str,
    ffprobe_path: str = "ffprobe",
    timeout_seconds: float = 10.0,
) -> float | None:
    """Extract duration using ``ffprobe`` if installed on PATH."""
    resolved = shutil.which(ffprobe_path)
    if not resolved:
        return None

    tmp_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(suffix=extension, delete=False) as tmp:
            tmp.write(data)
            tmp_path = tmp.name

        proc = await asyncio.create_subprocess_exec(
            resolved,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            tmp_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout_seconds)
        if proc.returncode != 0:
            return None
        raw = stdout.decode("utf-8", errors="ignore").strip()
        if not raw or raw == "N/A":
            return None
        duration = float(raw)
        return duration if duration >= 0 else None
    except (OSError, ValueError, TimeoutError):
        logger.debug("ffprobe duration inspection failed", exc_info=True)
        return None
    finally:
        if tmp_path:
            Path(tmp_path).unlink(missing_ok=True)


async def inspect_audio_duration(
    data: bytes,
    format_key: str,
    extension: str,
    *,
    backend: Literal["auto", "python", "ffprobe", "disabled"] = "auto",
    ffprobe_path: str = "ffprobe",
) -> float | None:
    """Inspect audio duration according to the configured backend."""
    if backend == "disabled":
        return None
    if backend in {"auto", "python"}:
        duration = extract_duration_python(data, format_key)
        if duration is not None or backend == "python":
            return duration
    if backend in {"auto", "ffprobe"}:
        return await extract_duration_ffprobe(data, extension, ffprobe_path=ffprobe_path)
    return None


def _parse_pcm_params(mime_type: str | None) -> tuple[int, int]:
    """Parse optional ``rate`` and ``channels`` parameters from an ``audio/l16`` MIME type."""
    sample_rate = 24000
    channels = 1
    if not mime_type:
        return sample_rate, channels
    for part in mime_type.split(";")[1:]:
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        key = key.strip().lower()
        value = value.strip()
        if key == "rate":
            try:
                parsed = int(value)
                if parsed > 0:
                    sample_rate = parsed
            except ValueError:
                pass
        elif key == "channels":
            try:
                parsed = int(value)
                if parsed > 0:
                    channels = parsed
            except ValueError:
                pass
    return sample_rate, channels


def wrap_pcm_as_wav(
    pcm_bytes: bytes,
    *,
    sample_rate: int = 24000,
    channels: int = 1,
    sample_width: int = 2,
) -> bytes:
    """Wrap raw 16-bit signed little-endian linear PCM bytes into a RIFF WAV container."""
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_bytes)
    return buffer.getvalue()


def ensure_wav_or_preserve_mime(
    audio_bytes: bytes,
    mime_type: str | None,
) -> tuple[bytes, str]:
    """Ensure raw PCM responses are wrapped in a WAV header and never mislabeled as WAV."""
    if len(audio_bytes) >= 12 and audio_bytes[:4] == b"RIFF" and audio_bytes[8:12] == b"WAVE":
        return audio_bytes, "audio/wav"

    normalized = normalize_mime_type(mime_type)
    if normalized in {"audio/l16", "audio/pcm", "audio/raw"}:
        sample_rate, channels = _parse_pcm_params(mime_type)
        wav_bytes = wrap_pcm_as_wav(
            audio_bytes,
            sample_rate=sample_rate,
            channels=channels,
            sample_width=2,
        )
        return wav_bytes, "audio/wav"

    detected = detect_audio_format_from_bytes(audio_bytes)
    if detected is not None:
        return audio_bytes, detected[1]

    if normalized:
        return audio_bytes, normalized

    return audio_bytes, "application/octet-stream"
