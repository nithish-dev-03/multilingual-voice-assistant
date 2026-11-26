import asyncio
from abc import ABC, abstractmethod

from app.schemas.chat import ChatMessage


class ConversationRepository(ABC):
    """Abstract storage contract for conversation message histories."""

    @abstractmethod
    async def get_history(self, conversation_id: str) -> list[ChatMessage]:
        """Return ordered history for ``conversation_id`` (empty list if new)."""

    @abstractmethod
    async def append_turn(
        self,
        conversation_id: str,
        user_message: str,
        assistant_message: str,
    ) -> None:
        """Persist a user + assistant turn for ``conversation_id``."""

    @abstractmethod
    async def clear(self, conversation_id: str) -> None:
        """Delete stored history for ``conversation_id``."""


class InMemoryConversationRepository(ConversationRepository):
    """In-memory conversation store with bounded per-conversation history.

    Limitations:
        - All conversations are lost on server restart.
        - Not shared across multiple worker processes; use Redis or PostgreSQL
          for multi-worker production deployments.
    """

    def __init__(self, max_turns: int = 10) -> None:
        if max_turns <= 0:
            raise ValueError("max_turns must be a positive integer.")
        self._max_messages = max_turns * 2
        self._conversations: dict[str, list[ChatMessage]] = {}
        self._lock = asyncio.Lock()

    async def get_history(self, conversation_id: str) -> list[ChatMessage]:
        async with self._lock:
            messages = self._conversations.get(conversation_id, [])
            return [msg.model_copy() for msg in messages]

    async def append_turn(
        self,
        conversation_id: str,
        user_message: str,
        assistant_message: str,
    ) -> None:
        async with self._lock:
            history = self._conversations.setdefault(conversation_id, [])
            history.append(ChatMessage(role="user", content=user_message))
            history.append(ChatMessage(role="assistant", content=assistant_message))
            if len(history) > self._max_messages:
                self._conversations[conversation_id] = history[-self._max_messages :]

    async def clear(self, conversation_id: str) -> None:
        async with self._lock:
            self._conversations.pop(conversation_id, None)
