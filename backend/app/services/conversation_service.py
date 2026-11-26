import uuid

from app.core.exceptions import InvalidConversationIdError
from app.repositories.conversation_repository import ConversationRepository
from app.schemas.chat import ChatMessage


class ConversationService:
    """Manages conversation identifiers and bounded turn history independently of chat logic."""

    def __init__(self, repository: ConversationRepository) -> None:
        self._repository = repository

    def resolve_conversation_id(self, conversation_id: str | None) -> str:
        """Validate a provided conversation UUID or allocate a new UUID."""
        if conversation_id is None:
            return str(uuid.uuid4())
        candidate = conversation_id.strip()
        if not candidate:
            raise InvalidConversationIdError("conversation_id cannot be blank.")
        try:
            parsed = uuid.UUID(candidate)
        except ValueError as exc:
            raise InvalidConversationIdError(
                "Invalid conversation_id format; expected a valid UUID."
            ) from exc
        return str(parsed)

    async def get_history(self, conversation_id: str) -> list[ChatMessage]:
        return await self._repository.get_history(conversation_id)

    async def save_turn(
        self,
        conversation_id: str,
        user_message: str,
        assistant_message: str,
    ) -> None:
        await self._repository.append_turn(conversation_id, user_message, assistant_message)
