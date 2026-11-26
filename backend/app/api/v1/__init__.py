from fastapi import APIRouter

from app.api.v1 import chat, voice

router = APIRouter()
router.include_router(voice.router)
router.include_router(chat.router)
