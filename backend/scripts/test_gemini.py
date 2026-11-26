"""Standalone script to verify Gemini Developer API connectivity."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.core.gemini import close_gemini_client, create_gemini_client
from app.services.chat_service import ChatService


async def main() -> int:
    settings = get_settings()
    client = create_gemini_client(settings)
    chat_service = ChatService(client, settings)
    try:
        reply = await chat_service.generate_reply("Reply with exactly: Gemini connection OK.")
        print(f"Model: {settings.chat_model}")
        print(f"Response: {reply}")
        return 0
    except AppError as exc:
        print(f"API error [{exc.error_code}]: {exc.message}", file=sys.stderr)
        return 1
    finally:
        await close_gemini_client(client)


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
