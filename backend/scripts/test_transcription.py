"""Standalone script to validate and transcribe local audio files using Gemini 3.5 Transcribe."""

import argparse
import asyncio
import mimetypes
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.core.gemini import close_gemini_client, create_gemini_client
from app.services.audio_service import AudioValidationService
from app.services.transcription_service import TranscriptionService


async def transcribe_file(
    file_path: Path,
    audio_service: AudioValidationService,
    transcription_service: TranscriptionService,
) -> bool:
    print(f"\n=== File: {file_path} ===")
    if not file_path.is_file():
        print(f"Error: File not found: {file_path}", file=sys.stderr)
        return False

    guessed_mime, _ = mimetypes.guess_type(file_path.name)
    raw_bytes = file_path.read_bytes()

    try:
        validated = await audio_service.validate_bytes(
            raw_bytes,
            filename=file_path.name,
            content_type=guessed_mime,
        )
        print(
            f"Validated: mime_type={validated.mime_type}, "
            f"size_bytes={validated.size_bytes}, duration_seconds={validated.duration_seconds}"
        )
        result = await transcription_service.transcribe(validated)
        print(f"Language code: {result.language_code}")
        print(f"Language name: {result.language_name}")
        print(f"Transcription: {result.text}")
        return True
    except AppError as exc:
        print(f"Error [{exc.error_code}]: {exc.message}", file=sys.stderr)
        return False


async def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate and transcribe one or more local audio files with Gemini."
    )
    parser.add_argument(
        "files",
        nargs="+",
        type=Path,
        help="Path(s) to audio files (WAV, MP3, M4A, AAC, OGG, FLAC, WebM).",
    )
    args = parser.parse_args()

    settings = get_settings()
    client = create_gemini_client(settings)
    audio_service = AudioValidationService(settings)
    transcription_service = TranscriptionService(client, settings)

    try:
        results = [
            await transcribe_file(path, audio_service, transcription_service)
            for path in args.files
        ]
        return 0 if all(results) else 1
    finally:
        await close_gemini_client(client)


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
