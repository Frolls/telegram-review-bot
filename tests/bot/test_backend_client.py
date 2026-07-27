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
            content=(
                b'data: {"type": "token", "delta": "Hel"}\n\n'
                b'data: {"type": "token", "delta": "lo"}\n\n'
                b'data: {"type": "done"}\n\n'
            ),
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
async def test_send_message_stores_done_message_id() -> None:
    chat_id = uuid4()
    message_id = uuid4()

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=(
                b'data: {"type": "token", "delta": "ok"}\n\n'
                + f'data: {{"type": "done", "message_id": "{message_id}"}}\n\n'.encode()
            ),
            headers={"content-type": "text/event-stream"},
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="http://backend",
    ) as http_client:
        client = BackendClient("http://backend", client=http_client)
        stream = client.send_message(chat_id, "Hi")
        tokens = [token async for token in stream]

    assert tokens == ["ok"]
    assert stream.message_id == message_id


@pytest.mark.asyncio
async def test_send_message_stores_final_sources_and_confidence() -> None:
    chat_id = uuid4()
    source = {
        "id": 1,
        "file_name": "policy.pdf",
        "page": 4,
        "score": 0.82,
        "snippet": "Use creates or removes to make command tasks idempotent.",
    }

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=(
                b'data: {"type": "token", "delta": "30 days [1]"}\n\n'
                + (
                    'data: {"type": "done", "confident": true, '
                    f'"sources": [{__import__("json").dumps(source)}]}}\n\n'
                ).encode()
            ),
            headers={"content-type": "text/event-stream"},
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="http://backend",
    ) as http_client:
        client = BackendClient("http://backend", client=http_client)
        stream = client.send_message(chat_id, "period?")
        tokens = [token async for token in stream]

    assert tokens == ["30 days [1]"]
    assert stream.sources == [source]
    assert stream.confident is True


@pytest.mark.asyncio
async def test_send_message_preserves_token_leading_spaces() -> None:
    chat_id = uuid4()

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=(
                b'data: {"type": "token", "delta": "Hello"}\n\n'
                b'data: {"type": "token", "delta": " world"}\n\n'
                b'data: {"type": "done"}\n\n'
            ),
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
async def test_send_message_sends_media_as_multipart() -> None:
    chat_id = uuid4()

    async def handler(request: httpx.Request) -> httpx.Response:
        body = await request.aread()
        assert request.headers["content-type"].startswith("multipart/form-data")
        assert b'name="content"' in body
        assert b'name="media"; filename="audio.ogg"' in body
        assert b"voice-bytes" in body
        return httpx.Response(
            200,
            content=b'data: {"type": "done"}\n\n',
            headers={"content-type": "text/event-stream"},
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="http://backend",
    ) as http_client:
        client = BackendClient("http://backend", client=http_client)
        tokens = [
            token
            async for token in client.send_message(
                chat_id,
                "voice",
                media=b"voice-bytes",
                mime="audio/ogg",
            )
        ]

    assert tokens == []


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


@pytest.mark.asyncio
async def test_save_feedback_posts_shown_sources() -> None:
    chat_id = uuid4()
    message_id = uuid4()
    source = {"id": 1, "file_name": "guide.md", "snippet": "text"}

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == f"/chats/{chat_id}/messages/{message_id}/feedback"
        assert __import__("json").loads(await request.aread()) == {
            "value": "up",
            "sources": [source],
        }
        return httpx.Response(200, json={"status": "ok"})

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="http://backend",
    ) as http_client:
        client = BackendClient("http://backend", client=http_client)
        await client.save_feedback(chat_id, message_id, "up", sources=[source])
