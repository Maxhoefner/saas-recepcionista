from httpx import AsyncClient


async def test_ai_settings_defaults_and_update(client: AsyncClient, owner: dict) -> None:
    biz, headers = owner["business_id"], owner["headers"]

    defaults = await client.get(f"/api/v1/businesses/{biz}/ai-settings", headers=headers)
    assert defaults.status_code == 200
    assert defaults.json()["assistant_name"] == "Sofi"

    updated = await client.put(
        f"/api/v1/businesses/{biz}/ai-settings",
        json={"assistant_name": "Lucía", "tone": "Divertida y directa"},
        headers=headers,
    )
    assert updated.status_code == 200
    assert updated.json()["assistant_name"] == "Lucía"
    assert updated.json()["tone"] == "Divertida y directa"
    assert updated.json()["language"] == "es"  # untouched field keeps its value


async def test_faq_crud(client: AsyncClient, owner: dict) -> None:
    biz, headers = owner["business_id"], owner["headers"]

    created = await client.post(
        f"/api/v1/businesses/{biz}/faqs",
        json={"question": "¿Aceptan mascotas?", "answer": "Sí, son bienvenidas."},
        headers=headers,
    )
    assert created.status_code == 201, created.text
    faq_id = created.json()["id"]

    listed = await client.get(f"/api/v1/businesses/{biz}/faqs", headers=headers)
    assert len(listed.json()) == 1

    updated = await client.patch(
        f"/api/v1/businesses/{biz}/faqs/{faq_id}", json={"active": False}, headers=headers
    )
    assert updated.status_code == 200
    assert updated.json()["active"] is False

    deleted = await client.delete(f"/api/v1/businesses/{biz}/faqs/{faq_id}", headers=headers)
    assert deleted.status_code == 204
