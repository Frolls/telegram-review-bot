from unittest.mock import AsyncMock
from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient

from bot.web import build_api


@pytest.mark.asyncio
async def test_delivery_is_deduplicated_after_service_restart(tmp_path):
    bot = SimpleNamespace(send_message=AsyncMock())
    db = str(tmp_path / "deliveries.sqlite")
    data = {"chat_id": 1, "text": "review done", "request_id": "action-1"}
    for iteration in range(2):
        app = build_api(bot, "secret", delivery_db=db)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/notify", json=data, headers={"X-Internal-Token": "secret"})
            assert response.status_code == 200
            assert response.json()["duplicate"] == bool(iteration)
    bot.send_message.assert_awaited_once()


@pytest.mark.asyncio
async def test_uncertain_delivery_is_not_retried(tmp_path):
    bot = SimpleNamespace(send_message=AsyncMock(side_effect=TimeoutError))
    app = build_api(bot, "secret", delivery_db=str(tmp_path / "db.sqlite"))
    data = {"chat_id": 1, "text": "hello", "request_id": "uncertain"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        assert (await client.post("/notify", json=data, headers={"X-Internal-Token": "wrong"})).status_code == 401
        assert (await client.post("/notify", json=data, headers={"X-Internal-Token": "secret"})).status_code == 502
        assert (await client.post("/notify", json=data, headers={"X-Internal-Token": "secret"})).status_code == 409
    bot.send_message.assert_awaited_once()
