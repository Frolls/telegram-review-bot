from __future__ import annotations

import json
from collections.abc import AsyncIterator
from uuid import UUID

import httpx


class BackendClient:
    def __init__(
        self,
        base_url: str,
        *,
        timeout: float | httpx.Timeout = 20.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            timeout=httpx.Timeout(timeout),
        )

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def get_or_create_chat(self, owner_external_id: str, interface: str) -> UUID:
        response = await self._client.post(
            "/chats",
            json={
                "owner_external_id": owner_external_id,
                "interface": interface,
            },
        )
        response.raise_for_status()
        return UUID(response.json()["chat_id"])

    async def send_message(
        self,
        chat_id: UUID,
        content: str,
        media: bytes | None = None,
        mime: str | None = None,
    ) -> AsyncIterator[str]:
        data = {"content": content}
        files = None
        if media is not None:
            filename = _filename_for_mime(mime)
            files = {"media": (filename, media, mime or "application/octet-stream")}

        async with self._client.stream(
            "POST",
            f"/chats/{chat_id}/messages",
            data=data,
            files=files,
            timeout=120.0,
        ) as response:
            response.raise_for_status()
            async for payload in _iter_sse_data(response):
                if payload == "[DONE]":
                    break
                try:
                    event = json.loads(payload)
                except json.JSONDecodeError:
                    yield payload
                    continue
                if event.get("type") == "token":
                    yield str(event.get("delta", ""))
                elif event.get("type") == "error":
                    yield str(event.get("message") or "Backend не смог обработать сообщение.")
                    return
                elif event.get("type") == "done":
                    return

    async def clear_messages(self, chat_id: UUID) -> None:
        response = await self._client.delete(f"/chats/{chat_id}/messages")
        response.raise_for_status()


async def _iter_sse_data(response: httpx.Response) -> AsyncIterator[str]:
    data_lines: list[str] = []

    async for raw_line in response.aiter_lines():
        line = raw_line.rstrip("\r")
        if line == "":
            if data_lines:
                yield "\n".join(data_lines)
                data_lines.clear()
            continue
        if line.startswith(":"):
            continue
        if line.startswith("data:"):
            value = line[5:]
            if value.startswith(" "):
                value = value[1:]
            data_lines.append(value)

    if data_lines:
        yield "\n".join(data_lines)


def _filename_for_mime(mime: str | None) -> str:
    if mime == "application/pdf":
        return "file.pdf"
    if mime and mime.endswith("wordprocessingml.document"):
        return "file.docx"
    if mime == "audio/ogg":
        return "audio.ogg"
    if mime == "audio/mpeg":
        return "audio.mp3"
    if mime == "audio/mp4":
        return "audio.m4a"
    if mime and mime.startswith("image/"):
        subtype = mime.split("/", 1)[1].split(";", 1)[0] or "jpeg"
        return f"image.{subtype}"
    return "file.bin"
