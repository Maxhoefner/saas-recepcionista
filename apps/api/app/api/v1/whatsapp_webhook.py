import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.providers import get_llm_provider
from app.ai.providers.base import LLMProvider
from app.core.config import get_settings
from app.core.db import get_db
from app.core.rate_limit import limiter
from app.schemas.whatsapp_webhook import WhatsAppWebhookPayload
from app.services import whatsapp_service
from app.whatsapp.providers import get_whatsapp_provider
from app.whatsapp.providers.base import WhatsAppProvider
from app.whatsapp.security import verify_signature

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhooks/whatsapp", tags=["whatsapp-webhook"])
settings = get_settings()


@router.get("")
async def verify_webhook(request: Request) -> Response:
    """Meta calls this once, synchronously, when you register the webhook
    URL in the App dashboard — echo back `hub.challenge` iff the verify
    token matches, otherwise the registration must fail."""
    params = request.query_params
    if (
        params.get("hub.mode") == "subscribe"
        and params.get("hub.verify_token") == settings.WHATSAPP_VERIFY_TOKEN
    ):
        return Response(content=params.get("hub.challenge", ""), media_type="text/plain")
    raise HTTPException(status.HTTP_403_FORBIDDEN, "Verificación de webhook inválida")


@router.post("", status_code=status.HTTP_200_OK)
@limiter.limit("300/minute")
async def receive_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    llm_provider: LLMProvider = Depends(get_llm_provider),
    whatsapp_provider: WhatsAppProvider = Depends(get_whatsapp_provider),
) -> dict:
    raw_body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256")
    if not verify_signature(
        payload=raw_body, signature_header=signature, app_secret=settings.WHATSAPP_APP_SECRET
    ):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Firma inválida")

    payload = WhatsAppWebhookPayload.model_validate_json(raw_body)

    try:
        await whatsapp_service.process_webhook_payload(
            db, payload=payload, llm_provider=llm_provider, whatsapp_provider=whatsapp_provider
        )
    except Exception:
        # Always ack 200 regardless — a non-200 makes Meta retry the whole
        # payload (and enough failures gets the webhook auto-disabled).
        # Idempotency means a retry safely redoes at most the failed part.
        logger.exception("Unhandled error processing WhatsApp webhook payload")

    return {"status": "ok"}
