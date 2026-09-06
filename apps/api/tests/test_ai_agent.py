from httpx import AsyncClient

from app.ai.providers.base import AgentTurnResult, ToolCallRequest
from tests.conftest import FakeProvider

_ALL_DAY_HOURS = [
    {"weekday": w, "start_time": "00:00:00", "end_time": "23:59:00"} for w in range(7)
]


async def _create_conversation(client: AsyncClient, owner: dict) -> dict:
    customer = (
        await client.post(
            f"/api/v1/businesses/{owner['business_id']}/customers",
            json={"phone": "+5491122334455", "name": "Juan Pérez"},
            headers=owner["headers"],
        )
    ).json()
    return (
        await client.post(
            f"/api/v1/businesses/{owner['business_id']}/conversations",
            json={"customer_id": customer["id"]},
            headers=owner["headers"],
        )
    ).json()


async def test_simple_text_reply_with_no_tools(
    client: AsyncClient, owner: dict, fake_provider: FakeProvider
) -> None:
    conversation = await _create_conversation(client, owner)
    fake_provider.queue(AgentTurnResult(text="¡Hola! ¿En qué te puedo ayudar?", tool_calls=[]))

    response = await client.post(
        f"/api/v1/businesses/{owner['business_id']}/conversations/{conversation['id']}/messages",
        json={"text": "Hola"},
        headers=owner["headers"],
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["customer_message"]["content"] == "Hola"
    assert body["assistant_reply"]["content"] == "¡Hola! ¿En qué te puedo ayudar?"

    messages = (
        await client.get(
            f"/api/v1/businesses/{owner['business_id']}/conversations/{conversation['id']}/messages",
            headers=owner["headers"],
        )
    ).json()
    assert [m["role"] for m in messages] == ["USER", "ASSISTANT"]


async def test_agent_uses_get_services_tool_result(
    client: AsyncClient, owner: dict, fake_provider: FakeProvider
) -> None:
    biz, headers = owner["business_id"], owner["headers"]
    await client.post(
        f"/api/v1/businesses/{biz}/services",
        json={"name": "Corte", "price_cents": 15000, "duration_minutes": 30},
        headers=headers,
    )
    conversation = await _create_conversation(client, owner)

    fake_provider.queue(
        AgentTurnResult(
            text=None,
            tool_calls=[ToolCallRequest(id="call_1", name="get_services", arguments={})],
        )
    )
    fake_provider.queue(AgentTurnResult(text="Tenemos Corte a $150.", tool_calls=[]))

    response = await client.post(
        f"/api/v1/businesses/{biz}/conversations/{conversation['id']}/messages",
        json={"text": "¿Qué servicios tienen?"},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["assistant_reply"]["content"] == "Tenemos Corte a $150."

    # The second call to the model must have received the tool's real result.
    assert len(fake_provider.calls) == 2
    tool_message = next(m for m in fake_provider.calls[1]["messages"] if m.role.value == "tool")
    assert "Corte" in tool_message.content


async def test_agent_creates_a_real_appointment_via_tool(
    client: AsyncClient, owner: dict, fake_provider: FakeProvider
) -> None:
    biz, headers = owner["business_id"], owner["headers"]
    await client.put(
        f"/api/v1/businesses/{biz}/business-hours", json=_ALL_DAY_HOURS, headers=headers
    )
    service = (
        await client.post(
            f"/api/v1/businesses/{biz}/services",
            json={"name": "Corte", "price_cents": 15000, "duration_minutes": 30},
            headers=headers,
        )
    ).json()
    await client.post(
        f"/api/v1/businesses/{biz}/professionals",
        json={"name": "María", "service_ids": [service["id"]]},
        headers=headers,
    )
    conversation = await _create_conversation(client, owner)

    fake_provider.queue(
        AgentTurnResult(
            text=None,
            tool_calls=[
                ToolCallRequest(
                    id="call_1",
                    name="create_appointment",
                    arguments={"service_name": "Corte", "start_datetime": "2026-12-15T10:00:00Z"},
                )
            ],
        )
    )
    fake_provider.queue(AgentTurnResult(text="¡Listo! Turno confirmado.", tool_calls=[]))

    response = await client.post(
        f"/api/v1/businesses/{biz}/conversations/{conversation['id']}/messages",
        json={"text": "Quiero un turno de corte el 15/12 a las 10"},
        headers=headers,
    )
    assert response.status_code == 200
    assert "confirmado" in response.json()["assistant_reply"]["content"]

    appointments_resp = await client.get(f"/api/v1/businesses/{biz}/appointments", headers=headers)
    appointments = appointments_resp.json()
    assert len(appointments) == 1
    assert appointments[0]["status"] == "PENDING"


async def test_handoff_stops_further_automatic_replies(
    client: AsyncClient, owner: dict, fake_provider: FakeProvider
) -> None:
    biz, headers = owner["business_id"], owner["headers"]
    conversation = await _create_conversation(client, owner)

    fake_provider.queue(
        AgentTurnResult(
            text="Ya te comunico con alguien.",
            tool_calls=[
                ToolCallRequest(
                    id="call_1", name="create_handoff", arguments={"reason": "pidió humano"}
                )
            ],
        )
    )

    response = await client.post(
        f"/api/v1/businesses/{biz}/conversations/{conversation['id']}/messages",
        json={"text": "quiero hablar con una persona"},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["assistant_reply"]["content"] == "Ya te comunico con alguien."

    conversations_resp = await client.get(
        f"/api/v1/businesses/{biz}/conversations", headers=headers
    )
    conversations = conversations_resp.json()
    assert conversations[0]["status"] == "HUMAN_HANDOFF"

    # A follow-up message gets stored, but the AI must not answer it anymore
    # (no queued response needed — the agent should never even be called).
    follow_up = await client.post(
        f"/api/v1/businesses/{biz}/conversations/{conversation['id']}/messages",
        json={"text": "hola?"},
        headers=headers,
    )
    assert follow_up.status_code == 200
    assert follow_up.json()["assistant_reply"] is None


async def test_tool_results_never_leak_another_businesss_data(
    client: AsyncClient, owner: dict, fake_provider: FakeProvider
) -> None:
    biz, headers = owner["business_id"], owner["headers"]
    await client.post(
        f"/api/v1/businesses/{biz}/services",
        json={"name": "Corte A", "price_cents": 1000, "duration_minutes": 30},
        headers=headers,
    )

    other = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "other-owner@example.com",
            "password": "supersecret123",
            "full_name": "Other Owner",
            "business_name": "Negocio B",
        },
    )
    other_headers = {"Authorization": f"Bearer {other.json()['access_token']}"}
    other_biz = (await client.get("/api/v1/businesses", headers=other_headers)).json()[0]["id"]
    await client.post(
        f"/api/v1/businesses/{other_biz}/services",
        json={"name": "Corte B", "price_cents": 2000, "duration_minutes": 30},
        headers=other_headers,
    )

    conversation = await _create_conversation(client, owner)
    fake_provider.queue(
        AgentTurnResult(
            text=None, tool_calls=[ToolCallRequest(id="call_1", name="get_services", arguments={})]
        )
    )
    fake_provider.queue(AgentTurnResult(text="ok", tool_calls=[]))

    await client.post(
        f"/api/v1/businesses/{biz}/conversations/{conversation['id']}/messages",
        json={"text": "que servicios hay"},
        headers=headers,
    )

    tool_message = next(m for m in fake_provider.calls[1]["messages"] if m.role.value == "tool")
    assert "Corte A" in tool_message.content
    assert "Corte B" not in tool_message.content
