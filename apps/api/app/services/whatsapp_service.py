import logging
import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.providers.base import LLMProvider
from app.core.security import decrypt_secret, encrypt_secret
from app.models.message import Message
from app.models.whatsapp_account import WhatsAppAccount
from app.schemas.whatsapp_account import WhatsAppAccountConnect
from app.schemas.whatsapp_webhook import WhatsAppMessage, WhatsAppWebhookPayload
from app.services import conversation_service, customer_service
from app.services.exceptions import NotFoundError, ServiceError
from app.whatsapp.providers.base import WhatsAppProvider

logger = logging.getLogger(__name__)


class PhoneNumberAlreadyConnectedError(ServiceError):
    pass


async def connect_account(
    db: AsyncSession, *, business_id: uuid.UUID, data: WhatsAppAccountConnect
) -> WhatsAppAccount:
    conflicting = await db.scalar(
        select(WhatsAppAccount).where(
            WhatsAppAccount.phone_number_id == data.phone_number_id,
            WhatsAppAccount.business_id != business_id,
        )
    )
    if conflicting is not None:
        raise PhoneNumberAlreadyConnectedError(data.phone_number_id)

    account = await db.scalar(
        select(WhatsAppAccount).where(WhatsAppAccount.business_id == business_id)
    )
    encrypted_token = encrypt_secret(data.access_token)
    if account is None:
        account = WhatsAppAccount(
            business_id=business_id,
            phone_number_id=data.phone_number_id,
            waba_id=data.waba_id,
            display_phone_number=data.display_phone_number,
            access_token_encrypted=encrypted_token,
        )
        db.add(account)
    else:
        account.phone_number_id = data.phone_number_id
        account.waba_id = data.waba_id
        account.display_phone_number = data.display_phone_number
        account.access_token_encrypted = encrypted_token

    await db.commit()
    await db.refresh(account)
    return account


async def get_account_for_business(db: AsyncSession, *, business_id: uuid.UUID) -> WhatsAppAccount:
    account = await db.scalar(
        select(WhatsAppAccount).where(WhatsAppAccount.business_id == business_id)
    )
    if account is None:
        raise NotFoundError("Este negocio todavía no conectó WhatsApp")
    return account


async def get_account_by_phone_number_id(
    db: AsyncSession, phone_number_id: str
) -> WhatsAppAccount | None:
    return await db.scalar(
        select(WhatsAppAccount).where(WhatsAppAccount.phone_number_id == phone_number_id)
    )


async def send_message(
    db: AsyncSession,
    *,
    business_id: uuid.UUID,
    to: str,
    text: str,
    provider: WhatsAppProvider,
) -> None:
    account = await get_account_for_business(db, business_id=business_id)
    await provider.send_text_message(
        phone_number_id=account.phone_number_id,
        access_token=decrypt_secret(account.access_token_encrypted),
        to=to,
        text=text,
    )


async def process_webhook_payload(
    db: AsyncSession,
    *,
    payload: WhatsAppWebhookPayload,
    llm_provider: LLMProvider,
    whatsapp_provider: WhatsAppProvider,
) -> None:
    for entry in payload.entry:
        for change in entry.changes:
            value = change.value
            if not value.messages:
                continue  # e.g. a delivery/read status update — nothing to do

            account = await get_account_by_phone_number_id(db, value.metadata.phone_number_id)
            if account is None:
                logger.warning(
                    "WhatsApp webhook: no connected account for phone_number_id %s",
                    value.metadata.phone_number_id,
                )
                continue

            contact_names = {c.wa_id: (c.profile.name or c.wa_id) for c in value.contacts}
            for message in value.messages:
                await _process_inbound_message(
                    db,
                    business_id=account.business_id,
                    message=message,
                    contact_names=contact_names,
                    llm_provider=llm_provider,
                    whatsapp_provider=whatsapp_provider,
                )


async def _process_inbound_message(
    db: AsyncSession,
    *,
    business_id: uuid.UUID,
    message: WhatsAppMessage,
    contact_names: dict[str, str],
    llm_provider: LLMProvider,
    whatsapp_provider: WhatsAppProvider,
) -> None:
    # Imported here, not at module load: app.ai.agent -> app.ai.tools ->
    # app.services.appointment_service -> app.services.reminder_service ->
    # this module, so a top-level import here would be circular. By call
    # time every module involved has already finished loading.
    from app.ai.agent import handle_message

    already_seen = await db.scalar(
        select(Message.id).where(Message.whatsapp_message_id == message.id)
    )
    if already_seen is not None:
        return  # fast-path idempotency check — the unique constraint below is the real guard

    if message.type != "text" or message.text is None:
        logger.info("Ignoring unsupported WhatsApp message type: %s", message.type)
        return

    customer_name = contact_names.get(message.from_, message.from_)
    customer = await customer_service.get_or_create_by_phone(
        db, business_id=business_id, phone=message.from_, name=customer_name
    )
    conversation = await conversation_service.get_or_create_conversation(
        db, business_id=business_id, customer_id=customer.id
    )

    try:
        _, reply = await handle_message(
            db,
            business_id=business_id,
            conversation=conversation,
            user_text=message.text.body,
            provider=llm_provider,
            whatsapp_message_id=message.id,
        )
    except IntegrityError:
        # A concurrent delivery of the same wamid won the unique-constraint
        # race — it's already been handled, there's nothing more to do here.
        await db.rollback()
        return

    if reply is not None and reply.content:
        try:
            await send_message(
                db,
                business_id=business_id,
                to=customer.phone,
                text=reply.content,
                provider=whatsapp_provider,
            )
        except Exception:
            logger.exception("Failed to send WhatsApp reply to %s", customer.phone)
