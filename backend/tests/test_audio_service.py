import io

import pytest
from fastapi import UploadFile
from starlette.datastructures import Headers

from app.core.exceptions import (
    AudioDurationExceededError,
    AudioTooLargeError,
    EmptyAudioError,
    InvalidAudioError,
    UnsupportedAudioFormatError,
)
from app.services.audio_service import AudioValidationService
from tests.conftest import build_flac_header_bytes, build_ogg_opus_bytes, build_wav_bytes


def _make_upload_file(data: bytes, *, filename: str, content_type: str | None) -> UploadFile:
    headers = Headers({"content-type": content_type}) if content_type else Headers()
    return UploadFile(file=io.BytesIO(data), filename=filename, headers=headers)


@pytest.mark.anyio
async def test_validate_valid_wav_file(test_settings) -> None:
    service = AudioValidationService(test_settings)
    wav_bytes = build_wav_bytes(duration_seconds=1.5)
    upload = _make_upload_file(wav_bytes, filename="sample.wav", content_type="audio/wav")

    result = await service.validate_upload(upload)

    assert result.filename == "sample.wav"
    assert result.mime_type == "audio/wav"
    assert result.size_bytes == len(wav_bytes)
    assert result.duration_seconds == pytest.approx(1.5, abs=0.01)
    assert result.data == wav_bytes


@pytest.mark.anyio
async def test_validate_valid_flac_and_opus_headers(test_settings) -> None:
    service = AudioValidationService(test_settings)

    flac_bytes = build_flac_header_bytes(sample_rate=44100, total_samples=88200)
    flac_res = await service.validate_upload(
        _make_upload_file(flac_bytes, filename="clip.flac", content_type="audio/flac")
    )
    assert flac_res.mime_type == "audio/flac"
    assert flac_res.duration_seconds == pytest.approx(2.0, abs=0.01)

    opus_bytes = build_ogg_opus_bytes(total_samples_48k=96000)
    opus_res = await service.validate_upload(
        _make_upload_file(opus_bytes, filename="voice.opus", content_type="audio/opus")
    )
    assert opus_res.mime_type == "audio/opus"
    assert opus_res.duration_seconds == pytest.approx(2.0, abs=0.01)


@pytest.mark.anyio
async def test_reject_empty_file(test_settings) -> None:
    service = AudioValidationService(test_settings)
    upload = _make_upload_file(b"", filename="empty.wav", content_type="audio/wav")

    with pytest.raises(EmptyAudioError):
        await service.validate_upload(upload)


@pytest.mark.anyio
async def test_reject_unsupported_extension(test_settings) -> None:
    service = AudioValidationService(test_settings)
    upload = _make_upload_file(b"%PDF-1.7", filename="notes.pdf", content_type="application/pdf")

    with pytest.raises(UnsupportedAudioFormatError):
        await service.validate_upload(upload)


@pytest.mark.anyio
async def test_reject_spoofed_content_type_with_non_audio_bytes(test_settings) -> None:
    service = AudioValidationService(test_settings)
    fake_wav = b"\x89PNG\r\n\x1a\nnot-actually-audio"
    upload = _make_upload_file(fake_wav, filename="fake.wav", content_type="audio/wav")

    with pytest.raises(UnsupportedAudioFormatError):
        await service.validate_upload(upload)


@pytest.mark.anyio
async def test_reject_invalid_declared_mime_type(test_settings) -> None:
    service = AudioValidationService(test_settings)
    wav_bytes = build_wav_bytes(duration_seconds=0.5)
    upload = _make_upload_file(wav_bytes, filename="sample.wav", content_type="text/plain")

    with pytest.raises(UnsupportedAudioFormatError):
        await service.validate_upload(upload)


@pytest.mark.anyio
async def test_reject_mismatched_extension_and_container(test_settings) -> None:
    service = AudioValidationService(test_settings)
    wav_bytes = build_wav_bytes(duration_seconds=0.5)
    upload = _make_upload_file(wav_bytes, filename="misnamed.mp3", content_type="audio/wav")

    with pytest.raises((InvalidAudioError, UnsupportedAudioFormatError)):
        await service.validate_upload(upload)


@pytest.mark.anyio
async def test_reject_oversized_file(test_settings) -> None:
    service = AudioValidationService(test_settings)
    # test_settings sets max_audio_size_mb = 1
    oversized = b"RIFF" + b"\x00" * 4 + b"WAVE" + b"\x00" * (1024 * 1024 + 100)
    upload = _make_upload_file(oversized, filename="huge.wav", content_type="audio/wav")

    with pytest.raises(AudioTooLargeError):
        await service.validate_upload(upload)


@pytest.mark.anyio
async def test_reject_duration_limit_exceeded(test_settings) -> None:
    service = AudioValidationService(test_settings)
    # test_settings sets max_audio_duration_seconds = 10
    long_wav = build_wav_bytes(duration_seconds=12.0, sample_rate=8000)
    upload = _make_upload_file(long_wav, filename="long.wav", content_type="audio/wav")

    with pytest.raises(AudioDurationExceededError):
        await service.validate_upload(upload)
