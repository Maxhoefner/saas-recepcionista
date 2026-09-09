import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.agent import handle_message
from app.ai.providers import get_llm_provider
from app.ai.providers.base import LLMProvider
from app.api.deps import get_current_user, require_business_role
from app.core.db import get_db
from app.models.conversation import Conversation, ConversationStatus
from app.models.user import User
from app.schemas.conversation import (
    ConversationCreate,
    ConversationRead,
    IncomingMessage,
    MessageExchange,
    MessageRead,
)
from app.services import audit_service, conversation_service
from app.services.exceptions import NotFoundError

router = APIRouter(prefix="/businesses/{business_id}/conversations", tags=["conversations"])

# Talking to customers is day-to-day operational work — any membership role.
_access = require_business_role()


@router.get("", response_model=list[ConversationRead], dependencies=[Depends(_access)])
async def list_conversations(
    business_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> list[Conversation]:
    return await conversation_service.list_conversations(db, business_id=business_id)


@router.post(
    "",
    response_model=ConversationRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(_access)],
)
async def create_conversation(
    business_id: uuid.UUID, data: ConversationCreate, db: AsyncSession = Depends(get_db)
) -> Conversation:
    try:
        return await conversation_service.get_or_create_conversation(
            db, business_id=business_id, customer_id=data.customer_id
        )
    except NotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cliente no encontrado") from exc


@router.get(
    "/{conversation_id}/messages",
    response_model=list[MessageRead],
    dependencies=[Depends(_access)],
)
async def list_messages(
    business_id: uuid.UUID, conversation_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> list:
    try:
        return await conversation_service.list_messages(
            db, business_id=business_id, conversation_id=conversation_id
        )
    except NotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversación no encontrada") from exc


@router.post(
    "/{conversation_id}/messages",
    response_model=MessageExchange,
    dependencies=[Depends(_access)],
)
async def send_message(
    business_id: uuid.UUID,
    conversation_id: uuid.UUID,
    data: IncomingMessage,
    db: AsyncSession = Depends(get_db),
    provider: LLMProvider = Depends(get_llm_provider),
) -> MessageExchange:
    """Simulates an inbound customer message and runs the agent — this is
    what the WhatsApp webhook (Fase 6) will do internally instead of going
    through HTTP, so it's also how we test/demo the agent until then."""
    try:
        conversation = await conversation_service.get_conversation(
            db, business_id=business_id, conversation_id=conversation_id
        )
    except NotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversación no encontrada") from exc

    customer_message, reply = await handle_message(
        db,
        business_id=business_id,
        conversation=conversation,
        user_text=data.text,
        provider=provider,
    )
    return MessageExchange(
        customer_message=MessageRead.model_validate(customer_message),
        assistant_reply=MessageRead.model_validate(reply) if reply else None,
    )


@router.post(
    "/{conversation_id}/handoff", response_model=ConversationRead, dependencies=[Depends(_access)]
)
async def handoff_to_human(
    business_id: uuid.UUID,
    conversation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Conversation:
    try:
        conversation = await conversation_service.set_status(
            db,
            business_id=business_id,
            conversation_id=conversation_id,
            status=ConversationStatus.HUMAN_HANDOFF,
        )
    except NotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversación no encontrada") from exc
    await audit_service.record(
        db,
        business_id=business_id,
        user_id=user.id,
        action="conversation.handoff",
        entity="conversation",
        entity_id=str(conversation_id),
    )
    await db.commit()
    return conversation


@router.post(
    "/{conversation_id}/return-to-ai",
    response_model=ConversationRead,
    dependencies=[Depends(_access)],
)
async def return_to_ai(
    business_id: uuid.UUID,
    conversation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Conversation:
    try:
        conversation = await conversation_service.set_status(
            db,
            business_id=business_id,
            conversation_id=conversation_id,
            status=ConversationStatus.AI_ACTIVE,
        )
    except NotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversación no encontrada") from exc
    await audit_service.record(
        db,
        business_id=business_id,
        user_id=user.id,
        action="conversation.return_to_ai",
        entity="conversation",
        entity_id=str(conversation_id),
    )
    await db.commit()
    return conversation
