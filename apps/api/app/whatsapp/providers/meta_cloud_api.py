import logging

import httpx

from app.core.config import get_settings
from app.whatsapp.providers.base import WhatsAppProvider

logger = logging.getLogger(__name__)
settings = get_settings()


class MetaCloudAPIProvider(WhatsAppProvider):
    """WhatsApp Business Cloud API. One instance is shared across all
    businesses — each call carries the specific account's phone_number_id
    and access token, since those are per-tenant, not process-wide config."""

    async def send_text_message(
        self, *, phone_number_id: str, access_token: str, to: str, text: str
    ) -> None:
        url = f"{settings.WHATSAPP_API_BASE_URL}/{phone_number_id}/messages"
        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "text",
            "text": {"body": text},
        }
        headers = {"Authorization": f"Bearer {access_token}"}

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, json=payload, headers=headers)

        if response.status_code >= 400:
            # Meta's error payloads may include tokens/PII in edge cases —
            # log the status and error code only, not the raw body.
            logger.error(
                "WhatsApp send failed: status=%s to=%s phone_number_id=%s",
                response.status_code,
                to,
                phone_number_id,
            )
            response.raise_for_status()
