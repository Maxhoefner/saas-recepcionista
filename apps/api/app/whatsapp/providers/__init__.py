from functools import lru_cache

from app.core.config import get_settings
from app.whatsapp.providers.base import WhatsAppProvider


@lru_cache
def get_whatsapp_provider() -> WhatsAppProvider:
    settings = get_settings()
    if settings.WHATSAPP_PROVIDER == "meta":
        from app.whatsapp.providers.meta_cloud_api import MetaCloudAPIProvider

        return MetaCloudAPIProvider()
    raise ValueError(f"Proveedor de WhatsApp desconocido: {settings.WHATSAPP_PROVIDER}")
