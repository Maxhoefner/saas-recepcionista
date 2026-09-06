from abc import ABC, abstractmethod


class WhatsAppProvider(ABC):
    """Abstraction over a specific WhatsApp API vendor. Meta's Cloud API is
    the only implementation today, but nothing outside `app/whatsapp/`
    imports it directly — swapping providers (or adding a BSP) means
    implementing this interface, not touching the webhook or send logic."""

    @abstractmethod
    async def send_text_message(
        self, *, phone_number_id: str, access_token: str, to: str, text: str
    ) -> None: ...
