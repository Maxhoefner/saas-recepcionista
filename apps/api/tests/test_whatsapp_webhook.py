import hashlib
import hmac
import json

from httpx import AsyncClient

from app.ai.providers.base import AgentTurnResult
from app.core.config import get_settings
from tests.conftest import FakeProvider, FakeWhatsAppProvider


def _signed_body(payload: dict) -> tuple[bytes, str]:
    body = json.dumps(payload).encode("utf-8")
    secret = get_settings().WHATSAPP_APP_SECRET
    signature = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return body, f"sha256={signature}"


def _message_payload(
    *, phone_number_id: str, wa_id: str, name: str, text: str, wamid: str
) -> dict:
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "waba_1",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "+5491100000000",
                                "phone_number_id": phone_number_id,
                            },
                            "contacts": [{"profile": {"name": name}, "wa_id": wa_id}],
                            "messages": [
                                {
                                    "from": wa_id,
                                    "id": wamid,
                                    "timestamp": "1700000000",
                                    "type": "text",
                                    "text": {"body": text},
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }


async def _connect_whatsapp(
    client: AsyncClient, owner: dict, phone_number_id: str = "1234567890"
) -> None:
    response = await client.put(
        f"/api/v1/businesses/{owner['business_id']}/whatsapp-account",
        json={
            "phone_number_id": phone_number_id,
            "waba_id": "waba_1",
            "display_phone_number": "+5491100000000",
            "access_token": "secret-token",
        },
        headers=owner["headers"],
    )
    assert response.status_code == 200, response.text


async def test_webhook_verification_challenge(client: AsyncClient) -> None:
    settings = get_settings()
    response = await client.get(
        "/api/v1/webhooks/whatsapp",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": settings.WHATSAPP_VERIFY_TOKEN,
            "hub.challenge": "abc123",
        },
    )
    assert response.status_code == 200
    assert response.text == "abc123"


async def test_webhook_verification_rejects_wrong_token(client: AsyncClient) -> None:
    response = await client.get(
        "/api/v1/webhooks/whatsapp",
        params={"hub.mode": "subscribe", "hub.verify_token": "wrong", "hub.challenge": "abc123"},
    )
    assert response.status_code == 403


async def test_webhook_rejects_invalid_signature(client: AsyncClient) -> None:
    body = json.dumps({"object": "whatsapp_business_account", "entry": []}).encode()
    response = await client.post(
        "/api/v1/webhooks/whatsapp",
        content=body,
        headers={"X-Hub-Signature-256": "sha256=deadbeef", "Content-Type": "application/json"},
    )
    assert response.status_code == 403


async def test_webhook_processes_a_new_message_and_replies(
    client: AsyncClient,
    owner: dict,
    fake_provider: FakeProvider,
    fake_whatsapp_provider: FakeWhatsAppProvider,
) -> None:
    await _connect_whatsapp(client, owner)
    fake_provider.queue(AgentTurnResult(text="¡Hola! ¿En qué te ayudo?", tool_calls=[]))

    payload = _message_payload(
        phone_number_id="1234567890",
        wa_id="5491122334455",
        name="Juan Pérez",
        text="Hola",
        wamid="wamid.1",
    )
    body, signature = _signed_body(payload)

    response = await client.post(
        "/api/v1/webhooks/whatsapp",
        content=body,
        headers={"X-Hub-Signature-256": signature, "Content-Type": "application/json"},
    )
    assert response.status_code == 200

    assert len(fake_whatsapp_provider.sent) == 1
    assert fake_whatsapp_provider.sent[0]["to"] == "5491122334455"
    assert fake_whatsapp_provider.sent[0]["text"] == "¡Hola! ¿En qué te ayudo?"

    customers = await client.get(
        f"/api/v1/businesses/{owner['business_id']}/customers", headers=owner["headers"]
    )
    assert len(customers.json()) == 1
    assert customers.json()[0]["name"] == "Juan Pérez"


async def test_webhook_is_idempotent_on_duplicate_message_id(
    client: AsyncClient,
    owner: dict,
    fake_provider: FakeProvider,
    fake_whatsapp_provider: FakeWhatsAppProvider,
) -> None:
    await _connect_whatsapp(client, owner)
    fake_provider.queue(AgentTurnResult(text="¡Hola!", tool_calls=[]))

    payload = _message_payload(
        phone_number_id="1234567890",
        wa_id="5491122334455",
        name="Juan",
        text="Hola",
        wamid="wamid.dup",
    )
    body, signature = _signed_body(payload)
    headers = {"X-Hub-Signature-256": signature, "Content-Type": "application/json"}

    first = await client.post("/api/v1/webhooks/whatsapp", content=body, headers=headers)
    assert first.status_code == 200
    second = await client.post("/api/v1/webhooks/whatsapp", content=body, headers=headers)
    assert second.status_code == 200

    # Only one reply ever sent, even though Meta "redelivered" the event.
    assert len(fake_whatsapp_provider.sent) == 1


async def test_webhook_ignores_unknown_phone_number_id(
    client: AsyncClient, fake_provider: FakeProvider, fake_whatsapp_provider: FakeWhatsAppProvider
) -> None:
    payload = _message_payload(
        phone_number_id="does-not-exist",
        wa_id="5491100000000",
        name="Nadie",
        text="Hola",
        wamid="wamid.unknown",
    )
    body, signature = _signed_body(payload)

    response = await client.post(
        "/api/v1/webhooks/whatsapp",
        content=body,
        headers={"X-Hub-Signature-256": signature, "Content-Type": "application/json"},
    )
    assert response.status_code == 200
    assert fake_whatsapp_provider.sent == []


async def test_webhook_status_only_payload_is_a_noop(
    client: AsyncClient, owner: dict, fake_whatsapp_provider: FakeWhatsAppProvider
) -> None:
    await _connect_whatsapp(client, owner)
    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "waba_1",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "+5491100000000",
                                "phone_number_id": "1234567890",
                            },
                            "statuses": [{"id": "wamid.1", "status": "delivered"}],
                        },
                    }
                ],
            }
        ],
    }
    body, signature = _signed_body(payload)
    response = await client.post(
        "/api/v1/webhooks/whatsapp",
        content=body,
        headers={"X-Hub-Signature-256": signature, "Content-Type": "application/json"},
    )
    assert response.status_code == 200
    assert fake_whatsapp_provider.sent == []
