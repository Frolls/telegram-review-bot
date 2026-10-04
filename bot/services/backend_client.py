from __future__ import annotations

import json
from collections.abc import AsyncIterator
from dataclasses import dataclass
from uuid import UUID

import httpx


@dataclass(frozen=True)
class PendingBroadcast:
    id: UUID
    message: str
    interface: str
    owner_external_ids: list[str]


class BackendClient:
    def __init__(
        self,
        base_url: str,
        *,
        admin_token: str | None = None,
        internal_token: str | None = None,
        owner_id: str | None = None,
        timeout: float | httpx.Timeout = 20.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._admin_token = admin_token
        self._internal_token = internal_token
        self._owner_id = owner_id
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            timeout=httpx.Timeout(timeout),
        )

    def for_user(self, owner_id: str) -> "BackendClient":
        return BackendClient(str(self._client.base_url), client=self._client,
                             admin_token=self._admin_token, internal_token=self._internal_token,
                             owner_id=owner_id)

    def _headers(self) -> dict[str, str]:
        return {"X-Internal-Token": self._internal_token or "", "X-User-ID": self._owner_id or ""}

    async def pending_action(self) -> dict | None:
        response = await self._client.get("/agent/pending", headers=self._headers())
        response.raise_for_status()
        return response.json().get("pending")

    async def agent(self, payload: dict) -> list[dict]:
        events = []
        async with self._client.stream("POST", "/agent/stream", json=payload,
                                       headers=self._headers(), timeout=180) as response:
            response.raise_for_status()
            async for value in _iter_sse_data(response):
                events.append(json.loads(value))
        return events

    async def list_messages(self, chat_id: UUID) -> list[dict]:
        response = await self._client.get(f"/chats/{chat_id}/messages", headers=self._headers(), params={"limit": 200})
        response.raise_for_status()
        return response.json()

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def get_or_create_chat(self, owner_external_id: str, interface: str) -> UUID:
        response = await self._client.post(
            "/chats",
            headers=self._headers(),
            json={
                "owner_external_id": owner_external_id,
                "interface": interface,
            },
        )
        response.raise_for_status()
        return UUID(response.json()["chat_id"])

    def send_message(
        self,
        chat_id: UUID,
        content: str,
        media: bytes | None = None,
        mime: str | None = None,
        filename: str | None = None,
    ) -> "BackendMessageStream":
        return BackendMessageStream(
            self._client,
            chat_id=chat_id,
            content=content,
            media=media,
            mime=mime,
            filename=filename,
            headers=self._headers(),
        )

    async def clear_messages(self, chat_id: UUID) -> None:
        response = await self._client.delete(f"/chats/{chat_id}/messages", headers=self._headers())
        response.raise_for_status()

    async def save_feedback(
        self,
        chat_id: UUID,
        message_id: UUID,
        value: str,
        *,
        sources: list[dict] | None = None,
    ) -> None:
        response = await self._client.post(
            f"/chats/{chat_id}/messages/{message_id}/feedback",
            headers=self._headers(),
            json={"value": value, "sources": sources or []},
        )
        response.raise_for_status()

    async def admin_stats(self) -> dict:
        response = await self._client.get("/chats/admin/stats", headers=self._admin_headers())
        response.raise_for_status()
        return response.json()

    async def admin_users(self, limit: int = 50) -> list[dict]:
        response = await self._client.get(
            "/chats/admin/users",
            params={"limit": limit},
            headers=self._admin_headers(),
        )
        response.raise_for_status()
        return list(response.json())

    async def admin_broadcast(self, message: str, interface_filter: str = "telegram") -> UUID:
        response = await self._client.post(
            "/chats/admin/broadcast",
            headers=self._admin_headers(),
            json={"message": message, "interface_filter": interface_filter},
        )
        response.raise_for_status()
        return UUID(response.json()["id"])

    async def fetch_pending_broadcasts(self) -> list[PendingBroadcast]:
        response = await self._client.get(
            "/chats/admin/broadcast/pending",
            headers=self._admin_headers(),
            params={"interface_filter": "telegram"},
        )
        response.raise_for_status()
        return [
            PendingBroadcast(
                id=UUID(item["id"]),
                message=str(item["message"]),
                interface=str(item["interface"]),
                owner_external_ids=[str(owner) for owner in item.get("owner_external_ids", [])],
            )
            for item in response.json()
        ]

    async def complete_broadcast(
        self,
        broadcast_id: UUID,
        *,
        status: str = "sent",
        error: str | None = None,
    ) -> None:
        response = await self._client.post(
            f"/chats/admin/broadcast/{broadcast_id}/complete",
            headers=self._admin_headers(),
            json={"status": status, "error": error},
        )
        response.raise_for_status()

    def _admin_headers(self) -> dict[str, str]:
        return {"X-Admin-Token": self._admin_token or ""}


class BackendMessageStream:
    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        chat_id: UUID,
        content: str,
        media: bytes | None,
        mime: str | None,
        filename: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        self._client = client
        self._chat_id = chat_id
        self._content = content
        self._media = media
        self._mime = mime
        self._filename = filename
        self._headers = headers or {}
        self.message_id: UUID | None = None
        self.sources: list[dict] = []
        self.confident: bool = False

    def __aiter__(self) -> AsyncIterator[str]:
        return self._iter()

    async def _iter(self) -> AsyncIterator[str]:
        data = {"content": self._content}
        files = None
        if self._media is not None:
            filename = self._filename or _filename_for_mime(self._mime)
            files = {"media": (filename, self._media, self._mime or "application/octet-stream")}

        async with self._client.stream(
            "POST",
            f"/chats/{self._chat_id}/messages",
            data=data,
            files=files,
            timeout=180.0,
            headers=self._headers,
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
                    raise RuntimeError(str(event.get("message") or "Backend не смог обработать сообщение."))
                elif event.get("type") == "done":
                    raw_sources = event.get("sources")
                    if isinstance(raw_sources, list):
                        self.sources = [
                            item for item in raw_sources if isinstance(item, dict)
                        ]
                    self.confident = bool(event.get("confident", False))
                    raw_message_id = event.get("message_id")
                    if raw_message_id:
                        self.message_id = UUID(str(raw_message_id))
                    return


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
