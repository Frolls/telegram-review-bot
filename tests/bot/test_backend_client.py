from __future__ import annotations

from uuid import UUID, uuid4

import httpx
import pytest

from bot.services.backend_client import BackendClient


@pytest.mark.asyncio
async def test_get_or_create_chat_returns_uuid() -> None:
    chat_id = uuid4()

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/chats"
        return httpx.Response(200, json={"chat_id": str(chat_id)})

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="http://backend",
    ) as http_client:
        client = BackendClient("http://backend", client=http_client)
        result = await client.get_or_create_chat("123", "telegram")

    assert result == chat_id


@pytest.mark.asyncio
async def test_send_message_parses_sse_frames() -> None:
    chat_id = uuid4()

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == f"/chats/{chat_id}/messages"
        return httpx.Response(
            200,
            content=b"data: Hel\n\ndata: lo\n\ndata: [DONE]\n\n",
            headers={"content-type": "text/event-stream"},
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="http://backend",
    ) as http_client:
        client = BackendClient("http://backend", client=http_client)
        tokens = [token async for token in client.send_message(chat_id, "Hi")]

    assert tokens == ["Hel", "lo"]


@pytest.mark.asyncio
async def test_send_message_preserves_token_leading_spaces() -> None:
    chat_id = uuid4()

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=b"data: Hello\n\ndata:  world\n\ndata: [DONE]\n\n",
            headers={"content-type": "text/event-stream"},
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="http://backend",
    ) as http_client:
        client = BackendClient("http://backend", client=http_client)
        text = "".join([token async for token in client.send_message(chat_id, "Hi")])

    assert text == "Hello world"


@pytest.mark.asyncio
async def test_clear_messages_sends_delete_to_chat_messages_url() -> None:
    chat_id = uuid4()
    seen_url: str | None = None

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal seen_url
        seen_url = str(request.url)
        assert request.method == "DELETE"
        return httpx.Response(200, json={"status": "ok"})

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="http://backend",
    ) as http_client:
        client = BackendClient("http://backend", client=http_client)
        await client.clear_messages(chat_id)

    assert seen_url == f"http://backend/chats/{chat_id}/messages"
    assert isinstance(chat_id, UUID)
