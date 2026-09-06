import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Conversation, ConversationStatus
from app.models.customer import Customer
from app.models.message import Message, MessageRole
from app.services.exceptions import NotFoundError


async def get_or_create_conversation(
    db: AsyncSession, *, business_id: uuid.UUID, customer_id: uuid.UUID
) -> Conversation:
    customer = await db.scalar(
        select(Customer).where(Customer.id == customer_id, Customer.business_id == business_id)
    )
    if customer is None:
        raise NotFoundError("Cliente no encontrado")

    conversation = await db.scalar(
        select(Conversation)
        .where(
            Conversation.business_id == business_id,
            Conversation.customer_id == customer_id,
            Conversation.status != ConversationStatus.CLOSED,
        )
        .order_by(Conversation.created_at.desc())
    )
    if conversation is not None:
        return conversation

    conversation = Conversation(
        business_id=business_id, customer_id=customer_id, status=ConversationStatus.AI_ACTIVE
    )
    db.add(conversation)
    await db.commit()
    await db.refresh(conversation)
    return conversation


async def get_conversation(
    db: AsyncSession, *, business_id: uuid.UUID, conversation_id: uuid.UUID
) -> Conversation:
    conversation = await db.scalar(
        select(Conversation).where(
            Conversation.id == conversation_id, Conversation.business_id == business_id
        )
    )
    if conversation is None:
        raise NotFoundError(conversation_id)
    return conversation


async def list_conversations(db: AsyncSession, *, business_id: uuid.UUID) -> list[Conversation]:
    result = await db.scalars(
        select(Conversation)
        .where(Conversation.business_id == business_id)
        .order_by(Conversation.last_message_at.desc().nullslast())
    )
    return list(result)


async def list_messages(
    db: AsyncSession, *, business_id: uuid.UUID, conversation_id: uuid.UUID
) -> list[Message]:
    await get_conversation(db, business_id=business_id, conversation_id=conversation_id)
    result = await db.scalars(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at)
    )
    return list(result)


async def append_message(
    db: AsyncSession,
    *,
    conversation_id: uuid.UUID,
    role: MessageRole,
    content: str | None,
    extra: dict[str, Any] | None = None,
    whatsapp_message_id: str | None = None,
) -> Message:
    message = Message(
        conversation_id=conversation_id,
        role=role,
        content=content,
        extra=extra,
        whatsapp_message_id=whatsapp_message_id,
    )
    db.add(message)
    await db.flush()
    return message


def touch(conversation: Conversation) -> None:
    conversation.last_message_at = datetime.now(UTC)


async def set_status(
    db: AsyncSession,
    *,
    business_id: uuid.UUID,
    conversation_id: uuid.UUID,
    status: ConversationStatus,
) -> Conversation:
    conversation = await get_conversation(
        db, business_id=business_id, conversation_id=conversation_id
    )
    conversation.status = status
    await db.commit()
    await db.refresh(conversation)
    return conversation
