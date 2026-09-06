import logging
from datetime import UTC, datetime
from typing import Any

from app.core.db import AsyncSessionLocal
from app.services import reminder_service
from app.whatsapp.providers import get_whatsapp_provider

logger = logging.getLogger(__name__)


async def send_due_reminders(ctx: dict[str, Any]) -> None:
    """Arq cron job — runs once a minute (see WorkerSettings). Opens its own
    DB session since it isn't tied to any FastAPI request."""
    provider = get_whatsapp_provider()
    async with AsyncSessionLocal() as db:
        due = await reminder_service.list_due_reminders(db, now=datetime.now(UTC))
        for reminder in due:
            try:
                await reminder_service.send_reminder(
                    db, reminder=reminder, whatsapp_provider=provider
                )
            except Exception:
                logger.exception("Unhandled error sending reminder %s", reminder.id)
